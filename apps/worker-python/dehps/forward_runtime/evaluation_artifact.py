from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.evaluation import (
    ActualOutcomeArtifactV1,
    EvaluationArtifactCompilerV1,
    EvaluationArtifactViolation,
    EvaluationCompileRequestV1,
    PredictionEvidenceArtifactV1,
)
from dehps.evaluation.artifact import EVALUATION_ARTIFACT_VERSION
from dehps.input_contracts import EvaluationCandidateV1
from dehps.input_contracts.candidate_abi import CandidateABIPackage
from dehps.input_contracts.evaluation_contract import EVALUATION_CONTRACT_VERSION
from dehps.optimization.walk_forward import build_ranked_universe
from dehps.ranking_contract import LEGACY_RANKING_CONTRACT, normalize_ranking_contract
from dehps.runtime_envelope import RuntimeEnvelopeV1
from dehps.runtime_provenance import (
    RUNTIME_ENVELOPE_PROJECTION_VERSION,
    RUNTIME_ENVELOPE_UNAVAILABLE,
    RUNTIME_ENVELOPE_VERIFIED,
    RuntimeEnvelopeProjection,
    project_runtime_envelope,
)
from dehps.scoring_kernel import candidate_store_from_matrix
from dehps.source_version import resolve_git_commit


FORWARD_EVALUATION_ARTIFACT_PROJECTION_VERSION = (
    "forward_evaluation_artifact_projection.v1"
)
DEFAULT_ARTIFACT_DIR = (
    ROOT_DIR / "data/output/prediction-evaluations/evaluation-artifacts"
)
_SAFE_FILE_PART = re.compile(r"[^A-Za-z0-9_.-]+")

CandidatePackageResolver = Callable[[str], CandidateABIPackage]
CodeCommitResolver = Callable[[], str]


class ForwardEvaluationArtifactRequiredError(RuntimeError):
    def __init__(self, projection: Mapping[str, Any]) -> None:
        self.projection = dict(projection)
        super().__init__(
            "forward_evaluation_artifact_required:"
            f"status={self.projection.get('status')}:"
            f"reason={self.projection.get('reason')}"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": "forward_evaluation_artifact_required",
            "projection": dict(self.projection),
        }


@lru_cache(maxsize=4)
def resolve_canonical_candidate_package(
    expected_package_digest: str,
) -> CandidateABIPackage:
    """Resolve one canonical Candidate ABI package, never an alternate universe.

    The ranked-universe loader owns its mmap cache. This adapter adds a small
    process-local ABI-package cache keyed by the digest recorded in the source
    Runtime Envelope.
    """

    store = candidate_store_from_matrix(build_ranked_universe())
    package = store.candidate_abi_package
    if package is None:
        raise RuntimeError("canonical_candidate_store_has_no_abi_package")
    if package.package_digest != expected_package_digest:
        raise ValueError(
            "candidate_package_digest_mismatch:"
            f"expected={expected_package_digest}:actual={package.package_digest}"
        )
    return package


def _safe_file_part(value: object) -> str:
    text = _SAFE_FILE_PART.sub("-", str(value or "").strip()).strip("-")
    return text[:80] or "none"


def _artifact_required(run: Mapping[str, Any]) -> bool:
    metadata = run.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    values = [
        run.get("evaluation_artifact_required"),
        metadata.get("evaluation_artifact_required"),
    ]
    configured = [value for value in values if value is not None]
    if not configured:
        return False
    if any(not isinstance(value, bool) for value in configured):
        raise TypeError("evaluation_artifact_required must be a boolean")
    if len(set(configured)) > 1:
        raise ValueError("evaluation_artifact_required values disagree")
    return bool(configured[0])


