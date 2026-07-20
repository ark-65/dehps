from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import re
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest, canonical_json
from dehps.evaluation import ActualOutcomeArtifactV1, PredictionEvidenceArtifactV1
from dehps.input_contracts import EvaluationMetricsV1, evaluate_ranked_candidates_v1
from dehps.input_contracts.evaluation_contract import (
    EVALUATION_CONTRACT_V1,
    EVALUATION_METRIC_MANIFEST_DIGEST,
)


FROZEN_FUTURE_SEALED_SNAPSHOT_PROTOCOL = (
    "dehps.m2-frozen-future-30-sealed-snapshot.v1"
)
FROZEN_FUTURE_EVALUATION_PROTOCOL = "dehps.m2-frozen-future-30-evaluation.v1"
FROZEN_FUTURE_EVALUATION_ARTIFACT_VERSION = "frozen_future_30_evaluation.v1"
FROZEN_FUTURE_HYPOTHESIS_KEY = "m2-frozen-future-30-ranked-null-v1"
FROZEN_FUTURE_EXPERIMENT_KEY = "m2-frozen-future-30-shadow-v1"
FROZEN_SOURCE_WORKER_TREE = "7a5f305a6162949a157c414d8078649d677c89cf"
FROZEN_CONFIG_HASH = "4de6114fa68db30ae0ad23ba5f5f515b1b1eabee8d251d83e1b04a6b6ed56385"
FROZEN_LINE_KEY = "static_100"
FROZEN_SCORING_CONTRACT = "dehps-scoring-strict-v1"
FROZEN_RANKING_CONTRACT = "strict_v1"
FROZEN_CANDIDATE_ABI = "candidate_abi.v1"
LEGAL_UNIVERSE_SIZE = 1_107_568
RANKED_UNIVERSE_SIZE = 1_105_506
EXCLUDED_UNIVERSE_COUNT = 2_062
FROZEN_TOP_N = 10_000
PRIMARY_METRIC_NAME = "exact_top10000_hit"

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ISSUE_PATTERN = re.compile(r"^[0-9]{7}$")
_CODE_COMMIT_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class FrozenFuture30Violation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise FrozenFuture30Violation(code, message, **context)


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _reject("frozen_future_parse_error", f"{field} must be an object", field=field)
    return value


