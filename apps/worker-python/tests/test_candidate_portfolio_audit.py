from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
from math import comb, isclose

import pytest

from dehps.portfolio import (
    NullModelConfig,
    PortfolioAuditViolation,
    ScoredCandidate,
    audit_candidate_portfolio,
    verify_portfolio_audit_payload,
)
from dehps.portfolio.audit import calculate_portfolio_metrics
from dehps.portfolio.artifact import load_and_verify_portfolio_audit_artifact
from scripts.audit_candidate_portfolio import main as audit_cli_main


def candidate(rank: int, numbers: tuple[int, ...], score: float = 1.0) -> ScoredCandidate:
    return ScoredCandidate.build(source_rank=rank, red_numbers=numbers, score=score)


def small_pool() -> tuple[ScoredCandidate, ...]:
    rows = (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 7),
        (1, 2, 3, 8, 9, 10),
        (11, 12, 13, 14, 15, 16),
        (17, 18, 19, 20, 21, 22),
        (23, 24, 25, 26, 27, 28),
    )
    return tuple(candidate(index, row, 1.0 - index / 100) for index, row in enumerate(rows, 1))


def test_scored_candidate_rejects_nonfinite_and_lex_id_mismatch():
    with pytest.raises(PortfolioAuditViolation, match="invalid_portfolio_score"):
        ScoredCandidate.build(
            source_rank=1,
            red_numbers=(1, 2, 3, 4, 5, 6),
            score=float("nan"),
        )
    with pytest.raises(PortfolioAuditViolation, match="portfolio_candidate_lex_id_mismatch"):
        ScoredCandidate.build(
            source_rank=1,
            red_numbers=(1, 2, 3, 4, 5, 6),
            score=1.0,
            lex_id=10,
        )


def test_scored_candidate_accepts_finite_postgres_decimal_without_string_coercion():
    row = ScoredCandidate.build(
        source_rank=1,
        red_numbers=(1, 2, 3, 4, 5, 6),
        score=Decimal("1.125"),
    )

    assert row.score == 1.125
    with pytest.raises(PortfolioAuditViolation, match="invalid_portfolio_score"):
        ScoredCandidate.build(
            source_rank=1,
            red_numbers=(1, 2, 3, 4, 5, 6),
            score="1.125",
        )


def test_audit_rejects_duplicate_candidates_and_rank_disorder():
    first = candidate(1, (1, 2, 3, 4, 5, 6))
    duplicate = candidate(2, (1, 2, 3, 4, 5, 6))
    with pytest.raises(PortfolioAuditViolation, match="portfolio_duplicate_candidate"):
        audit_candidate_portfolio(
            (first, duplicate),
            null_config=NullModelConfig(uniform_legal_replicates=2, random_from_pool_replicates=2),
        )
    with pytest.raises(PortfolioAuditViolation, match="portfolio_source_rank_order_invalid"):
        audit_candidate_portfolio(
            (candidate(2, (1, 2, 3, 4, 5, 7)), first),
            null_config=NullModelConfig(uniform_legal_replicates=2, random_from_pool_replicates=2),
        )


def test_audit_rejects_leaking_history_cutoff_and_strict_rank_disorder():
    pool = small_pool()
    config = NullModelConfig(uniform_legal_replicates=2, random_from_pool_replicates=2)
    with pytest.raises(PortfolioAuditViolation, match="portfolio_history_cutoff_leakage"):
        audit_candidate_portfolio(
            pool[:2],
            candidate_pool=pool,
            source={"as_of_issue": "2026084", "target_issue": "2026084"},
            null_config=config,
        )
    disordered = (
        candidate(1, (1, 2, 3, 4, 5, 6), 0.5),
        candidate(2, (1, 2, 3, 4, 5, 7), 0.6),
    )
    with pytest.raises(PortfolioAuditViolation, match="portfolio_strict_ranking_order_mismatch"):
        audit_candidate_portfolio(
            disordered,
            source={"ranking_contract": "strict_v1"},
            null_config=config,
        )


