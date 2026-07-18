from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from dehps.feature_runtime.abi import (
    FeatureABICompiler,
    FeatureABIPackage,
    _package_from_source_identity,
)
from dehps.feature_runtime.compiler import (
    FEATURE_ARTIFACT_VERSION,
    FEATURE_COMPILER_VERSION,
    FeatureArtifactHeader,
    FeatureCompileRequest,
    FeatureCompiler,
    FeatureRuntimeViolation,
    candidate_static_digest,
    feature_array_digest,
    feature_artifact_digest,
)
from dehps.input_contracts.candidate_abi import CandidateABIVerifier
from dehps.input_contracts.feature_contract import (
    FEATURE_COMPONENT_MANIFEST_DIGEST,
    FEATURE_CONTRACT_V1,
    FEATURE_VECTOR_LENGTH,
    FeatureContractVerifier,
)
from dehps.models.frequency_ranker import train_frequency_stats
from dehps.scoring_kernel.numpy_backend import component_tile
from dehps.scoring_kernel.packing import pack_window_state


FEATURE_ABI_DIRECT_PRODUCER_VERSION = "dehps.feature-abi-direct-producer.numpy-reference.v1"
FEATURE_ABI_STAGED_PRODUCER_VERSION = "dehps.feature-abi-staged-producer.reference.v1"


@dataclass(frozen=True)
class FeatureABIProducerResult:
    package: FeatureABIPackage
    source_header: FeatureArtifactHeader
    source_artifact_digest: str
    producer_version: str
    payload_materializations: int
    abi_buffer_copied: bool

    def as_dict(self) -> dict[str, int | bool | str]:
        return {
            "producer_version": self.producer_version,
            "source_artifact_digest": self.source_artifact_digest,
            "source_header_digest": self.source_header.header_digest,
            "package_digest": self.package.package_digest,
            "payload_materializations": self.payload_materializations,
            "abi_buffer_copied": self.abi_buffer_copied,
        }


class FeatureABIProducer(Protocol):
    version: str

    def produce(self, request: FeatureCompileRequest) -> FeatureABIProducerResult: ...


