from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import re
from typing import Any

import numpy as np

from dehps.contracts import ContractRef, canonical_digest
from dehps.input_contracts.candidate_abi import CandidateABIVerifier
from dehps.input_contracts.feature_contract import (
    FEATURE_COMPONENT_MANIFEST_DIGEST,
    FEATURE_CONTRACT_V1,
    FEATURE_VECTOR_LENGTH,
    FeatureContractVerifier,
)
from dehps.input_contracts.history_window import WindowArtifact
from dehps.models.frequency_ranker import train_frequency_stats
from dehps.scoring_kernel.contracts import CandidateStore
from dehps.scoring_kernel.numpy_backend import component_tile
from dehps.scoring_kernel.packing import pack_window_state


FEATURE_COMPILER_VERSION = "dehps.feature-compiler.numpy-reference.v1"
FEATURE_ARTIFACT_VERSION = "dehps.feature-artifact.v1"
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FeatureRuntimeViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _require_digest(name: str, value: str) -> None:
    if not _DIGEST_PATTERN.fullmatch(value):
        raise FeatureRuntimeViolation(
            "invalid_feature_digest",
            f"{name} must be a lowercase sha256 digest",
            field=name,
        )


def feature_array_digest(array: np.ndarray, *, domain: str) -> str:
    digest = sha256(domain.encode("ascii") + b"\x00")
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(b"\x00")
    digest.update(",".join(str(value) for value in array.shape).encode("ascii"))
    digest.update(b"\x00")
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _candidate_static_digest(store: CandidateStore, *, start: int, end: int) -> str:
    fields = (
        "structural_score",
        "consecutive_pair_count",
        "odd_count",
        "zone_counts",
        "gaps",
        "sum_value",
        "span_value",
        "qian_kun_code",
        "first_last_sum",
        "sum_bucket",
        "span_bucket",
        "ac_value",
        "big_count",
        "even_count",
        "prime_count",
        "mod012_counts",
        "tail_unique_count",
        "sum_tail",
        "max_gap",
        "min_gap",
    )
    return canonical_digest(
        {
            "candidate_store_version": store.store_version,
            "candidate_store_fingerprint": store.fingerprint,
            "row_range": [start, end],
            "buffers": {
                name: feature_array_digest(
                    getattr(store, name)[start:end],
                    domain=f"dehps.feature-compiler.candidate-static.{name}.v1",
                )
                for name in fields
            },
        },
        domain="dehps.feature-compiler.candidate-static-input.v1",
    )


@dataclass(frozen=True)
class FeatureCompileRequest:
    window: WindowArtifact
    candidate_store: CandidateStore
    start: int = 0
    end: int | None = None
    target_draw_date: date | None = None

    def normalized_range(self) -> tuple[int, int]:
        row_count = len(self.candidate_store)
        end = row_count if self.end is None else self.end
        if isinstance(self.start, bool) or not isinstance(self.start, int):
            raise FeatureRuntimeViolation("invalid_feature_row_range", "start must be an integer")
        if isinstance(end, bool) or not isinstance(end, int):
            raise FeatureRuntimeViolation("invalid_feature_row_range", "end must be an integer")
        if not 0 <= self.start <= end <= row_count:
            raise FeatureRuntimeViolation(
                "invalid_feature_row_range",
                "feature row range must satisfy 0 <= start <= end <= candidate_count",
                start=self.start,
                end=end,
                candidate_count=row_count,
            )
        if self.target_draw_date is not None and (
            not isinstance(self.target_draw_date, date) or isinstance(self.target_draw_date, datetime)
        ):
            raise FeatureRuntimeViolation(
                "invalid_feature_target_date",
                "target_draw_date must be a date or null",
            )
        selected_dates = tuple(record.draw_date for record in self.window.records if record.draw_date is not None)
        if self.target_draw_date is not None and selected_dates and self.target_draw_date <= max(selected_dates):
            raise FeatureRuntimeViolation(
                "feature_target_date_leakage",
                "target_draw_date must be after every dated Window record",
                target_draw_date=self.target_draw_date.isoformat(),
                latest_window_date=max(selected_dates).isoformat(),
            )
        return self.start, end

    @property
    def target_context_digest(self) -> str:
        return canonical_digest(
            {
                "target_draw_date": self.target_draw_date,
                "target_weekday": self.target_draw_date.weekday() if self.target_draw_date else None,
            },
            domain="dehps.feature-compiler.target-context.v1",
        )


