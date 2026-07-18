from __future__ import annotations

from copy import deepcopy
import math

import pytest

import dehps.optimization.prediction_evaluation as current_evaluation
from dehps.input_contracts import (
    EVALUATION_CONTRACT_V1,
    EVALUATION_CONTRACT_VERSION,
    EVALUATION_GOLDEN_SUITE,
    EVALUATION_METRIC_MANIFEST_DIGEST,
    EvaluationCandidateV1,
    EvaluationContractVerifier,
    EvaluationContractViolation,
    classify_evaluation_comparison,
    evaluate_ranked_candidates_v1,
    evaluation_metric_manifest,
)
from dehps.ranking_contract import (
    CANDIDATE_IDENTITY_REGRESSION,
    LEGACY_RANKING_CONTRACT,
    RANKING_CONTRACT_DIFFERENCE,
    SCORE_REGRESSION,
    STRICT_RANKING_CONTRACT,
)


def _golden_rows() -> tuple[EvaluationCandidateV1, ...]:
    return tuple(
        EvaluationCandidateV1(
            rank=int(row["rank"]),
            red_numbers=tuple(int(number) for number in row["red_numbers"]),
            score=float(row["score"]),
        )
        for row in EVALUATION_GOLDEN_SUITE["candidate_rows"]
    )


def test_evaluation_contract_identity_and_manifest_are_frozen() -> None:
    manifest = evaluation_metric_manifest()

    EvaluationContractVerifier().verify_manifest(manifest)
    assert EVALUATION_CONTRACT_V1.key == EVALUATION_CONTRACT_VERSION
    assert manifest["metrics"]["cutoffs"] == [100, 1_000, 10_000]
    assert manifest["rank_namespaces"]["export_rank"] != manifest["rank_namespaces"][
        "model_score_rank"
    ]
    assert len(EVALUATION_METRIC_MANIFEST_DIGEST) == 64


def test_evaluation_golden_suite_reproduces_existing_forward_semantics() -> None:
    metrics = evaluate_ranked_candidates_v1(
        actual_red_numbers=EVALUATION_GOLDEN_SUITE["actual_red_numbers"],
        candidates=_golden_rows(),
        ranking_contract=EVALUATION_GOLDEN_SUITE["source_ranking_contract"],
    )

    assert metrics.as_dict() == EVALUATION_GOLDEN_SUITE["expected"]
    assert EVALUATION_GOLDEN_SUITE["actual_blue_number"] == 16
    assert metrics.as_dict()["blue_scored"] is False


def test_evaluation_golden_suite_matches_current_forward_evaluator(monkeypatch) -> None:
    source_rows = [
        {
            "line_key": "static_100",
            "line_label": "100-period static training",
            "line_kind": "static",
            "snapshot_key": "evaluation-contract-golden",
            "run_id": "golden-run",
            "source_round_index": 1,
            "as_of_issue": "2026079",
            "next_issue": "2026080",
            "prediction_metadata": {},
            "prediction_ranking_contract": STRICT_RANKING_CONTRACT,
            "top_n": 10_001,
            "rank": int(row["rank"]),
            "red_numbers": list(row["red_numbers"]),
            "score": float(row["score"]),
            "generated_at": "2026-07-16T10:00:00Z",
        }
        for row in EVALUATION_GOLDEN_SUITE["candidate_rows"]
    ]
    monkeypatch.setattr(
        current_evaluation,
        "load_prediction_rows",
        lambda *_args, **_kwargs: (source_rows, None),
    )
    monkeypatch.setattr(
        current_evaluation,
        "load_actual_draw",
        lambda *_args, **_kwargs: {
            "issue": "2026080",
            "draw_date": "2026-07-16",
            "red_numbers": EVALUATION_GOLDEN_SUITE["actual_red_numbers"],
            "blue_number": EVALUATION_GOLDEN_SUITE["actual_blue_number"],
        },
    )

    current = current_evaluation.evaluate_prediction_snapshot(
        object(),
        line_key="static_100",
        predicted_issue="2026080",
        write_report=False,
        persist=False,
    )
    expected = EVALUATION_GOLDEN_SUITE["expected"]

    for field in (
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
    ):
        assert current[field] == expected[field]
    assert current["summary"]["matched_red_count_by_cutoff"] == expected[
        "matched_red_count_by_cutoff"
    ]
    assert current["summary"]["blue_scored"] is expected["blue_scored"]


