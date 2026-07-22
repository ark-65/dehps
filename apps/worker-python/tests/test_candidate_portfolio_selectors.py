from __future__ import annotations

import numpy as np
import pytest

from dehps.portfolio import (
    PortfolioAuditViolation,
    PortfolioRequest,
    ScoredCandidate,
    compute_candidate_pool_digest,
    select_portfolio,
)
from dehps.scoring_kernel.topk_reducer import ordered_topk


def candidate(rank: int, numbers: tuple[int, ...], score: float) -> ScoredCandidate:
    return ScoredCandidate.build(source_rank=rank, red_numbers=numbers, score=score)


def candidate_pool() -> tuple[ScoredCandidate, ...]:
    rows = (
        ((1, 2, 3, 4, 5, 6), 1.00),
        ((1, 2, 3, 4, 5, 7), 0.99),
        ((1, 2, 3, 4, 6, 7), 0.99),
        ((1, 2, 3, 5, 6, 7), 0.97),
        ((8, 9, 10, 11, 12, 13), 0.80),
        ((14, 15, 16, 17, 18, 19), 0.79),
        ((20, 21, 22, 23, 24, 25), 0.78),
        ((26, 27, 28, 29, 30, 31), 0.77),
    )
    return tuple(
        candidate(rank, numbers, score)
        for rank, (numbers, score) in enumerate(rows, 1)
    )


def request(
    selector_key: str,
    config: dict[str, object],
    *,
    seed: int | None = None,
    replicate_id: int = 0,
    budget: int = 4,
) -> PortfolioRequest:
    pool = candidate_pool()
    return PortfolioRequest.build(
        candidates=pool,
        budget=budget,
        selector_key=selector_key,
        selector_config=config,
        candidate_pool_digest=compute_candidate_pool_digest(pool),
        history_digest="a" * 64,
        score_config_digest="b" * 64,
        seed=seed,
        context={
            "line_key": "test_line",
            "as_of_issue": "2026083",
            "target_issue": "2026084",
            "replicate_id": replicate_id,
        },
    )


def greedy_config() -> dict[str, float]:
    return {"alpha": 0.01, "lambda": 10.0, "nu": 2.0, "mu2": 2.0, "mu3": 2.0}


def cluster_config() -> dict[str, object]:
    return {
        "cluster_count": 4,
        "medoid_initialization": "score_first_farthest",
        "quota_mode": "equal",
        "within_cluster_rule": "score_topk",
        "redistribution_rule": "largest_deficit_then_cluster_id",
        "max_iterations": 10,
    }


def test_portfolio_request_is_immutable_and_fails_closed_on_leakage_and_pool_digest():
    built = request("score_topk", {})
    with pytest.raises(TypeError):
        built.selector_config["unexpected"] = True

    pool = candidate_pool()
    kwargs = {
        "candidates": pool,
        "budget": 4,
        "selector_key": "score_topk",
        "selector_config": {},
        "candidate_pool_digest": compute_candidate_pool_digest(pool),
        "history_digest": "a" * 64,
        "score_config_digest": "b" * 64,
        "seed": None,
    }
    with pytest.raises(PortfolioAuditViolation, match="portfolio_selector_history_cutoff_leakage"):
        PortfolioRequest.build(
            **kwargs,
            context={
                "line_key": "test",
                "as_of_issue": "2026084",
                "target_issue": "2026084",
                "replicate_id": 0,
            },
        )
    with pytest.raises(PortfolioAuditViolation, match="portfolio_selector_pool_digest_mismatch"):
        PortfolioRequest.build(
            **{**kwargs, "candidate_pool_digest": "c" * 64},
            context={
                "line_key": "test",
                "as_of_issue": "2026083",
                "target_issue": "2026084",
                "replicate_id": 0,
            },
        )


def test_score_topk_has_exact_strict_v1_production_reducer_parity():
    pool = candidate_pool()
    selection = select_portfolio(request("score_topk", {}))
    expected_ids, expected_scores = ordered_topk(
        np.asarray([row.lex_id for row in pool], dtype=np.int64),
        np.asarray([row.score for row in pool], dtype=np.float64),
        4,
    )

    assert selection.selection_order_lex_ids == tuple(expected_ids.tolist())
    assert [row.score for row in selection.selected] == expected_scores.tolist()
    assert selection.audit_metrics["score"]["retention_ratio_vs_score_topk"] == 1.0
    assert selection.provenance["selector_protocol"] == "candidate_portfolio_selector.v1"
    assert len(selection.provenance["selector_code_commit"]) == 40
    assert selection.evidence_level == "RESEARCH_ONLY"
    assert selection.automatic_promotion_allowed is False


def test_random_from_top_pool_is_seeded_reproducible_and_context_separated():
    config = {"sampling_contract": "uniform_without_replacement"}
    first = select_portfolio(request("random_from_top_pool", config, seed=77))
    repeated = select_portfolio(request("random_from_top_pool", config, seed=77))
    next_replicate = select_portfolio(
        request("random_from_top_pool", config, seed=77, replicate_id=1)
    )

    assert first.portfolio_digest == repeated.portfolio_digest
    assert first.provenance["derived_seed"] == repeated.provenance["derived_seed"]
    assert first.provenance["derived_seed"] != next_replicate.provenance["derived_seed"]
    assert len(first.selected) == len({row.lex_id for row in first.selected}) == 4
    with pytest.raises(PortfolioAuditViolation, match="portfolio_random_pool_seed_missing"):
        select_portfolio(request("random_from_top_pool", config))


def test_greedy_uses_explicit_utility_and_reduces_overlap_without_thresholds():
    baseline = select_portfolio(request("score_topk", {}))
    first = select_portfolio(request("greedy_score_diversity", greedy_config()))
    repeated = select_portfolio(request("greedy_score_diversity", greedy_config()))

    assert first.portfolio_digest == repeated.portfolio_digest
    assert first.selection_order_lex_ids == repeated.selection_order_lex_ids
    assert (
        first.audit_metrics["pairwise_overlap"]["mean"]
        < baseline.audit_metrics["pairwise_overlap"]["mean"]
    )
    assert first.provenance["utility_formula"] == "alpha*Q-lambda*R-nu*E+mu2*C2+mu3*C3"
    assert "overlap_threshold" not in first.provenance
    with pytest.raises(PortfolioAuditViolation, match="portfolio_greedy_config_fields_invalid"):
        select_portfolio(
            request(
                "greedy_score_diversity",
                {"alpha": 1.0, "lambda": 1.0},
            )
        )


def test_cluster_quota_is_deterministic_capacity_safe_and_records_redistribution():
    first = select_portfolio(request("cluster_quota", cluster_config(), budget=6))
    repeated = select_portfolio(request("cluster_quota", cluster_config(), budget=6))

    assert first.portfolio_digest == repeated.portfolio_digest
    assert first.selection_order_lex_ids == repeated.selection_order_lex_ids
    assert sum(first.provenance["quotas"]) == 6
    assert all(
        quota <= size
        for quota, size in zip(first.provenance["quotas"], first.provenance["cluster_sizes"])
    )
    assert len(first.provenance["medoid_lex_ids"]) == 4
    assert len(first.provenance["quota_redistributions"]) == 2
    assert first.provenance["algorithm"] == "deterministic_jaccard_k_medoids_quota_v1"