@dataclass(frozen=True)
class FeatureArtifactHeader:
    artifact_version: str
    compiler_version: str
    feature_contract: ContractRef
    component_manifest_digest: str
    window_artifact_digest: str
    candidate_package_digest: str
    candidate_static_digest: str
    target_context_digest: str
    start: int
    end: int
    row_count: int
    component_count: int
    dtype: str
    values_digest: str

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": self.artifact_version,
            "compiler_version": self.compiler_version,
            "feature_contract": self.feature_contract.normative_identity(),
            "component_manifest_digest": self.component_manifest_digest,
            "window_artifact_digest": self.window_artifact_digest,
            "candidate_package_digest": self.candidate_package_digest,
            "candidate_static_digest": self.candidate_static_digest,
            "target_context_digest": self.target_context_digest,
            "start": self.start,
            "end": self.end,
            "row_count": self.row_count,
            "component_count": self.component_count,
            "dtype": self.dtype,
            "values_digest": self.values_digest,
        }

    @property
    def header_digest(self) -> str:
        return canonical_digest(self.identity_payload(), domain="dehps.feature-artifact-header.v1")


@dataclass(frozen=True)
class CompiledFeatureArtifact:
    header: FeatureArtifactHeader
    values: np.ndarray

    @property
    def artifact_digest(self) -> str:
        return canonical_digest(
            {
                "artifact_type": FEATURE_ARTIFACT_VERSION,
                "header_digest": self.header.header_digest,
                "values_digest": self.header.values_digest,
            },
            domain="dehps.feature-artifact.v1",
        )

    def as_metadata(self) -> dict[str, Any]:
        return {
            **self.header.identity_payload(),
            "header_digest": self.header.header_digest,
            "artifact_digest": self.artifact_digest,
        }


class FeatureArtifactVerifier:
    """Fail-closed verifier for reference Feature artifacts; it never repairs values."""

    def verify(
        self,
        artifact: CompiledFeatureArtifact,
        *,
        request: FeatureCompileRequest | None = None,
    ) -> None:
        header = artifact.header
        if header.artifact_version != FEATURE_ARTIFACT_VERSION:
            self._reject("unsupported_feature_artifact_version", "unsupported Feature artifact version")
        if header.compiler_version != FEATURE_COMPILER_VERSION:
            self._reject("unsupported_feature_compiler", "unsupported Feature compiler version")
        if not header.feature_contract.normatively_equals(FEATURE_CONTRACT_V1):
            self._reject("feature_contract_mismatch", "Feature artifact must use feature.v1.0.0")
        if header.component_manifest_digest != FEATURE_COMPONENT_MANIFEST_DIGEST:
            self._reject("feature_manifest_digest_mismatch", "Feature component manifest digest is not v1")
        for name, value in (
            ("component_manifest_digest", header.component_manifest_digest),
            ("window_artifact_digest", header.window_artifact_digest),
            ("candidate_package_digest", header.candidate_package_digest),
            ("candidate_static_digest", header.candidate_static_digest),
            ("target_context_digest", header.target_context_digest),
            ("values_digest", header.values_digest),
        ):
            _require_digest(name, value)
        if header.start < 0 or header.end < header.start or header.row_count != header.end - header.start:
            self._reject("feature_row_range_mismatch", "Feature header row range is inconsistent")
        if header.component_count != FEATURE_VECTOR_LENGTH:
            self._reject("feature_component_count_mismatch", "Feature artifact must contain 32 components")
        if header.dtype != "float64":
            self._reject("feature_dtype_mismatch", "Feature artifact dtype metadata must be float64")
        values = artifact.values
        if not isinstance(values, np.ndarray):
            self._reject("feature_buffer_type_mismatch", "Feature values must be a NumPy array")
        if values.dtype != np.dtype("float64") or values.dtype.str != np.dtype("<f8").str:
            self._reject("feature_buffer_dtype_mismatch", "Feature values must be native little-endian float64")
        if values.shape != (header.row_count, FEATURE_VECTOR_LENGTH):
            self._reject("feature_buffer_shape_mismatch", "Feature values shape does not match the header")
        if not values.flags.c_contiguous:
            self._reject("feature_buffer_not_contiguous", "Feature values must be C-contiguous")
        if not np.isfinite(values).all():
            self._reject("feature_buffer_non_finite", "Feature values must be finite")
        actual_values_digest = feature_array_digest(values, domain="dehps.feature-artifact.values.v1")
        if header.values_digest != actual_values_digest:
            self._reject("feature_values_digest_mismatch", "Feature values do not match the header digest")

        if request is not None:
            request.window.verify()
            request.candidate_store.validate()
            start, end = request.normalized_range()
            candidate_package = request.candidate_store.candidate_abi_package
            if candidate_package is None:  # guarded by CandidateStore.validate
                self._reject("candidate_abi_missing", "Feature input has no Candidate ABI package")
            if (header.start, header.end) != (start, end):
                self._reject("feature_request_range_mismatch", "Feature artifact does not match request range")
            if header.window_artifact_digest != request.window.artifact_digest:
                self._reject("feature_window_binding_mismatch", "Feature artifact does not match Window artifact")
            if header.candidate_package_digest != candidate_package.package_digest:
                self._reject("feature_candidate_binding_mismatch", "Feature artifact does not match Candidate ABI")
            if header.candidate_static_digest != _candidate_static_digest(
                request.candidate_store,
                start=start,
                end=end,
            ):
                self._reject("feature_candidate_static_binding_mismatch", "Feature artifact does not match candidate static inputs")
            if header.target_context_digest != request.target_context_digest:
                self._reject("feature_target_context_mismatch", "Feature artifact does not match target context")

    @staticmethod
    def _reject(code: str, message: str, **context: Any) -> None:
        raise FeatureRuntimeViolation(code, message, **context)


