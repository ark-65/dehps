from engineering_fixtures import planner


def test_contract_records_required_modules_tests_interfaces_and_non_goals() -> None:
    service = planner()
    plan = service.load_plan(None)
    contract = service.build_contract(plan)

    assert contract.plan_key == plan.plan_key
    assert contract.plan_fingerprint == plan.plan_fingerprint
    assert contract.contract_hash
    assert contract.modules_to_modify
    assert contract.files_to_add
    assert contract.tests_to_add
    assert contract.interfaces_to_add
    assert contract.production_impact == "none"
    assert contract.objective_policy_change_allowed is False
    assert contract.promotion_change_allowed is False
    assert contract.registry_update_allowed is False
    assert contract.experiment_execution_allowed is False
    assert contract.evidence_write_allowed is False
    assert "do not execute Experiment" in contract.non_goals
