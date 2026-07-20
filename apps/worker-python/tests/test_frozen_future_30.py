from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from itertools import islice, combinations
from pathlib import Path

import pytest

from dehps.contracts import canonical_digest
from dehps.evaluation import ActualOutcomeArtifactV1, PredictionEvidenceArtifactV1
from dehps.experiments.frozen_future_30 import (
    FROZEN_FUTURE_SEALED_SNAPSHOT_PROTOCOL,
    FrozenFuture30EvaluationArtifactV1,
    FrozenFuture30Violation,
    compile_frozen_future_evaluation,
    verify_frozen_future_evaluation,
    verify_frozen_future_snapshot,
    write_frozen_future_evaluation,
)
from dehps.input_contracts import EvaluationCandidateV1


CODE_COMMIT = "a" * 40
CONFIG_HASH = "4de6114fa68db30ae0ad23ba5f5f515b1b1eabee8d251d83e1b04a6b6ed56385"
WORKER_TREE = "7a5f305a6162949a157c414d8078649d677c89cf"
CANDIDATE_PACKAGE_DIGEST = "b" * 64


def _seal(payload: dict) -> dict:
    unsigned = {key: value for key, value in payload.items() if key != "manifest_digest"}
    return {
        **unsigned,
        "manifest_digest": canonical_digest(
            unsigned,
            domain=FROZEN_FUTURE_SEALED_SNAPSHOT_PROTOCOL,
        ),
    }


@pytest.fixture(scope="module")
def sealed_snapshot() -> dict:
    rows = tuple(islice(combinations(range(1, 34), 6), 10_000))
    candidates = tuple(
        EvaluationCandidateV1(
            rank=index,
            red_numbers=numbers,
            score=1.0 - index / 100_000,
        )
        for index, numbers in enumerate(rows, start=1)
    )
    prediction = PredictionEvidenceArtifactV1.build(
        prediction_run_key="m2-frozen-future-30:static_100:2026083:fixture",
        line_key="static_100",
        target_issue="2026083",
        candidate_package_digest=CANDIDATE_PACKAGE_DIGEST,
        scoring_contract="dehps-scoring-strict-v1",
        ranking_contract="strict_v1",
        candidates=candidates,
    )
    state = {
        "latest_issue": "2026082",
        "target_present": False,
        "state_digest": "c" * 64,
    }
    return _seal(
        {
            "protocol": FROZEN_FUTURE_SEALED_SNAPSHOT_PROTOCOL,
            "hypothesis_key": "m2-frozen-future-30-ranked-null-v1",
            "experiment_key": "m2-frozen-future-30-shadow-v1",
            "operator_run_id": "fixture",
            "cohort_ordinal": 1,
            "sealed_at": "2026-07-20T09:32:30Z",
            "generated_at": "2026-07-20T09:30:01Z",
            "as_of_issue": "2026082",
            "target_issue": "2026083",
            "next_draw_date": "2026-07-21",
            "line_key": "static_100",
            "source_run_id": "fixture",
            "source_round_index": 1,
            "snapshot_key": "fixture",
            "config_hash": CONFIG_HASH,
            "config": {"frequency_weight": 1.0},
            "history_fingerprint": "d" * 64,
            "ranking_contract": "strict_v1",
            "scoring_contract": "dehps-scoring-strict-v1",
            "legal_universe_size": 1_107_568,
            "ranked_universe_size": 1_105_506,
            "excluded_universe_count": 2_062,
            "source_identity": {
                "preregistered_commit": "e" * 40,
                "executed_commit": "f" * 40,
                "preregistered_worker_tree": WORKER_TREE,
                "executed_worker_tree": WORKER_TREE,
                "worker_tree_exact": True,
            },
            "runtime_identity": {
                "verified_runtime_id": "verified_runtime.v1-fixture",
                "runtime_verification_digest": "1" * 64,
                "runtime_envelope_digest": "2" * 64,
                "candidate_abi": "candidate_abi.v1",
                "candidate_abi_verification_id": "verified_candidate.v1-fixture",
                "candidate_package_digest": CANDIDATE_PACKAGE_DIGEST,
            },
            "shadow_equality": {
                "comparison_status": "exact",
                "comparison_digest": "3" * 64,
                "official_backend": "feature_abi_numpy_reference",
                "shadow_backend": "feature_abi_numba_cpu",
                "runtime_identity_mismatch_count": 0,
                "candidate_identity_mismatch_count": 0,
                "topk_id_mismatch_count": 0,
                "topk_score_mismatch_count": 0,
            },
            "prediction_evidence": prediction.as_dict(),
            "production_state_before": state,
            "production_state_after_build": dict(state),
            "outcome_available_at_seal": False,
            "production_access": False,
            "production_state_changed": False,
            "production_selection_changed": False,
            "promotion_allowed": False,
            "research_decision_allowed": False,
        }
    )


