from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from psycopg.errors import UniqueViolation

from dehps.research.errors import RegistryConflictError
from dehps.research.repository import HypothesisRepository
from dehps.research.status import EvidenceDirection


class Result:
    def __init__(self, row=None) -> None:
        self.row = row

    def fetchone(self):
        return self.row


class DuplicateEvidenceConnection:
    def __init__(self) -> None:
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.rolled_back = exc_type is not None
        return False

    def cursor(self, row_factory=None):
        return self

    def execute(self, sql, params=None):
        compact = " ".join(sql.split())
        if compact.startswith("SELECT id FROM research_hypotheses"):
            return Result({"id": 2})
        if compact.startswith("INSERT INTO research_hypothesis_evidence"):
            raise UniqueViolation("duplicate evidence")
        return Result()


def test_duplicate_content_hash_is_a_domain_conflict_and_rolls_back() -> None:
    connection = DuplicateEvidenceConnection()

    @contextmanager
    def factory():
        with connection:
            yield connection

    repository = HypothesisRepository(factory)  # type: ignore[arg-type]

    with pytest.raises(RegistryConflictError, match="duplicate evidence content hash"):
        repository.add_evidence(
            hypothesis_key="hypothesis-1",
            evidence_type="metric_summary",
            direction=EvidenceDirection.CONTRADICTING,
            summary="same evidence",
            observed_at=datetime(2026, 7, 13, tzinfo=timezone.utc),
            content_hash="a" * 64,
        )

    assert connection.rolled_back is True


def test_schema_deduplicates_by_hypothesis_type_and_hash_not_summary() -> None:
    from pathlib import Path

    sql = (Path(__file__).resolve().parents[3] / "infra/postgres/init/001_init.sql").read_text()
    assert "(hypothesis_id, evidence_type, content_hash)" in sql
    assert "WHERE content_hash IS NOT NULL" in sql
