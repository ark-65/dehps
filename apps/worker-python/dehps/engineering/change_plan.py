from __future__ import annotations

from dehps.engineering.contracts import (
    ChangeAction,
    ChangePlanItem,
    EngineeringChangePlan,
    LocatedComponent,
)
from dehps.research_planning.models import ExperimentPlan


FORBIDDEN_PATHS = (
    "apps/worker-python/dehps/training/production_runtime.py",
    "apps/worker-python/dehps/training/supervisor.py",
    "apps/worker-python/dehps/evaluation/objective_policy.py",
    "apps/worker-python/dehps/evaluation/promotion.py",
    "apps/worker-python/dehps/research/",
    "apps/worker-python/dehps/research_evidence/",
    "infra/",
    "data/output/",
    "runtime/",
)


class ChangePlanner:
    def build(
        self,
        plan: ExperimentPlan,
        located: tuple[LocatedComponent, ...],
    ) -> EngineeringChangePlan:
        items: list[ChangePlanItem] = []
        for component in located:
            if component.kind == "test":
                continue
            if component.exists:
                action = ChangeAction.REUSE if component.kind in {"ranker", "feature", "baseline", "metrics", "statistics"} else ChangeAction.MODIFY
                purpose = (
                    "reuse existing implementation without copying logic"
                    if action == ChangeAction.REUSE
                    else "extend existing isolated experiment implementation to satisfy the approved plan"
                )
            else:
                action = ChangeAction.ADD
                purpose = "add missing isolated experiment implementation surface"
            items.append(
                ChangePlanItem(
                    action=action,
                    path=component.path,
                    purpose=purpose,
                    risk=self._risk(component),
                    dependencies=self._dependencies(component, located),
                    compatibility_requirements=(
                        "preserve existing public interfaces",
                        "do not change production training behavior",
                        "do not change Objective Policy or Promotion Gate",
                        "do not write Evidence or Registry decisions",
                    ),
                )
            )
        if not any(item.action == ChangeAction.ADD for item in items):
            items.append(
                ChangePlanItem(
                    action=ChangeAction.ADD,
                    path=f"apps/worker-python/tests/test_{plan.mechanism}_engineering_contract.py",
                    purpose="add focused contract coverage for the generated implementation plan",
                    risk="low",
                    dependencies=tuple(sorted({item.path for item in items if item.action != ChangeAction.ADD})[:8]),
                    compatibility_requirements=("test-only addition", "no runtime behavior change"),
                )
            )
        return EngineeringChangePlan(
            plan_key=plan.plan_key,
            items=tuple(items),
            forbidden_paths=FORBIDDEN_PATHS,
            production_impact="none",
        )

    @staticmethod
    def _risk(component: LocatedComponent) -> str:
        if component.kind in {"ranker", "feature", "baseline", "metrics", "statistics"}:
            return "low"
        if component.kind in {"executor", "experiment_cli"}:
            return "medium"
        return "low" if component.exists else "medium"

    @staticmethod
    def _dependencies(
        component: LocatedComponent,
        located: tuple[LocatedComponent, ...],
    ) -> tuple[str, ...]:
        if component.kind in {"executor", "experiment_cli", "artifact_writer"}:
            return tuple(
                item.path
                for item in located
                if item.kind in {"ranker", "feature", "baseline", "metrics", "statistics"}
            )
        return ()
