import pytest

from dehps.agents.actions import AgentAction
from dehps.agents.errors import AgentAuthorizationError
from dehps.agents.policy import AgentAuthorityPolicy, AuthorizationContext
from dehps.agents.roles import AgentRole


@pytest.mark.parametrize(
    ("role", "action", "reason"),
    [
        (AgentRole.RESEARCH, AgentAction.MODIFY_CODE, "research_engineering_operation_forbidden"),
        (AgentRole.ENGINEERING, AgentAction.ADD_EVIDENCE_PROPOSAL, "engineering_research_decision_forbidden"),
        (AgentRole.REVIEWER, AgentAction.RUN_ISOLATED_EXPERIMENT, "reviewer_execution_forbidden"),
        (AgentRole.OPERATOR, AgentAction.CREATE_HYPOTHESIS_PROPOSAL, "operator_research_forbidden"),
    ],
)
def test_role_boundaries_have_specific_audit_codes(role, action, reason) -> None:
    decision = AgentAuthorityPolicy().authorize(AuthorizationContext(role=role, action=action))
    assert decision.allowed is False
    assert decision.reason_code == reason


def test_actor_cannot_declare_two_roles_in_one_authorization_context() -> None:
    with pytest.raises(ValueError):
        AgentRole("research,engineering")
