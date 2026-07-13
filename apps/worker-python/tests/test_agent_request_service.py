from dataclasses import replace
from datetime import datetime, timezone

import pytest

from dehps.agents.errors import AgentAuthorizationError
from dehps.agents.requests import (
    AgentExecutionStatus,
    AgentRequest,
    AgentRequestExecution,
    AgentRequestStatus,
    AgentRequestType,
    AgentRiskLevel,
)
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def draft() -> AgentRequest:
    return AgentRequest(
        id=1, request_key="eng-1", request_type=AgentRequestType.ENGINEERING_IMPLEMENTATION,
        requested_by_role=AgentRole.ENGINEERING, requested_by="eng:a", hypothesis_id=None,
        experiment_id=None, parent_request_id=None, title="Implement", summary="",
        payload={"scope": "api", "acceptance": "tests", "non_goals": []},
        status=AgentRequestStatus.DRAFT, risk_level=AgentRiskLevel.MEDIUM,
        requires_review=True, created_at=NOW, updated_at=NOW, submitted_at=None,
        resolved_at=None,
    )


class Repository:
    def __init__(self) -> None:
        self.value = draft()

    def get_request(self, key):
        return self.value

    def transition(self, **kwargs):
        self.value = replace(self.value, status=kwargs["new_status"])
        return self.value

    def stop_active_execution(self, **kwargs):
        self.value = replace(self.value, status=kwargs["request_status"])
        execution = AgentRequestExecution(
            id=2, request_id=1, executor_role=AgentRole.ENGINEERING, executor_id="eng:a",
            execution_type="modify_code", status=AgentExecutionStatus.CANCELLED,
            environment="development", run_id=None, started_at=NOW, completed_at=NOW,
            result={}, artifact_paths=[], error={"stopped": True}, created_at=NOW,
        )
        return self.value, execution


def test_only_recorded_requester_can_submit() -> None:
    service = AgentRequestService(Repository())  # type: ignore[arg-type]
    with pytest.raises(AgentAuthorizationError, match="recorded requester"):
        service.submit("eng-1", actor_role=AgentRole.ENGINEERING, actor_id="eng:other")


def test_submit_writes_lifecycle_transition_after_authorization() -> None:
    service = AgentRequestService(Repository())  # type: ignore[arg-type]
    result = service.submit("eng-1", actor_role=AgentRole.ENGINEERING, actor_id="eng:a")
    assert result.status == AgentRequestStatus.SUBMITTED


def test_cancelling_executing_request_atomically_stops_execution() -> None:
    repository = Repository()
    repository.value = replace(repository.value, status=AgentRequestStatus.EXECUTING)
    service = AgentRequestService(repository)  # type: ignore[arg-type]
    result = service.cancel(
        "eng-1", actor_role=AgentRole.ENGINEERING, actor_id="eng:a", reason={"why": "stop"},
        environment="development",
    )
    assert result.status == AgentRequestStatus.CANCELLED