def test_evaluation_cutoffs_are_inclusive_and_red5_means_exactly_five() -> None:
    payload = evaluate_ranked_candidates_v1(
        actual_red_numbers=(1, 2, 3, 4, 5, 6),
        candidates=_golden_rows(),
        ranking_contract=STRICT_RANKING_CONTRACT,
    ).as_dict()

    assert payload["exact_rank"] == 2
    assert payload["red5_rank"] == 1
    assert payload["matched_red_count_by_cutoff"]["top_100"] == {"6": 1, "5": 2}
    assert payload["matched_red_count_by_cutoff"]["top_1000"] == {"6": 1, "5": 4}
    assert payload["matched_red_count_by_cutoff"]["top_10000"] == {"6": 1, "5": 5}


@pytest.mark.parametrize(
    ("rows", "code"),
    [
        (
            (
                EvaluationCandidateV1(2, (1, 2, 3, 4, 5, 7), 0.9),
                EvaluationCandidateV1(1, (1, 2, 3, 4, 5, 8), 0.8),
            ),
            "evaluation_rank_order_invalid",
        ),
        (
            (
                EvaluationCandidateV1(1, (1, 2, 3, 4, 5, 7), 0.9),
                EvaluationCandidateV1(2, (1, 2, 3, 4, 5, 7), 0.8),
            ),
            "evaluation_candidate_duplicate",
        ),
        (
            (EvaluationCandidateV1(1, (1, 2, 3, 4, 5, 7), math.nan),),
            "evaluation_score_invalid",
        ),
        (
            (EvaluationCandidateV1(1, (1, 2, 3, 4, 5, 7), "0.9"),),  # type: ignore[arg-type]
            "evaluation_score_invalid",
        ),
        (
            (
                EvaluationCandidateV1(1, (1, 2, 3, 4, 5, 8), 0.8),
                EvaluationCandidateV1(2, (1, 2, 3, 4, 5, 7), 0.8),
            ),
            "evaluation_strict_tie_order_invalid",
        ),
    ],
)
def test_evaluation_verifier_fails_closed_on_invalid_candidate_rows(rows, code) -> None:
    with pytest.raises(EvaluationContractViolation) as exc_info:
        evaluate_ranked_candidates_v1(
            actual_red_numbers=(1, 2, 3, 4, 5, 6),
            candidates=rows,
            ranking_contract=STRICT_RANKING_CONTRACT,
        )

    assert exc_info.value.code == code


def test_evaluation_verifier_rejects_invalid_outcome_and_manifest_drift() -> None:
    with pytest.raises(EvaluationContractViolation) as exc_info:
        evaluate_ranked_candidates_v1(
            actual_red_numbers=(1, 2, 3, 4, 5, 5),
            candidates=(),
            ranking_contract=STRICT_RANKING_CONTRACT,
        )
    assert exc_info.value.code == "evaluation_outcome_invalid"

    manifest = deepcopy(evaluation_metric_manifest())
    manifest["metrics"]["red5"] = "at_least_5"
    with pytest.raises(EvaluationContractViolation) as exc_info:
        EvaluationContractVerifier().verify_manifest(manifest)
    assert exc_info.value.code == "evaluation_manifest_digest_mismatch"


def test_evaluation_comparison_separates_contract_differences_from_regressions() -> None:
    common = {
        "left_evaluation_contract": EVALUATION_CONTRACT_VERSION,
        "right_evaluation_contract": EVALUATION_CONTRACT_VERSION,
        "left_scoring_contract": "dehps-scoring-strict-v1",
        "right_scoring_contract": "dehps-scoring-strict-v1",
        "metric_mismatch_count": 0,
    }
    assert classify_evaluation_comparison(
        **common,
        left_ranking_contract=LEGACY_RANKING_CONTRACT,
        right_ranking_contract=STRICT_RANKING_CONTRACT,
        candidate_id_mismatch_count=1,
        score_mismatch_count=0,
    ) == RANKING_CONTRACT_DIFFERENCE
    assert classify_evaluation_comparison(
        **common,
        left_ranking_contract=LEGACY_RANKING_CONTRACT,
        right_ranking_contract=STRICT_RANKING_CONTRACT,
        candidate_id_mismatch_count=1,
        score_mismatch_count=1,
    ) == SCORE_REGRESSION
    assert classify_evaluation_comparison(
        **common,
        left_ranking_contract=STRICT_RANKING_CONTRACT,
        right_ranking_contract=STRICT_RANKING_CONTRACT,
        candidate_id_mismatch_count=1,
        score_mismatch_count=0,
    ) == CANDIDATE_IDENTITY_REGRESSION

    with pytest.raises(EvaluationContractViolation) as exc_info:
        classify_evaluation_comparison(
            **common,
            left_ranking_contract=STRICT_RANKING_CONTRACT,
            right_ranking_contract=STRICT_RANKING_CONTRACT,
            candidate_id_mismatch_count=-1,
            score_mismatch_count=0,
        )
    assert exc_info.value.code == "evaluation_mismatch_count_invalid"
