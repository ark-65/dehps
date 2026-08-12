from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dehps.agents.errors import (
    AgentAuthorizationError,
    AgentRequestTransitionError,
    AgentRequestValidationError,
)
from dehps.agents.handoffs import (
    request_uses_engineering_result_contract,
    validate_engineering_result,
    validate_research_to_engineering_payload,
)
from dehps.agents.policy import AgentAuthorityPolicy, AuthorizationContext
from dehps.agents.repository import (
    AgentRequestExecutionMetadata,
    AgentRequestRepository,
)
from dehps.agents.requests import (
    REQUEST_TRANSITIONS,
    REQUEST_TYPE_SPECS,
    AgentExecutionStatus,
    AgentRequest,
    AgentRequestExecution,
    AgentRequestStatus,
    AgentRequestType,
    AgentRiskLevel,
)
from dehps.agents.roles import AgentRole

RISK_ORDER = {
    AgentRiskLevel.LOW: 0,
    AgentRiskLevel.MEDIUM: 1,
    AgentRiskLevel.HIGH: 2,
    AgentRiskLevel.CRITICAL: 3,
}


class AgentRequestService:
    def __init__(
        self,
        repository: AgentRequestRepository,
        policy: AgentAuthorityPolicy | None = None,
    ) -> None:
        self.repository = repository
        self.policy = policy or AgentAuthorityPolicy()

    def create_draft(
        self,
        *,
        request_key: str,
        request_type: AgentRequestType,
        requested_by_role: AgentRole,
        requested_by: str,
        title: str,
        summary: str,
        payload: Mapping[str, Any],
        environment: str = "isolated",
        risk_level: AgentRiskLevel | None = None,
        hypothesis_key: str | None = None,
        experiment_key: str | None = None,
        parent_request_key: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> AgentRequest:
        spec = REQUEST_TYPE_SPECS[request_type]
        selected_risk = risk_level or spec.risk_level
        if RISK_ORDER[selected_risk] < RISK_ORDER[spec.risk_level]:
            raise AgentRequestValidationError(
                f"risk level cannot be lower than {spec.risk_level.value} for {request_type.value}"
            )
        self._validate_payload(request_type, payload)
        self._validate_handoff_payload(
            request_type,
            payload,
            hypothesis_key=hypothesis_key,
            experiment_key=experiment_key,
            draft=True,
        )
        self._validate_links(
            request_type,
            hypothesis_key=hypothesis_key,
            experiment_key=experiment_key,
        )
        self._authorize(
            role=requested_by_role,
            action=spec.creation_action,
            request_type=request_type,
            request_status=AgentRequestStatus.DRAFT,
            environment=environment,
            risk_level=selected_risk,
        )
        if not request_key.strip() or not requested_by.strip() or not title.strip():
            raise AgentRequestValidationError("request_key, requested_by, and title are required")
        return self.repository.create_draft(
            request_key=request_key,
            request_type=request_type,
            requested_by_role=requested_by_role,
            requested_by=requested_by,
            title=title,
            summary=summary,
            payload=payload,
            risk_level=selected_risk,
            requires_review=True,
            hypothesis_key=hypothesis_key,
            experiment_key=experiment_key,
            parent_request_key=parent_request_key,
            metadata=metadata,
        )

    def update_draft_payload(
        self,
        request_key: str,
        *,
        actor_role: AgentRole,
        actor_id: str,
        payload: Mapping[str, Any],
        environment: str = "isolated",
    ) -> AgentRequest:
        request = self.repository.get_request(request_key)
        if request.status != AgentRequestStatus.DRAFT:
            raise AgentRequestTransitionError("only draft request payloads may be edited")
        self._require_request_owner(request, actor_role, actor_id)
        self._validate_payload(request.request_type, payload)
        self._validate_handoff_payload(
            request.request_type,
            payload,
            hypothesis_key=str(request.payload.get("hypothesis_key") or "") or None,
            experiment_key=str(request.payload.get("experiment_key") or "") or None,
            draft=True,
        )
        self._authorize_request(request, actor_role, REQUEST_TYPE_SPECS[request.request_type].creation_action, environment)
        return self.repository.update_payload(request_key=request_key, payload=payload)

    def submit(
        self,
        request_key: str,
        *,
        actor_role: AgentRole,
        actor_id: str,
        environment: str = "isolated",
    ) -> AgentRequest:
        request = self.repository.get_request(request_key)
        self._require_request_owner(request, actor_role, actor_id)
        self._validate_handoff_payload(
            request.request_type,
            request.payload,
            hypothesis_key=str(request.payload.get("hypothesis_key") or "") or None,
            experiment_key=str(request.payload.get("experiment_key") or "") or None,
            draft=False,
        )
        self._authorize_request(request, actor_role, REQUEST_TYPE_SPECS[request.request_type].creation_action, environment)
        return self._transition(
            request,
            AgentRequestStatus.SUBMITTED,
            decision_code="request_submitted",
            summary="request submitted for review",
            reason={},
            actor_role=actor_role,
            actor_id=actor_id,
        )

    def begin_review(
        self,
        request_key: str,
        *,
        reviewer_role: AgentRole,
        reviewer_id: str,
        environment: str = "isolated",
    ) -> AgentRequest:
        request = self.repository.get_request(request_key)
        self._authorize_request(request, reviewer_role, self._review_action("review"), environment)
        self._require_independent_critical_reviewer(request, reviewer_id)
        return self._transition(
            request,
            AgentRequestStatus.UNDER_REVIEW,
            decision_code="review_started",
            summary="request review started",
            reason={},
            actor_role=reviewer_role,
            actor_id=reviewer_id,
        )

    def approve(
        self,
        request_key: str,
        *,
        reviewer_role: AgentRole,
        reviewer_id: str,
        reason: Mapping[str, Any],
        environment: str = "isolated",
    ) -> AgentRequest:
        request = self.repository.get_request(request_key)
        self._authorize_request(request, reviewer_role, self._review_action("approve"), environment)
        self._require_independent_critical_reviewer(request, reviewer_id)
        return self._transition(
            request,
            AgentRequestStatus.APPROVED,
            decision_code="request_approved",
            summary="request approved for execution",
            reason=reason,
            actor_role=reviewer_role,
            actor_id=reviewer_id,
        )

    def reject(
        self,
        request_key: str,
        *,
        reviewer_role: AgentRole,
        reviewer_id: str,
        reason: Mapping[str, Any],
        environment: str = "isolated",
    ) -> AgentRequest:
        request = self.repository.get_request(request_key)
        self._authorize_request(request, reviewer_role, self._review_action("reject"), environment)
        self._require_independent_critical_reviewer(request, reviewer_id)
        return self._transition(
            request,
            AgentRequestStatus.REJECTED,
            decision_code="request_rejected",
            summary="request rejected",
            reason=reason,
            actor_role=reviewer_role,
            actor_id=reviewer_id,
        )

    def cancel(
        self,
        request_key: str,
        *,
        actor_role: AgentRole,
        actor_id: str,
        reason: Mapping[str, Any],
        environment: str = "isolated",
    ) -> AgentRequest:
        request = self.repository.get_request(request_key)
        self._authorize_request(request, actor_role, self._cancel_action(), environment)
        self._ensure_transition(request.status, AgentRequestStatus.CANCELLED)
        if request.status == AgentRequestStatus.EXECUTING:
            stopped, _ = self.repository.stop_active_execution(
                request_key=request_key,
                request_status=AgentRequestStatus.CANCELLED,
                decided_by_role=actor_role,
                decided_by=actor_id,
                decision_code="request_cancelled",
                summary="request and active execution cancelled",
                reason=reason,
            )
            return stopped
        return self._transition(
            request,
            AgentRequestStatus.CANCELLED,
            decision_code="request_cancelled",
            summary="request cancelled",
            reason=reason,
            actor_role=actor_role,
            actor_id=actor_id,
        )

    def begin_execution(
        self,
        request_key: str,
        *,
        executor_role: AgentRole,
        executor_id: str,
        environment: str,
        run_id: str | None = None,
    ) -> tuple[AgentRequest, AgentRequestExecution]:
        request = self.repository.get_request(request_key)
        spec = REQUEST_TYPE_SPECS[request.request_type]
        self._ensure_transition(request.status, AgentRequestStatus.EXECUTING)
        self._authorize_request(request, executor_role, spec.execution_action, environment)
        if executor_role == AgentRole.OPERATOR and not str(run_id or "").strip():
            raise AgentRequestValidationError("Operator executions require a run_id")
        return self.repository.begin_execution(
            request_key=request_key,
            executor_role=executor_role,
            executor_id=executor_id,
            execution_type=spec.execution_action.value,
            environment=environment,
            run_id=run_id,
        )

    def begin_execution_metadata(
        self,
        request_key: str,
        *,
        executor_role: AgentRole,
        executor_id: str,
        environment: str,
        run_id: str | None = None,
    ) -> tuple[AgentRequest, AgentRequestExecutionMetadata]:
        request = self.repository.get_request(request_key)
        spec = REQUEST_TYPE_SPECS[request.request_type]
        self._ensure_transition(request.status, AgentRequestStatus.EXECUTING)
        self._authorize_request(request, executor_role, spec.execution_action, environment)
        if executor_role == AgentRole.OPERATOR and not str(run_id or "").strip():
            raise AgentRequestValidationError("Operator executions require a run_id")
        return self.repository.begin_execution_metadata(
            request_key=request_key,
            executor_role=executor_role,
            executor_id=executor_id,
            execution_type=spec.execution_action.value,
            environment=environment,
            run_id=run_id,
        )

    def complete_execution(
        self,
        request_key: str,
        *,
        execution_id: int,
        executor_role: AgentRole,
        executor_id: str,
        result: Mapping[str, Any],
        artifact_paths: list[str],
    ) -> tuple[AgentRequest, AgentRequestExecution]:
        request, execution = self._execution_context(request_key, execution_id)
        self._authorize_request(request, executor_role, REQUEST_TYPE_SPECS[request.request_type].execution_action, execution.environment)
        self._ensure_transition(request.status, AgentRequestStatus.COMPLETED)
        if request_uses_engineering_result_contract(request.request_type):
            validate_engineering_result(result)
        return self.repository.finish_execution(
            request_key=request_key,
            execution_id=execution_id,
            executor_role=executor_role,
            executor_id=executor_id,
            execution_status=AgentExecutionStatus.COMPLETED,
            request_status=AgentRequestStatus.COMPLETED,
            result=result,
            artifact_paths=artifact_paths,
            error={},
        )

    def fail_execution(
        self,
        request_key: str,
        *,
        execution_id: int,
        executor_role: AgentRole,
        executor_id: str,
        error: Mapping[str, Any],
    ) -> tuple[AgentRequest, AgentRequestExecution]:
        request, execution = self._execution_context(request_key, execution_id)
        self._authorize_request(request, executor_role, REQUEST_TYPE_SPECS[request.request_type].execution_action, execution.environment)
        self._ensure_transition(request.status, AgentRequestStatus.FAILED)
        return self.repository.finish_execution(
            request_key=request_key,
            execution_id=execution_id,
            executor_role=executor_role,
            executor_id=executor_id,
            execution_status=AgentExecutionStatus.FAILED,
            request_status=AgentRequestStatus.FAILED,
            result={},
            artifact_paths=[],
            error=error,
        )

    def complete_execution_metadata(
        self,
        request_key: str,
        *,
        execution_id: int,
        executor_role: AgentRole,
        executor_id: str,
        result: Mapping[str, Any],
        artifact_paths: list[str],
    ) -> tuple[AgentRequest, AgentRequestExecutionMetadata]:
        request, execution = self._execution_metadata_context(request_key, execution_id)
        self._authorize_request(
            request,
            executor_role,
            REQUEST_TYPE_SPECS[request.request_type].execution_action,
            execution.environment,
        )
        self._ensure_transition(request.status, AgentRequestStatus.COMPLETED)
        if request_uses_engineering_result_contract(request.request_type):
            validate_engineering_result(result)
        return self.repository.finish_execution_metadata(
            request_key=request_key,
            execution_id=execution_id,
            executor_role=executor_role,
            executor_id=executor_id,
            execution_status=AgentExecutionStatus.COMPLETED,
            request_status=AgentRequestStatus.COMPLETED,
            result=result,
            artifact_paths=artifact_paths,
            error={},
        )

    def fail_execution_metadata(
        self,
        request_key: str,
        *,
        execution_id: int,
        executor_role: AgentRole,
        executor_id: str,
        error: Mapping[str, Any],
    ) -> tuple[AgentRequest, AgentRequestExecutionMetadata]:
        request, execution = self._execution_metadata_context(request_key, execution_id)
        self._authorize_request(
            request,
            executor_role,
            REQUEST_TYPE_SPECS[request.request_type].execution_action,
            execution.environment,
        )
        self._ensure_transition(request.status, AgentRequestStatus.FAILED)
        return self.repository.finish_execution_metadata(
            request_key=request_key,
            execution_id=execution_id,
            executor_role=executor_role,
            executor_id=executor_id,
            execution_status=AgentExecutionStatus.FAILED,
            request_status=AgentRequestStatus.FAILED,
            result={},
            artifact_paths=[],
            error=error,
        )

    def invalidate(
        self,
        request_key: str,
        *,
        reviewer_role: AgentRole,
        reviewer_id: str,
        reason: Mapping[str, Any],
        environment: str = "isolated",
    ) -> AgentRequest:
        request = self.repository.get_request(request_key)
        self._authorize_request(request, reviewer_role, self._review_action("reject"), environment)
        self._ensure_transition(request.status, AgentRequestStatus.INVALIDATED)
        if request.status == AgentRequestStatus.EXECUTING:
            stopped, _ = self.repository.stop_active_execution(
                request_key=request_key,
                request_status=AgentRequestStatus.INVALIDATED,
                decided_by_role=reviewer_role,
                decided_by=reviewer_id,
                decision_code="request_invalidated",
                summary="request invalidated and active execution stopped",
                reason=reason,
            )
            return stopped
        return self._transition(
            request,
            AgentRequestStatus.INVALIDATED,
            decision_code="request_invalidated",
            summary="request invalidated by review",
            reason=reason,
            actor_role=reviewer_role,
            actor_id=reviewer_id,
        )

    def _execution_context(
        self,
        request_key: str,
        execution_id: int,
    ) -> tuple[AgentRequest, AgentRequestExecution]:
        request = self.repository.get_request(request_key)
        executions = self.repository.list_executions(request_key)
        execution = next((item for item in executions if item.id == execution_id), None)
        if execution is None:
            raise AgentRequestValidationError(f"execution is not attached to request: {execution_id}")
        return request, execution

    def _execution_metadata_context(
        self,
        request_key: str,
        execution_id: int,
    ) -> tuple[AgentRequest, AgentRequestExecutionMetadata]:
        request = self.repository.get_request(request_key)
        execution = self.repository.get_execution_metadata(request_key, execution_id)
        return request, execution

    def _require_independent_critical_reviewer(
        self,
        request: AgentRequest,
        reviewer_id: str,
    ) -> None:
        if request.risk_level != AgentRiskLevel.CRITICAL:
            return
        if reviewer_id == request.requested_by:
            raise AgentAuthorizationError(
                "critical request reviewer must differ from the recorded requester"
            )
        if any(
            execution.executor_id == reviewer_id
            for execution in self.repository.list_execution_metadata(request.request_key)
        ):
            raise AgentAuthorizationError(
                "critical request reviewer must differ from every recorded executor"
            )

    def _transition(
        self,
        request: AgentRequest,
        new_status: AgentRequestStatus,
        *,
        decision_code: str,
        summary: str,
        reason: Mapping[str, Any],
        actor_role: AgentRole,
        actor_id: str,
    ) -> AgentRequest:
        self._ensure_transition(request.status, new_status)
        return self.repository.transition(
            request_key=request.request_key,
            expected_status=request.status,
            new_status=new_status,
            decision_code=decision_code,
            summary=summary,
            reason=reason,
            decided_by_role=actor_role,
            decided_by=actor_id,
        )

    @staticmethod
    def _ensure_transition(current: AgentRequestStatus, new: AgentRequestStatus) -> None:
        if new not in REQUEST_TRANSITIONS[current]:
            raise AgentRequestTransitionError(
                f"invalid Agent Request transition: {current.value} -> {new.value}"
            )

    @staticmethod
    def _validate_payload(request_type: AgentRequestType, payload: Mapping[str, Any]) -> None:
        spec = REQUEST_TYPE_SPECS[request_type]
        missing = sorted(field for field in spec.required_payload_fields if field not in payload)
        if missing:
            raise AgentRequestValidationError(
                f"{request_type.value} payload is missing: {', '.join(missing)}"
            )

    @staticmethod
    def _validate_links(
        request_type: AgentRequestType,
        *,
        hypothesis_key: str | None,
        experiment_key: str | None,
    ) -> None:
        spec = REQUEST_TYPE_SPECS[request_type]
        if spec.requires_hypothesis and not hypothesis_key:
            raise AgentRequestValidationError(f"{request_type.value} requires a hypothesis link")
        if spec.requires_experiment and not experiment_key:
            raise AgentRequestValidationError(f"{request_type.value} requires an experiment link")

    def _validate_handoff_payload(
        self,
        request_type: AgentRequestType,
        payload: Mapping[str, Any],
        *,
        hypothesis_key: str | None,
        experiment_key: str | None,
        draft: bool,
    ) -> None:
        if request_type == AgentRequestType.ENGINEERING_EXPERIMENT_TOOL:
            validate_research_to_engineering_payload(payload)
            if payload.get("hypothesis_key") != hypothesis_key:
                raise AgentRequestValidationError("handoff hypothesis_key must match the linked hypothesis")
            if payload.get("experiment_key") != experiment_key:
                raise AgentRequestValidationError("handoff experiment_key must match the linked experiment")
        elif request_type == AgentRequestType.OPERATOR_ISOLATED_RUN:
            tool_key = str(payload.get("approved_tool_request_key") or "")
            if not draft or tool_key:
                self._require_completed_request(
                    tool_key,
                    expected_type=AgentRequestType.ENGINEERING_EXPERIMENT_TOOL,
                    label="approved experiment tool",
                )
            if payload.get("environment") != "isolated":
                raise AgentRequestValidationError("operator_isolated_run environment must be isolated")
            if payload.get("production_access") is not False:
                raise AgentRequestValidationError("operator_isolated_run production_access must be false")
        elif request_type == AgentRequestType.RESEARCH_EVIDENCE_SUBMISSION:
            execution_key = str(payload.get("execution_request_key") or "")
            execution_request = self._require_completed_request(
                execution_key,
                expected_type=AgentRequestType.OPERATOR_ISOLATED_RUN,
                label="isolated execution",
            )
            if not self.repository.list_executions(execution_request.request_key):
                raise AgentRequestValidationError(
                    "Evidence Proposal requires an audited isolated execution record"
                )

    def _require_completed_request(
        self,
        request_key: str,
        *,
        expected_type: AgentRequestType,
        label: str,
    ) -> AgentRequest:
        if not request_key:
            raise AgentRequestValidationError(f"{label} request key is required")
        request = self.repository.get_request(request_key)
        if request.request_type != expected_type or request.status != AgentRequestStatus.COMPLETED:
            raise AgentRequestValidationError(
                f"{label} must reference a completed {expected_type.value} request"
            )
        return request

    @staticmethod
    def _require_request_owner(
        request: AgentRequest,
        actor_role: AgentRole,
        actor_id: str,
    ) -> None:
        if request.requested_by_role != actor_role or request.requested_by != actor_id:
            raise AgentAuthorizationError("only the recorded requester may submit or edit the draft")

    def _authorize_request(
        self,
        request: AgentRequest,
        role: AgentRole,
        action: Any,
        environment: str,
    ) -> None:
        self._authorize(
            role=role,
            action=action,
            request_type=request.request_type,
            request_status=request.status,
            environment=environment,
            risk_level=request.risk_level,
        )

    def _authorize(
        self,
        *,
        role: AgentRole,
        action: Any,
        request_type: AgentRequestType,
        request_status: AgentRequestStatus,
        environment: str,
        risk_level: AgentRiskLevel,
    ) -> None:
        decision = self.policy.authorize(
            AuthorizationContext(
                role=role,
                action=action,
                request_type=request_type.value,
                request_status=request_status.value,
                environment=environment,
                risk_level=risk_level.value,
            )
        )
        if not decision.allowed:
            raise AgentAuthorizationError(f"{decision.reason_code}: {decision.summary}")

    @staticmethod
    def _review_action(kind: str):
        from dehps.agents.actions import AgentAction

        return {
            "review": AgentAction.REVIEW_REQUEST,
            "approve": AgentAction.APPROVE_REQUEST,
            "reject": AgentAction.REJECT_REQUEST,
        }[kind]

    @staticmethod
    def _cancel_action():
        from dehps.agents.actions import AgentAction

        return AgentAction.CANCEL_REQUEST
