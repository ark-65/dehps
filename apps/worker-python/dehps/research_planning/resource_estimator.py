from __future__ import annotations

from dehps.research_planning.models import ResourceBudget


DEFAULT_STAGE_BUDGETS = {
    "feasibility": 10_000,
    "historical_search": 100_000,
    "frozen_validation": 100_000,
    "forward_validation": 100_000,
    "decision_review": 0,
}


class ResourceEstimator:
    def estimate(self) -> ResourceBudget:
        return ResourceBudget(
            cpu_hours=4.0,
            memory_gb=8.0,
            timeout_seconds=7_200,
            storage_mb=512,
            candidate_budget_per_stage=dict(DEFAULT_STAGE_BUDGETS),
            baseline_budget_per_stage=dict(DEFAULT_STAGE_BUDGETS),
            production_access=False,
        )
