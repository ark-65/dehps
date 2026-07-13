from __future__ import annotations

from dataclasses import asdict
from typing import Any

from dehps.agents.errors import AgentAuthorityError, AgentRequestConflictError
from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequest, AgentRequestStatus, AgentRequestType, AgentRiskLevel
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService
from dehps.research.errors import HypothesisRegistryError
from dehps.research_autonomy.context import ResearchContext, ResearchContextBuilder
from dehps.research_planning.execution_contract import operator_payload, operator_request_key
from dehps.research_planning.implementation_contract import (
    EXPERIMENT_KEY_BY_STAGE,
    engineering_payload,
    engineering_request_key,
)
from dehps.research_planning.models import (
    ExperimentPlan,
    ExperimentPlanValidationReport,
    MaterializationResult,
)
from dehps.research_planning.planner import ExperimentPlanner
from dehps.research_planning.proposal_reader import ApprovedProposal, ApprovedProposalReader
from dehps.research_planning.repository import ExperimentPlanningRepository
from dehps.research_planning.validation import ExperimentPlanValidator


class ExperimentPlanningService:
    def __init__(
        self,
        *,
        agent_repository: AgentRequestRepository | None = None,
        agent_service: AgentRequestService | None = None,
        context_builder: ResearchContextBuilder | None = None,
        planner: ExperimentPlanner | None = None,
        validator: ExperimentPlanValidator | None = None,
        repository: ExperimentPlanningRepository | None = None,
    ) -> None:
        self.agent_repository = agent_repository or AgentRequestRepository()
        self.agent_service = agent_service or AgentRequestService(self.agent_repository)
        self.context_builder = context_builder or ResearchContextBuilder()
        self.planner = planner or ExperimentPlanner()
        self.validator = validator or ExperimentPlanValidator()
        self.repository = repository or ExperimentPlanningRepository()

    def build(
        self,
        *,
        proposal_request_key: str | None,
    ) -> tuple[ExperimentPlan, ApprovedProposal, ResearchContext]:
        self.agent_repository.ensure_schema()
        approved = (
            ApprovedProposalReader(self.agent_repository).latest()
            if proposal_request_key is None
            else ApprovedProposalReader(self.agent_repository).read(proposal_request_key)
        )
        context = self.context_builder.build()
        plan = self.planner.build(
            approved.proposal,
            context,
            reviewer_decision=approved.approval_decision,
        )
        return plan, approved, context

    def validate(
        self,
        *,
        proposal_request_key: str | None,
    ) -> tuple[ExperimentPlan, ExperimentPlanValidationReport]:
        plan, approved, context = self.build(proposal_request_key=proposal_request_key)
        return plan, self.validator.validate(plan, approved.proposal, context)

    def materialize(
        self,
        *,
        proposal_request_key: str,
    ) -> tuple[ExperimentPlan, ExperimentPlanValidationReport, MaterializationResult]:
        plan, approved, context = self.build(proposal_request_key=proposal_request_key)
        report = self.validator.validate(plan, approved.proposal, context)
        if not report.valid:
            raise HypothesisRegistryError(
                "experiment plan validation failed: " + "; ".join(report.failure_reasons)
            )
        result = self.repository.materialize(
            plan,
            proposal_request_key=approved.request.request_key,
            reviewer_approval=approved.approval_decision,
        )
        return plan, report, result

    def create_engineering_request(
        self,
        *,
        plan_key: str,
        requested_by: str,
    ) -> AgentRequest:
        plan = self._materialized_plan(plan_key)
        experiment_key = EXPERIMENT_KEY_BY_STAGE["feasibility"]
        key = engineering_request_key(plan)
        payload = engineering_payload(plan, experiment_key=experiment_key)
        try:
            request = self.agent_service.create_draft(
                request_key=key,
                request_type=AgentRequestType.ENGINEERING_EXPERIMENT_TOOL,
                requested_by_role=AgentRole.RESEARCH,
                requested_by=requested_by,
                title=f"Implement isolated tool for {plan.plan_key}",
                summary="Engineering implementation request for a preregistered experiment plan.",
                payload=payload,
                environment="isolated",
                risk_level=AgentRiskLevel.MEDIUM,
                hypothesis_key=plan.hypothesis_key,
                experiment_key=experiment_key,
                metadata={
                    "experiment_plan_key": plan.plan_key,
                    "plan_fingerprint": plan.plan_fingerprint,
                },
            )
        except AgentRequestConflictError:
            existing = self.agent_repository.get_request(key)
            if existing.payload != payload:
                raise
            request = existing
        if request.status == AgentRequestStatus.DRAFT:
            return self.agent_service.submit(
                request.request_key,
                actor_role=AgentRole.RESEARCH,
                actor_id=requested_by,
                environment="isolated",
            )
        return request

    def create_operator_request(
        self,
        *,
        plan_key: str,
        requested_by: str,
    ) -> AgentRequest:
        plan = self._materialized_plan(plan_key)
        experiment_key = EXPERIMENT_KEY_BY_STAGE["feasibility"]
        engineering_key = engineering_request_key(plan)
        try:
            self.agent_repository.get_request(engineering_key)
        except AgentAuthorityError as exc:
            raise HypothesisRegistryError(
                f"engineering request must exist before operator draft: {engineering_key}"
            ) from exc
        key = operator_request_key(plan)
        payload = operator_payload(
            plan,
            experiment_key=experiment_key,
            engineering_request_key=engineering_key,
        )
        try:
            return self.agent_service.create_draft(
                request_key=key,
                request_type=AgentRequestType.OPERATOR_ISOLATED_RUN,
                requested_by_role=AgentRole.RESEARCH,
                requested_by=requested_by,
                title=f"Draft isolated run for {plan.plan_key}",
                summary="Operator draft only; submission waits for completed Engineering implementation.",
                payload=payload,
                environment="isolated",
                risk_level=AgentRiskLevel.HIGH,
                hypothesis_key=plan.hypothesis_key,
                experiment_key=experiment_key,
                parent_request_key=engineering_key,
                metadata={
                    "experiment_plan_key": plan.plan_key,
                    "plan_fingerprint": plan.plan_fingerprint,
                    "submit_blocked_until": "engineering_experiment_tool_completed",
                },
            )
        except AgentRequestConflictError:
            existing = self.agent_repository.get_request(key)
            if existing.payload != payload:
                raise
            return existing

    def list_plans(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        return self.repository.list_plans(limit=limit, offset=offset)

    def show_plan(self, plan_key: str) -> dict[str, Any]:
        return self.repository.get_plan_record(plan_key)

    def plan_requests(self, plan_key: str) -> list[dict[str, Any]]:
        return self.repository.list_plan_requests(plan_key)

    def _materialized_plan(self, plan_key: str) -> ExperimentPlan:
        payload = self.repository.get_materialized_plan_payload(plan_key)
        return _plan_from_payload(payload)


def _plan_from_payload(payload: dict[str, Any]) -> ExperimentPlan:
    from dehps.research_planning.models import (
        ArtifactContract,
        EvidenceContract,
        ExperimentStage,
        ImplementationStep,
        ResourceBudget,
    )

    data = dict(payload)
    data["implementation_steps"] = tuple(
        ImplementationStep(**item) for item in data.get("implementation_steps", ())
    )
    data["experiment_stages"] = tuple(
        ExperimentStage(**item) for item in data.get("experiment_stages", ())
    )
    data["resource_budget"] = ResourceBudget(**data["resource_budget"])
    data["artifact_contract"] = ArtifactContract(**data["artifact_contract"])
    data["evidence_contract"] = EvidenceContract(**data["evidence_contract"])
    for key in (
        "invariants",
        "self_deception_controls",
        "stop_conditions",
    ):
        data[key] = tuple(data.get(key, ()))
    return ExperimentPlan(**data)


def jsonable(value: object) -> dict[str, Any]:
    import json

    return json.loads(json.dumps(asdict(value), sort_keys=True, default=str))
