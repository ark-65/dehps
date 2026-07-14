from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from dehps.research_scheduler.state import ResearchAction


@dataclass(frozen=True)
class SchedulerBudget:
    cpu_slots: int = 1
    memory_gb: int = 4
    gpu_slots: int = 0
    daily_experiment_limit: int = 1
    daily_experiments_used: int = 0
    forward_quota: int = 20
    forward_used: int = 0
    proposal_quota: int = 1
    proposal_used: int = 0

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason_code: str
    summary: str
    budget: SchedulerBudget


class BudgetManager:
    """Small deterministic budget guard; it never provisions resources."""

    def __init__(self, budget: SchedulerBudget | None = None) -> None:
        self.budget = budget or SchedulerBudget()

    def authorize(self, action: ResearchAction) -> BudgetDecision:
        if self.budget.cpu_slots < 1:
            return self._deny("cpu_exhausted", "no CPU slot is available")
        if self.budget.memory_gb < 1:
            return self._deny("memory_exhausted", "no memory budget is available")
        if action in {ResearchAction.CREATE_PROPOSAL_REQUEST, ResearchAction.SUBMIT_PATTERN_HYPOTHESIS}:
            if self.budget.proposal_used >= self.budget.proposal_quota:
                return self._deny("proposal_quota_exhausted", "daily proposal quota is exhausted")
        if action in {
            ResearchAction.CREATE_ENGINEERING_REQUEST,
            ResearchAction.CREATE_OPERATOR_REQUEST,
        }:
            if self.budget.daily_experiments_used >= self.budget.daily_experiment_limit:
                return self._deny("daily_experiment_quota_exhausted", "daily experiment quota is exhausted")
        if action == ResearchAction.CREATE_OPERATOR_REQUEST:
            if self.budget.forward_used >= self.budget.forward_quota:
                return self._deny("forward_quota_exhausted", "forward quota is exhausted")
        return BudgetDecision(True, "budget_available", "budget allows the action", self.budget)

    def stop_if_exhausted(self) -> BudgetDecision | None:
        for action in (
            ResearchAction.CREATE_PROPOSAL_REQUEST,
            ResearchAction.CREATE_ENGINEERING_REQUEST,
            ResearchAction.CREATE_OPERATOR_REQUEST,
        ):
            decision = self.authorize(action)
            if decision.allowed:
                return None
        return self._deny("all_action_budgets_exhausted", "no research-producing action has remaining budget")

    def _deny(self, code: str, summary: str) -> BudgetDecision:
        return BudgetDecision(False, code, summary, self.budget)