def _stored_runtime_projection(run: Mapping[str, Any]) -> RuntimeEnvelopeProjection:
    metadata = run.get("metadata")
    if not isinstance(metadata, Mapping):
        return project_runtime_envelope(
            None,
            unavailable_reason="prediction_created_without_runtime_envelope",
        )
    raw_projection = metadata.get("runtime_envelope_projection")
    if raw_projection is None:
        prediction_metadata = metadata.get("prediction_metadata")
        if isinstance(prediction_metadata, Mapping):
            raw_projection = prediction_metadata.get("runtime_envelope_projection")
    if raw_projection is None:
        return project_runtime_envelope(
            None,
            unavailable_reason="prediction_created_without_runtime_envelope",
        )
    if not isinstance(raw_projection, Mapping):
        raise TypeError("runtime_envelope_projection must be an object")
    if raw_projection.get("protocol") != RUNTIME_ENVELOPE_PROJECTION_VERSION:
        raise ValueError("runtime_envelope_projection protocol is unsupported")
    status = raw_projection.get("status")
    if status == RUNTIME_ENVELOPE_UNAVAILABLE:
        reason = raw_projection.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("unavailable runtime_envelope_projection requires a reason")
        if raw_projection.get("envelope") is not None:
            raise ValueError("unavailable runtime_envelope_projection must not carry an envelope")
        return project_runtime_envelope(None, unavailable_reason=reason)
    if status != RUNTIME_ENVELOPE_VERIFIED:
        raise ValueError("runtime_envelope_projection status is unsupported")
    if raw_projection.get("reason") is not None:
        raise ValueError("verified runtime_envelope_projection must not carry a reason")
    return project_runtime_envelope(
        raw_projection.get("envelope"),
        unavailable_reason="prediction_created_without_runtime_envelope",
    )


def _base_projection(
    *,
    run: Mapping[str, Any],
    required: bool,
    status: str,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "protocol": FORWARD_EVALUATION_ARTIFACT_PROJECTION_VERSION,
        "status": status,
        "reason": reason,
        "evaluation_contract": EVALUATION_CONTRACT_VERSION,
        "artifact_version": EVALUATION_ARTIFACT_VERSION,
        "artifact_digest": None,
        "artifact_path": None,
        "evaluation_envelope": None,
        "prediction_ranking_contract": normalize_ranking_contract(
            run.get("ranking_contract")
        ),
        "source_runtime_envelope_digest": None,
        "candidate_package_digest": None,
        "automatic_promotion_allowed": False,
        "required": required,
    }


def _failure_reason(exc: Exception) -> str:
    if isinstance(exc, EvaluationArtifactViolation):
        return exc.code
    code = getattr(exc, "code", None)
    return str(code) if isinstance(code, str) and code else type(exc).__name__


