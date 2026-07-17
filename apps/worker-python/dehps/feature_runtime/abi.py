from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import numpy as np

from dehps.contracts import ContractRef, canonical_digest
from dehps.feature_runtime.compiler import (
    FEATURE_ARTIFACT_VERSION,
    CompiledFeatureArtifact,
    FeatureArtifactVerifier,
    FeatureRuntimeViolation,
    feature_array_digest,
)
from dehps.input_contracts.feature_contract import (
    FEATURE_COMPONENT_MANIFEST_DIGEST,
    FEATURE_CONTRACT_V1,
    FEATURE_VECTOR_LENGTH,
)


FEATURE_ABI_VERSION = "feature_abi.v1"
FEATURE_ABI_LAYOUT_VERSION = "dehps.feature-abi.layout.v1"
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")

FEATURE_ABI_LAYOUT_DEFINITION = {
    "abi_version": FEATURE_ABI_VERSION,
    "organization": "dense_component_matrix",
    "buffer_order": ["values"],
    "buffers": {
        "values": {
            "dtype": "float64",
            "endianness": "little",
            "shape": ["R", FEATURE_VECTOR_LENGTH],
            "strides_bytes": {
                "nonempty": [FEATURE_VECTOR_LENGTH * 8, 8],
                "empty": [0, 0],
            },
            "order": "C",
            "alignment": 8,
            "finite_values": "required",
        },
    },
    "row_identity": "candidate_abi_row_index",
    "row_range": "half_open_[start,end)_within_one_candidate_abi_package",
    "component_axis": {
        "order": "feature_component_index_ascending",
        "component_manifest_digest": FEATURE_COMPONENT_MANIFEST_DIGEST,
    },
    "chunk_semantics": "each_package_is_one_contiguous_tile_and_tile_size_is_not_semantic",
    "payload_framing": "one_named_buffer_with_domain_separated_sha256",
    "pointers_and_padding_in_identity": False,
}
FEATURE_ABI_LAYOUT_DIGEST = canonical_digest(
    FEATURE_ABI_LAYOUT_DEFINITION,
    domain="dehps.feature-abi-layout.v1",
)


def _require_digest(name: str, value: str) -> None:
    if not _DIGEST_PATTERN.fullmatch(value):
        raise FeatureRuntimeViolation(
            "invalid_feature_abi_digest",
            f"{name} must be a lowercase sha256 digest",
            field=name,
        )


@dataclass(frozen=True)
class FeatureBufferMetadata:
    name: str
    dtype: str
    endianness: str
    shape: tuple[int, int]
    strides: tuple[int, int]
    alignment: int
    byte_length: int
    buffer_digest: str

    def identity_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "endianness": self.endianness,
            "shape": list(self.shape),
            "strides": list(self.strides),
            "alignment": self.alignment,
            "byte_length": self.byte_length,
            "buffer_digest": self.buffer_digest,
        }


def _values_metadata(values: np.ndarray) -> FeatureBufferMetadata:
    return FeatureBufferMetadata(
        name="values",
        dtype="float64",
        endianness="little",
        shape=(int(values.shape[0]), int(values.shape[1])),
        strides=(int(values.strides[0]), int(values.strides[1])),
        alignment=8,
        byte_length=int(values.nbytes),
        buffer_digest=feature_array_digest(values, domain="dehps.feature-abi.buffer.values.v1"),
    )


def _payload_digest(buffer: FeatureBufferMetadata) -> str:
    return canonical_digest(
        {"buffers": [buffer.identity_payload()]},
        domain="dehps.feature-abi-payload.v1",
    )


@dataclass(frozen=True)
class FeatureABIHeader:
    abi_version: str
    feature_contract: ContractRef
    component_manifest_digest: str
    layout_digest: str
    source_artifact_version: str
    source_artifact_digest: str
    window_artifact_digest: str
    candidate_package_digest: str
    candidate_static_digest: str
    target_context_digest: str
    start: int
    end: int
    row_count: int
    component_count: int
    payload_digest: str
    buffer: FeatureBufferMetadata

    def identity_payload(self) -> dict[str, Any]:
        return {
            "abi_version": self.abi_version,
            "feature_contract": self.feature_contract.normative_identity(),
            "component_manifest_digest": self.component_manifest_digest,
            "layout_digest": self.layout_digest,
            "source_artifact_version": self.source_artifact_version,
            "source_artifact_digest": self.source_artifact_digest,
            "window_artifact_digest": self.window_artifact_digest,
            "candidate_package_digest": self.candidate_package_digest,
            "candidate_static_digest": self.candidate_static_digest,
            "target_context_digest": self.target_context_digest,
            "start": self.start,
            "end": self.end,
            "row_count": self.row_count,
            "component_count": self.component_count,
            "payload_digest": self.payload_digest,
            "buffer": self.buffer.identity_payload(),
        }

    @property
    def header_digest(self) -> str:
        return canonical_digest(self.identity_payload(), domain="dehps.feature-abi-header.v1")


