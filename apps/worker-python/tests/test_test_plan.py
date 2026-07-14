from dehps.engineering.contracts import TestKind as EngineeringTestKind
from dehps.engineering.tests import EngineeringTestPlanner
from experiment_plan_fixtures import ranking_plan


def test_test_planner_generates_unit_integration_regression_and_smoke() -> None:
    plan = ranking_plan()
    test_plan = EngineeringTestPlanner().build(plan, mechanism=plan.mechanism)

    assert {item.kind for item in test_plan.items} == {
        EngineeringTestKind.UNIT,
        EngineeringTestKind.INTEGRATION,
        EngineeringTestKind.REGRESSION,
        EngineeringTestKind.SMOKE,
    }
    assert any("pytest" in command for command in test_plan.commands)
    assert all(item.assertions for item in test_plan.items)
