from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import json
import re
from typing import Any

import numpy as np

from dehps.contracts import ContractRef, canonical_digest, canonical_json
from dehps.input_contracts.candidate_abi import (
    CandidateABIPackage,
    CandidateABIVerifier,
    CandidateContractViolation,
)
from dehps.input_contracts.evaluation_contract import (
    EVALUATION_CONTRACT_V1,
    EVALUATION_METRIC_MANIFEST_DIGEST,
    EVALUATION_SCORING_CONTRACT,
    EvaluationCandidateV1,
    EvaluationContractVerifier,
    EvaluationContractViolation,
    EvaluationMetricsV1,
    evaluate_ranked_candidates_v1,
)
from dehps.ranking_contract import normalize_ranking_contract
from dehps.runtime_envelope import (
    RuntimeEnvelopeV1,
    RuntimeEnvelopeVerifier,
    RuntimeEnvelopeViolation,
    RuntimeState,
)


PREDICTION_EVIDENCE_ARTIFACT_VERSION = "prediction_evidence.v1"
ACTUAL_OUTCOME_ARTIFACT_VERSION = "actual_outcome.v1"
EVALUATION_ARTIFACT_VERSION = "evaluation_artifact.v1"
EVALUATION_STAGE_ENVELOPE_VERSION = "evaluation_stage_envelope.v1"
EVALUATION_COMPILER_VERSION = "dehps.evaluation-compiler.reference.v1"

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ISSUE_PATTERN = re.compile(r"^[0-9]{7}$")
_CODE_COMMIT_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class EvaluationArtifactViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise EvaluationArtifactViolation(code, message, **context)


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _DIGEST_PATTERN.fullmatch(value):
        _reject(
            "invalid_evaluation_artifact_digest",
            f"{name} must be a lowercase sha256 digest",
            field=name,
        )
    return value


def _require_issue(name: str, value: object) -> str:
    if not isinstance(value, str) or not _ISSUE_PATTERN.fullmatch(value):
        _reject(
            "invalid_evaluation_artifact_issue",
            f"{name} must be a seven-digit issue",
            field=name,
        )
    return value


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _reject("evaluation_artifact_parse_error", f"{field} must be an object", field=field)
    return value


