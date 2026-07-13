from pathlib import Path

from dehps.agents.requests import (
    AgentExecutionStatus,
    AgentRequestStatus,
    AgentRequestType,
    AgentRiskLevel,
)
from dehps.storage.postgres_store import ensure_agent_authority_schema


class RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(sql)


def test_schema_defines_three_agent_tables_and_database_guards() -> None:
    sql = (Path(__file__).resolve().parents[3] / "infra/postgres/init/001_init.sql").read_text()

    for table in ("agent_requests", "agent_request_decisions", "agent_request_executions"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "agent_request_decisions_immutable" in sql
    assert "approved agent request payload is frozen" in sql
    assert "submitted agent requests cannot be deleted" in sql
    assert "dehps.agent_request_status_transition" in sql
    assert "ON DELETE RESTRICT" in sql


def test_compatibility_schema_applies_round20_then_round21_without_seed_data() -> None:
    connection = RecordingConnection()

    ensure_agent_authority_schema(connection)  # type: ignore[arg-type]

    assert len(connection.statements) == 2
    assert connection.statements[0].startswith("CREATE TABLE IF NOT EXISTS research_hypothesis_families")
    assert connection.statements[1].startswith("CREATE TABLE IF NOT EXISTS agent_requests")
    assert "INSERT INTO dehps_strategies" not in connection.statements[1]


def test_domain_enums_match_database_contract() -> None:
    assert {item.value for item in AgentRequestStatus} == {
        "draft", "submitted", "under_review", "approved", "rejected", "cancelled",
        "executing", "completed", "failed", "invalidated",
    }
    assert {item.value for item in AgentRiskLevel} == {"low", "medium", "high", "critical"}
    assert {item.value for item in AgentExecutionStatus} == {"running", "completed", "failed", "cancelled"}
    assert len(AgentRequestType) == 14
