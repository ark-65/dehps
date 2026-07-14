from dehps.engineering.change_plan import ChangePlanner
from dehps.engineering.locator import RepositoryLocator
from experiment_plan_fixtures import ranking_plan


def test_change_plan_includes_reuse_modify_add_and_forbidden_boundaries() -> None:
    plan = ranking_plan()
    located = RepositoryLocator().locate(plan)
    change_plan = ChangePlanner().build(plan, located)

    actions = {item.action.value for item in change_plan.items}
    assert {"reuse", "modify", "add"}.issubset(actions)
    assert change_plan.production_impact == "none"
    assert "apps/worker-python/dehps/evaluation/objective_policy.py" in change_plan.forbidden_paths
    assert not any("production_runtime.py" in item.path for item in change_plan.items)
