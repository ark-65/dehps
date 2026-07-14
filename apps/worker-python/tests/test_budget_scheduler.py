import pytest

from dehps.research_runtime.budget import RuntimeBudgetScheduler
from dehps.research_runtime.models import ResearchRuntimeBudget, ResearchRuntimeStatus


def test_research_budget_allows_configured_research_slice() -> None:
    decision = RuntimeBudgetScheduler(
        ResearchRuntimeBudget(research_cpu=12, forward_cpu=4, total_memory_gb=20, research_memory_gb=18, forward_memory_gb=2)
    ).authorize_research_cycle()

    assert decision.allowed is True
    assert decision.status == ResearchRuntimeStatus.RESEARCH_RUNNING


def test_research_budget_exhaustion_is_independent_status() -> None:
    decision = RuntimeBudgetScheduler(
        ResearchRuntimeBudget(daily_cycle_limit=3, cycles_used=3)
    ).authorize_research_cycle()

    assert decision.allowed is False
    assert decision.status == ResearchRuntimeStatus.RESEARCH_BUDGET_EXHAUSTED


def test_budget_rejects_memory_overcommit() -> None:
    with pytest.raises(ValueError):
        RuntimeBudgetScheduler(
            ResearchRuntimeBudget(total_memory_gb=20, research_memory_gb=19, forward_memory_gb=2)
        )
