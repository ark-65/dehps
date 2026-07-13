from __future__ import annotations

from dataclasses import dataclass

from dehps.agents.actions import AgentAction
from dehps.agents.decisions import AuthorizationDecision
from dehps.agents.permissions import is_action_permitted
from dehps.agents.requests import (
    AgentRequestStatus,
    AgentRequestType,
    AgentRiskLevel,
    REQUEST_TYPE_SPECS,
)
from dehps.agents.roles import AgentRole


VALID_ENVIRONMENTS = frozenset({"isolated", "development", "production"})
EXECUTION_STATUSES = frozenset({AgentRequestStatus.APPROVED.value, AgentRequestStatus.EXECUTING.value})
ENGINEERING_RESEARCH_ACTIONS = frozenset(
    {
        AgentAction.CREATE_HYPOTHESIS_PROPOSAL,
        AgentAction.CREATE_EXPERIMENT_PLAN,
        AgentAction.SUBMIT_PREREGISTRATION,
        AgentAction.ADD_EVIDENCE_PROPOSAL,
        AgentAction.SUBMIT_HYPOTHESIS_DECISION,
    }
)
RESEARCH_ENGINEERING_ACTIONS = frozenset(
    {
        AgentAction.MODIFY_CODE,
        AgentAction.RUN_TESTS,
        AgentAction.CREATE_PULL_REQUEST,
        AgentAction.RESTART_PRODUCTION_SUPERVISOR,
        AgentAction.APPLY_DATABASE_MIGRATION,
        AgentAction.PUBLISH_RELEASE,
    }
)
REVIEWER_EXECUTION_ACTIONS = frozenset(
    {
        AgentAction.MODIFY_CODE,
        AgentAction.RUN_TESTS,
        AgentAction.RUN_ISOLATED_EXPERIMENT,
        AgentAction.RESTART_PRODUCTION_SUPERVISOR,
        AgentAction.APPLY_DATABASE_MIGRATION,
        AgentAction.PUBLISH_RELEASE,
    }
)
OPERATOR_RESEARCH_ACTIONS = frozenset(
    {
        AgentAction.CREATE_HYPOTHESIS_PROPOSAL,
        AgentAction.CREATE_EXPERIMENT_PLAN,
        AgentAction.SUBMIT_PREREGISTRATION,
        AgentAction.ADD_EVIDENCE_PROPOSAL,
        AgentAction.SUBMIT_HYPOTHESIS_DECISION,
    }
)


@dataclass(frozen=True)
class AuthorizationContext:
    role: AgentRole
    action: AgentAction
    request_type: str | None = None
    request_status: str | None = None
    environment: str = "isolated"
    risk_level: str | None = None