def test_two_ticket_metrics_are_hand_computable():
    metrics = calculate_portfolio_metrics(
        (
            (1, 2, 3, 4, 5, 6),
            (1, 2, 3, 4, 5, 7),
        ),
        scores=(1.0, 0.5),
    )

    assert metrics["candidate_count"] == 2
    assert metrics["pairwise_overlap"] == {
        "pair_count": 1,
        "histogram": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 1, "6": 0},
        "mean": 5.0,
        "p50": 5.0,
        "p90": 5.0,
        "maximum": 5,
    }
    assert metrics["pair_coverage"]["unique_count"] == 20
    assert metrics["triple_coverage"]["unique_count"] == 30
    assert metrics["number_exposure"]["maximum_numbers"] == [1, 2, 3, 4, 5]
    assert metrics["number_exposure"]["maximum_per_ticket_rate"] == 1.0


def test_average_overlap_matches_uniform_analytic_expectation_in_seeded_null():
    pool = small_pool()
    artifact = audit_candidate_portfolio(
        pool[:3],
        candidate_pool=pool,
        null_config=NullModelConfig(
            master_seed=101,
            uniform_legal_replicates=600,
            random_from_pool_replicates=20,
        ),
        generated_at="2026-07-22T00:00:00+00:00",
        code_commit="b" * 40,
    )
    baseline = artifact.null_comparisons["uniform_legal_same_budget"]["metrics"]
    expected = 6 * 6 / 33

    assert isclose(baseline["average_pair_overlap"]["mean"], expected, abs_tol=0.08)
    assert baseline["average_pair_overlap"]["sample_sd"] > 0.0


def test_event_specific_ess_names_threshold_and_formula():
    metrics = calculate_portfolio_metrics(
        (
            (1, 2, 3, 4, 5, 6),
            (7, 8, 9, 10, 11, 12),
            (13, 14, 15, 16, 17, 18),
        ),
    )

    for key, event in (("red3_plus", "red3_plus"), ("red4_plus", "red4_plus")):
        payload = metrics["effective_sample_size"][key]
        assert payload["event"] == event
        assert payload["formula"] == "B/(1+(B-1)*mean_pair_indicator_correlation)"
        assert payload["null_hit_probability_per_ticket"] > 0.0


def test_seeded_audit_content_is_reproducible_and_artifact_is_verifiable():
    pool = small_pool()
    kwargs = {
        "candidate_pool": pool,
        "source": {"source_kind": "test", "history_digest": "a" * 64},
        "null_config": NullModelConfig(
            master_seed=77,
            uniform_legal_replicates=10,
            random_from_pool_replicates=10,
        ),
        "code_commit": "b" * 40,
    }
    first = audit_candidate_portfolio(
        pool[:3],
        generated_at="2026-07-22T00:00:00+00:00",
        **kwargs,
    )
    second = audit_candidate_portfolio(
        pool[:3],
        generated_at="2026-07-22T00:01:00+00:00",
        **kwargs,
    )

    assert first.content_digest == second.content_digest
    assert first.artifact_digest != second.artifact_digest
    assert first.null_comparisons == second.null_comparisons
    assert verify_portfolio_audit_payload(first.as_dict())["valid"] is True


def test_audit_reports_score_retention_against_same_pool_score_topk():
    pool = small_pool()
    artifact = audit_candidate_portfolio(
        (pool[0], pool[-1]),
        candidate_pool=pool,
        null_config=NullModelConfig(uniform_legal_replicates=2, random_from_pool_replicates=2),
        generated_at="2026-07-22T00:00:00+00:00",
        code_commit="b" * 40,
    )
    score = artifact.metrics["score"]

    assert score["score_topk_mean"] == pytest.approx((pool[0].score + pool[1].score) / 2)
    assert score["mean_difference_vs_score_topk"] < 0.0
    assert score["retention_ratio_vs_score_topk"] < 1.0
    assert "mean_score_distribution" in artifact.null_comparisons["random_from_candidate_pool"]


