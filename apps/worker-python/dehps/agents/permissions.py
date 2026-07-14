from __future__ import annotations

from dehps.agents.actions import AgentAction
from dehps.agents.roles import AgentRole


ROLE_ACTION_PERMISSIONS: dict[AgentRole, frozenset[AgentAction]] = {
    AgentRole.RESEARCH: frozenset(
        {
            AgentAction.READ_HYPOTHESIS,
            AgentAction.CREATE_HYPOTHESIS_PROPOSAL,
            AgentAction.CREATE_EXPERIMENT_PLAN,
            AgentAction.SUBMIT_PREREGISTRATION,
            AgentAction.ADD_EVIDENCE_PROPOSAL,
            AgentAction.SUBMIT_HYPOTHESIS_DECISION,
            AgentAction.SCHEDULE_RESEARCH,
            AgentAction.CREATE_ENGINEERING_REQUEST,
            AgentAction.CANCEL_REQUEST,
        }
    ),
    AgentRole.ENGINEERING: frozenset(
        {
            AgentAction.READ_HYPOTHESIS,
            AgentAction.CREATE_ENGINEERING_REQUEST,
            AgentAction.MODIFY_CODE,
            AgentAction.RUN_TESTS,
            AgentAction.CREATE_PULL_REQUEST,
            AgentAction.CANCEL_REQUEST,
        }
    ),
    AgentRole.REVIEWER: frozenset(
        {
            AgentAction.READ_HYPOTHESIS,
            AgentAction.REVIEW_REQUEST,
            AgentAction.APPROVE_REQUEST,
            AgentAction.REJECT_REQUEST,
        }
    ),
    AgentRole.OPERATOR: frozenset(
        {
            AgentAction.READ_HYPOTHESIS,
            AgentAction.RUN_ISOLATED_EXPERIMENT,
            AgentAction.RESTART_PRODUCTION_SUPERVISOR,
            AgentAction.APPLY_DATABASE_MIGRATION,
            AgentAction.PUBLISH_RELEASE,
            AgentAction.CANCEL_REQUEST,
        }
    ),
}


def is_action_permitted(role: AgentRole, action: AgentAction) -> bool:
    return action in ROLE_ACTION_PERMISSIONS.get(role, frozenset())
