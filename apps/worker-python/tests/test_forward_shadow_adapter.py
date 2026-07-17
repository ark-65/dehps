from __future__ import annotations

from copy import deepcopy
import itertools

import numpy as np
import pytest

from dehps.forward_runtime.shadow_adapter import (
    compare_forward_evaluation,
    compare_official_candidate_artifact,
    forward_operational_evidence,
)
from dehps.scoring_kernel import KernelResult
from dehps.optimization.walk_forward import build_ranked_universe
from dehps.scoring_kernel import candidate_store_from_matrix


@pytest.fixture(scope="module")
def candidate_store():
    candidates = list(itertools.islice(itertools.combinations(range(1, 34), 6), 10))
    return candidate_store_from_matrix(
        build_ranked_universe(
            candidates,
            use_cache=False,
            include_hard_filter_exclusions=True,
        )
    )


def result() -> KernelResult:
    return KernelResult(
        backend="numpy_reference",
        contract_version="dehps-scoring-strict-v1",
        target_scores=np.ascontiguousarray([0.12345678], dtype=np.float64),
        exact_ranks=np.ascontiguousarray([321], dtype=np.int64),
        top_candidate_ids=np.ascontiguousarray([[0, 1, 2]], dtype=np.int64),
        top_scores=np.ascontiguousarray([[0.9, 0.8, 0.7]], dtype=np.float64),
        red5_candidate_ids=np.ascontiguousarray([-1 * np.ones(1)], dtype=np.int64),
        red5_scores=np.ascontiguousarray([0.0], dtype=np.float64),
        red5_ranks=np.ascontiguousarray([-1], dtype=np.int64),
    )


def stored_candidates(candidate_store) -> list[dict]:
    return [
        {
            "rank": index + 1,
            "red_numbers": [int(value) for value in candidate_store.numbers[index]],
            "score": score,
        }
        for index, score in enumerate((0.9, 0.8, 0.7))
    ]


def evaluation_row() -> dict:
    return {
        "forward_evaluation_status": "completed",
        "status": "evaluated",
        "candidate_count": 3,
        "top_n": 3,
        "summary": {
            "leakage_passed": True,
            "ranking_audit": {
                "model_score_rank": 321,
                "model_score": 0.12345678,
            },
        },
    }


def test_stored_official_candidate_artifact_matches_kernel_row_identity(candidate_store) -> None:
    check = compare_official_candidate_artifact(
        candidate_store=candidate_store,
        official_result=result(),
        stored_candidates=stored_candidates(candidate_store),
    )

    assert check.status == "matched"
    assert check.candidate_count == 3
    assert check.id_mismatch_count == 0
    assert check.score_mismatch_count == 0


def test_stored_official_candidate_drift_is_counted_not_repaired(candidate_store) -> None:
    candidates = stored_candidates(candidate_store)
    candidates[1]["red_numbers"] = candidates[2]["red_numbers"]
    candidates[2]["score"] = 0.1

    check = compare_official_candidate_artifact(
        candidate_store=candidate_store,
        official_result=result(),
        stored_candidates=candidates,
    )

    assert check.status == "mismatch"
    assert check.id_mismatch_count == 1
    assert check.score_mismatch_count == 1


def test_forward_evaluation_requires_completed_leakage_safe_rank_evidence() -> None:
    passed = compare_forward_evaluation(
        official_result=result(),
        evaluation_row=evaluation_row(),
    )
    assert passed.status == "passed"
    assert passed.mismatch_count == 0

    assert compare_forward_evaluation(
        official_result=result(),
        evaluation_row=None,
    ).status == "pending"

    changed = deepcopy(evaluation_row())
    changed["summary"]["ranking_audit"]["model_score_rank"] = 322
    failed = compare_forward_evaluation(
        official_result=result(),
        evaluation_row=changed,
    )
    assert failed.status == "failed"
    assert failed.mismatch_count == 1


def test_posthoc_adapter_evidence_cannot_claim_simultaneous_capture(candidate_store) -> None:
    artifact = compare_official_candidate_artifact(
        candidate_store=candidate_store,
        official_result=result(),
        stored_candidates=stored_candidates(candidate_store),
    )
    evaluation = compare_forward_evaluation(
        official_result=result(),
        evaluation_row=evaluation_row(),
    )

    operational = forward_operational_evidence(
        prediction_run={
            "prediction_run_key": "static_100:2026082:fixture",
            "ranking_contract": "strict_v1",
        },
        artifact_check=artifact,
        evaluation_check=evaluation,
        source_code_commit="a" * 40,
        replay_code_commit="b" * 40,
        capture_mode="posthoc_reconstruction",
        restart_recovery_result="passed",
        watchdog_result="passed",
    )

    assert operational.capture_mode == "posthoc_reconstruction"
    assert operational.source_code_commit != operational.replay_code_commit
    assert operational.official_candidate_artifact_status == "matched"
