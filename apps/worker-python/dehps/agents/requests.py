from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from dehps.agents.actions import AgentAction
from dehps.agents.roles import AgentRole


class AgentRequestStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALIDATED = "invalidated"


class AgentExecutionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentRequestType(str, Enum):
    RESEARCH_HYPOTHESIS_PROPOSAL = "research_hypothesis_proposal"
    RESEARCH_PREREGISTRATION = "research_preregistration"
    RESEARCH_EXPERIMENT_PLAN = "research_experiment_plan"
    RESEARCH_EVIDENCE_SUBMISSION = "research_evidence_submission"
    RESEARCH_DECISION_SUBMISSION = "research_decision_submission"
    ENGINEERING_IMPLEMENTATION = "engineering_implementation"
    ENGINEERING_BUG_FIX = "engineering_bug_fix"
    ENGINEERING_TEST_ADDITION = "engineering_test_addition"
    ENGINEERING_RUNTIME_FIX = "engineering_runtime_fix"
    ENGINEERING_EXPERIMENT_TOOL = "engineering_experiment_tool"
    OPERATOR_ISOLATED_RUN = "operator_isolated_run"
    OPERATOR_DATABASE_MIGRATION = "operator_database_migration"
    OPERATOR_SUPERVISOR_RESTART = "operator_supervisor_restart"
    OPERATOR_RELEASE = "operator_release"


@dataclass(frozen=True)
class AgentRequestTypeSpec:
    request_type: AgentRequestType
    initiator_roles: frozenset[AgentRole]
    reviewer_roles: frozenset[AgentRole]
    executor_roles: frozenset[AgentRole]
    creation_action: AgentAction
    execution_action: AgentAction
    risk_level: AgentRiskLevel
    requires_hypothesis: bool
    requires_experiment: bool
    required_payload_fields: frozenset[str]
    allows_production: bool
    allows_code_modification: bool
    allows_hypothesis_status_transition: bool


RESEARCH_HANDOFF_FIELDS = frozenset(
    {
        "hypothesis_key",
        "experiment_key",
        "scientific_question",
        "input_boundary",
        "expected_tool_interface",
        "baseline_contract",
        "metric_contract",
        "failure_condition",
        "non_goals",
        "production_impact",
    }
)


def _spec(
    request_type: AgentRequestType,
    *,
    initiators: set[AgentRole],
    executors: set[AgentRole],
    creation: AgentAction,
    execution: AgentAction,
    risk: AgentRiskLevel,
    fields: set[str],
    hypothesis: bool = False,
    experiment: bool = False,
    production: bool = False,
    code: bool = False,
    hypothesis_status: bool = False,
) -> AgentRequestTypeSpec:
    return AgentRequestTypeSpec(
        request_type=request_type,
        initiator_roles=frozenset(initiators),
        reviewer_roles=frozenset({AgentRole.REVIEWER}),
        executor_roles=frozenset(executors),
        creation_action=creation,
        execution_action=execution,
        risk_level=risk,
        requires_hypothesis=hypothesis,
        requires_experiment=experiment,
        required_payload_fields=frozenset(fields),
        allows_production=production,
        allows_code_modification=code,
        allows_hypothesis_status_transition=hypothesis_status,
    )