class FeatureCompiler:
    """Reference compiler from verified Window/Candidate inputs to a Feature artifact.

    The result is control-plane evidence, not Feature ABI v1 and not a Kernel hot-path input.
    """

    def compile(self, request: FeatureCompileRequest) -> CompiledFeatureArtifact:
        FeatureContractVerifier().verify_manifest()
        request.window.verify()
        request.candidate_store.validate()
        start, end = request.normalized_range()
        if not request.window.records:
            raise FeatureRuntimeViolation(
                "empty_feature_window",
                "Feature Compiler requires at least one selected history record",
            )
        candidate_package = request.candidate_store.candidate_abi_package
        if candidate_package is None:  # guarded by CandidateStore.validate
            raise FeatureRuntimeViolation("candidate_abi_missing", "Feature input has no Candidate ABI package")
        CandidateABIVerifier().verify(candidate_package)

        history = [record.as_history_draw() for record in request.window.records]
        stats = train_frequency_stats(history, target_draw_date=request.target_draw_date)
        packed_window = pack_window_state(stats)
        values = np.ascontiguousarray(
            component_tile(request.candidate_store, packed_window, start, end),
            dtype=np.float64,
        )
        if values.shape != (end - start, FEATURE_VECTOR_LENGTH):
            raise FeatureRuntimeViolation(
                "feature_compiler_shape_mismatch",
                "reference compiler produced an unexpected Feature shape",
                expected=[end - start, FEATURE_VECTOR_LENGTH],
                actual=list(values.shape),
            )
        if not np.isfinite(values).all():
            raise FeatureRuntimeViolation(
                "feature_compiler_non_finite",
                "reference compiler produced non-finite Feature values",
            )

        header = FeatureArtifactHeader(
            artifact_version=FEATURE_ARTIFACT_VERSION,
            compiler_version=FEATURE_COMPILER_VERSION,
            feature_contract=FEATURE_CONTRACT_V1,
            component_manifest_digest=FEATURE_COMPONENT_MANIFEST_DIGEST,
            window_artifact_digest=request.window.artifact_digest,
            candidate_package_digest=candidate_package.package_digest,
            candidate_static_digest=_candidate_static_digest(
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
            values_digest=feature_array_digest(values, domain="dehps.feature-artifact.values.v1"),
        )
        artifact = CompiledFeatureArtifact(header=header, values=values)
        FeatureArtifactVerifier().verify(artifact, request=request)
        return artifact
