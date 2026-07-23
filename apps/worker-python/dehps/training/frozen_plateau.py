from __future__ import annotations

from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import Any


FrozenGate = Callable[[dict, dict | None], dict]


def validate_frozen_plateau_patience(value: int | None) -> int | None:
    if value is None:
        return None
    patience = int(value)
    if patience < 1:
        raise ValueError("frozen plateau patience must be positive when provided")
    return patience


def frozen_frontier_sort_key(summary: dict) -> tuple:
    validation = (
        summary.get("frozen_validation")
        if isinstance(summary.get("frozen_validation"), dict)
        else {}
    )
    quality = (
        validation.get("rank_quality")
        if isinstance(validation.get("rank_quality"), dict)
        else {}
    )
    reward = (
        validation.get("reward")
        if isinstance(validation.get("reward"), dict)
        else {}
    )
    return (
        int(validation.get("top_100_hits") or 0),
        int(validation.get("top_1000_hits") or 0),
        int(validation.get("top_10000_hits") or 0),
        float(reward.get("objectiveScore") or 0.0),
        -int(quality.get("tail_over_1000000_count") or 0),
        -int(quality.get("tail_over_900000_count") or 0),
        -int(quality.get("tail_over_750000_count") or 0),
        -float(quality.get("p95_rank") or 0.0),
        -int(validation.get("worst_rank") or 0),
        -float(validation.get("median_rank") or 0.0),
        str(summary.get("config_hash") or ""),
    )


def frozen_frontier_snapshot(summary: dict | None) -> dict | None:
    if (
        not isinstance(summary, dict)
        or not isinstance(summary.get("frozen_validation"), dict)
        or not summary.get("config_hash")
    ):
        return None
    validation = summary["frozen_validation"]
    quality = (
        validation.get("rank_quality")
        if isinstance(validation.get("rank_quality"), dict)
        else {}
    )
    reward = (
        validation.get("reward")
        if isinstance(validation.get("reward"), dict)
        else {}
    )
    return {
        "config_hash": str(summary.get("config_hash") or ""),
        "primary_score": [
            int(validation.get("top_100_hits") or 0),
            int(validation.get("top_1000_hits") or 0),
            int(validation.get("top_10000_hits") or 0),
        ],
        "objective": float(reward.get("objectiveScore") or 0.0),
        "tail": {
            "worst_rank": int(validation.get("worst_rank") or 0),
            "p95_rank": quality.get("p95_rank"),
            "tail_risk": quality.get("tail_risk_penalty"),
            "tail_over_750000_count": int(
                quality.get("tail_over_750000_count") or 0
            ),
            "tail_over_900000_count": int(
                quality.get("tail_over_900000_count") or 0
            ),
            "tail_over_1000000_count": int(
                quality.get("tail_over_1000000_count") or 0
            ),
        },
    }


def initial_frozen_plateau_state(
    *,
    patience_rounds: int | None,
    baseline: dict | None,
) -> dict[str, Any]:
    patience = validate_frozen_plateau_patience(patience_rounds)
    frontier = frozen_frontier_snapshot(baseline)
    return {
        "protocol": "frozen-validation-plateau-v1",
        "enabled": patience is not None,
        "patience_rounds": patience,
        "stagnation_rounds": 0,
        "last_improved_round": None,
        "last_search_improved_round": None,
        "frontier_config_hash": (
            str(frontier.get("config_hash") or "") if frontier else None
        ),
        "frontier": frontier,
        "initialized": frontier is not None,
        "initialized_round": 0 if frontier is not None else None,
        "selection_overfit": False,
        "selection_overfit_count": 0,
        "stop_requested": False,
        "stop_reason": None,
        "stopped_at_round": None,
        "history": [],
    }


def compact_frozen_plateau_round_state(state: dict[str, Any]) -> dict[str, Any]:
    compact = {
        key: deepcopy(value)
        for key, value in state.items()
        if key != "history"
    }
    history = state.get("history")
    compact["latest_event"] = (
        deepcopy(history[-1])
        if isinstance(history, list) and history
        else None
    )
    return compact


