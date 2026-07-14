import json
from dataclasses import asdict

from experiment_plan_fixtures import ranking_plan


def test_experiment_plan_is_serializable_and_fingerprint_self_consistent() -> None:
    plan = ranking_plan()
    payload = json.loads(plan.canonical_json())

    assert payload["plan_key"] == plan.plan_key
    assert payload["plan_fingerprint"] == plan.plan_fingerprint
    assert plan.recomputed_fingerprint == plan.plan_fingerprint
    assert json.dumps(asdict(plan), sort_keys=True, default=str)


def test_plan_contains_no_runtime_result_values() -> None:
    plan = ranking_plan()
    text = plan.canonical_json().lower()

    assert "evidence_created" not in text
    assert "actual_red_numbers" not in text
    assert "hit_result" not in text
    assert "completed_at" not in text
