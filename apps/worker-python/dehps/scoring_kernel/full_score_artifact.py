from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest
from dehps.feature_runtime.compiler import feature_array_digest
from dehps.input_contracts.feature_contract import FEATURE_VECTOR_LENGTH
from dehps.ranking_contract import STRICT_RANKING_CONTRACT
from dehps.runtime_envelope import (
    RuntimeEnvelopeCompiler,
    RuntimeEnvelopeV1,
    RuntimeEnvelopeVerifier,
    RuntimeState,
)
from dehps.scoring_kernel.contracts import (
    SCORE_ROUND_DIGITS,
    STRICT_CONTRACT_VERSION,
    WeightMatrix,
)
from dehps.unified_runtime import (
    RuntimeVerificationSession,
    UnifiedRuntimeVerifier,
    VerifiedRuntimePackage,
)


FULL_SCORE_GRID_ARTIFACT_VERSION = "full_score_grid_artifact.v1"
FULL_SCORE_GRID_BACKEND = "feature_abi_numpy_reference"
FULL_SCORE_GRID_LAYOUT = "candidate_major_c_contiguous"


class FullScoreGridViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _weights_digest(weights: WeightMatrix) -> str:
    return feature_array_digest(
        weights.values,
        domain="dehps.full-score-grid.weights.v1",
    )


def _scores_digest(scores: np.ndarray) -> str:
    return feature_array_digest(
        scores,
        domain="dehps.full-score-grid.scores.v1",
    )


@dataclass(frozen=True)
class FullScoreGridHeaderV1:
    artifact_version: str
    scoring_contract: str
    ranking_contract: str
    backend: str
    verified_runtime_id: str
    runtime_verification_digest: str
    feature_runtime_digest: str
    candidate_count: int
    config_count: int
    component_count: int
    dtype: str
    layout: str
    weights_digest: str
    scores_digest: str

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": self.artifact_version,
            "scoring_contract": self.scoring_contract,
            "ranking_contract": self.ranking_contract,
            "backend": self.backend,
            "verified_runtime_id": self.verified_runtime_id,
            "runtime_verification_digest": self.runtime_verification_digest,
            "feature_runtime_digest": self.feature_runtime_digest,
            "candidate_count": self.candidate_count,
            "config_count": self.config_count,
            "component_count": self.component_count,
            "dtype": self.dtype,
            "layout": self.layout,
            "weights_digest": self.weights_digest,
            "scores_digest": self.scores_digest,
        }

    @property
    def header_digest(self) -> str:
        return canonical_digest(
            self.identity_payload(),
            domain="dehps.full-score-grid.header.v1",
        )


@dataclass(frozen=True)
class FullScoreGridArtifactV1:
    header: FullScoreGridHeaderV1
    scores: np.ndarray
    runtime_envelope: RuntimeEnvelopeV1

    @property
    def payload_digest(self) -> str:
        return canonical_digest(
            {
                "artifact_version": self.header.artifact_version,
                "header_digest": self.header.header_digest,
                "scores_digest": self.header.scores_digest,
            },
            domain="dehps.full-score-grid.payload.v1",
        )

    @property
    def artifact_digest(self) -> str:
        return canonical_digest(
            {
                "payload_digest": self.payload_digest,
                "runtime_envelope_digest": self.runtime_envelope.envelope_digest,
            },
            domain="dehps.full-score-grid.artifact.v1",
        )

    def as_metadata(self) -> dict[str, Any]:
        return {
            **self.header.identity_payload(),
            "header_digest": self.header.header_digest,
            "payload_digest": self.payload_digest,
            "artifact_digest": self.artifact_digest,
            "runtime_envelope": self.runtime_envelope.as_dict(),
        }


class FullScoreGridArtifactCompilerV1:
    def compile(
        self,
        *,
        verified_runtime: VerifiedRuntimePackage,
        weights: WeightMatrix,
        code_commit: str,
    ) -> FullScoreGridArtifactV1:
        verifier = UnifiedRuntimeVerifier()
        verification_session = verifier.verification_session(verified_runtime)
        with verification_session:
            return self._compile_in_session(
                verified_runtime=verified_runtime,
                weights=weights,
                code_commit=code_commit,
                verification_session=verification_session,
            )

    def _compile_in_session(
        self,
        *,
        verified_runtime: VerifiedRuntimePackage,
        weights: WeightMatrix,
        code_commit: str,
        verification_session: RuntimeVerificationSession,
    ) -> FullScoreGridArtifactV1:
        UnifiedRuntimeVerifier().require_active_session(
            verification_session,
            package=verified_runtime,
        )
        runtime = verified_runtime.runtime
        if weights.config_count < 1:
            self._reject("full_score_config_count_invalid", "at least one config is required")
        if weights.values.shape[1] != FEATURE_VECTOR_LENGTH:
            self._reject(
                "full_score_component_count_mismatch",
                "WeightMatrix must match the frozen Feature ABI vector length",
                expected=FEATURE_VECTOR_LENGTH,
                actual=int(weights.values.shape[1]),
            )

        ready = RuntimeEnvelopeCompiler().compile_kernel_ready(
            verified_runtime,
            backend=FULL_SCORE_GRID_BACKEND,
            code_commit=code_commit,
            artifact_type="full_score_grid",
            verification_session=verification_session,
        )
        executing = ready.transition(RuntimeState.KERNEL_EXECUTING)
        scores = np.empty(
            (runtime.candidate_count, weights.config_count),
            dtype=np.float64,
        )
        for tile in runtime.feature_tiles:
            np.matmul(
                tile.values,
                weights.values.T,
                out=scores[tile.header.start : tile.header.end],
            )
        np.round(scores, SCORE_ROUND_DIGITS, out=scores)
        if not np.isfinite(scores).all():
            self._reject("full_score_nonfinite", "compiled score grid must be finite")
        scores.setflags(write=False)
        header = FullScoreGridHeaderV1(
            artifact_version=FULL_SCORE_GRID_ARTIFACT_VERSION,
            scoring_contract=STRICT_CONTRACT_VERSION,
            ranking_contract=STRICT_RANKING_CONTRACT,
            backend=FULL_SCORE_GRID_BACKEND,
            verified_runtime_id=verified_runtime.verified_runtime_id,
            runtime_verification_digest=verified_runtime.verification_digest,
            feature_runtime_digest=runtime.runtime_digest,
            candidate_count=runtime.candidate_count,
            config_count=weights.config_count,
            component_count=FEATURE_VECTOR_LENGTH,
            dtype=scores.dtype.str,
            layout=FULL_SCORE_GRID_LAYOUT,
            weights_digest=_weights_digest(weights),
            scores_digest=_scores_digest(scores),
        )
        provisional = FullScoreGridArtifactV1(
            header=header,
            scores=scores,
            runtime_envelope=executing,
        )
        artifact = FullScoreGridArtifactV1(
            header=header,
            scores=scores,
            runtime_envelope=executing.produce_artifact(provisional.payload_digest),
        )
        FullScoreGridArtifactVerifierV1().verify(
            artifact,
            verified_runtime=verified_runtime,
            weights=weights,
            verification_session=verification_session,
        )
        return artifact

    @staticmethod
    def _reject(code: str, message: str, **context: Any) -> None:
        raise FullScoreGridViolation(code, message, **context)


