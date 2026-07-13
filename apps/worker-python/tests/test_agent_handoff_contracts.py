import pytest

from dehps.agents.errors import AgentRequestValidationError
from dehps.agents.handoffs import (
    validate_engineering_result,
    validate_research_to_engineering_payload,
)


def handoff() -> dict:
    return {
        "hypothesis_key": "hypothesis-1", "experiment_key": "experiment-1",
        "scientific_question": "Can the tool measure the preregistered metric?",
        "input_boundary": {}, "expected_tool_interface": {}, "baseline_contract": {},
        "metric_contract": {}, "failure_condition": {}, "non_goals": [],
        "production_impact": "none",
    }


def implementation_result() -> dict:
    return {
        "implementation_commit": "abc123", "test_commands": ["pytest -q"],
        "test_results": {"passed": 3}, "artifact_paths": [], "interface_contract": {},
        "known_limitations": [],
    }


def test_research_to_engineering_contract_is_structured_and_nonproduction() -> None:
    validate_research_to_engineering_payload(handoff())
    invalid = {**handoff(), "production_impact": "restart"}
    with pytest.raises(AgentRequestValidationError, match="must be 'none'"):
        validate_research_to_engineering_payload(invalid)


def test_engineering_result_cannot_claim_research_conclusions_or_add_fields() -> None:
    validate_engineering_result(implementation_result())
    invalid = {**implementation_result(), "conclusion": "predictive lift proven"}
    with pytest.raises(AgentRequestValidationError, match="frozen handoff contract"):
        validate_engineering_result(invalid)
    conclusion = {**implementation_result(), "known_limitations": ["hypothesis accepted"]}
    with pytest.raises(AgentRequestValidationError, match="cannot return research conclusion"):
        validate_engineering_result(conclusion)