REQUEST_TYPE_SPECS: dict[AgentRequestType, AgentRequestTypeSpec] = {
    AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL: _spec(
        AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL,
        initiators={AgentRole.RESEARCH}, executors={AgentRole.RESEARCH},
        creation=AgentAction.CREATE_HYPOTHESIS_PROPOSAL,
        execution=AgentAction.CREATE_HYPOTHESIS_PROPOSAL,
        risk=AgentRiskLevel.LOW,
        fields={"hypothesis_key", "scientific_question", "null_hypothesis", "failure_condition"},
    ),
    AgentRequestType.RESEARCH_PREREGISTRATION: _spec(
        AgentRequestType.RESEARCH_PREREGISTRATION,
        initiators={AgentRole.RESEARCH}, executors={AgentRole.REVIEWER},
        creation=AgentAction.SUBMIT_PREREGISTRATION,
        execution=AgentAction.REVIEW_REQUEST,
        risk=AgentRiskLevel.MEDIUM,
        fields={"hypothesis_key", "preregistration_snapshot"}, hypothesis=True,
        hypothesis_status=True,
    ),
    AgentRequestType.RESEARCH_EXPERIMENT_PLAN: _spec(
        AgentRequestType.RESEARCH_EXPERIMENT_PLAN,
        initiators={AgentRole.RESEARCH}, executors={AgentRole.RESEARCH},
        creation=AgentAction.CREATE_EXPERIMENT_PLAN,
        execution=AgentAction.CREATE_EXPERIMENT_PLAN,
        risk=AgentRiskLevel.MEDIUM,
        fields={"hypothesis_key", "experiment_key", "protocol", "failure_condition"},
        hypothesis=True,
    ),
    AgentRequestType.RESEARCH_EVIDENCE_SUBMISSION: _spec(
        AgentRequestType.RESEARCH_EVIDENCE_SUBMISSION,
        initiators={AgentRole.RESEARCH}, executors={AgentRole.REVIEWER},
        creation=AgentAction.ADD_EVIDENCE_PROPOSAL,
        execution=AgentAction.REVIEW_REQUEST,
        risk=AgentRiskLevel.MEDIUM,
        fields={"hypothesis_key", "experiment_key", "evidence", "execution_request_key"},
        hypothesis=True, experiment=True,
    ),
    AgentRequestType.RESEARCH_DECISION_SUBMISSION: _spec(
        AgentRequestType.RESEARCH_DECISION_SUBMISSION,
        initiators={AgentRole.RESEARCH}, executors={AgentRole.REVIEWER},
        creation=AgentAction.SUBMIT_HYPOTHESIS_DECISION,
        execution=AgentAction.REVIEW_REQUEST,
        risk=AgentRiskLevel.HIGH,
        fields={"hypothesis_key", "proposed_status", "evidence_ids", "reason"},
        hypothesis=True, hypothesis_status=True,
    ),
    AgentRequestType.ENGINEERING_IMPLEMENTATION: _spec(
        AgentRequestType.ENGINEERING_IMPLEMENTATION,
        initiators={AgentRole.ENGINEERING}, executors={AgentRole.ENGINEERING},
        creation=AgentAction.CREATE_ENGINEERING_REQUEST, execution=AgentAction.MODIFY_CODE,
        risk=AgentRiskLevel.MEDIUM, fields={"scope", "acceptance", "non_goals"}, code=True,
    ),
    AgentRequestType.ENGINEERING_BUG_FIX: _spec(
        AgentRequestType.ENGINEERING_BUG_FIX,
        initiators={AgentRole.ENGINEERING}, executors={AgentRole.ENGINEERING},
        creation=AgentAction.CREATE_ENGINEERING_REQUEST, execution=AgentAction.MODIFY_CODE,
        risk=AgentRiskLevel.MEDIUM, fields={"reproducer", "expected_behavior", "scope"}, code=True,
    ),
    AgentRequestType.ENGINEERING_TEST_ADDITION: _spec(
        AgentRequestType.ENGINEERING_TEST_ADDITION,
        initiators={AgentRole.ENGINEERING}, executors={AgentRole.ENGINEERING},
        creation=AgentAction.CREATE_ENGINEERING_REQUEST, execution=AgentAction.RUN_TESTS,
        risk=AgentRiskLevel.LOW, fields={"test_scope", "expected_assertions"}, code=True,
    ),
    AgentRequestType.ENGINEERING_RUNTIME_FIX: _spec(
        AgentRequestType.ENGINEERING_RUNTIME_FIX,
        initiators={AgentRole.ENGINEERING}, executors={AgentRole.ENGINEERING},
        creation=AgentAction.CREATE_ENGINEERING_REQUEST, execution=AgentAction.MODIFY_CODE,
        risk=AgentRiskLevel.HIGH, fields={"incident", "reproducer", "rollback"}, code=True,
    ),
    AgentRequestType.ENGINEERING_EXPERIMENT_TOOL: _spec(
        AgentRequestType.ENGINEERING_EXPERIMENT_TOOL,
        initiators={AgentRole.RESEARCH}, executors={AgentRole.ENGINEERING},
        creation=AgentAction.CREATE_ENGINEERING_REQUEST, execution=AgentAction.MODIFY_CODE,
        risk=AgentRiskLevel.MEDIUM, fields=set(RESEARCH_HANDOFF_FIELDS),
        hypothesis=True, experiment=True, code=True,
    ),
    AgentRequestType.OPERATOR_ISOLATED_RUN: _spec(
        AgentRequestType.OPERATOR_ISOLATED_RUN,
        initiators={AgentRole.RESEARCH}, executors={AgentRole.OPERATOR},
        creation=AgentAction.CREATE_EXPERIMENT_PLAN,
        execution=AgentAction.RUN_ISOLATED_EXPERIMENT,
        risk=AgentRiskLevel.HIGH,
        fields={"experiment_key", "approved_tool_request_key", "environment", "run_contract"},
        hypothesis=True, experiment=True,
    ),
    AgentRequestType.OPERATOR_DATABASE_MIGRATION: _spec(
        AgentRequestType.OPERATOR_DATABASE_MIGRATION,
        initiators={AgentRole.ENGINEERING}, executors={AgentRole.OPERATOR},
        creation=AgentAction.CREATE_ENGINEERING_REQUEST,
        execution=AgentAction.APPLY_DATABASE_MIGRATION,
        risk=AgentRiskLevel.CRITICAL,
        fields={"migration", "target_database", "rollback", "verification"}, production=True,
    ),
    AgentRequestType.OPERATOR_SUPERVISOR_RESTART: _spec(
        AgentRequestType.OPERATOR_SUPERVISOR_RESTART,
        initiators={AgentRole.ENGINEERING}, executors={AgentRole.OPERATOR},
        creation=AgentAction.CREATE_ENGINEERING_REQUEST,
        execution=AgentAction.RESTART_PRODUCTION_SUPERVISOR,
        risk=AgentRiskLevel.CRITICAL,
        fields={"run_id", "reason", "arguments", "rollback"}, production=True,
    ),
    AgentRequestType.OPERATOR_RELEASE: _spec(
        AgentRequestType.OPERATOR_RELEASE,
        initiators={AgentRole.ENGINEERING, AgentRole.OPERATOR}, executors={AgentRole.OPERATOR},
        creation=AgentAction.CREATE_ENGINEERING_REQUEST,
        execution=AgentAction.PUBLISH_RELEASE,
        risk=AgentRiskLevel.CRITICAL,
        fields={"version", "commit", "checks", "rollback"}, production=True,
    ),
}


@dataclass(frozen=True)
class AgentRequest:
    id: int
    request_key: str
    request_type: AgentRequestType
    requested_by_role: AgentRole
    requested_by: str
    hypothesis_id: int | None
    experiment_id: int | None
    parent_request_id: int | None
    title: str
    summary: str
    payload: dict[str, Any]
    status: AgentRequestStatus
    risk_level: AgentRiskLevel
    requires_review: bool
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    resolved_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRequestExecution:
    id: int
    request_id: int
    executor_role: AgentRole
    executor_id: str
    execution_type: str
    status: AgentExecutionStatus
    environment: str
    run_id: str | None
    started_at: datetime
    completed_at: datetime | None
    result: dict[str, Any]
    artifact_paths: list[str]
    error: dict[str, Any]
    created_at: datetime
