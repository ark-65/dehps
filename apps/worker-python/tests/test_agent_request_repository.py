from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequestStatus
from dehps.agents.roles import AgentRole


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def request_row(status: str = "submitted") -> dict[str, object]:
    return {
        "id": 7, "request_key": "request-1", "request_type": "engineering_implementation",
        "requested_by_role": "engineering", "requested_by": "agent:eng", "hypothesis_id": None,
        "experiment_id": None, "parent_request_id": None, "title": "Implement", "summary": "",
        "payload_json": {"scope": "cli", "acceptance": "tests", "non_goals": []},
        "status": status, "risk_level": "medium", "requires_review": True,
        "created_at": NOW, "updated_at": NOW, "submitted_at": NOW, "resolved_at": None,
        "metadata_json": {},
    }


class Result:
    def __init__(self, row=None) -> None:
        self.row = row

    def fetchone(self):
        return self.row


class ScriptedConnection:
    def __init__(self, fail_decision: bool = False) -> None:
        self.fail_decision = fail_decision
        self.statements: list[str] = []
        self.committed = False
        self.rolled_back = False

    def cursor(self, row_factory=None):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.rolled_back = exc_type is not None
        self.committed = exc_type is None
        return False

    def execute(self, sql, params=None):
        compact = " ".join(sql.split())
        self.statements.append(compact)
        if compact.startswith("SELECT * FROM agent_requests"):
            return Result(request_row())
        if compact.startswith("UPDATE agent_requests"):
            return Result(request_row("under_review"))
        if compact.startswith("INSERT INTO agent_request_decisions") and self.fail_decision:
            raise RuntimeError("decision write failed")
        return Result()


def repository(connection: ScriptedConnection) -> AgentRequestRepository:
    @contextmanager
    def factory():
        with connection:
            yield connection

    return AgentRequestRepository(factory)  # type: ignore[arg-type]


def test_status_and_append_only_decision_share_one_transaction() -> None:
    connection = ScriptedConnection()

    result = repository(connection).transition(
        request_key="request-1",
        expected_status=AgentRequestStatus.SUBMITTED,
        new_status=AgentRequestStatus.UNDER_REVIEW,
        decision_code="review_started",
        summary="review",
        reason={},
        decided_by_role=AgentRole.REVIEWER,
        decided_by="agent:review",
    )

    assert result.status == AgentRequestStatus.UNDER_REVIEW
    assert connection.committed is True
    assert any("set_config('dehps.agent_request_status_transition'" in sql for sql in connection.statements)
    assert next(i for i, sql in enumerate(connection.statements) if sql.startswith("UPDATE agent_requests")) < next(
        i for i, sql in enumerate(connection.statements) if sql.startswith("INSERT INTO agent_request_decisions")
    )


def test_decision_failure_rolls_back_status_change() -> None:
    connection = ScriptedConnection(fail_decision=True)
    with pytest.raises(RuntimeError, match="decision write failed"):
        repository(connection).transition(
            request_key="request-1",
            expected_status=AgentRequestStatus.SUBMITTED,
            new_status=AgentRequestStatus.UNDER_REVIEW,
            decision_code="review_started",
            summary="review",
            reason={},
            decided_by_role=AgentRole.REVIEWER,
            decided_by="agent:review",
        )
    assert connection.rolled_back is True
    assert connection.committed is False
