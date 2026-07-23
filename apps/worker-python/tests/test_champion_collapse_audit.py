from __future__ import annotations

import numpy as np
import pytest

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.champion_collapse_audit import (
    ChampionCollapseAuditError,
    persisted_boundary_summary,
    topk_sequence_digest,
    validate_candidate_state,
)


def _candidate(
    config_hash: str,
    *,
    family: str,
    objective: float,
    frozen: float,
    median: float,
    worst: int,
    hits: tuple[int, int, int] = (3, 3, 4),
) -> dict:
    return {
        "config_hash": config_hash,
        "config": FrequencyRankerConfig().__dict__,
        "candidate_source": {"key": family},
        "source_key": family,
        "top_100_hits": hits[0],
        "top_1000_hits": hits[1],
        "top_10000_hits": hits[2],
        "median_rank": median,
        "worst_rank": worst,
        "reward": {"objectiveScore": objective},
        "frozen_validation": {"reward": {"objectiveScore": frozen}},
    }


def _source(candidates: list[dict]) -> dict:
    return {
        "round_summary": {
            "round_count": 143,
            "last_improved_round": 58,
            "stagnation_rounds": 85,
        },
        "research_learning": {
            "champion": {
                "config_hash": candidates[0]["config_hash"],
                "round": 58,
            }
        },
        "research_candidate_state": {
            "candidate_count": len(candidates),
            "candidates": candidates,
            "evaluated_config_hashes": [
                candidate["config_hash"] for candidate in candidates
            ],
        },
    }


def test_candidate_state_requires_complete_unique_hashes_and_champion_first() -> None:
    candidates = [
        _candidate(
            "a" * 64,
            family="normal",
            objective=10,
            frozen=-3,
            median=100,
            worst=1000,
        ),
        _candidate(
            "b" * 64,
            family="restart",
            objective=9,
            frozen=-1,
            median=90,
            worst=900,
        ),
    ]
    source = _source(candidates)

    assert len(validate_candidate_state(source)) == 2
    source["research_candidate_state"]["evaluated_config_hashes"][1] = "a" * 64
    with pytest.raises(ChampionCollapseAuditError, match="incomplete"):
        validate_candidate_state(source)


def test_persisted_boundary_separates_family_and_component_winners() -> None:
    candidates = [
        _candidate(
            "a" * 64,
            family="normal",
            objective=10.0,
            frozen=-3,
            median=100,
            worst=1000,
        ),
        _candidate(
            "b" * 64,
            family="normal",
            objective=9.9,
            frozen=-1,
            median=90,
            worst=900,
        ),
        _candidate(
            "c" * 64,
            family="restart",
            objective=4.0,
            frozen=2,
            median=80,
            worst=1100,
            hits=(1, 2, 3),
        ),
    ]
    summary = persisted_boundary_summary(_source(candidates), candidates)

    assert summary["persisted_champion"]["config_hash"] == "a" * 64
    assert summary["runner_up"]["primary_signature_tied"] is True
    assert summary["objective_boundary"][
        "champion_minus_runner_up_objective_score"
    ] == pytest.approx(0.1)
    assert summary["objective_boundary"]["distinct_selector_winner_count"] == 3
    assert summary["source_families"]["overall_counts"] == {
        "normal": 2,
        "restart": 1,
    }
    assert summary["primary_signatures"]["unique_count"] == 2


def test_topk_sequence_digest_is_order_sensitive_and_deterministic() -> None:
    first = np.array([4, 3, 2, 1, 0], dtype=np.int64)
    second = np.array([3, 4, 2, 1, 0], dtype=np.int64)

    assert topk_sequence_digest(first, 3) == topk_sequence_digest(first.copy(), 3)
    assert topk_sequence_digest(first, 3) != topk_sequence_digest(second, 3)
