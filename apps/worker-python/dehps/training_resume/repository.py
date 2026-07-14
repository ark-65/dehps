from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.draw_sync.models import jsonable, stable_hash, utc_now
from dehps.storage.postgres_store import ensure_draw_sync_schema


ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]


def _json(value: object) -> str:
    return json.dumps(jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


class TrainingResumeRepository:
    def __init__(self, connection_factory: ConnectionFactory = get_connection) -> None:
        self.connection_factory = connection_factory

    def ensure_schema(self) -> None:
        with self.connection_factory() as conn:
            ensure_draw_sync_schema(conn)

    def claim_event(self, event_key: str) -> dict[str, Any] | None:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                UPDATE draw_issue_events
                SET status = 'consuming'
                WHERE event_key = %s
                  AND status IN ('pending', 'failed')
                RETURNING *
                """,
                (event_key,),
            ).fetchone()
        return dict(row) if row else None

    def mark_event_consumed(self, *, event_key: str, run_id: str) -> None:
        with self.connection_factory() as conn:
            conn.execute(
                """
                UPDATE draw_issue_events
                SET status = 'consumed', consumed_at = now(), consumer_run_id = %s
                WHERE event_key = %s AND status = 'consuming'
                """,
                (run_id, event_key),
            )

    def mark_event_failed(self, *, event_key: str, reason: dict[str, Any]) -> None:
        with self.connection_factory() as conn:
            conn.execute(
                """
                UPDATE draw_issue_events
                SET status = 'failed', metadata_json = metadata_json || %s::jsonb
                WHERE event_key = %s AND status = 'consuming'
                """,
                (_json({"last_failure": reason}), event_key),
            )

    def record_attempt(
        self,
        *,
        event_key: str | None,
        decision: str,
        reason_code: str,
        old_run_id: str | None,
        new_run_id: str | None,
        result: dict[str, Any],
    ) -> str:
        attempt_key = f"training-resume-{stable_hash((event_key, decision, reason_code, new_run_id, utc_now().isoformat()))[:20]}"
        with self.connection_factory() as conn:
            conn.execute(
                """
                INSERT INTO training_resume_attempts (
                  attempt_key, event_key, decision, reason_code, old_run_id,
                  new_run_id, completed_at, result_json
                ) VALUES (%s, %s, %s, %s, %s, %s, now(), %s::jsonb)
                """,
                (attempt_key, event_key, decision, reason_code, old_run_id, new_run_id, _json(result)),
            )
        return attempt_key

    def history(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT *
                FROM training_resume_attempts
                ORDER BY started_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def status(self) -> dict[str, Any]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            ensure_draw_sync_schema(conn)
            latest = cursor.execute(
                "SELECT * FROM training_resume_attempts ORDER BY started_at DESC, id DESC LIMIT 1"
            ).fetchone()
            pending = cursor.execute(
                "SELECT count(*)::int AS count FROM draw_issue_events WHERE status IN ('pending', 'failed')"
            ).fetchone()
        return {
            "latest_attempt": dict(latest) if latest else None,
            "retryable_event_count": int(pending["count"] if pending else 0),
        }
