import itertools

import pytest

from dehps.agents.actions import AgentAction
from dehps.agents.permissions import ROLE_ACTION_PERMISSIONS, is_action_permitted
from dehps.agents.policy import AgentAuthorityPolicy, AuthorizationContext
from dehps.agents.requests import AgentRequestType, REQUEST_TYPE_SPECS
from dehps.agents.roles import AgentRole


def test_permission_matrix_covers_every_role_action_combination() -> None:
    assert set(ROLE_ACTION_PERMISSIONS) == set(AgentRole)
    for role, action in itertools.product(AgentRole, AgentAction):
        assert is_action_permitted(role, action) is (action in ROLE_ACTION_PERMISSIONS[role])


def test_no_role_can_promote_production_strategy() -> None:
    policy = AgentAuthorityPolicy()
    for role in AgentRole:
        decision = policy.authorize(
            AuthorizationContext(
                role=role,
                action=AgentAction.PROMOTE_PRODUCTION_STRATEGY,
                environment="production",
            )
        )
        assert decision.allowed is False
        assert decision.reason_code == "promotion_reserved_for_existing_gate"


@pytest.mark.parametrize(
    ("role", "action"),
    [
        (AgentRole.RESEARCH, AgentAction.MODIFY_CODE),
        (AgentRole.ENGINEERING, AgentAction.SUBMIT_HYPOTHESIS_DECISION),
        (AgentRole.REVIEWER, AgentAction.RUN_ISOLATED_EXPERIMENT),
        (AgentRole.OPERATOR, AgentAction.CREATE_HYPOTHESIS_PROPOSAL),
    ],
)
def test_hard_role_separation_is_denied(role, action) -> None:
    result = AgentAuthorityPolicy().authorize(
        AuthorizationContext(role=role, action=action, environment="isolated")
    )
    assert result.allowed is False


def test_research_to_engineering_handoff_requires_approved_execution() -> None:
    policy = AgentAuthorityPolicy()
    request_type = AgentRequestType.ENGINEERING_EXPERIMENT_TOOL.value

    create = policy.authorize(
        AuthorizationContext(
            role=AgentRole.RESEARCH,
            action=AgentAction.CREATE_ENGINEERING_REQUEST,
            request_type=request_type,
        )
    )
    early_execute = policy.authorize(
        AuthorizationContext(
            role=AgentRole.ENGINEERING,
            action=AgentAction.MODIFY_CODE,
            request_type=request_type,
            request_status="submitted",
        )
    )
    execute = policy.authorize(
        AuthorizationContext(
            role=AgentRole.ENGINEERING,
            action=AgentAction.MODIFY_CODE,
            request_type=request_type,
            request_status="approved",
        )
    )

    assert create.allowed is True
    assert early_execute.reason_code == "request_not_approved"
    assert execute.allowed is True


def test_shared_creation_and_execution_action_uses_approved_phase() -> None:
    policy = AgentAuthorityPolicy()
    request_type = AgentRequestType.RESEARCH_EXPERIMENT_PLAN.value

    draft = policy.authorize(
        AuthorizationContext(
            role=AgentRole.RESEARCH,
            action=AgentAction.CREATE_EXPERIMENT_PLAN,
            request_type=request_type,
            request_status="draft",
        )
    )
    approved = policy.authorize(
        AuthorizationContext(
            role=AgentRole.RESEARCH,
            action=AgentAction.CREATE_EXPERIMENT_PLAN,
            request_type=request_type,
            request_status="approved",
        )
    )

    assert draft.allowed is True
    assert approved.allowed is True


def test_production_is_stricter_than_isolated() -> None:
    policy = AgentAuthorityPolicy()
    context = dict(
        role=AgentRole.OPERATOR,
        action=AgentAction.RUN_ISOLATED_EXPERIMENT,
        request_type=AgentRequestType.OPERATOR_ISOLATED_RUN.value,
        request_status="approved",
    )
    assert policy.authorize(AuthorizationContext(environment="isolated", **context)).allowed is True
    production = policy.authorize(AuthorizationContext(environment="production", **context))
    assert production.allowed is False
    assert production.reason_code == "production_not_allowed"


def test_every_request_type_has_explicit_authority_contract() -> None:
    assert set(REQUEST_TYPE_SPECS) == set(AgentRequestType)
    for request_type, spec in REQUEST_TYPE_SPECS.items():
        assert spec.request_type == request_type
        assert spec.initiator_roles
        assert spec.reviewer_roles == {AgentRole.REVIEWER}
        assert spec.executor_roles
        assert spec.required_payload_fields
