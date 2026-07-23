from __future__ import annotations

import pytest

from dehps.training.frozen_plateau import (
    compact_frozen_plateau_round_state,
    evaluate_frozen_plateau_round,
    initial_frozen_plateau_state,
    validate_frozen_plateau_patience,
)
from dehps.training.runtime import frozen_validation_promotion_gate


def frozen_summary(
    config_hash: str,
    *,
    primary: tuple[int, int, int] = (0, 0, 0),
    objective: float = -10.0,
    worst_rank: int = 1_000_000,
    p95_rank: float = 900_000.0,
    tail_risk: float = 20.0,
    tail_counts: tuple[int, int, int] = (3, 2, 1),
) -> dict:
    return {
        "config_hash": config_hash,
        "frozen_validation": {
            "top_100_hits": primary[0],
            "top_1000_hits": primary[1],
            "top_10000_hits": primary[2],
            "median_rank": 500_000.0,
            "worst_rank": worst_rank,
            "reward": {"objectiveScore": objective},
            "rank_quality": {
                "p95_rank": p95_rank,
                "tail_risk_penalty": tail_risk,
                "tail_over_750000_count": tail_counts[0],
                "tail_over_900000_count": tail_counts[1],
                "tail_over_1000000_count": tail_counts[2],
            },
        },
    }


def test_patience_must_be_positive_when_enabled() -> None:
    assert validate_frozen_plateau_patience(None) is None
    assert validate_frozen_plateau_patience(40) == 40
    with pytest.raises(ValueError, match="must be positive"):
        validate_frozen_plateau_patience(0)


def test_first_round_initializes_missing_baseline_without_counting_improvement() -> None:
    state = initial_frozen_plateau_state(patience_rounds=2, baseline=None)
    candidate = frozen_summary("baseline")

    updated, frontier = evaluate_frozen_plateau_round(
        state=state,
        frontier_summary=None,
        summaries=[candidate],
        round_index=1,
        raw_search_improved=True,
        frozen_gate=frozen_validation_promotion_gate,
    )

    assert frontier == candidate
    assert updated["initialized_round"] == 1
    assert updated["last_improved_round"] is None
    assert updated["stagnation_rounds"] == 0
    assert updated["selection_overfit"] is False
    assert updated["history"][-1]["event"] == "baseline_initialized"


def test_legacy_baseline_without_frozen_validation_is_not_a_frontier() -> None:
    state = initial_frozen_plateau_state(
        patience_rounds=2,
        baseline={"config_hash": "legacy"},
    )

    assert state["initialized"] is False
    assert state["frontier"] is None
    assert state["frontier_config_hash"] is None


def test_search_only_improvement_does_not_reset_frozen_plateau() -> None:
    baseline = frozen_summary("baseline")
    state = initial_frozen_plateau_state(
        patience_rounds=2,
        baseline=baseline,
    )
    replay = frozen_summary("search-challenger")

    first, frontier = evaluate_frozen_plateau_round(
        state=state,
        frontier_summary=baseline,
        summaries=[replay],
        round_index=1,
        raw_search_improved=True,
        frozen_gate=frozen_validation_promotion_gate,
    )
    second, frontier = evaluate_frozen_plateau_round(
        state=first,
        frontier_summary=frontier,
        summaries=[replay],
        round_index=2,
        raw_search_improved=False,
        frozen_gate=frozen_validation_promotion_gate,
    )

    assert first["selection_overfit"] is True
    assert first["selection_overfit_count"] == 1
    assert first["stagnation_rounds"] == 1
    assert second["stagnation_rounds"] == 2
    assert second["stop_requested"] is True
    assert second["stop_reason"] == "frozen_validation_plateau"
    assert second["last_search_improved_round"] == 1
    assert second["last_improved_round"] is None
    assert frontier == baseline


def test_any_strict_frozen_candidate_advances_frontier_and_resets_counter() -> None:
    baseline = frozen_summary("baseline")
    state = initial_frozen_plateau_state(
        patience_rounds=3,
        baseline=baseline,
    )
    state["stagnation_rounds"] = 2
    worse = frozen_summary("worse", objective=-11.0)
    better = frozen_summary(
        "better",
        primary=(0, 0, 1),
        objective=-9.0,
    )

    updated, frontier = evaluate_frozen_plateau_round(
        state=state,
        frontier_summary=baseline,
        summaries=[worse, better],
        round_index=3,
        raw_search_improved=False,
        frozen_gate=frozen_validation_promotion_gate,
    )

    assert frontier == better
    assert updated["frontier_config_hash"] == "better"
    assert updated["last_improved_round"] == 3
    assert updated["stagnation_rounds"] == 0
    assert updated["stop_requested"] is False
    assert updated["history"][-1]["event"] == "frontier_advanced"


def test_primary_and_objective_lift_cannot_hide_worse_tail() -> None:
    baseline = frozen_summary("baseline")
    state = initial_frozen_plateau_state(
        patience_rounds=1,
        baseline=baseline,
    )
    worse_tail = frozen_summary(
        "worse-tail",
        primary=(0, 0, 1),
        objective=-9.0,
        worst_rank=1_000_001,
    )

    updated, frontier = evaluate_frozen_plateau_round(
        state=state,
        frontier_summary=baseline,
        summaries=[worse_tail],
        round_index=1,
        raw_search_improved=False,
        frozen_gate=frozen_validation_promotion_gate,
    )

    assert frontier == baseline
    assert updated["stagnation_rounds"] == 1
    assert updated["stop_requested"] is True


def test_compact_round_state_keeps_only_the_latest_history_event() -> None:
    baseline = frozen_summary("baseline")
    state = initial_frozen_plateau_state(
        patience_rounds=2,
        baseline=baseline,
    )
    state["history"] = [{"round": 1}, {"round": 2}]

    compact = compact_frozen_plateau_round_state(state)

    assert "history" not in compact
    assert compact["latest_event"] == {"round": 2}
