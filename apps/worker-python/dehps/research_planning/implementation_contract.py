from __future__ import annotations

from dataclasses import asdict
from typing import Any

from dehps.research_planning.models import ExperimentPlan


EXPERIMENT_KEY_BY_STAGE = {
    "feasibility": "ranking_disagreement_feasibility_v1",
    "historical_search": "ranking_disagreement_historical_search_v1",
    "frozen_validation": "ranking_disagreement_frozen_validation_v1",
    "forward_validation": "ranking_disagreement_forward_validation_v1",
}


def engineering_request_key(plan: ExperimentPlan) -> str:
    return f"engineering-experiment-tool-{plan.plan_fingerprint[:16]}"


def engineering_payload(plan: ExperimentPlan, *, experiment_key: str) -> dict[str, Any]:
    return {
        "hypothesis_key": plan.hypothesis_key,
        "experiment_key": experiment_key,
        "experiment_plan_key": plan.plan_key,
        "mechanism": plan.mechanism,
        "scientific_question": plan.scientific_question,
        "input_boundary": plan.input_boundary,
        "expected_tool_interface": {
            "implementation_steps": [asdict(step) for step in plan.implementation_steps],
            "experiment_stages": [asdict(stage) for stage in plan.experiment_stages],
        },
        "required_interfaces": {
            "ranker_snapshot": "ranker_snapshots.json",
            "disagreement_features": "disagreement_features.json",
            "matched_baselines": "matched_baselines.json",
            "stage_metrics": "metrics_by_stage.json",
        },
        "feature_contract": plan.feature_contract,
        "ranker_contract": plan.model_contract,
        "baseline_contract": plan.baseline_contract,
        "metric_contract": plan.metric_contract,
        "artifact_contract": asdict(plan.artifact_contract),
        "test_contract": {
            "must_test": [
                "no target result input",
                "fixed ranker list and config hashes",
                "budget matched baselines",
                "complete output for every stratum",
                "no Evidence writes",
            ],
            "exit_on_failure": True,
        },
        "failure_condition": plan.failure_condition,
        "non_goals": [
            "do not modify production ranking algorithms",
            "do not run the experiment",
            "do not write Evidence",
            "do not change Objective Policy or Promotion Gate",
            "do not restart Supervisor",
        ],
        "production_impact": "none",
    }