class DirectFeatureABIProducer:
    """Compile one Feature tile directly into the existing Artifact/ABI identities.

    The result is deliberately unverified. RuntimeABICache remains the authority that
    performs formal Feature ABI verification before insertion.
    """

    version = FEATURE_ABI_DIRECT_PRODUCER_VERSION

    def __init__(
        self,
        *,
        component_producer: Callable[..., np.ndarray] = component_tile,
    ) -> None:
        self._component_producer = component_producer

    def produce(self, request: FeatureCompileRequest) -> FeatureABIProducerResult:
        FeatureContractVerifier().verify_manifest()
        request.window.verify()
        request.candidate_store.validate()
        start, end = request.normalized_range()
        if not request.window.records:
            raise FeatureRuntimeViolation(
                "empty_feature_window",
                "Feature ABI producer requires at least one selected history record",
            )
        candidate_package = request.candidate_store.candidate_abi_package
        if candidate_package is None:
            raise FeatureRuntimeViolation(
                "candidate_abi_missing",
                "Feature ABI producer input has no Candidate ABI package",
            )
        CandidateABIVerifier().verify(candidate_package)

        history = [record.as_history_draw() for record in request.window.records]
        stats = train_frequency_stats(
            history,
            target_draw_date=request.target_draw_date,
        )
        packed_window = pack_window_state(stats)
        values = self._component_producer(
            request.candidate_store,
            packed_window,
            start,
            end,
        )
        self._verify_component_output(values, row_count=end - start)

        source_header = FeatureArtifactHeader(
            artifact_version=FEATURE_ARTIFACT_VERSION,
            compiler_version=FEATURE_COMPILER_VERSION,
            feature_contract=FEATURE_CONTRACT_V1,
            component_manifest_digest=FEATURE_COMPONENT_MANIFEST_DIGEST,
            window_artifact_digest=request.window.artifact_digest,
            candidate_package_digest=candidate_package.package_digest,
            candidate_static_digest=candidate_static_digest(
                request.candidate_store,
                start=start,
                end=end,
            ),
            target_context_digest=request.target_context_digest,
            start=start,
            end=end,
            row_count=end - start,
            component_count=FEATURE_VECTOR_LENGTH,
            dtype="float64",
            values_digest=feature_array_digest(
                values,
                domain="dehps.feature-artifact.values.v1",
            ),
        )
        source_artifact_digest = feature_artifact_digest(source_header)
        package = _package_from_source_identity(
            source=source_header,
            source_artifact_digest=source_artifact_digest,
            values=values,
        )
        if package.values is not values:
            raise FeatureRuntimeViolation(
                "feature_abi_direct_producer_buffer_copy",
                "direct Feature ABI production must preserve the component values buffer",
            )
        return FeatureABIProducerResult(
            package=package,
            source_header=source_header,
            source_artifact_digest=source_artifact_digest,
            producer_version=self.version,
            payload_materializations=1,
            abi_buffer_copied=False,
        )

    @staticmethod
    def _verify_component_output(values: np.ndarray, *, row_count: int) -> None:
        if not isinstance(values, np.ndarray):
            raise FeatureRuntimeViolation(
                "feature_abi_direct_producer_buffer_type_mismatch",
                "component producer must return a NumPy array",
            )
        if values.dtype != np.dtype("<f8") or values.dtype.str != np.dtype("<f8").str:
            raise FeatureRuntimeViolation(
                "feature_abi_direct_producer_dtype_mismatch",
                "component producer must return little-endian float64",
            )
        if values.shape != (row_count, FEATURE_VECTOR_LENGTH):
            raise FeatureRuntimeViolation(
                "feature_abi_direct_producer_shape_mismatch",
                "component producer returned an unexpected Feature shape",
                expected=[row_count, FEATURE_VECTOR_LENGTH],
                actual=list(values.shape),
            )
        if not values.flags.c_contiguous:
            raise FeatureRuntimeViolation(
                "feature_abi_direct_producer_not_contiguous",
                "component producer must return a C-contiguous Feature buffer",
            )
        expected_strides = (FEATURE_VECTOR_LENGTH * 8, 8) if row_count else (0, 0)
        if values.strides != expected_strides:
            raise FeatureRuntimeViolation(
                "feature_abi_direct_producer_stride_mismatch",
                "component producer returned invalid Feature strides",
            )
        if values.ctypes.data % 8:
            raise FeatureRuntimeViolation(
                "feature_abi_direct_producer_alignment_mismatch",
                "component producer returned an unaligned Feature buffer",
            )
        if not np.isfinite(values).all():
            raise FeatureRuntimeViolation(
                "feature_abi_direct_producer_non_finite",
                "component producer returned non-finite Feature values",
            )


class StagedFeatureABIProducer:
    """Explicit compatibility oracle for the original two-compiler path."""

    version = FEATURE_ABI_STAGED_PRODUCER_VERSION

    def __init__(
        self,
        *,
        feature_compiler: FeatureCompiler | None = None,
        abi_compiler: FeatureABICompiler | None = None,
    ) -> None:
        self.feature_compiler = feature_compiler or FeatureCompiler()
        self.abi_compiler = abi_compiler or FeatureABICompiler()

    def produce(self, request: FeatureCompileRequest) -> FeatureABIProducerResult:
        artifact = self.feature_compiler.compile(request)
        package = self.abi_compiler.compile(artifact)
        return FeatureABIProducerResult(
            package=package,
            source_header=artifact.header,
            source_artifact_digest=artifact.artifact_digest,
            producer_version=self.version,
            payload_materializations=1,
            abi_buffer_copied=package.values is not artifact.values,
        )


__all__ = [
    "FEATURE_ABI_DIRECT_PRODUCER_VERSION",
    "FEATURE_ABI_STAGED_PRODUCER_VERSION",
    "DirectFeatureABIProducer",
    "FeatureABIProducer",
    "FeatureABIProducerResult",
    "StagedFeatureABIProducer",
]
