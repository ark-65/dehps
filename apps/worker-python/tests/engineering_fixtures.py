from __future__ import annotations

from dataclasses import asdict

from dehps.engineering.planner import EngineeringPlanner
from dehps.research_planning.models import ExperimentPlan
from experiment_plan_fixtures import ranking_plan


class PlanningRepository:
    def __init__(self, plan: ExperimentPlan | None = None) -> None:
        self.plan = plan or ranking_plan()

    def get_materialized_plan_payload(self, plan_key: str):
        return asdict(self.plan)

    def list_plans(self, *, limit: int = 100, offset: int = 0):
        return [{"plan": asdict(self.plan)}]


def planner(plan: ExperimentPlan | None = None) -> EngineeringPlanner:
    return EngineeringPlanner(planning_repository=PlanningRepository(plan))  # type: ignore[arg-type]