@dataclass(frozen=True)
class FeatureRuntimeEnvelope:
    feature_contract: ContractRef
    feature_abi: str
    component_manifest_digest: str
    layout_digest: str
    source_artifact_digest: str
    window_artifact_digest: str
    candidate_package_digest: str
    candidate_static_digest: str
    target_context_digest: str
    start: int
    end: int
    row_count: int
    payload_digest: str
    package_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "feature_contract": self.feature_contract.as_dict(),
            "feature_abi": self.feature_abi,
            "component_manifest_digest": self.component_manifest_digest,
            "layout_digest": self.layout_digest,
            "source_artifact_digest": self.source_artifact_digest,
            "window_artifact_digest": self.window_artifact_digest,
            "candidate_package_digest": self.candidate_package_digest,
            "candidate_static_digest": self.candidate_static_digest,
            "target_context_digest": self.target_context_digest,
            "start": self.start,
            "end": self.end,
            "row_count": self.row_count,
            "payload_digest": self.payload_digest,
            "package_digest": self.package_digest,
        }


@dataclass(frozen=True)
class FeatureABIPackage:
    header: FeatureABIHeader
    values: np.ndarray

    @property
    def package_digest(self) -> str:
        return canonical_digest(
            {
                "artifact_type": "feature_abi_package.v1",
                "header_digest": self.header.header_digest,
                "payload_digest": self.header.payload_digest,
            },
            domain="dehps.feature-abi-package.v1",
        )

    @property
    def runtime_envelope(self) -> FeatureRuntimeEnvelope:
        return FeatureRuntimeEnvelope(
            feature_contract=self.header.feature_contract,
            feature_abi=self.header.abi_version,
            component_manifest_digest=self.header.component_manifest_digest,
            layout_digest=self.header.layout_digest,
            source_artifact_digest=self.header.source_artifact_digest,
            window_artifact_digest=self.header.window_artifact_digest,
            candidate_package_digest=self.header.candidate_package_digest,
            candidate_static_digest=self.header.candidate_static_digest,
            target_context_digest=self.header.target_context_digest,
            start=self.header.start,
            end=self.header.end,
            row_count=self.header.row_count,
            payload_digest=self.header.payload_digest,
            package_digest=self.package_digest,
        )


class FeatureABICompiler:
    """Describe an already-compiled Feature Artifact as Feature ABI without copying values."""

    def compile(self, artifact: CompiledFeatureArtifact) -> FeatureABIPackage:
        FeatureArtifactVerifier().verify(artifact)
        buffer = _values_metadata(artifact.values)
        source = artifact.header
        header = FeatureABIHeader(
            abi_version=FEATURE_ABI_VERSION,
            feature_contract=source.feature_contract,
            component_manifest_digest=source.component_manifest_digest,
            layout_digest=FEATURE_ABI_LAYOUT_DIGEST,
            source_artifact_version=source.artifact_version,
            source_artifact_digest=artifact.artifact_digest,
            window_artifact_digest=source.window_artifact_digest,
            candidate_package_digest=source.candidate_package_digest,
            candidate_static_digest=source.candidate_static_digest,
            target_context_digest=source.target_context_digest,
            start=source.start,
            end=source.end,
            row_count=source.row_count,
            component_count=source.component_count,
            payload_digest=_payload_digest(buffer),
            buffer=buffer,
        )
        package = FeatureABIPackage(header=header, values=artifact.values)
        FeatureABIVerifier().verify(package, source_artifact=artifact)
        return package


