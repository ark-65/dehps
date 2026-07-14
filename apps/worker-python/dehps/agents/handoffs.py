from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dehps.agents.errors import AgentRequestValidationError
from dehps.agents.requests import AgentRequestType, RESEARCH_HANDOFF_FIELDS


ENGINEERING_RESULT_REQUIRED_FIELDS = frozenset(
    {
        "implementation_commit",
        "test_commands",
        "test_results",
        "artifact_paths",
        "interface_contract",
        "known_limitations",
    }
)
ENGINEERING_RESULT_ALLOWED_FIELDS = ENGINEERING_RESULT_REQUIRED_FIELDS | frozenset(
    {
        "implemented_plan_fingerprint",
        "interfaces",
        "artifact_contract",
        "production_impact",
    }
)
FORBIDDEN_ENGINEERING_CONCLUSIONS = frozenset(
    {
        "hypothesis accepted",
        "hypothesis rejected",
        "signal exists",
        "predictive lift proven",
    }
)


def validate_research_to_engineering_payload(payload: Mapping[str, Any]) -> None:
    missing = sorted(RESEARCH_HANDOFF_FIELDS.difference(payload))
    if missing:
        raise AgentRequestValidationError(
            "engineering_experiment_tool handoff is missing: " + ", ".join(missing)
        )
    if payload.get("production_impact") != "none":
        raise AgentRequestValidationError(
            "engineering_experiment_tool production_impact must be 'none'"
        )
    for object_field in (
        "input_boundary",
        "expected_tool_interface",
        "baseline_contract",
        "metric_contract",
        "failure_condition",
    ):
        if not isinstance(payload.get(object_field), dict):
            raise AgentRequestValidationError(f"{object_field} must be a JSON object")
    if not isinstance(payload.get("non_goals"), list):
        raise AgentRequestValidationError("non_goals must be a JSON array")


def validate_engineering_result(result: Mapping[str, Any]) -> None:
    fields = frozenset(result)
    missing = sorted(ENGINEERING_RESULT_REQUIRED_FIELDS.difference(fields))
    unexpected = sorted(fields.difference(ENGINEERING_RESULT_ALLOWED_FIELDS))
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unexpected:
            details.append("unexpected " + ", ".join(unexpected))
        raise AgentRequestValidationError(
            "engineering result must use the frozen handoff contract: " + "; ".join(details)
        )
    for list_field in ("test_commands", "artifact_paths", "known_limitations"):
        if not isinstance(result.get(list_field), list):
            raise AgentRequestValidationError(f"{list_field} must be a JSON array")
    for object_field in ("test_results", "interface_contract"):
        if not isinstance(result.get(object_field), dict):
            raise AgentRequestValidationError(f"{object_field} must be a JSON object")
    for optional_object_field in ("interfaces", "artifact_contract"):
        if optional_object_field in result and not isinstance(result.get(optional_object_field), dict):
            raise AgentRequestValidationError(f"{optional_object_field} must be a JSON object")
    if "production_impact" in result and result.get("production_impact") != "none":
        raise AgentRequestValidationError("engineering result production_impact must be 'none'")
    conclusion = _find_forbidden_conclusion(result)
    if conclusion:
        raise AgentRequestValidationError(
            f"Engineering Agent cannot return research conclusion: {conclusion}"
        )


def request_uses_engineering_result_contract(request_type: AgentRequestType) -> bool:
    return request_type in {
        AgentRequestType.ENGINEERING_IMPLEMENTATION,
        AgentRequestType.ENGINEERING_BUG_FIX,
        AgentRequestType.ENGINEERING_TEST_ADDITION,
        AgentRequestType.ENGINEERING_RUNTIME_FIX,
        AgentRequestType.ENGINEERING_EXPERIMENT_TOOL,
    }


def _find_forbidden_conclusion(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            found = _find_forbidden_conclusion(str(key)) or _find_forbidden_conclusion(nested)
            if found:
                return found
        return None
    if isinstance(value, list):
        for nested in value:
            found = _find_forbidden_conclusion(nested)
            if found:
                return found
        return None
    if isinstance(value, str):
        normalized = " ".join(value.lower().replace("_", " ").split())
        return next(
            (phrase for phrase in FORBIDDEN_ENGINEERING_CONCLUSIONS if phrase in normalized),
            None,
        )
    return None
