from __future__ import annotations

from typing import Any

from dehps.research_planning.models import ExperimentPlan


def operator_request_key(plan: ExperimentPlan) -> str:
    return f"operator-isolated-run-{plan.plan_fingerprint[:16]}"


def operator_payload(
    plan: ExperimentPlan,
    *,
    experiment_key: str,
    engineering_request_key: str,
) -> dict[str, Any]:
    return {
        "experiment_key": experiment_key,
        "experiment_plan_key": plan.plan_key,
        "engineering_request_key": engineering_request_key,
        "approved_tool_request_key": "",
        "environment": "isolated",
        "database": "isolated",
        "output_directory": f"data/output/research-planning/{plan.plan_key}",
        "cpu_budget": {"hours": plan.resource_budget.cpu_hours},
        "memory_budget": {"gb": plan.resource_budget.memory_gb},
        "timeout": {"seconds": plan.resource_budget.timeout_seconds},
        "allowed_commands": [],
        "production_access": False,
        "run_contract": {
            "plan_key": plan.plan_key,
            "plan_fingerprint": plan.plan_fingerprint,
            "artifact_contract": plan.artifact_contract.schema_version,
            "evidence_writes_allowed": False,
            "production_access": False,
        },
    }