class FullScoreGridArtifactVerifierV1:
    def verify(
        self,
        artifact: FullScoreGridArtifactV1,
        *,
        verified_runtime: VerifiedRuntimePackage,
        weights: WeightMatrix,
        verification_session: RuntimeVerificationSession | None = None,
    ) -> None:
        if verification_session is None:
            verifier = UnifiedRuntimeVerifier()
            with verifier.verification_session(verified_runtime) as active_session:
                return self.verify(
                    artifact,
                    verified_runtime=verified_runtime,
                    weights=weights,
                    verification_session=active_session,
                )
        UnifiedRuntimeVerifier().require_active_session(
            verification_session,
            package=verified_runtime,
        )
        if not isinstance(artifact, FullScoreGridArtifactV1):
            self._reject("full_score_artifact_type_invalid", "unsupported artifact object")
        runtime = verified_runtime.runtime
        header = artifact.header
        expected_identity = {
            "artifact_version": FULL_SCORE_GRID_ARTIFACT_VERSION,
            "scoring_contract": STRICT_CONTRACT_VERSION,
            "ranking_contract": STRICT_RANKING_CONTRACT,
            "backend": FULL_SCORE_GRID_BACKEND,
            "verified_runtime_id": verified_runtime.verified_runtime_id,
            "runtime_verification_digest": verified_runtime.verification_digest,
            "feature_runtime_digest": runtime.runtime_digest,
            "candidate_count": runtime.candidate_count,
            "config_count": weights.config_count,
            "component_count": FEATURE_VECTOR_LENGTH,
            "dtype": np.dtype(np.float64).str,
            "layout": FULL_SCORE_GRID_LAYOUT,
            "weights_digest": _weights_digest(weights),
        }
        actual_identity = {
            field: getattr(header, field) for field in expected_identity
        }
        if actual_identity != expected_identity:
            self._reject(
                "full_score_header_binding_mismatch",
                "FullScore header does not match Runtime or weights",
            )
        scores = artifact.scores
        if (
            not isinstance(scores, np.ndarray)
            or scores.dtype != np.float64
            or scores.shape != (runtime.candidate_count, weights.config_count)
            or not scores.flags.c_contiguous
            or scores.dtype.hasobject
        ):
            self._reject(
                "full_score_buffer_metadata_mismatch",
                "score grid dtype, shape, or layout is invalid",
            )
        if scores.flags.writeable:
            self._reject(
                "full_score_buffer_writable",
                "verified FullScore score buffers must be read-only",
            )
        if not np.isfinite(scores).all():
            self._reject("full_score_nonfinite", "score grid contains non-finite values")
        if header.scores_digest != _scores_digest(scores):
            self._reject(
                "full_score_payload_digest_mismatch",
                "score grid does not match its header digest",
            )
        envelope = artifact.runtime_envelope
        if envelope.artifact_type != "full_score_grid":
            self._reject(
                "full_score_envelope_artifact_type_mismatch",
                "Runtime Envelope artifact type is invalid",
            )
        RuntimeEnvelopeVerifier().verify_artifact_payload(
            envelope,
            payload_digest=artifact.payload_digest,
            runtime=runtime,
            expected_backend=FULL_SCORE_GRID_BACKEND,
            verification_session=verification_session,
        )

    @staticmethod
    def _reject(code: str, message: str, **context: Any) -> None:
        raise FullScoreGridViolation(code, message, **context)


__all__ = (
    "FULL_SCORE_GRID_ARTIFACT_VERSION",
    "FULL_SCORE_GRID_BACKEND",
    "FULL_SCORE_GRID_LAYOUT",
    "FullScoreGridArtifactCompilerV1",
    "FullScoreGridArtifactV1",
    "FullScoreGridArtifactVerifierV1",
    "FullScoreGridHeaderV1",
    "FullScoreGridViolation",
)
