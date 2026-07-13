from __future__ import annotations

import pytest

from dehps.search.budget import (
    DEFAULT_CANDIDATE_BUDGET_POLICY,
    ReservedCandidateBudget,
    allocate_candidate_budget,
)
from dehps.search.fields import CONTEXT_FIELDS, PHASE_SEARCH_FIELDS
from dehps.search.phases import SearchState, select_search_phase
from dehps.search.stagnation import rank_homogeneity_guardrail


@pytest.mark.parametrize(
    ("round_index", "expected"),
    [
        (0, ("large", 0.20, "early_broad")),
        (2, ("medium", 0.10, "early_broad")),
        (24, ("medium", 0.08, "mid_search")),
        (26, ("small", 0.04, "mid_search")),
        (72, ("small", 0.03, "late_refine")),
        (73, ("micro", 0.015, "late_refine")),
    ],
)
def test_select_search_phase_preserves_legacy_schedule(round_index: int, expected: tuple[str, float, str]) -> None:
    phase = select_search_phase(SearchState(round_index=round_index))

    assert (phase.name, phase.distance, phase.stage) == expected
    assert phase.fields == PHASE_SEARCH_FIELDS[phase.name]


def test_stagnation_forces_large_phase_without_changing_field_space() -> None:
    phase = select_search_phase(SearchState(round_index=90, stagnation_rounds=16))

    assert (phase.name, phase.distance, phase.stage) == ("large", 0.15, "stagnation_broad")
    assert phase.fields == CONTEXT_FIELDS


def test_allocate_candidate_budget_preserves_reserved_order_and_total() -> None:
    budget = allocate_candidate_budget(
        20,
        DEFAULT_CANDIDATE_BUDGET_POLICY,
        reserved=(
            ReservedCandidateBudget("weight_kdj", 0.22, 20),
            ReservedCandidateBudget("recency_canary", 0.12, 15),
        ),
    )

    assert budget.as_dict() == {
        "exploitation": 5,
        "exploration": 4,
        "replay": 2,
        "baseline": 1,
        "weight_kdj": 5,
        "recency_canary": 3,
    }
    assert budget.total == 20


def test_rank_homogeneity_policy_is_independent_of_supervisor_runtime() -> None:
    repeated = [{"prefilter": {"round_best_rank_signature_hash": "same"}} for _ in range(4)]

    result = rank_homogeneity_guardrail(repeated, stagnation_rounds=4)

    assert result["active"] is True
    assert result["trigger_mode"] == "exact_repeat"
    assert result["signatures"] == ["same"]
