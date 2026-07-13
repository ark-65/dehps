from dehps.agents.actions import AgentAction
from dehps.agents.policy import AgentAuthorityPolicy, AuthorizationContext
from dehps.agents.requests import AgentRequestType
from dehps.agents.roles import AgentRole


def test_execution_is_reauthorized_against_status_and_executor_role() -> None:
    policy = AgentAuthorityPolicy()
    base = dict(
        action=AgentAction.MODIFY_CODE,
        request_type=AgentRequestType.ENGINEERING_EXPERIMENT_TOOL.value,
        environment="development",
        risk_level="medium",
    )
    assert not policy.authorize(AuthorizationContext(role=AgentRole.ENGINEERING, request_status="submitted", **base)).allowed
    assert not policy.authorize(AuthorizationContext(role=AgentRole.RESEARCH, request_status="approved", **base)).allowed
    assert policy.authorize(AuthorizationContext(role=AgentRole.ENGINEERING, request_status="approved", **base)).allowed


def test_operator_execution_requires_operator_request_and_nonproduction_contract() -> None:
    policy = AgentAuthorityPolicy()
    isolated = AuthorizationContext(
        role=AgentRole.OPERATOR,
        action=AgentAction.RUN_ISOLATED_EXPERIMENT,
        request_type=AgentRequestType.OPERATOR_ISOLATED_RUN.value,
        request_status="approved",
        environment="isolated",
        risk_level="high",
    )
    assert policy.authorize(isolated).allowed
    assert not policy.authorize(AuthorizationContext(**{**isolated.__dict__, "environment": "production"})).allowed