def _digest(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST_PATTERN.fullmatch(value):
        _reject(
            "frozen_future_digest_invalid",
            f"{field} must be a lowercase sha256 digest",
            field=field,
        )
    return value


def _issue(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _ISSUE_PATTERN.fullmatch(value):
        _reject(
            "frozen_future_issue_invalid",
            f"{field} must be a seven-digit issue",
            field=field,
        )
    return value


def _aware_datetime(value: object, *, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise FrozenFuture30Violation(
                "frozen_future_datetime_invalid",
                f"{field} must be an ISO datetime",
                field=field,
            ) from exc
    else:
        _reject(
            "frozen_future_datetime_invalid",
            f"{field} must be an ISO datetime",
            field=field,
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _reject(
            "frozen_future_datetime_invalid",
            f"{field} must include a timezone",
            field=field,
        )
    return parsed.astimezone(timezone.utc)


def _date(value: object, *, field: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise FrozenFuture30Violation(
                "frozen_future_date_invalid",
                f"{field} must be an ISO date",
                field=field,
            ) from exc
    _reject(
        "frozen_future_date_invalid",
        f"{field} must be an ISO date",
        field=field,
    )


def _datetime_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _metrics_from_dict(value: object) -> EvaluationMetricsV1:
    payload = _mapping(value, field="metrics")
    try:
        counts = _mapping(payload["matched_red_count_by_cutoff"], field="matched counts")
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
    except FrozenFuture30Violation:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise FrozenFuture30Violation(
            "frozen_future_parse_error",
            "metrics payload is malformed",
        ) from exc
    if dict(payload) != metrics.as_dict():
        _reject(
            "frozen_future_metrics_serialization_mismatch",
            "metrics payload is not canonical",
        )
    return metrics


@dataclass(frozen=True)
class VerifiedFrozenFutureSnapshotV1:
    cohort_ordinal: int
    target_issue: str
    as_of_issue: str
    next_draw_date: date
    generated_at: datetime
    sealed_at: datetime
    manifest_digest: str
    prediction: PredictionEvidenceArtifactV1


def verify_frozen_future_snapshot(value: object) -> VerifiedFrozenFutureSnapshotV1:
    payload = _mapping(value, field="sealed_snapshot")
    try:
        manifest_digest = _digest(payload["manifest_digest"], field="manifest_digest")
        unsigned = dict(payload)
        del unsigned["manifest_digest"]
    except KeyError as exc:
        raise FrozenFuture30Violation(
            "frozen_future_parse_error",
            "sealed snapshot is missing manifest_digest",
        ) from exc
    observed_digest = canonical_digest(
        unsigned,
        domain=FROZEN_FUTURE_SEALED_SNAPSHOT_PROTOCOL,
    )
    if observed_digest != manifest_digest:
        _reject(
            "frozen_future_manifest_digest_mismatch",
            "sealed snapshot manifest digest does not match its payload",
            expected=manifest_digest,
            observed=observed_digest,
        )

    expected_scalars = {
        "protocol": FROZEN_FUTURE_SEALED_SNAPSHOT_PROTOCOL,
        "hypothesis_key": FROZEN_FUTURE_HYPOTHESIS_KEY,
        "experiment_key": FROZEN_FUTURE_EXPERIMENT_KEY,
        "line_key": FROZEN_LINE_KEY,
        "config_hash": FROZEN_CONFIG_HASH,
        "scoring_contract": FROZEN_SCORING_CONTRACT,
        "ranking_contract": FROZEN_RANKING_CONTRACT,
        "legal_universe_size": LEGAL_UNIVERSE_SIZE,
        "ranked_universe_size": RANKED_UNIVERSE_SIZE,
        "excluded_universe_count": EXCLUDED_UNIVERSE_COUNT,
        "outcome_available_at_seal": False,
        "production_access": False,
        "production_state_changed": False,
        "production_selection_changed": False,
        "promotion_allowed": False,
        "research_decision_allowed": False,
    }
    mismatches = [
        field for field, expected in expected_scalars.items() if payload.get(field) != expected
    ]
    if mismatches:
        _reject(
            "frozen_future_frozen_identity_mismatch",
            "sealed snapshot does not preserve the preregistered identity",
            fields=mismatches,
        )

    ordinal = payload.get("cohort_ordinal")
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or not 1 <= ordinal <= 30:
        _reject(
            "frozen_future_ordinal_invalid",
            "cohort_ordinal must be an integer in [1,30]",
        )
    as_of_issue = _issue(payload.get("as_of_issue"), field="as_of_issue")
    target_issue = _issue(payload.get("target_issue"), field="target_issue")
    if int(as_of_issue) >= int(target_issue):
        _reject(
            "frozen_future_history_leakage",
            "as_of_issue must strictly precede target_issue",
        )
    next_draw_date = _date(payload.get("next_draw_date"), field="next_draw_date")
    generated_at = _aware_datetime(payload.get("generated_at"), field="generated_at")
    sealed_at = _aware_datetime(payload.get("sealed_at"), field="sealed_at")
    if sealed_at < generated_at:
        _reject(
            "frozen_future_time_order_invalid",
            "sealed_at must not precede generated_at",
        )
    if sealed_at.date() > next_draw_date:
        _reject(
            "frozen_future_snapshot_after_draw_date",
            "sealed snapshot date must not follow next_draw_date",
        )

    source_identity = _mapping(payload.get("source_identity"), field="source_identity")
    source_mismatches = [
        field
        for field in ("preregistered_worker_tree", "executed_worker_tree")
        if source_identity.get(field) != FROZEN_SOURCE_WORKER_TREE
    ]
    if source_identity.get("worker_tree_exact") is not True:
        source_mismatches.append("worker_tree_exact")
    if source_mismatches:
        _reject(
            "frozen_future_source_identity_mismatch",
            "sealed snapshot source worker tree is not frozen",
            fields=source_mismatches,
        )

    runtime_identity = _mapping(payload.get("runtime_identity"), field="runtime_identity")
    if runtime_identity.get("candidate_abi") != FROZEN_CANDIDATE_ABI:
        _reject(
            "frozen_future_candidate_abi_mismatch",
            "sealed snapshot Candidate ABI contract changed",
        )
    for field in (
        "runtime_verification_digest",
        "runtime_envelope_digest",
        "candidate_package_digest",
    ):
        _digest(runtime_identity.get(field), field=f"runtime_identity.{field}")
    for field in ("verified_runtime_id", "candidate_abi_verification_id"):
        value_at_field = runtime_identity.get(field)
        if not isinstance(value_at_field, str) or not value_at_field.strip():
            _reject(
                "frozen_future_runtime_identity_missing",
                f"runtime_identity.{field} is required",
                field=field,
            )

    shadow = _mapping(payload.get("shadow_equality"), field="shadow_equality")
    shadow_expected = {
        "comparison_status": "exact",
        "runtime_identity_mismatch_count": 0,
        "candidate_identity_mismatch_count": 0,
        "topk_id_mismatch_count": 0,
        "topk_score_mismatch_count": 0,
    }
    shadow_mismatches = [
        field for field, expected in shadow_expected.items() if shadow.get(field) != expected
    ]
    if shadow_mismatches:
        _reject(
            "frozen_future_shadow_mismatch",
            "sealed snapshot shadow evidence is not exact",
            fields=shadow_mismatches,
        )
    _digest(shadow.get("comparison_digest"), field="shadow_equality.comparison_digest")

    before = _mapping(payload.get("production_state_before"), field="production_state_before")
    after = _mapping(
        payload.get("production_state_after_build"),
        field="production_state_after_build",
    )
    if dict(before) != dict(after):
        _reject(
            "frozen_future_production_state_changed",
            "production state changed while the snapshot was built",
        )
    _digest(before.get("state_digest"), field="production_state_before.state_digest")

    try:
        prediction = PredictionEvidenceArtifactV1.from_dict(payload["prediction_evidence"])
    except KeyError as exc:
        raise FrozenFuture30Violation(
            "frozen_future_parse_error",
            "sealed snapshot is missing Prediction Evidence",
        ) from exc
    parent_mismatches: list[str] = []
    if prediction.target_issue != target_issue:
        parent_mismatches.append("prediction.target_issue")
    if prediction.line_key != FROZEN_LINE_KEY:
        parent_mismatches.append("prediction.line_key")
    if prediction.scoring_contract != FROZEN_SCORING_CONTRACT:
        parent_mismatches.append("prediction.scoring_contract")
    if prediction.ranking_contract != FROZEN_RANKING_CONTRACT:
        parent_mismatches.append("prediction.ranking_contract")
    if prediction.candidate_package_digest != runtime_identity.get("candidate_package_digest"):
        parent_mismatches.append("prediction.candidate_package_digest")
    if len(prediction.candidates) != FROZEN_TOP_N:
        parent_mismatches.append("prediction.candidate_count")
    if tuple(candidate.rank for candidate in prediction.candidates) != tuple(
        range(1, FROZEN_TOP_N + 1)
    ):
        parent_mismatches.append("prediction.candidate_ranks")
    if len({candidate.red_numbers for candidate in prediction.candidates}) != FROZEN_TOP_N:
        parent_mismatches.append("prediction.candidate_uniqueness")
    if parent_mismatches:
        _reject(
            "frozen_future_prediction_parent_mismatch",
            "Prediction Evidence does not match the sealed snapshot contract",
            fields=parent_mismatches,
        )

    return VerifiedFrozenFutureSnapshotV1(
        cohort_ordinal=ordinal,
        target_issue=target_issue,
        as_of_issue=as_of_issue,
        next_draw_date=next_draw_date,
        generated_at=generated_at,
        sealed_at=sealed_at,
        manifest_digest=manifest_digest,
        prediction=prediction,
    )


@dataclass(frozen=True)
class FrozenFuture30EvaluationArtifactV1:
    cohort_ordinal: int
    target_issue: str
    sealed_snapshot_manifest_digest: str
    prediction_artifact_digest: str
    outcome: ActualOutcomeArtifactV1
    metrics: EvaluationMetricsV1
    evaluated_at: datetime
    evaluation_code_commit: str

    @property
    def primary_hit(self) -> bool:
        return self.metrics.exact_rank is not None and self.metrics.exact_rank <= FROZEN_TOP_N

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": FROZEN_FUTURE_EVALUATION_ARTIFACT_VERSION,
            "protocol": FROZEN_FUTURE_EVALUATION_PROTOCOL,
            "hypothesis_key": FROZEN_FUTURE_HYPOTHESIS_KEY,
            "experiment_key": FROZEN_FUTURE_EXPERIMENT_KEY,
            "cohort_ordinal": self.cohort_ordinal,
            "target_issue": self.target_issue,
            "sealed_snapshot_manifest_digest": self.sealed_snapshot_manifest_digest,
            "prediction_artifact_digest": self.prediction_artifact_digest,
            "outcome": self.outcome.as_dict(),
            "evaluation_contract": EVALUATION_CONTRACT_V1.as_dict(),
            "evaluation_metric_manifest_digest": EVALUATION_METRIC_MANIFEST_DIGEST,
            "metrics": self.metrics.as_dict(),
            "primary_metric": {
                "name": PRIMARY_METRIC_NAME,
                "value": self.primary_hit,
            },
            "evaluated_at": _datetime_text(self.evaluated_at),
            "evaluation_code_commit": self.evaluation_code_commit,
            "scientific_decision_allowed": False,
            "production_selection_changed": False,
            "promotion_allowed": False,
        }

    @property
    def artifact_digest(self) -> str:
        return canonical_digest(
            self.identity_payload(),
            domain=FROZEN_FUTURE_EVALUATION_PROTOCOL,
        )

    def verify(self) -> None:
        if (
            isinstance(self.cohort_ordinal, bool)
            or not isinstance(self.cohort_ordinal, int)
            or not 1 <= self.cohort_ordinal <= 30
        ):
            _reject(
                "frozen_future_ordinal_invalid",
                "cohort_ordinal must be an integer in [1,30]",
            )
        _issue(self.target_issue, field="target_issue")
        _digest(
            self.sealed_snapshot_manifest_digest,
            field="sealed_snapshot_manifest_digest",
        )
        _digest(self.prediction_artifact_digest, field="prediction_artifact_digest")
        self.outcome.verify()
        if self.outcome.target_issue != self.target_issue:
            _reject(
                "frozen_future_outcome_target_mismatch",
                "Actual Outcome targets another issue",
            )
        if tuple(self.metrics.actual_red_numbers) != tuple(self.outcome.red_numbers):
            _reject(
                "frozen_future_metrics_outcome_mismatch",
                "evaluation metrics do not bind the Actual Outcome",
            )
        evaluated_at = _aware_datetime(self.evaluated_at, field="evaluated_at")
        if evaluated_at.date() < self.outcome.draw_date:
            _reject(
                "frozen_future_evaluation_before_draw",
                "evaluated_at must not precede the authoritative draw date",
            )
        if not _CODE_COMMIT_PATTERN.fullmatch(self.evaluation_code_commit):
            _reject(
                "frozen_future_evaluation_commit_invalid",
                "evaluation_code_commit must be a full Git or tree identity",
            )

    def as_dict(self) -> dict[str, Any]:
        self.verify()
        return {**self.identity_payload(), "artifact_digest": self.artifact_digest}

    @classmethod
    def from_dict(cls, value: object) -> FrozenFuture30EvaluationArtifactV1:
        payload = _mapping(value, field="evaluation_artifact")
        expected_constants = {
            "artifact_version": FROZEN_FUTURE_EVALUATION_ARTIFACT_VERSION,
            "protocol": FROZEN_FUTURE_EVALUATION_PROTOCOL,
            "hypothesis_key": FROZEN_FUTURE_HYPOTHESIS_KEY,
            "experiment_key": FROZEN_FUTURE_EXPERIMENT_KEY,
            "evaluation_contract": EVALUATION_CONTRACT_V1.as_dict(),
            "evaluation_metric_manifest_digest": EVALUATION_METRIC_MANIFEST_DIGEST,
            "scientific_decision_allowed": False,
            "production_selection_changed": False,
            "promotion_allowed": False,
        }
        mismatches = [
            field
            for field, expected in expected_constants.items()
            if payload.get(field) != expected
        ]
        if mismatches:
            _reject(
                "frozen_future_evaluation_contract_mismatch",
                "evaluation artifact contract or guard changed",
                fields=mismatches,
            )
        try:
            artifact = cls(
                cohort_ordinal=payload["cohort_ordinal"],
                target_issue=payload["target_issue"],
                sealed_snapshot_manifest_digest=payload["sealed_snapshot_manifest_digest"],
                prediction_artifact_digest=payload["prediction_artifact_digest"],
                outcome=ActualOutcomeArtifactV1.from_dict(payload["outcome"]),
                metrics=_metrics_from_dict(payload["metrics"]),
                evaluated_at=_aware_datetime(payload["evaluated_at"], field="evaluated_at"),
                evaluation_code_commit=payload["evaluation_code_commit"],
            )
            artifact.verify()
        except FrozenFuture30Violation:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise FrozenFuture30Violation(
                "frozen_future_parse_error",
                "evaluation artifact is malformed",
            ) from exc
        primary = payload.get("primary_metric")
        expected_primary = {"name": PRIMARY_METRIC_NAME, "value": artifact.primary_hit}
        if primary != expected_primary:
            _reject(
                "frozen_future_primary_metric_mismatch",
                "primary metric does not match Evaluation Contract metrics",
            )
        if dict(payload) != artifact.as_dict():
            _reject(
                "frozen_future_evaluation_serialization_mismatch",
                "evaluation artifact is not canonical or its digest changed",
            )
        return artifact


def compile_frozen_future_evaluation(
    *,
    sealed_snapshot: object,
    outcome: ActualOutcomeArtifactV1,
    evaluated_at: datetime,
    evaluation_code_commit: str,
) -> FrozenFuture30EvaluationArtifactV1:
    verified = verify_frozen_future_snapshot(sealed_snapshot)
    outcome.verify()
    if outcome.target_issue != verified.target_issue:
        _reject(
            "frozen_future_outcome_target_mismatch",
            "Actual Outcome targets another sealed issue",
        )
    if outcome.draw_date != verified.next_draw_date:
        _reject(
            "frozen_future_outcome_date_mismatch",
            "Actual Outcome draw_date does not match the sealed next_draw_date",
            expected=verified.next_draw_date.isoformat(),
            observed=outcome.draw_date.isoformat(),
        )
    metrics = evaluate_ranked_candidates_v1(
        actual_red_numbers=outcome.red_numbers,
        candidates=verified.prediction.candidates,
        ranking_contract=verified.prediction.ranking_contract,
    )
    canonical_evaluated_at = _aware_datetime(evaluated_at, field="evaluated_at")
    if canonical_evaluated_at < verified.sealed_at:
        _reject(
            "frozen_future_evaluation_before_seal",
            "evaluated_at must not precede the sealed prediction snapshot",
        )
    artifact = FrozenFuture30EvaluationArtifactV1(
        cohort_ordinal=verified.cohort_ordinal,
        target_issue=verified.target_issue,
        sealed_snapshot_manifest_digest=verified.manifest_digest,
        prediction_artifact_digest=verified.prediction.artifact_digest,
        outcome=outcome,
        metrics=metrics,
        evaluated_at=canonical_evaluated_at,
        evaluation_code_commit=evaluation_code_commit,
    )
    artifact.verify()
    return artifact


def verify_frozen_future_evaluation(
    value: object,
    *,
    sealed_snapshot: object | None = None,
) -> FrozenFuture30EvaluationArtifactV1:
    artifact = FrozenFuture30EvaluationArtifactV1.from_dict(value)
    if sealed_snapshot is None:
        return artifact
    expected = compile_frozen_future_evaluation(
        sealed_snapshot=sealed_snapshot,
        outcome=artifact.outcome,
        evaluated_at=artifact.evaluated_at,
        evaluation_code_commit=artifact.evaluation_code_commit,
    )
    if artifact.as_dict() != expected.as_dict():
        _reject(
            "frozen_future_evaluation_parent_mismatch",
            "evaluation artifact does not match its sealed snapshot parent",
        )
    return artifact


def write_frozen_future_evaluation(
    artifact: FrozenFuture30EvaluationArtifactV1,
    *,
    output_dir: Path,
) -> Path:
    payload = artifact.as_dict()
    text = canonical_json(payload) + "\n"
    path = output_dir / (
        f"evaluation-{artifact.target_issue}-ordinal-{artifact.cohort_ordinal:02d}-"
        f"{artifact.artifact_digest}.json"
    )
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            _reject(
                "frozen_future_content_address_collision",
                "evaluation artifact path already contains different bytes",
                path=str(path),
            )
        return path
    atomic_write_text(path, text)
    return path