def evaluate_frozen_plateau_round(
    *,
    state: dict[str, Any],
    frontier_summary: dict | None,
    summaries: Sequence[dict],
    round_index: int,
    raw_search_improved: bool,
    frozen_gate: FrozenGate,
) -> tuple[dict[str, Any], dict | None]:
    if round_index < 1:
        raise ValueError("frozen plateau round index must be positive")

    eligible = [
        summary
        for summary in summaries
        if isinstance(summary, dict)
        and isinstance(summary.get("frozen_validation"), dict)
        and bool(summary.get("config_hash"))
    ]
    updated = deepcopy(state)
    updated["last_search_improved_round"] = (
        round_index
        if raw_search_improved
        else updated.get("last_search_improved_round")
    )

    if not isinstance(frontier_summary, dict):
        baseline = max(eligible, key=frozen_frontier_sort_key) if eligible else None
        initialized = isinstance(baseline, dict)
        if initialized:
            updated["initialized"] = True
            updated["initialized_round"] = round_index
            updated["frontier"] = frozen_frontier_snapshot(baseline)
            updated["frontier_config_hash"] = str(
                baseline.get("config_hash") or ""
            )
        event = {
            "round": round_index,
            "event": (
                "baseline_initialized"
                if initialized
                else "baseline_initialization_missing"
            ),
            "eligible_candidate_count": len(eligible),
            "advancing_candidate_count": 0,
            "frozen_improved": False,
            "raw_search_improved": bool(raw_search_improved),
            "selection_overfit": False,
            "stagnation_rounds": 0,
            "frontier_config_hash": updated.get("frontier_config_hash"),
            "gate": None,
        }
        updated["history"] = [*list(updated.get("history") or ()), event]
        return updated, baseline

    passing: list[tuple[dict, dict]] = []
    for summary in eligible:
        gate = frozen_gate(summary, frontier_summary)
        if gate.get("passed") is True:
            passing.append((summary, gate))

    if passing:
        frontier_candidate, selected_gate = max(
            passing,
            key=lambda item: frozen_frontier_sort_key(item[0]),
        )
        updated["stagnation_rounds"] = 0
        updated["last_improved_round"] = round_index
        updated["frontier"] = frozen_frontier_snapshot(frontier_candidate)
        updated["frontier_config_hash"] = str(
            frontier_candidate.get("config_hash") or ""
        )
        updated["selection_overfit"] = False
        next_frontier = frontier_candidate
        event_name = "frontier_advanced"
    else:
        selected_gate = None
        updated["stagnation_rounds"] = int(
            updated.get("stagnation_rounds") or 0
        ) + 1
        updated["selection_overfit"] = bool(raw_search_improved)
        if updated["selection_overfit"]:
            updated["selection_overfit_count"] = int(
                updated.get("selection_overfit_count") or 0
            ) + 1
        next_frontier = frontier_summary
        event_name = (
            "selection_overfit"
            if updated["selection_overfit"]
            else "frozen_plateau"
        )

    patience = updated.get("patience_rounds")
    stop_requested = bool(
        updated.get("enabled")
        and isinstance(patience, int)
        and int(updated["stagnation_rounds"]) >= patience
    )
    updated["stop_requested"] = stop_requested
    updated["stop_reason"] = (
        "frozen_validation_plateau" if stop_requested else None
    )
    updated["stopped_at_round"] = round_index if stop_requested else None
    event = {
        "round": round_index,
        "event": event_name,
        "eligible_candidate_count": len(eligible),
        "advancing_candidate_count": len(passing),
        "frozen_improved": bool(passing),
        "raw_search_improved": bool(raw_search_improved),
        "selection_overfit": bool(updated["selection_overfit"]),
        "stagnation_rounds": int(updated["stagnation_rounds"]),
        "frontier_config_hash": updated.get("frontier_config_hash"),
        "gate": selected_gate,
    }
    updated["history"] = [*list(updated.get("history") or ()), event]
    return updated, next_frontier
