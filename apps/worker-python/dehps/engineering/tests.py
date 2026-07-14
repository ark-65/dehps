from __future__ import annotations

from dehps.engineering.contracts import EngineeringTestPlan, TestKind, TestPlanItem
from dehps.research_planning.models import ExperimentPlan


class EngineeringTestPlanner:
    def build(self, plan: ExperimentPlan, *, mechanism: str) -> EngineeringTestPlan:
        slug = mechanism or plan.mechanism
        return EngineeringTestPlan(
            plan_key=plan.plan_key,
            items=(
                TestPlanItem(
                    kind=TestKind.UNIT,
                    path=f"apps/worker-python/tests/test_{slug}_implementation_contract.py",
                    purpose="verify deterministic helper interfaces and payload normalization",
                    assertions=(
                        "contract can be built from the frozen ExperimentPlan",
                        "required artifact and metric fields are preserved",
                        "forbidden runtime fields are absent",
                    ),
                    covers=("implementation_contract", "artifact_contract"),
                ),
                TestPlanItem(
                    kind=TestKind.INTEGRATION,
                    path=f"apps/worker-python/tests/test_{slug}_engineering_integration.py",
                    purpose="verify existing experiment package, baselines, rankers, and metrics compose",
                    assertions=(
                        "existing ranker/feature/baseline/metric modules are located",
                        "the implementation can run against tiny synthetic or fixed fixture input",
                        "no Evidence or Registry write occurs during implementation validation",
                    ),
                    covers=("repository_locator", "expected_tool_interface"),
                ),
                TestPlanItem(
                    kind=TestKind.REGRESSION,
                    path=f"apps/worker-python/tests/test_{slug}_no_production_regression.py",
                    purpose="guard production training, Objective, Promotion, and Registry boundaries",
                    assertions=(
                        "production training modules are not touched",
                        "Objective Policy and Promotion Gate are not modified",
                        "Registry and Evidence writers are not called",
                    ),
                    covers=("non_goals", "forbidden_paths"),
                ),
                TestPlanItem(
                    kind=TestKind.SMOKE,
                    path=f"apps/worker-python/tests/test_{slug}_engineering_smoke.py",
                    purpose="verify a dry engineering plan can be produced without repository mutation",
                    assertions=(
                        "engineering plan command exits successfully",
                        "git status is unchanged by contract generation",
                        "no experiment execution artifact is created",
                    ),
                    covers=("engineering_service", "cli"),
                ),
            ),
            commands=(
                "apps/worker-python/.venv/bin/python -m pytest -q "
                f"apps/worker-python/tests/test_{slug}_implementation_contract.py",
                "apps/worker-python/.venv/bin/python -m pytest -q",
            ),
        )
