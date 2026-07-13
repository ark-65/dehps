from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from dehps.research.repository import HypothesisRepository
from dehps.research.status import HypothesisStatus


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def hypothesis_row(status: str = "proposed") -> dict[str, object]:
    return {
        "id": 11,
        "hypothesis_key": "hypothesis-1",
        "family_id": 3,
        "parent_hypothesis_id": None,
        "title": "Hypothesis",
        "statement": "statement",
        "mechanism": "mechanism",
        "null_hypothesis": "null",
        "minimal_non_null": "minimal",
        "invariants_json": ["frozen history"],
        "baseline_definition_json": {"key": "null"},
        "metric_definition_json": {"key": "objective"},
        "failure_condition_json": {"rule": "no lift"},
        "self_deception_risk_json": ["seed"],
        "status": status,
        "rejection_scope": "none",
        "rejection_reason": None,
        "reopen_condition": None,
        "created_at": NOW,
        "updated_at": NOW,
        "preregistered_at": None,
        "started_at": None,
        "resolved_at": None,
        "metadata_json": {},
    }


class Result:
    def __init__(self, row=None, rows=None) -> None:
        self.row = row
        self.rows = rows if rows is not None else ([] if row is None else [row])

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class ScriptedConnection:
    def __init__(self, *, fail_decision: bool = False) -> None:
        self.fail_decision = fail_decision
        self.statements: list[tuple[str, object]] = []
        self.committed = False
        self.rolled_back = False

    def cursor(self, row_factory=None):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type:
            self.rolled_back = True
        else:
            self.committed = True
        return False

    def execute(self, sql, params=None):
        compact = " ".join(sql.split())
        self.statements.append((compact, params))
        if compact.startswith("SELECT * FROM research_hypotheses"):
            return Result(hypothesis_row())
        if compact.startswith("UPDATE research_hypotheses"):
            row = hypothesis_row("preregistered")
            row["preregistered_at"] = NOW
            return Result(row)
        if compact.startswith("INSERT INTO research_hypothesis_decisions"):
            if self.fail_decision:
                raise RuntimeError("decision write failed")
            return Result()
        return Result()


def repository(connection: ScriptedConnection) -> HypothesisRepository:
    @contextmanager
    def factory():
        with connection:
            yield connection

    return HypothesisRepository(factory)  # type: ignore[arg-type]


def test_transition_and_decision_share_one_transaction() -> None:
    connection = ScriptedConnection()

    result = repository(connection).transition_hypothesis(
        hypothesis_key="hypothesis-1",
        new_status=HypothesisStatus.PREREGISTERED,
        decision_code="preregistered",
        summary="complete",
        decided_by="human:test",
    )

    assert result.status == HypothesisStatus.PREREGISTERED
    assert connection.committed is True
    status_update = next(
        index for index, (sql, _) in enumerate(connection.statements) if sql.startswith("UPDATE research_hypotheses")
    )
    decision_insert = next(
        index
        for index, (sql, _) in enumerate(connection.statements)
        if sql.startswith("INSERT INTO research_hypothesis_decisions")
    )
    assert status_update < decision_insert
    assert any("set_config('dehps.registry_status_transition'" in sql for sql, _ in connection.statements)


def test_decision_failure_rolls_back_status_transition() -> None:
    connection = ScriptedConnection(fail_decision=True)

    with pytest.raises(RuntimeError, match="decision write failed"):
        repository(connection).transition_hypothesis(
            hypothesis_key="hypothesis-1",
            new_status=HypothesisStatus.PREREGISTERED,
            decision_code="preregistered",
            summary="complete",
            decided_by="human:test",
        )

    assert connection.rolled_back is True
    assert connection.committed is False