class ForwardEvaluationArtifactAdapter:
    def __init__(
        self,
        *,
        candidate_resolver: CandidatePackageResolver = resolve_canonical_candidate_package,
        code_commit_resolver: CodeCommitResolver = resolve_git_commit,
        artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    ) -> None:
        self.candidate_resolver = candidate_resolver
        self.code_commit_resolver = code_commit_resolver
        self.artifact_dir = artifact_dir

    def __call__(
        self,
        *,
        run: Mapping[str, Any],
        actual: Mapping[str, Any],
        candidates: Sequence[Mapping[str, Any]],
        ranking_audit: Mapping[str, Any],
        evaluation_payload: Mapping[str, Any],
        write_artifact: bool,
    ) -> dict[str, Any]:
        try:
            required = _artifact_required(run)
        except Exception as exc:
            projection = _base_projection(
                run=run,
                required=False,
                status="failed",
                reason=_failure_reason(exc),
            )
            raise ForwardEvaluationArtifactRequiredError(projection) from exc

        ranking_contract = normalize_ranking_contract(run.get("ranking_contract"))
        if ranking_contract == LEGACY_RANKING_CONTRACT:
            projection = _base_projection(
                run=run,
                required=required,
                status="unavailable",
                reason="legacy_ranking_contract",
            )
            return self._enforce_required(projection)

        source_envelope: RuntimeEnvelopeV1 | None = None
        try:
            source_projection = _stored_runtime_projection(run)
            if source_projection.status == RUNTIME_ENVELOPE_UNAVAILABLE:
                projection = _base_projection(
                    run=run,
                    required=required,
                    status="unavailable",
                    reason=source_projection.reason,
                )
                return self._enforce_required(projection)
            source_envelope = source_projection.envelope
            if source_envelope is None:
                raise ValueError("verified source Runtime Envelope is missing")
            projection = self._compile(
                run=run,
                actual=actual,
                candidates=candidates,
                ranking_audit=ranking_audit,
                evaluation_payload=evaluation_payload,
                source_envelope=source_envelope,
                required=required,
                write_artifact=write_artifact,
            )
        except ForwardEvaluationArtifactRequiredError:
            raise
        except Exception as exc:
            projection = _base_projection(
                run=run,
                required=required,
                status="failed",
                reason=_failure_reason(exc),
            )
            if source_envelope is not None:
                projection["source_runtime_envelope_digest"] = (
                    source_envelope.envelope_digest
                )
                projection["candidate_package_digest"] = (
                    source_envelope.candidate_package_digest
                )
            as_dict = getattr(exc, "as_dict", None)
            if callable(as_dict):
                projection["failure"] = as_dict()
            else:
                projection["failure"] = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
        return self._enforce_required(projection)

    @staticmethod
    def _enforce_required(projection: dict[str, Any]) -> dict[str, Any]:
        if projection["required"] and projection["status"] != "verified":
            raise ForwardEvaluationArtifactRequiredError(projection)
        return projection

    def _compile(
        self,
        *,
        run: Mapping[str, Any],
        actual: Mapping[str, Any],
        candidates: Sequence[Mapping[str, Any]],
        ranking_audit: Mapping[str, Any],
        evaluation_payload: Mapping[str, Any],
        source_envelope: RuntimeEnvelopeV1,
        required: bool,
        write_artifact: bool,
    ) -> dict[str, Any]:
        summary = evaluation_payload.get("summary")
        if evaluation_payload.get("status") != "evaluated":
            raise ValueError("evaluation payload status must be evaluated")
        if not isinstance(summary, Mapping) or summary.get("leakage_passed") is not True:
            raise ValueError("evaluation payload must pass leakage guard")
        if int(evaluation_payload.get("candidate_count") or 0) != len(candidates):
            raise ValueError("evaluation candidate rows are incomplete")
        self._verify_parent_bindings(
            run=run,
            actual=actual,
            ranking_audit=ranking_audit,
            evaluation_payload=evaluation_payload,
        )

        candidate_package = self.candidate_resolver(
            source_envelope.candidate_package_digest
        )
        prediction = PredictionEvidenceArtifactV1.build(
            prediction_run_key=str(run["prediction_run_key"]),
            line_key=str(run["line_key"]),
            target_issue=str(run["target_issue"]),
            candidate_package_digest=source_envelope.candidate_package_digest,
            scoring_contract=source_envelope.scoring_contract,
            ranking_contract=normalize_ranking_contract(run.get("ranking_contract")),
            candidates=tuple(
                EvaluationCandidateV1(
                    rank=int(row["rank"]),
                    red_numbers=tuple(int(number) for number in row["red_numbers"]),
                    score=float(row["score"]),
                )
                for row in candidates
            ),
        )
        outcome = ActualOutcomeArtifactV1.build(
            target_issue=str(actual["issue"]),
            draw_date=actual["draw_date"],
            red_numbers=actual["red_numbers"],
            blue_number=int(actual["blue_number"]),
        )
        artifact = EvaluationArtifactCompilerV1().compile(
            EvaluationCompileRequestV1(
                source_runtime_envelope=source_envelope,
                candidate_package=candidate_package,
                prediction=prediction,
                outcome=outcome,
                ranking_audit=ranking_audit,
                evaluation_code_commit=self.code_commit_resolver(),
            )
        )
        self._verify_evaluation_payload(evaluation_payload, artifact.metrics.as_dict())
        artifact_path = self._write_artifact(artifact.as_dict()) if write_artifact else None
        return {
            **_base_projection(
                run=run,
                required=required,
                status="verified",
                reason=None,
            ),
            "artifact_digest": artifact.artifact_digest,
            "artifact_path": str(artifact_path) if artifact_path is not None else None,
            "evaluation_envelope": artifact.envelope.as_dict(),
            "source_runtime_envelope_digest": source_envelope.envelope_digest,
            "candidate_package_digest": candidate_package.package_digest,
        }

    @staticmethod
    def _verify_parent_bindings(
        *,
        run: Mapping[str, Any],
        actual: Mapping[str, Any],
        ranking_audit: Mapping[str, Any],
        evaluation_payload: Mapping[str, Any],
    ) -> None:
        expected = {
            "prediction_run_key": str(run["prediction_run_key"]),
            "line_key": str(run["line_key"]),
            "predicted_issue": str(run["target_issue"]),
            "prediction_ranking_contract": normalize_ranking_contract(
                run.get("ranking_contract")
            ),
            "actual_draw_date": actual["draw_date"],
            "actual_blue_number": int(actual["blue_number"]),
            "ranking_audit": dict(ranking_audit),
        }
        mismatches = [
            field
            for field, expected_value in expected.items()
            if evaluation_payload.get(field) != expected_value
        ]
        if mismatches:
            raise EvaluationArtifactViolation(
                "forward_evaluation_parent_binding_mismatch",
                "forward evaluation payload does not match its run, outcome, or ranking parents",
                fields=mismatches,
            )

    @staticmethod
    def _verify_evaluation_payload(
        evaluation_payload: Mapping[str, Any],
        artifact_metrics: Mapping[str, Any],
    ) -> None:
        direct_fields = (
            "actual_red_numbers",
            "exact_rank",
            "exact_score",
            "red5_rank",
            "red5_score",
            "red5_numbers",
            "hit_top_100",
            "hit_top_1000",
            "hit_top_10000",
            "hit_red5_top_100",
            "hit_red5_top_1000",
            "hit_red5_top_10000",
        )
        mismatches = [
            field
            for field in direct_fields
            if evaluation_payload.get(field) != artifact_metrics.get(field)
        ]
        summary = evaluation_payload.get("summary")
        summary = summary if isinstance(summary, Mapping) else {}
        if summary.get("matched_red_count_by_cutoff") != artifact_metrics.get(
            "matched_red_count_by_cutoff"
        ):
            mismatches.append("summary.matched_red_count_by_cutoff")
        if summary.get("blue_scored") is not False:
            mismatches.append("summary.blue_scored")
        if mismatches:
            raise EvaluationArtifactViolation(
                "forward_evaluation_payload_mismatch",
                "forward evaluation payload does not match recomputed Evaluation Artifact metrics",
                fields=mismatches,
            )

    def _write_artifact(self, payload: Mapping[str, Any]) -> Path:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        envelope = payload["evaluation_envelope"]
        prediction = payload["prediction"]
        digest = str(payload["artifact_digest"])
        path = self.artifact_dir / (
            "evaluation-artifact-"
            f"{_safe_file_part(prediction['target_issue'])}-"
            f"{_safe_file_part(prediction['prediction_run_key'])}-"
            f"{_safe_file_part(envelope['target_issue'])}-"
            f"{digest[:16]}.json"
        )
        atomic_write_text(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        return path


__all__ = [
    "DEFAULT_ARTIFACT_DIR",
    "FORWARD_EVALUATION_ARTIFACT_PROJECTION_VERSION",
    "ForwardEvaluationArtifactAdapter",
    "ForwardEvaluationArtifactRequiredError",
    "resolve_canonical_candidate_package",
]