def _contract_ref(value: object, *, field: str) -> ContractRef:
    payload = _mapping(value, field=field)
    try:
        return ContractRef(
            family=str(payload["family"]),
            semantic_version=str(payload["semantic_version"]),
            schema_version=str(payload["schema_version"]),
            normative_digest=str(payload["normative_digest"]),
            golden_suite_digest=str(payload["golden_suite_digest"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationArtifactViolation(
            "evaluation_artifact_parse_error",
            f"{field} is not a valid ContractRef",
            field=field,
        ) from exc


def _verify_candidate_package(package: CandidateABIPackage) -> None:
    try:
        CandidateABIVerifier().verify(package)
    except CandidateContractViolation as exc:
        raise EvaluationArtifactViolation(
            "evaluation_candidate_package_invalid",
            "resolved Candidate ABI package failed verification",
            cause=exc.code,
        ) from exc


def _verify_source_runtime(envelope: RuntimeEnvelopeV1) -> None:
    try:
        RuntimeEnvelopeVerifier().verify(envelope)
    except RuntimeEnvelopeViolation as exc:
        raise EvaluationArtifactViolation(
            "evaluation_source_runtime_invalid",
            "source Runtime Envelope failed verification",
            cause=exc.code,
        ) from exc


def _evaluate_metrics(
    *,
    actual_red_numbers: Sequence[object],
    candidates: Sequence[EvaluationCandidateV1],
    ranking_contract: object,
) -> EvaluationMetricsV1:
    try:
        return evaluate_ranked_candidates_v1(
            actual_red_numbers=actual_red_numbers,
            candidates=candidates,
            ranking_contract=ranking_contract,
        )
    except EvaluationContractViolation as exc:
        raise EvaluationArtifactViolation(
            "evaluation_parent_contract_invalid",
            "Prediction or Outcome evidence violates Evaluation Contract v1",
            cause=exc.code,
        ) from exc


def _candidate_payload(candidates: Sequence[EvaluationCandidateV1]) -> list[dict[str, Any]]:
    return [
        {
            "rank": candidate.rank,
            "red_numbers": list(candidate.red_numbers),
            "score": float(candidate.score),
        }
        for candidate in candidates
    ]


@dataclass(frozen=True)
class PredictionEvidenceArtifactV1:
    prediction_run_key: str
    line_key: str
    target_issue: str
    candidate_package_digest: str
    scoring_contract: str
    ranking_contract: str
    candidates: tuple[EvaluationCandidateV1, ...]

    @classmethod
    def build(
        cls,
        *,
        prediction_run_key: str,
        line_key: str,
        target_issue: str,
        candidate_package_digest: str,
        scoring_contract: str,
        ranking_contract: object,
        candidates: Sequence[EvaluationCandidateV1],
    ) -> PredictionEvidenceArtifactV1:
        try:
            normalized_ranking = normalize_ranking_contract(ranking_contract)
        except ValueError as exc:
            raise EvaluationArtifactViolation(
                "prediction_evidence_ranking_contract_invalid",
                "Prediction Evidence ranking contract is unknown",
            ) from exc
        artifact = cls(
            prediction_run_key=prediction_run_key,
            line_key=line_key,
            target_issue=target_issue,
            candidate_package_digest=candidate_package_digest,
            scoring_contract=scoring_contract,
            ranking_contract=normalized_ranking,
            candidates=tuple(candidates),
        )
        artifact.verify()
        return artifact

    @property
    def candidate_payload_digest(self) -> str:
        return canonical_digest(
            _candidate_payload(self.candidates),
            domain="dehps.prediction-evidence.candidates.v1",
        )

    @property
    def artifact_digest(self) -> str:
        return canonical_digest(
            self.identity_payload(),
            domain="dehps.prediction-evidence-artifact.v1",
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": PREDICTION_EVIDENCE_ARTIFACT_VERSION,
            "prediction_run_key": self.prediction_run_key,
            "line_key": self.line_key,
            "target_issue": self.target_issue,
            "candidate_package_digest": self.candidate_package_digest,
            "scoring_contract": self.scoring_contract,
            "ranking_contract": self.ranking_contract,
            "candidate_count": len(self.candidates),
            "candidate_payload_digest": self.candidate_payload_digest,
        }

    def verify(self) -> None:
        if not isinstance(self.prediction_run_key, str) or not self.prediction_run_key.strip():
            _reject("prediction_evidence_run_key_missing", "prediction_run_key is required")
        if not isinstance(self.line_key, str) or not self.line_key.strip():
            _reject("prediction_evidence_line_key_missing", "line_key is required")
        _require_issue("target_issue", self.target_issue)
        _require_digest("candidate_package_digest", self.candidate_package_digest)
        if self.scoring_contract != EVALUATION_SCORING_CONTRACT:
            _reject(
                "prediction_evidence_scoring_contract_mismatch",
                "Prediction Evidence must bind the strict v1 scoring contract",
            )
        try:
            normalized_ranking = normalize_ranking_contract(self.ranking_contract)
        except ValueError as exc:
            raise EvaluationArtifactViolation(
                "prediction_evidence_ranking_contract_invalid",
                "Prediction Evidence ranking contract is unknown",
            ) from exc
        if normalized_ranking != self.ranking_contract:
            _reject(
                "prediction_evidence_ranking_contract_not_normalized",
                "Prediction Evidence ranking contract must be normalized",
            )
        if not self.candidates:
            _reject(
                "prediction_evidence_candidates_missing",
                "successful evaluation requires at least one candidate row",
            )
        try:
            EvaluationContractVerifier().verify_candidates(
                self.candidates,
                ranking_contract=self.ranking_contract,
            )
        except EvaluationContractViolation as exc:
            raise EvaluationArtifactViolation(
                "prediction_evidence_candidates_invalid",
                "Prediction candidate rows violate Evaluation Contract v1",
                cause=exc.code,
            ) from exc

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "candidates": _candidate_payload(self.candidates),
            "artifact_digest": self.artifact_digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> PredictionEvidenceArtifactV1:
        payload = _mapping(value, field="prediction")
        try:
            rows = payload["candidates"]
            if not isinstance(rows, list):
                raise TypeError("candidates must be a list")
            candidates = tuple(
                EvaluationCandidateV1(
                    rank=row["rank"],
                    red_numbers=tuple(row["red_numbers"]),
                    score=row["score"],
                )
                for row in rows
            )
            artifact = cls.build(
                prediction_run_key=payload["prediction_run_key"],
                line_key=payload["line_key"],
                target_issue=payload["target_issue"],
                candidate_package_digest=payload["candidate_package_digest"],
                scoring_contract=payload["scoring_contract"],
                ranking_contract=payload["ranking_contract"],
                candidates=candidates,
            )
        except EvaluationArtifactViolation:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise EvaluationArtifactViolation(
                "evaluation_artifact_parse_error",
                "Prediction Evidence payload is malformed",
            ) from exc
        if dict(payload) != artifact.as_dict():
            _reject(
                "prediction_evidence_serialization_mismatch",
                "Prediction Evidence serialization is not canonical",
            )
        return artifact


@dataclass(frozen=True)
class ActualOutcomeArtifactV1:
    target_issue: str
    draw_date: date
    red_numbers: tuple[int, ...]
    blue_number: int

    @classmethod
    def build(
        cls,
        *,
        target_issue: str,
        draw_date: date,
        red_numbers: Sequence[object],
        blue_number: int,
    ) -> ActualOutcomeArtifactV1:
        try:
            canonical = EvaluationContractVerifier().verify_outcome(red_numbers)
        except EvaluationContractViolation as exc:
            raise EvaluationArtifactViolation(
                "actual_outcome_red_invalid",
                "Actual Outcome violates Evaluation Contract v1",
                cause=exc.code,
            ) from exc
        artifact = cls(
            target_issue=target_issue,
            draw_date=draw_date,
            red_numbers=canonical,
            blue_number=blue_number,
        )
        artifact.verify()
        return artifact

    def verify(self) -> None:
        _require_issue("target_issue", self.target_issue)
        if not isinstance(self.draw_date, date) or isinstance(self.draw_date, datetime):
            _reject("actual_outcome_date_invalid", "draw_date must be a date")
        try:
            canonical = EvaluationContractVerifier().verify_outcome(self.red_numbers)
        except EvaluationContractViolation as exc:
            raise EvaluationArtifactViolation(
                "actual_outcome_red_invalid",
                "Actual Outcome violates Evaluation Contract v1",
                cause=exc.code,
            ) from exc
        if canonical != self.red_numbers:
            _reject("actual_outcome_not_canonical", "actual red numbers must be canonical")
        if (
            isinstance(self.blue_number, bool)
            or not isinstance(self.blue_number, int)
            or not 1 <= self.blue_number <= 16
        ):
            _reject("actual_outcome_blue_invalid", "blue_number must be an integer in [1,16]")

    @property
    def artifact_digest(self) -> str:
        return canonical_digest(self.identity_payload(), domain="dehps.actual-outcome-artifact.v1")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": ACTUAL_OUTCOME_ARTIFACT_VERSION,
            "target_issue": self.target_issue,
            "draw_date": self.draw_date.isoformat(),
            "red_numbers": list(self.red_numbers),
            "blue_number": self.blue_number,
            "blue_scored": False,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "artifact_digest": self.artifact_digest}

    @classmethod
    def from_dict(cls, value: object) -> ActualOutcomeArtifactV1:
        payload = _mapping(value, field="outcome")
        try:
            raw_date = payload["draw_date"]
            if not isinstance(raw_date, str):
                raise TypeError("draw_date must be an ISO date")
            artifact = cls.build(
                target_issue=payload["target_issue"],
                draw_date=date.fromisoformat(raw_date),
                red_numbers=payload["red_numbers"],
                blue_number=payload["blue_number"],
            )
        except EvaluationArtifactViolation:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise EvaluationArtifactViolation(
                "evaluation_artifact_parse_error",
                "Actual Outcome payload is malformed",
            ) from exc
        if dict(payload) != artifact.as_dict():
            _reject(
                "actual_outcome_serialization_mismatch",
                "Actual Outcome serialization is not canonical",
            )
        return artifact


@dataclass(frozen=True)
class EvaluationStageEnvelopeV1:
    envelope_version: str
    artifact_version: str
    compiler_version: str
    evaluation_contract: ContractRef
    metric_manifest_digest: str
    target_issue: str
    source_runtime_envelope_digest: str
    source_runtime_artifact_payload_digest: str
    prediction_artifact_digest: str
    outcome_artifact_digest: str
    ranking_audit_digest: str
    evaluation_payload_digest: str
    evaluation_code_commit: str
    evidence_status: str = "evaluated"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "envelope_version": self.envelope_version,
            "artifact_version": self.artifact_version,
            "compiler_version": self.compiler_version,
            "evaluation_contract": self.evaluation_contract.as_dict(),
            "metric_manifest_digest": self.metric_manifest_digest,
            "target_issue": self.target_issue,
            "source_runtime_envelope_digest": self.source_runtime_envelope_digest,
            "source_runtime_artifact_payload_digest": self.source_runtime_artifact_payload_digest,
            "prediction_artifact_digest": self.prediction_artifact_digest,
            "outcome_artifact_digest": self.outcome_artifact_digest,
            "ranking_audit_digest": self.ranking_audit_digest,
            "evaluation_payload_digest": self.evaluation_payload_digest,
            "evaluation_code_commit": self.evaluation_code_commit,
            "evidence_status": self.evidence_status,
        }

    @property
    def envelope_digest(self) -> str:
        return canonical_digest(
            self.identity_payload(),
            domain="dehps.evaluation-stage-envelope.v1",
        )

    def verify(self) -> None:
        if self.envelope_version != EVALUATION_STAGE_ENVELOPE_VERSION:
            _reject("evaluation_stage_envelope_version_mismatch", "unsupported stage envelope")
        if self.artifact_version != EVALUATION_ARTIFACT_VERSION:
            _reject("evaluation_artifact_version_mismatch", "unsupported Evaluation Artifact")
        if self.compiler_version != EVALUATION_COMPILER_VERSION:
            _reject("evaluation_compiler_version_mismatch", "unsupported Evaluation compiler")
        if not self.evaluation_contract.normatively_equals(EVALUATION_CONTRACT_V1):
            _reject("evaluation_artifact_contract_mismatch", "Evaluation Contract is not v1")
        if self.metric_manifest_digest != EVALUATION_METRIC_MANIFEST_DIGEST:
            _reject("evaluation_artifact_manifest_mismatch", "Evaluation manifest digest is not v1")
        _require_issue("target_issue", self.target_issue)
        for name, value in (
            ("metric_manifest_digest", self.metric_manifest_digest),
            ("source_runtime_envelope_digest", self.source_runtime_envelope_digest),
            ("source_runtime_artifact_payload_digest", self.source_runtime_artifact_payload_digest),
            ("prediction_artifact_digest", self.prediction_artifact_digest),
            ("outcome_artifact_digest", self.outcome_artifact_digest),
            ("ranking_audit_digest", self.ranking_audit_digest),
            ("evaluation_payload_digest", self.evaluation_payload_digest),
        ):
            _require_digest(name, value)
        if not isinstance(self.evaluation_code_commit, str) or not _CODE_COMMIT_PATTERN.fullmatch(
            self.evaluation_code_commit
        ):
            _reject(
                "evaluation_artifact_code_commit_invalid",
                "Evaluation Artifact requires a full code commit",
            )
        if self.evidence_status != "evaluated":
            _reject(
                "evaluation_artifact_status_mismatch",
                "Evaluation Artifact v1 represents completed evaluated evidence only",
            )

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "envelope_digest": self.envelope_digest}

    @classmethod
    def from_dict(cls, value: object) -> EvaluationStageEnvelopeV1:
        payload = _mapping(value, field="evaluation_envelope")
        try:
            envelope = cls(
                envelope_version=payload["envelope_version"],
                artifact_version=payload["artifact_version"],
                compiler_version=payload["compiler_version"],
                evaluation_contract=_contract_ref(
                    payload["evaluation_contract"],
                    field="evaluation_envelope.evaluation_contract",
                ),
                metric_manifest_digest=payload["metric_manifest_digest"],
                target_issue=payload["target_issue"],
                source_runtime_envelope_digest=payload["source_runtime_envelope_digest"],
                source_runtime_artifact_payload_digest=payload[
                    "source_runtime_artifact_payload_digest"
                ],
                prediction_artifact_digest=payload["prediction_artifact_digest"],
                outcome_artifact_digest=payload["outcome_artifact_digest"],
                ranking_audit_digest=payload["ranking_audit_digest"],
                evaluation_payload_digest=payload["evaluation_payload_digest"],
                evaluation_code_commit=payload["evaluation_code_commit"],
                evidence_status=payload["evidence_status"],
            )
            envelope.verify()
        except EvaluationArtifactViolation:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise EvaluationArtifactViolation(
                "evaluation_artifact_parse_error",
                "Evaluation Stage Envelope payload is malformed",
            ) from exc
        if dict(payload) != envelope.as_dict():
            _reject(
                "evaluation_stage_envelope_serialization_mismatch",
                "Evaluation Stage Envelope serialization is not canonical",
            )
        return envelope