def _outcome(numbers: tuple[int, ...]) -> ActualOutcomeArtifactV1:
    return ActualOutcomeArtifactV1.build(
        target_issue="2026083",
        draw_date=date(2026, 7, 21),
        red_numbers=numbers,
        blue_number=16,
    )


def _compile(sealed_snapshot: dict, numbers: tuple[int, ...]):
    return compile_frozen_future_evaluation(
        sealed_snapshot=sealed_snapshot,
        outcome=_outcome(numbers),
        evaluated_at=datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc),
        evaluation_code_commit=CODE_COMMIT,
    )


def test_compile_hit_and_detached_round_trip(sealed_snapshot: dict) -> None:
    first = tuple(sealed_snapshot["prediction_evidence"]["candidates"][0]["red_numbers"])
    artifact = _compile(sealed_snapshot, first)

    assert artifact.metrics.exact_rank == 1
    assert artifact.primary_hit is True
    restored = FrozenFuture30EvaluationArtifactV1.from_dict(deepcopy(artifact.as_dict()))
    assert restored.as_dict() == artifact.as_dict()
    assert verify_frozen_future_evaluation(
        artifact.as_dict(), sealed_snapshot=sealed_snapshot
    ).artifact_digest == artifact.artifact_digest


def test_compile_miss_preserves_primary_false(sealed_snapshot: dict) -> None:
    artifact = _compile(sealed_snapshot, (28, 29, 30, 31, 32, 33))

    assert artifact.metrics.exact_rank is None
    assert artifact.primary_hit is False


def test_sealed_manifest_mutation_fails_closed(sealed_snapshot: dict) -> None:
    payload = deepcopy(sealed_snapshot)
    payload["config_hash"] = "0" * 64

    with pytest.raises(FrozenFuture30Violation) as exc_info:
        verify_frozen_future_snapshot(payload)
    assert exc_info.value.code == "frozen_future_manifest_digest_mismatch"


def test_readdressed_frozen_identity_mutation_still_fails(sealed_snapshot: dict) -> None:
    payload = deepcopy(sealed_snapshot)
    payload["config_hash"] = "0" * 64
    payload = _seal(payload)

    with pytest.raises(FrozenFuture30Violation) as exc_info:
        verify_frozen_future_snapshot(payload)
    assert exc_info.value.code == "frozen_future_frozen_identity_mismatch"


def test_readdressed_short_candidate_set_still_fails(sealed_snapshot: dict) -> None:
    payload = deepcopy(sealed_snapshot)
    prediction = PredictionEvidenceArtifactV1.from_dict(payload["prediction_evidence"])
    shortened = PredictionEvidenceArtifactV1.build(
        prediction_run_key=prediction.prediction_run_key,
        line_key=prediction.line_key,
        target_issue=prediction.target_issue,
        candidate_package_digest=prediction.candidate_package_digest,
        scoring_contract=prediction.scoring_contract,
        ranking_contract=prediction.ranking_contract,
        candidates=prediction.candidates[:-1],
    )
    payload["prediction_evidence"] = shortened.as_dict()
    payload = _seal(payload)

    with pytest.raises(FrozenFuture30Violation) as exc_info:
        verify_frozen_future_snapshot(payload)
    assert exc_info.value.code == "frozen_future_prediction_parent_mismatch"
    assert set(exc_info.value.context["fields"]) == {
        "prediction.candidate_count",
        "prediction.candidate_ranks",
        "prediction.candidate_uniqueness",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("outcome_available_at_seal", True),
        ("production_access", True),
        ("production_selection_changed", True),
        ("promotion_allowed", True),
        ("research_decision_allowed", True),
    ),
)
def test_readdressed_guard_mutation_fails(
    sealed_snapshot: dict,
    field: str,
    value: bool,
) -> None:
    payload = deepcopy(sealed_snapshot)
    payload[field] = value
    payload = _seal(payload)

    with pytest.raises(FrozenFuture30Violation) as exc_info:
        verify_frozen_future_snapshot(payload)
    assert exc_info.value.code == "frozen_future_frozen_identity_mismatch"