class AgentAuthorityPolicy:
    def authorize(self, context: AuthorizationContext) -> AuthorizationDecision:
        if context.environment not in VALID_ENVIRONMENTS:
            return self._deny("invalid_environment", f"unknown environment: {context.environment}")
        if context.action == AgentAction.PROMOTE_PRODUCTION_STRATEGY:
            return self._deny(
                "promotion_reserved_for_existing_gate",
                "no Agent role can promote a production strategy; the existing Promotion Gate remains authoritative",
            )
        if context.role == AgentRole.RESEARCH and context.action in RESEARCH_ENGINEERING_ACTIONS:
            return self._deny(
                "research_engineering_operation_forbidden",
                "Research Agent cannot modify code, run engineering work, or perform operations",
            )
        if context.role == AgentRole.ENGINEERING and context.action in ENGINEERING_RESEARCH_ACTIONS:
            return self._deny(
                "engineering_research_decision_forbidden",
                "Engineering Agent cannot create or change research hypotheses, evidence, or conclusions",
            )
        if context.role == AgentRole.REVIEWER and context.action in REVIEWER_EXECUTION_ACTIONS:
            return self._deny("reviewer_execution_forbidden", "Reviewer cannot execute or modify work")
        if context.role == AgentRole.OPERATOR and context.action in OPERATOR_RESEARCH_ACTIONS:
            return self._deny("operator_research_forbidden", "Operator cannot define or conclude research")
        if not is_action_permitted(context.role, context.action):
            return self._deny(
                "role_action_denied",
                f"{context.role.value} is not permitted to perform {context.action.value}",
            )

        if context.action == AgentAction.READ_HYPOTHESIS and context.request_type is None:
            return self._allow("read_allowed", "role may read auditable research records")

        if context.request_type is None:
            return self._deny("request_context_required", "this action requires a typed Agent Request")
        try:
            request_type = AgentRequestType(context.request_type)
        except ValueError:
            return self._deny("unknown_request_type", f"unknown request type: {context.request_type}")
        spec = REQUEST_TYPE_SPECS[request_type]

        if context.risk_level is not None:
            try:
                risk = AgentRiskLevel(context.risk_level)
            except ValueError:
                return self._deny("invalid_risk_level", f"unknown risk level: {context.risk_level}")
            if risk == AgentRiskLevel.CRITICAL and context.action in {
                AgentAction.APPROVE_REQUEST,
                AgentAction.REJECT_REQUEST,
                AgentAction.REVIEW_REQUEST,
            } and context.role != AgentRole.REVIEWER:
                return self._deny("critical_reviewer_required", "critical requests require Reviewer authority")

        # Some research request types deliberately use the same domain action for
        # creation and execution.  Once a request is approved, treat that action
        # as execution so the executor role and approval gate are both enforced.
        if context.action == spec.execution_action and context.request_status in EXECUTION_STATUSES:
            if context.role not in spec.executor_roles:
                return self._deny("request_executor_denied", "role cannot execute this request type")
        elif context.action == spec.creation_action:
            if context.role not in spec.initiator_roles:
                return self._deny("request_initiator_denied", "role cannot initiate this request type")
        elif context.action in {
            AgentAction.REVIEW_REQUEST,
            AgentAction.APPROVE_REQUEST,
            AgentAction.REJECT_REQUEST,
        }:
            if context.role not in spec.reviewer_roles:
                return self._deny("request_reviewer_denied", "role cannot review this request type")
        elif context.action == AgentAction.CANCEL_REQUEST:
            if context.role not in spec.initiator_roles and context.role != AgentRole.OPERATOR:
                return self._deny("request_cancel_denied", "role cannot cancel this request")
        elif context.action == spec.execution_action:
            return self._deny("request_not_approved", "request must be approved before execution")
        else:
            return self._deny(
                "action_not_valid_for_request_type",
                f"{context.action.value} is not valid for {request_type.value}",
            )

        if context.action == AgentAction.MODIFY_CODE and not spec.allows_code_modification:
            return self._deny("request_forbids_code_change", "request type does not permit code changes")
        if context.environment == "production":
            if not spec.allows_production:
                return self._deny("production_not_allowed", "request type is restricted to non-production environments")
            if context.role != AgentRole.OPERATOR and context.action not in {
                AgentAction.REVIEW_REQUEST,
                AgentAction.APPROVE_REQUEST,
                AgentAction.REJECT_REQUEST,
                spec.creation_action,
            }:
                return self._deny("production_operator_required", "production execution requires Operator role")
            if context.action == AgentAction.CREATE_PULL_REQUEST:
                return self._deny("automatic_production_pr_forbidden", "Agents cannot create production PRs")

        return self._allow(
            "authorized",
            f"{context.role.value} may perform {context.action.value} for {request_type.value}",
        )

    @staticmethod
    def _allow(code: str, summary: str) -> AuthorizationDecision:
        return AuthorizationDecision(True, code, summary)

    @staticmethod
    def _deny(code: str, summary: str) -> AuthorizationDecision:
        return AuthorizationDecision(False, code, summary)