def _metrics_from_dict(value: object) -> EvaluationMetricsV1:
    payload = _mapping(value, field="metrics")
    try:
        counts = payload["matched_red_count_by_cutoff"]
        if not isinstance(counts, Mapping):
            raise TypeError("matched_red_count_by_cutoff must be an object")
        metrics = EvaluationMetricsV1(
            actual_red_numbers=tuple(payload["actual_red_numbers"]),
            exact_rank=payload["exact_rank"],
            exact_score=payload["exact_score"],
            red5_rank=payload["red5_rank"],
            red5_score=payload["red5_score"],
            red5_numbers=(
                None if payload["red5_numbers"] is None else tuple(payload["red5_numbers"])
            ),
            matched_red_count_by_cutoff=tuple(
                (
                    cutoff,
                    counts[f"top_{cutoff}"]["6"],
                    counts[f"top_{cutoff}"]["5"],
                )
                for cutoff in (100, 1_000, 10_000)
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationArtifactViolation(
            "evaluation_artifact_parse_error",
            "Evaluation metrics payload is malformed",
        ) from exc
    if dict(payload) != metrics.as_dict():
        _reject(
            "evaluation_metrics_serialization_mismatch",
            "Evaluation metrics serialization is not canonical",
        )
    return metrics


def _evaluation_payload_digest(metrics: EvaluationMetricsV1) -> str:
    return canonical_digest(
        {"evidence_status": "evaluated", "metrics": metrics.as_dict()},
        domain="dehps.evaluation-artifact.payload.v1",
    )


@dataclass(frozen=True)
class CompiledEvaluationArtifactV1:
    envelope: EvaluationStageEnvelopeV1
    source_runtime_envelope: RuntimeEnvelopeV1
    prediction: PredictionEvidenceArtifactV1
    outcome: ActualOutcomeArtifactV1
    ranking_audit_json: str
    metrics: EvaluationMetricsV1

    @property
    def ranking_audit(self) -> dict[str, Any]:
        try:
            value = json.loads(self.ranking_audit_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise EvaluationArtifactViolation(
                "evaluation_ranking_audit_invalid",
                "ranking audit must be canonical JSON",
            ) from exc
        if not isinstance(value, dict):
            _reject("evaluation_ranking_audit_invalid", "ranking audit must be an object")
        return value

    @property
    def ranking_audit_digest(self) -> str:
        return canonical_digest(
            self.ranking_audit,
            domain="dehps.evaluation-artifact.ranking-audit.v1",
        )

    @property
    def artifact_digest(self) -> str:
        return canonical_digest(
            {
                "artifact_version": EVALUATION_ARTIFACT_VERSION,
                "envelope_digest": self.envelope.envelope_digest,
                "parent_digests": [
                    self.source_runtime_envelope.envelope_digest,
                    self.prediction.artifact_digest,
                    self.outcome.artifact_digest,
                    self.ranking_audit_digest,
                ],
                "payload_digest": _evaluation_payload_digest(self.metrics),
            },
            domain="dehps.evaluation-artifact.v1",
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_version": EVALUATION_ARTIFACT_VERSION,
            "evaluation_envelope": self.envelope.as_dict(),
            "source_runtime_envelope": self.source_runtime_envelope.as_dict(),
            "prediction": self.prediction.as_dict(),
            "outcome": self.outcome.as_dict(),
            "ranking_audit": self.ranking_audit,
            "metrics": self.metrics.as_dict(),
            "artifact_digest": self.artifact_digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> CompiledEvaluationArtifactV1:
        payload = _mapping(value, field="evaluation_artifact")
        try:
            ranking_audit = _mapping(payload["ranking_audit"], field="ranking_audit")
            artifact = cls(
                envelope=EvaluationStageEnvelopeV1.from_dict(payload["evaluation_envelope"]),
                source_runtime_envelope=RuntimeEnvelopeV1.from_dict(
                    payload["source_runtime_envelope"]
                ),
                prediction=PredictionEvidenceArtifactV1.from_dict(payload["prediction"]),
                outcome=ActualOutcomeArtifactV1.from_dict(payload["outcome"]),
                ranking_audit_json=canonical_json(ranking_audit),
                metrics=_metrics_from_dict(payload["metrics"]),
            )
        except EvaluationArtifactViolation:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise EvaluationArtifactViolation(
                "evaluation_artifact_parse_error",
                "Evaluation Artifact payload is malformed",
            ) from exc
        EvaluationArtifactVerifier().verify(artifact)
        if dict(payload) != artifact.as_dict():
            _reject(
                "evaluation_artifact_serialization_mismatch",
                "Evaluation Artifact serialization is not canonical",
            )
        return artifact


@dataclass(frozen=True)
class EvaluationCompileRequestV1:
    source_runtime_envelope: RuntimeEnvelopeV1
    candidate_package: CandidateABIPackage
    prediction: PredictionEvidenceArtifactV1
    outcome: ActualOutcomeArtifactV1
    ranking_audit: Mapping[str, Any]
    evaluation_code_commit: str


class EvaluationArtifactCompilerV1:
    def compile(self, request: EvaluationCompileRequestV1) -> CompiledEvaluationArtifactV1:
        EvaluationContractVerifier().verify_manifest()
        request.prediction.verify()
        request.outcome.verify()
        _verify_candidate_package(request.candidate_package)
        _verify_source_runtime(request.source_runtime_envelope)
        if not isinstance(request.ranking_audit, Mapping):
            _reject("evaluation_ranking_audit_invalid", "ranking audit must be an object")
        try:
            ranking_audit_json = canonical_json(request.ranking_audit)
        except (TypeError, ValueError) as exc:
            raise EvaluationArtifactViolation(
                "evaluation_ranking_audit_invalid",
                "ranking audit must be a canonical JSON object",
            ) from exc

        metrics = _evaluate_metrics(
            actual_red_numbers=request.outcome.red_numbers,
            candidates=request.prediction.candidates,
            ranking_contract=request.prediction.ranking_contract,
        )
        source_payload_digest = request.source_runtime_envelope.artifact_payload_digest
        if source_payload_digest is None:
            _reject(
                "evaluation_source_payload_digest_missing",
                "source scoring Runtime Envelope has no artifact payload digest",
            )
        ranking_audit_digest = canonical_digest(
            json.loads(ranking_audit_json),
            domain="dehps.evaluation-artifact.ranking-audit.v1",
        )
        envelope = EvaluationStageEnvelopeV1(
            envelope_version=EVALUATION_STAGE_ENVELOPE_VERSION,
            artifact_version=EVALUATION_ARTIFACT_VERSION,
            compiler_version=EVALUATION_COMPILER_VERSION,
            evaluation_contract=EVALUATION_CONTRACT_V1,
            metric_manifest_digest=EVALUATION_METRIC_MANIFEST_DIGEST,
            target_issue=request.prediction.target_issue,
            source_runtime_envelope_digest=request.source_runtime_envelope.envelope_digest,
            source_runtime_artifact_payload_digest=source_payload_digest,
            prediction_artifact_digest=request.prediction.artifact_digest,
            outcome_artifact_digest=request.outcome.artifact_digest,
            ranking_audit_digest=ranking_audit_digest,
            evaluation_payload_digest=_evaluation_payload_digest(metrics),
            evaluation_code_commit=request.evaluation_code_commit,
        )
        artifact = CompiledEvaluationArtifactV1(
            envelope=envelope,
            source_runtime_envelope=request.source_runtime_envelope,
            prediction=request.prediction,
            outcome=request.outcome,
            ranking_audit_json=ranking_audit_json,
            metrics=metrics,
        )
        EvaluationArtifactVerifier().verify(
            artifact,
            candidate_package=request.candidate_package,
        )
        return artifact


class EvaluationArtifactVerifier:
    """Fail closed; verifies parents and recomputes metrics without repairing evidence."""

    def verify(
        self,
        artifact: CompiledEvaluationArtifactV1,
        *,
        candidate_package: CandidateABIPackage | None = None,
    ) -> None:
        artifact.envelope.verify()
        artifact.prediction.verify()
        artifact.outcome.verify()
        _verify_source_runtime(artifact.source_runtime_envelope)
        source = artifact.source_runtime_envelope
        if source.state is not RuntimeState.ARTIFACT_PRODUCED:
            _reject(
                "evaluation_source_runtime_state_invalid",
                "Evaluation requires an artifact_produced scoring Runtime Envelope",
            )
        if source.artifact_type != "scoring_kernel_result":
            _reject(
                "evaluation_source_artifact_type_invalid",
                "Evaluation source must be a scoring_kernel_result",
            )
        if source.evaluation_contract is not None:
            _reject(
                "evaluation_source_already_evaluated",
                "source scoring Runtime Envelope must not already bind an Evaluation Contract",
            )
        if source.candidate_package_digest != artifact.prediction.candidate_package_digest:
            _reject(
                "evaluation_candidate_binding_mismatch",
                "Prediction Evidence does not match the source Candidate ABI package",
            )
        if source.scoring_contract != artifact.prediction.scoring_contract:
            _reject(
                "evaluation_scoring_binding_mismatch",
                "Prediction Evidence does not match the source Scoring Contract",
            )
        if source.ranking_contract != artifact.prediction.ranking_contract:
            _reject(
                "evaluation_ranking_binding_mismatch",
                "Prediction Evidence does not match the source Ranking Contract",
            )
        if artifact.prediction.target_issue != artifact.outcome.target_issue:
            _reject(
                "evaluation_target_issue_mismatch",
                "Prediction and Actual Outcome target issues differ",
            )
        if (
            source.history_latest_issue is not None
            and artifact.prediction.target_issue <= source.history_latest_issue
        ):
            _reject(
                "evaluation_source_history_leakage",
                "evaluation target issue must be after the source History Snapshot",
                target_issue=artifact.prediction.target_issue,
                history_latest_issue=source.history_latest_issue,
            )
        if canonical_json(artifact.ranking_audit) != artifact.ranking_audit_json:
            _reject(
                "evaluation_ranking_audit_not_canonical",
                "ranking audit JSON is not canonical",
            )
        expected_metrics = _evaluate_metrics(
            actual_red_numbers=artifact.outcome.red_numbers,
            candidates=artifact.prediction.candidates,
            ranking_contract=artifact.prediction.ranking_contract,
        )
        if artifact.metrics != expected_metrics:
            _reject(
                "evaluation_metrics_mismatch",
                "Evaluation metrics do not match Prediction and Outcome evidence",
            )

        source_payload_digest = source.artifact_payload_digest
        if source_payload_digest is None:
            _reject(
                "evaluation_source_payload_digest_missing",
                "source scoring Runtime Envelope has no payload digest",
            )
        expected = {
            "target_issue": artifact.prediction.target_issue,
            "source_runtime_envelope_digest": source.envelope_digest,
            "source_runtime_artifact_payload_digest": source_payload_digest,
            "prediction_artifact_digest": artifact.prediction.artifact_digest,
            "outcome_artifact_digest": artifact.outcome.artifact_digest,
            "ranking_audit_digest": artifact.ranking_audit_digest,
            "evaluation_payload_digest": _evaluation_payload_digest(artifact.metrics),
        }
        actual = {name: getattr(artifact.envelope, name) for name in expected}
        if actual != expected:
            _reject(
                "evaluation_stage_binding_mismatch",
                "Evaluation Stage Envelope does not match its parent evidence",
            )

        if candidate_package is not None:
            _verify_candidate_package(candidate_package)
            if candidate_package.package_digest != source.candidate_package_digest:
                _reject(
                    "evaluation_candidate_package_mismatch",
                    "resolved Candidate ABI package does not match the source Runtime Envelope",
                )
            self._verify_candidate_membership(artifact.prediction.candidates, candidate_package)

    @staticmethod
    def _verify_candidate_membership(
        candidates: Sequence[EvaluationCandidateV1],
        candidate_package: CandidateABIPackage,
    ) -> None:
        lex_ids = candidate_package.lex_id
        for row, candidate in enumerate(candidates):
            position = int(np.searchsorted(lex_ids, candidate.lex_id))
            if (
                position >= len(lex_ids)
                or int(lex_ids[position]) != candidate.lex_id
                or tuple(int(number) for number in candidate_package.numbers[position])
                != candidate.red_numbers
            ):
                _reject(
                    "evaluation_candidate_not_in_source_package",
                    "Prediction candidate is absent from the resolved Candidate ABI package",
                    row=row,
                    lex_id=candidate.lex_id,
                )