class FeatureABIVerifier:
    """Fail-closed Feature ABI v1 verifier; it never casts, copies, or repairs buffers."""

    def verify(
        self,
        package: FeatureABIPackage,
        *,
        source_artifact: CompiledFeatureArtifact | None = None,
    ) -> None:
        header = package.header
        if header.abi_version != FEATURE_ABI_VERSION:
            self._reject("unsupported_feature_abi_version", "unsupported Feature ABI version")
        if not header.feature_contract.normatively_equals(FEATURE_CONTRACT_V1):
            self._reject("feature_abi_contract_mismatch", "Feature ABI must use feature.v1.0.0")
        if header.component_manifest_digest != FEATURE_COMPONENT_MANIFEST_DIGEST:
            self._reject("feature_abi_manifest_mismatch", "Feature ABI component manifest is not v1")
        if header.layout_digest != FEATURE_ABI_LAYOUT_DIGEST:
            self._reject("feature_abi_layout_mismatch", "Feature ABI layout digest is not v1")
        if header.source_artifact_version != FEATURE_ARTIFACT_VERSION:
            self._reject("feature_abi_source_version_mismatch", "Feature ABI source must be Feature Artifact v1")
        for name, value in (
            ("component_manifest_digest", header.component_manifest_digest),
            ("layout_digest", header.layout_digest),
            ("source_artifact_digest", header.source_artifact_digest),
            ("window_artifact_digest", header.window_artifact_digest),
            ("candidate_package_digest", header.candidate_package_digest),
            ("candidate_static_digest", header.candidate_static_digest),
            ("target_context_digest", header.target_context_digest),
            ("payload_digest", header.payload_digest),
        ):
            _require_digest(name, value)
        if header.start < 0 or header.end < header.start or header.row_count != header.end - header.start:
            self._reject("feature_abi_row_range_mismatch", "Feature ABI row range is inconsistent")
        if header.component_count != FEATURE_VECTOR_LENGTH:
            self._reject("feature_abi_component_count_mismatch", "Feature ABI must contain 32 components")

        values = package.values
        if not isinstance(values, np.ndarray):
            self._reject("feature_abi_buffer_type_mismatch", "Feature ABI values must be a NumPy array")
        if values.dtype != np.dtype("<f8") or values.dtype.str != np.dtype("<f8").str:
            self._reject("feature_abi_buffer_dtype_mismatch", "Feature ABI values must be little-endian float64")
        if values.shape != (header.row_count, FEATURE_VECTOR_LENGTH):
            self._reject("feature_abi_buffer_shape_mismatch", "Feature ABI values shape is invalid")
        if not values.flags.c_contiguous:
            self._reject("feature_abi_buffer_not_contiguous", "Feature ABI values must be C-contiguous")
        expected_strides = (FEATURE_VECTOR_LENGTH * 8, 8) if header.row_count else (0, 0)
        if values.strides != expected_strides:
            self._reject("feature_abi_buffer_stride_mismatch", "Feature ABI values strides are invalid")
        if values.ctypes.data % 8:
            self._reject("feature_abi_buffer_alignment_mismatch", "Feature ABI values must be 8-byte aligned")
        if not np.isfinite(values).all():
            self._reject("feature_abi_buffer_non_finite", "Feature ABI values must be finite")
        actual_buffer = _values_metadata(values)
        if header.buffer != actual_buffer:
            self._reject("feature_abi_buffer_metadata_mismatch", "Feature ABI metadata does not match values")
        if header.payload_digest != _payload_digest(actual_buffer):
            self._reject("feature_abi_payload_mismatch", "Feature ABI payload digest does not match values")

        if source_artifact is not None:
            FeatureArtifactVerifier().verify(source_artifact)
            source = source_artifact.header
            expected = {
                "source_artifact_digest": source_artifact.artifact_digest,
                "window_artifact_digest": source.window_artifact_digest,
                "candidate_package_digest": source.candidate_package_digest,
                "candidate_static_digest": source.candidate_static_digest,
                "target_context_digest": source.target_context_digest,
                "start": source.start,
                "end": source.end,
                "row_count": source.row_count,
                "component_count": source.component_count,
            }
            actual = {name: getattr(header, name) for name in expected}
            if actual != expected:
                self._reject("feature_abi_source_binding_mismatch", "Feature ABI does not match its source artifact")
            if header.buffer.buffer_digest != _values_metadata(source_artifact.values).buffer_digest:
                self._reject("feature_abi_source_payload_mismatch", "Feature ABI values differ from source artifact")

    @staticmethod
    def _reject(code: str, message: str, **context: Any) -> None:
        raise FeatureRuntimeViolation(code, message, **context)


FEATURE_ABI_GOLDEN_SUITE = {
    "suite": "feature_abi_golden.v1",
    "expected_layout_digest": "7793e71afbc7a3bb6cbd507c3661b780bec6d9e0a9a3cc60a91fa91f0d37362c",
    "component_manifest_digest": FEATURE_COMPONENT_MANIFEST_DIGEST,
    "buffer_case": {
        "shape": [1, FEATURE_VECTOR_LENGTH],
        "dtype": "float64",
        "values_source": "FEATURE_GOLDEN_SUITE.golden_vector.values",
        "source_digests": {
            "window_artifact_digest": "1" * 64,
            "candidate_package_digest": "2" * 64,
            "candidate_static_digest": "3" * 64,
            "target_context_digest": "4" * 64,
        },
        "expected_buffer_digest": "515326784d364d5e72161d3b324c0d9b2eb103989970d81982eb22db03e58975",
        "expected_payload_digest": "4a9ea8f2fd8cb9eff8585535fdb99ee013457b9998b6a15cf9c4fb50f759294d",
        "expected_header_digest": "f042ab239ced9dd443c9a6c94ddcc38b82a1562f64363742f5fb2e1bb3a19161",
        "expected_package_digest": "0b7dc2610bbf99f70bddfda5c336c92645edc6a3a4bab33dbbd464949c244c98",
    },
}
