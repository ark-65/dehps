from pathlib import Path

from dehps.research.status import (
    EvidenceDirection,
    ExperimentStatus,
    HypothesisFamilyStatus,
    HypothesisStatus,
    RejectionScope,
)
from dehps.storage.postgres_store import ensure_hypothesis_registry_schema


class RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(sql)


def test_init_schema_defines_five_registry_tables_and_guards() -> None:
    sql = (Path(__file__).resolve().parents[3] / "infra/postgres/init/001_init.sql").read_text()

    for table in (
        "research_hypothesis_families",
        "research_hypotheses",
        "research_hypothesis_experiments",
        "research_hypothesis_evidence",
        "research_hypothesis_decisions",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "ON DELETE RESTRICT" in sql
    assert "research_hypothesis_decisions_immutable" in sql
    assert "research_hypotheses_status_guard" in sql
    assert "uq_research_hypothesis_evidence_content" in sql


def test_compatibility_schema_uses_same_registry_ddl() -> None:
    connection = RecordingConnection()

    ensure_hypothesis_registry_schema(connection)  # type: ignore[arg-type]

    assert len(connection.statements) == 1
    sql = connection.statements[0]
    assert sql.startswith("CREATE TABLE IF NOT EXISTS research_hypothesis_families")
    assert "CREATE TABLE IF NOT EXISTS research_hypothesis_decisions" in sql
    assert "INSERT INTO dehps_strategies" not in sql


def test_domain_status_values_match_database_contract() -> None:
    assert {value.value for value in HypothesisStatus} == {
        "proposed",
        "preregistered",
        "running",
        "accepted_for_followup",
        "rejected",
        "inconclusive",
        "invalidated",
    }
    assert {value.value for value in HypothesisFamilyStatus} == {
        "active",
        "partially_rejected",
        "rejected",
        "exhausted",
        "reopened",
    }
    assert {value.value for value in ExperimentStatus} == {
        "planned",
        "running",
        "completed",
        "failed",
        "invalidated",
        "cancelled",
    }
    assert {value.value for value in RejectionScope} == {
        "none",
        "parameter_region",
        "mechanism_family",
    }
    assert {value.value for value in EvidenceDirection} == {
        "supporting",
        "contradicting",
        "neutral",
        "invalidating",
    }
