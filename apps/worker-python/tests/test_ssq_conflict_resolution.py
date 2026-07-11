from datetime import datetime, timezone

import pytest

from dehps.crawler.ssq_conflict_resolution import (
    SsqConflictResolutionError,
    resolve_ssq_data_conflict,
)


class FakeResult:
    def __init__(self, *, one=None, all_rows=None):
        self.one = one
        self.all_rows = all_rows or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.all_rows


class FakeConn:
    def __init__(self, *, conflict, canonical, resolved_ids=(7,)):
        self.conflict = conflict
        self.canonical = canonical
        self.resolved_ids = resolved_ids
        self.history_update = None
        self.resolution_update = None

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        if normalized.startswith("ALTER TABLE ssq_data_conflicts"):
            return FakeResult()
        if normalized.startswith("SELECT issue, existing_red_numbers"):
            return FakeResult(one=self.conflict)
        if normalized.startswith("SELECT red_numbers, blue_number FROM ssq_history"):
            return FakeResult(one=self.canonical)
        if normalized.startswith("UPDATE ssq_history"):
            self.history_update = params
            return FakeResult()
        if normalized.startswith("UPDATE ssq_data_conflicts"):
            self.resolution_update = params
            return FakeResult(all_rows=[(row_id,) for row_id in self.resolved_ids])
        raise AssertionError(f"unexpected SQL: {normalized}")


EXISTING_RED = [1, 2, 3, 4, 5, 6]
INCOMING_RED = [1, 2, 3, 4, 5, 7]


def conflict_row(*, resolved_at=None, existing_red=EXISTING_RED):
    return (
        "2026078",
        existing_red,
        INCOMING_RED,
        8,
        9,
        "zhcw",
        resolved_at,
    )


def resolve(conn, *, action="existing"):
    return resolve_ssq_data_conflict(
        conn,
        conflict_id=7,
        action=action,
        resolution_note="checked against official announcement",
        resolved_by="operator@example.com",
    )


def test_accept_existing_preserves_canonical_and_resolves_duplicate_evidence():
    conn = FakeConn(
        conflict=conflict_row(),
        canonical=(EXISTING_RED, 8),
        resolved_ids=(7, 8),
    )

    result = resolve(conn)

    assert result["resolved_conflict_ids"] == [7, 8]
    assert result["canonical_updated"] is False
    assert result["resolved_red_numbers"] == EXISTING_RED
    assert conn.history_update is None
    assert conn.resolution_update[0] == "existing"
    assert conn.resolution_update[5] == "2026078"


def test_accept_incoming_updates_canonical_then_preserves_conflict_evidence():
    conn = FakeConn(conflict=conflict_row(), canonical=(EXISTING_RED, 8))

    result = resolve(conn, action="incoming")

    assert result["canonical_updated"] is True
    assert result["resolved_red_numbers"] == INCOMING_RED
    assert conn.history_update == (
        INCOMING_RED,
        *INCOMING_RED,
        9,
        "zhcw",
        "2026078",
    )
    assert conn.resolution_update[0] == "incoming"


def test_rejects_resolution_when_canonical_changed_to_third_state():
    conn = FakeConn(
        conflict=conflict_row(),
        canonical=([2, 3, 4, 5, 6, 7], 10),
    )

    with pytest.raises(SsqConflictResolutionError, match="canonical_changed_outside_conflict"):
        resolve(conn, action="incoming")

    assert conn.history_update is None
    assert conn.resolution_update is None


def test_rejects_already_resolved_conflict():
    conn = FakeConn(
        conflict=conflict_row(resolved_at=datetime.now(timezone.utc)),
        canonical=(EXISTING_RED, 8),
    )

    with pytest.raises(SsqConflictResolutionError, match="conflict_already_resolved"):
        resolve(conn)


def test_rejects_malformed_conflict_numbers_before_update():
    conn = FakeConn(
        conflict=conflict_row(existing_red=[1, 2, 3, 4, 5]),
        canonical=(EXISTING_RED, 8),
    )

    with pytest.raises(SsqConflictResolutionError, match="invalid_existing_red_numbers"):
        resolve(conn)

    assert conn.history_update is None
    assert conn.resolution_update is None


@pytest.mark.parametrize(
    ("note", "actor", "expected"),
    [
        ("", "operator", "resolution_note_required"),
        ("checked", "", "resolved_by_required"),
    ],
)
def test_requires_human_audit_metadata(note, actor, expected):
    conn = FakeConn(conflict=conflict_row(), canonical=(EXISTING_RED, 8))

    with pytest.raises(SsqConflictResolutionError, match=expected):
        resolve_ssq_data_conflict(
            conn,
            conflict_id=7,
            action="existing",
            resolution_note=note,
            resolved_by=actor,
        )
