from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone

from experiment_plan_fixtures import ranking_plan
from dehps.agents.errors import AgentRequestValidationError
from dehps.agents.requests import AgentRequest, AgentRequestStatus, AgentRequestType, AgentRiskLevel
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService
from dehps.research_planning.implementation_contract import engineering_payload
from dehps.research_planning.execution_contract import operator_payload
from dehps.research_planning.service import ExperimentPlanningService


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def request(key, request_type, payload, status=AgentRequestStatus.DRAFT):
    return AgentRequest(
        id=1,
        request_key=key,
        request_type=request_type,
        requested_by_role=AgentRole.RESEARCH,
        requested_by="research:planner",
        hypothesis_id=2,
        experiment_id=3,
        parent_request_id=None,
        title="request",
        summary="",
        payload=payload,
        status=status,
        risk_level=AgentRiskLevel.MEDIUM
        if request_type == AgentRequestType.ENGINEERING_EXPERIMENT_TOOL
        else AgentRiskLevel.HIGH,
        requires_review=True,
        created_at=NOW,
        updated_at=NOW,
        submitted_at=None,
        resolved_at=None,
        metadata={},
    )


class PlanRepository:
    def __init__(self, plan):
        self.plan = plan

    def get_materialized_plan_payload(self, key):
        return asdict(self.plan)


class AgentRepository:
    def __init__(self):
        self.requests = {}

    def get_request(self, key):
        return self.requests[key]


class AgentService:
    def __init__(self, repository):
        self.repository = repository
        self.created = []

    def create_draft(self, **kwargs):
        item = request(kwargs["request_key"], kwargs["request_type"], kwargs["payload"])
        self.repository.requests[item.request_key] = item
        self.created.append(kwargs)
        return item

    def submit(self, key, **kwargs):
        item = self.repository.requests[key]
        item = replace(item, status=AgentRequestStatus.SUBMITTED, submitted_at=NOW)
        self.repository.requests[key] = item
        return item


def test_engineering_request_payload_is_submitted_and_nonproduction() -> None:
    plan = ranking_plan()
    payload = engineering_payload(plan, experiment_key="ranking_disagreement_feasibility_v1")

    assert payload["production_impact"] == "none"
    assert payload["hypothesis_key"] == plan.hypothesis_key
    assert payload["experiment_plan_key"] == plan.plan_key
    assert payload["feature_contract"] == plan.feature_contract


def test_operator_request_payload_is_draft_only_and_nonproduction() -> None:
    plan = ranking_plan()
    payload = operator_payload(
        plan,
        experiment_key="ranking_disagreement_feasibility_v1",
        engineering_request_key="engineering-1",
    )

    assert payload["database"] == "isolated"
    assert payload["production_access"] is False
    assert payload["allowed_commands"] == []
    assert payload["approved_tool_request_key"] == ""


def test_planning_service_submits_engineering_and_keeps_operator_draft() -> None:
    plan = ranking_plan()
    agent_repository = AgentRepository()
    agent_service = AgentService(agent_repository)
    service = ExperimentPlanningService(
        agent_repository=agent_repository,  # type: ignore[arg-type]
        agent_service=agent_service,  # type: ignore[arg-type]
        repository=PlanRepository(plan),  # type: ignore[arg-type]
    )

    engineering = service.create_engineering_request(
        plan_key=plan.plan_key,
        requested_by="research:planner",
    )
    operator = service.create_operator_request(
        plan_key=plan.plan_key,
        requested_by="research:planner",
    )

    assert engineering.status == AgentRequestStatus.SUBMITTED
    assert operator.status == AgentRequestStatus.DRAFT
    assert operator.request_type == AgentRequestType.OPERATOR_ISOLATED_RUN


def test_operator_draft_can_exist_before_engineering_completion_but_cannot_submit() -> None:
    plan = ranking_plan()
    payload = operator_payload(
        plan,
        experiment_key="ranking_disagreement_feasibility_v1",
        engineering_request_key="engineering-1",
    )
    item = request("operator-1", AgentRequestType.OPERATOR_ISOLATED_RUN, payload)

    class Repository:
        value = item

        def get_request(self, key):
            return self.value

    service = AgentRequestService(Repository())  # type: ignore[arg-type]

    with pytest_raises_validation():
        service.submit(
            "operator-1",
            actor_role=AgentRole.RESEARCH,
            actor_id="research:planner",
            environment="isolated",
        )


class pytest_raises_validation:
    def __enter__(self):
        import pytest

        self.manager = pytest.raises(AgentRequestValidationError)
        return self.manager.__enter__()

    def __exit__(self, exc_type, exc, tb):
        return self.manager.__exit__(exc_type, exc, tb)
