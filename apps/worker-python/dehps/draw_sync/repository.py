from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.draw_sync.models import (
    DrawIssueEventStatus,
    DrawSyncResult,
    NewIssueAvailableEvent,
    jsonable,
)
from dehps.storage.postgres_store import ensure_draw_sync_schema


ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]


def _json(value: object) -> str:
    return json.dumps(jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


class DrawSyncRepository:
    def __init__(self, connection_factory: ConnectionFactory = get_connection) -> None:
        self.connection_factory = connection_factory

    def ensure_schema(self) -> None:
        with self.connection_factory() as conn:
            ensure_draw_sync_schema(conn)

    def latest_issue(self) -> str | None:
        with self.connection_factory() as conn:
            row = conn.execute("SELECT max(issue) FROM ssq_history").fetchone()
        return str(row[0]) if row and row[0] is not None else None

    def load_audit_draws(self) -> tuple[tuple[str, tuple[int, ...], int | None], ...]:
        with self.connection_factory() as conn:
            rows = conn.execute(
                "SELECT issue, red_numbers, blue_number FROM ssq_history ORDER BY issue"
            ).fetchall()
        return tuple((str(row[0]), tuple(int(n) for n in row[1]), None if row[2] is None else int(row[2])) for row in rows)

    def record_run(self, result: DrawSyncResult) -> DrawSyncResult:
        with self.connection_factory() as conn:
            ensure_draw_sync_schema(conn)
            conn.execute(
                """
                INSERT INTO draw_sync_runs (
                  run_key, started_at, completed_at, status, previous_latest_issue,
                  current_latest_issue, inserted_issues_json, updated_issues_json,
                  audit_passed, fingerprint_before, fingerprint_after, event_key,
                  warnings_json, error_json, metadata_json
                ) VALUES (
                  %s, COALESCE(%s, now()), COALESCE(%s, now()), %s, %s, %s,
                  %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb
                )
                ON CONFLICT (run_key) DO NOTHING
                """,
                (
                    result.run_key,
                    result.started_at,
                    result.completed_at,
                    result.status.value,
                    result.previous_latest_issue,
                    result.current_latest_issue,
                    _json(result.inserted_issues),
                    _json(result.updated_issues),
                    result.audit_passed,
                    result.history_fingerprint_before,
                    result.history_fingerprint_after,
                    result.event_key,
                    _json(result.warnings),
                    _json(result.error or {}),
                    _json({"source": result.source, "audit_report_hash": result.audit_report_hash}),
                ),
            )
        return result

    def upsert_event(self, event: NewIssueAvailableEvent) -> NewIssueAvailableEvent:
        with self.connection_factory() as conn:
            ensure_draw_sync_schema(conn)
            conn.execute(
                """
                INSERT INTO draw_issue_events (
                  event_key, previous_issue, new_issue, history_fingerprint,
                  audit_report_hash, source, status, synced_at, metadata_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (event_key) DO NOTHING
                """,
                (
                    event.event_key,
                    event.previous_issue,
                    event.new_issue,
                    event.history_fingerprint,
                    event.audit_report_hash,
                    event.source,
                    event.status.value,
                    event.synced_at,
                    _json({}),
                ),
            )
        return event

    def list_events(
        self,
        *,
        status: DrawIssueEventStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value)
        where = "" if not clauses else "WHERE " + " AND ".join(clauses)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"""
                SELECT *
                FROM draw_issue_events
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_event(self) -> dict[str, Any] | None:
        events = self.list_events(limit=1)
        return events[0] if events else None

    def list_runs(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT *
                FROM draw_sync_runs
                ORDER BY started_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def status(self) -> dict[str, Any]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            ensure_draw_sync_schema(conn)
            latest_run = cursor.execute(
                "SELECT * FROM draw_sync_runs ORDER BY started_at DESC, id DESC LIMIT 1"
            ).fetchone()
            latest_event = cursor.execute(
                "SELECT * FROM draw_issue_events ORDER BY created_at DESC, id DESC LIMIT 1"
            ).fetchone()
            pending = cursor.execute(
                "SELECT count(*)::int AS count FROM draw_issue_events WHERE status = 'pending'"
            ).fetchone()
        return {
            "latest_run": dict(latest_run) if latest_run else None,
            "latest_event": dict(latest_event) if latest_event else None,
            "pending_event_count": int(pending["count"] if pending else 0),
        }