def test_artifact_verifier_rejects_metric_tampering():
    pool = small_pool()
    artifact = audit_candidate_portfolio(
        pool[:2],
        candidate_pool=pool,
        null_config=NullModelConfig(uniform_legal_replicates=2, random_from_pool_replicates=2),
        generated_at="2026-07-22T00:00:00+00:00",
        code_commit="b" * 40,
    )
    tampered = deepcopy(artifact.as_dict())
    tampered["metrics"]["pairwise_overlap"]["mean"] = 0.0

    with pytest.raises(PortfolioAuditViolation, match="portfolio_audit_content_digest_mismatch"):
        verify_portfolio_audit_payload(tampered)

    tampered_config = deepcopy(artifact.as_dict())
    tampered_config["null_config"]["master_seed"] = 999
    with pytest.raises(PortfolioAuditViolation, match="portfolio_audit_null_config_digest_mismatch"):
        verify_portfolio_audit_payload(tampered_config)

    unexpected = deepcopy(artifact.as_dict())
    unexpected["promotion_hint"] = "production"
    with pytest.raises(PortfolioAuditViolation, match="portfolio_audit_artifact_fields_unexpected"):
        verify_portfolio_audit_payload(unexpected)

    malformed_nulls = deepcopy(artifact.as_dict())
    malformed_nulls["null_comparisons"] = []
    with pytest.raises(PortfolioAuditViolation, match="portfolio_audit_null_set_invalid"):
        verify_portfolio_audit_payload(malformed_nulls)

    changed_null_protocol = deepcopy(artifact.as_dict())
    changed_null_protocol["null_comparisons"]["uniform_legal_same_budget"]["protocol"] = "v2"
    with pytest.raises(PortfolioAuditViolation, match="portfolio_audit_null_protocol_invalid"):
        verify_portfolio_audit_payload(changed_null_protocol)

    mismatched_null_budget = deepcopy(artifact.as_dict())
    mismatched_null_budget["null_comparisons"]["random_from_candidate_pool"]["budget"] = 3
    with pytest.raises(PortfolioAuditViolation, match="portfolio_audit_null_budget_mismatch"):
        verify_portfolio_audit_payload(mismatched_null_budget)


def test_old_source_provenance_gaps_are_fail_closed_for_promotion():
    pool = small_pool()
    artifact = audit_candidate_portfolio(
        pool[:2],
        candidate_pool=pool,
        source={"source_kind": "legacy"},
        null_config=NullModelConfig(uniform_legal_replicates=2, random_from_pool_replicates=2),
        generated_at="2026-07-22T00:00:00+00:00",
        code_commit="b" * 40,
    )
    payload = artifact.as_dict()

    assert payload["status"] == "audited_with_provenance_gaps"
    assert payload["automatic_promotion_allowed"] is False
    assert set(payload["provenance_gaps"]) == {
        "history_digest",
        "score_config_digest",
        "scoring_contract",
        "ranking_contract",
        "source_code_commit",
    }


def test_core_coverage_denominators_use_full_legal_universe():
    metrics = calculate_portfolio_metrics(tuple(item.red_numbers for item in small_pool()))

    assert metrics["pair_coverage"]["legal_universe_count"] == comb(33, 2)
    assert metrics["triple_coverage"]["legal_universe_count"] == comb(33, 3)


def test_json_cli_writes_and_verifies_read_only_artifact(tmp_path, capsys):
    pool = small_pool()
    input_path = tmp_path / "portfolio.json"
    output_path = tmp_path / "audit.json"
    input_path.write_text(
        json.dumps(
            {
                "source": {"source_kind": "test_json"},
                "candidate_pool": [row.as_dict() for row in pool],
            }
        ),
        encoding="utf-8",
    )

    result = audit_cli_main(
        [
            "--input",
            str(input_path),
            "--budget",
            "2",
            "--pool-limit",
            "6",
            "--uniform-replicates",
            "2",
            "--pool-replicates",
            "2",
            "--output",
            str(output_path),
        ]
    )

    assert result == 0
    assert output_path.exists()
    assert load_and_verify_portfolio_audit_artifact(output_path)["valid"] is True
    capsys.readouterr()