def test_outcome_target_mismatch_fails(sealed_snapshot: dict) -> None:
    outcome = ActualOutcomeArtifactV1.build(
        target_issue="2026084",
        draw_date=date(2026, 7, 23),
        red_numbers=(1, 2, 3, 4, 5, 6),
        blue_number=1,
    )

    with pytest.raises(FrozenFuture30Violation) as exc_info:
        compile_frozen_future_evaluation(
            sealed_snapshot=sealed_snapshot,
            outcome=outcome,
            evaluated_at=datetime.now(timezone.utc),
            evaluation_code_commit=CODE_COMMIT,
        )
    assert exc_info.value.code == "frozen_future_outcome_target_mismatch"


def test_outcome_draw_date_mismatch_fails(sealed_snapshot: dict) -> None:
    outcome = ActualOutcomeArtifactV1.build(
        target_issue="2026083",
        draw_date=date(2026, 7, 22),
        red_numbers=(1, 2, 3, 4, 5, 6),
        blue_number=1,
    )

    with pytest.raises(FrozenFuture30Violation) as exc_info:
        compile_frozen_future_evaluation(
            sealed_snapshot=sealed_snapshot,
            outcome=outcome,
            evaluated_at=datetime(2026, 7, 22, 14, 30, tzinfo=timezone.utc),
            evaluation_code_commit=CODE_COMMIT,
        )
    assert exc_info.value.code == "frozen_future_outcome_date_mismatch"


def test_detached_metric_mutation_fails(sealed_snapshot: dict) -> None:
    first = tuple(sealed_snapshot["prediction_evidence"]["candidates"][0]["red_numbers"])
    payload = _compile(sealed_snapshot, first).as_dict()
    payload["metrics"]["exact_rank"] = 2

    with pytest.raises(FrozenFuture30Violation) as exc_info:
        FrozenFuture30EvaluationArtifactV1.from_dict(payload)
    assert exc_info.value.code in {
        "frozen_future_primary_metric_mismatch",
        "frozen_future_evaluation_serialization_mismatch",
    }


def test_invalid_evaluation_commit_fails(sealed_snapshot: dict) -> None:
    first = tuple(sealed_snapshot["prediction_evidence"]["candidates"][0]["red_numbers"])

    with pytest.raises(FrozenFuture30Violation) as exc_info:
        compile_frozen_future_evaluation(
            sealed_snapshot=sealed_snapshot,
            outcome=_outcome(first),
            evaluated_at=datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc),
            evaluation_code_commit="short",
        )
    assert exc_info.value.code == "frozen_future_evaluation_commit_invalid"


@pytest.mark.parametrize(
    ("evaluated_at", "expected_code"),
    (
        (
            datetime(2026, 7, 19, tzinfo=timezone.utc),
            "frozen_future_evaluation_before_seal",
        ),
        (
            datetime(2026, 7, 20, 12, tzinfo=timezone.utc),
            "frozen_future_evaluation_before_draw",
        ),
    ),
)
def test_evaluation_time_boundary_fails_closed(
    sealed_snapshot: dict,
    evaluated_at: datetime,
    expected_code: str,
) -> None:
    first = tuple(sealed_snapshot["prediction_evidence"]["candidates"][0]["red_numbers"])

    with pytest.raises(FrozenFuture30Violation) as exc_info:
        compile_frozen_future_evaluation(
            sealed_snapshot=sealed_snapshot,
            outcome=_outcome(first),
            evaluated_at=evaluated_at,
            evaluation_code_commit=CODE_COMMIT,
        )
    assert exc_info.value.code == expected_code


def test_content_addressed_writer_is_idempotent(
    sealed_snapshot: dict,
    tmp_path: Path,
) -> None:
    first = tuple(sealed_snapshot["prediction_evidence"]["candidates"][0]["red_numbers"])
    artifact = _compile(sealed_snapshot, first)

    first_path = write_frozen_future_evaluation(artifact, output_dir=tmp_path)
    second_path = write_frozen_future_evaluation(artifact, output_dir=tmp_path)

    assert first_path == second_path
    assert verify_frozen_future_evaluation(
        __import__("json").loads(first_path.read_text()),
        sealed_snapshot=sealed_snapshot,
    ).artifact_digest == artifact.artifact_digest


def test_content_addressed_writer_rejects_different_bytes(
    sealed_snapshot: dict,
    tmp_path: Path,
) -> None:
    first = tuple(sealed_snapshot["prediction_evidence"]["candidates"][0]["red_numbers"])
    artifact = _compile(sealed_snapshot, first)
    path = write_frozen_future_evaluation(artifact, output_dir=tmp_path)
    path.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(FrozenFuture30Violation) as exc_info:
        write_frozen_future_evaluation(artifact, output_dir=tmp_path)
    assert exc_info.value.code == "frozen_future_content_address_collision"
