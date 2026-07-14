from __future__ import annotations

from dataclasses import dataclass

from dehps.research_runtime.models import ResearchRuntimeBudget, ResearchRuntimeStatus


@dataclass(frozen=True)
class RuntimeBudgetDecision:
    allowed: bool
    status: ResearchRuntimeStatus
    reason_code: str
    budget: ResearchRuntimeBudget


class RuntimeBudgetScheduler:
    def __init__(self, budget: ResearchRuntimeBudget | None = None) -> None:
        self.budget = budget or ResearchRuntimeBudget()
        self.budget.validate()

    def authorize_research_cycle(self) -> RuntimeBudgetDecision:
        if self.budget.cycles_used >= self.budget.daily_cycle_limit:
            return RuntimeBudgetDecision(
                False,
                ResearchRuntimeStatus.RESEARCH_BUDGET_EXHAUSTED,
                "research_cycle_budget_exhausted",
                self.budget,
            )
        if self.budget.research_cpu < 1 or self.budget.research_memory_gb < 1:
            return RuntimeBudgetDecision(
                False,
                ResearchRuntimeStatus.RESEARCH_WAITING_RESOURCES,
                "research_resources_unavailable",
                self.budget,
            )
        return RuntimeBudgetDecision(
            True,
            ResearchRuntimeStatus.RESEARCH_RUNNING,
            "research_budget_available",
            self.budget,
        )
