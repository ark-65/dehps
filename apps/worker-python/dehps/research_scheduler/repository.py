from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any, ContextManager

from psycopg import Connection
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.research_scheduler.state import (
    OpenAgentRequest,
    QueueStatus,
    ResearchAction,
    SchedulerQueueItem,
    TERMINAL_AGENT_REQUEST_STATUSES,
)
from dehps.storage.postgres_store import ensure_research_scheduler_schema


ConnectionFactory = Callable[[], ContextManager[Connection[Any]]]


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _queue_item(row: dict[str, Any]) -> SchedulerQueueItem:
    return SchedulerQueueItem(
        queue_key=str(row["queue_key"]),
        queue_status=QueueStatus(row["queue_status"]),
        action=ResearchAction(row["action"]),
        priority_score=float(row["priority_score"]),
        context_fingerprint=str(row["context_fingerprint"]),
        reason=dict(row.get("reason_json") or {}),
        budget=dict(row.get("budget_json") or {}),
        policy=dict(row.get("policy_json") or {}),
        target_hypothesis_key=row.get("target_hypothesis_key"),
        target_family_key=row.get("target_family_key"),
        target_experiment_key=row.get("target_experiment_key"),
        request_key=row.get("request_key"),
        created_by=str(row["created_by"]),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        completed_at=row.get("completed_at"),
        metadata=dict(row.get("metadata_json") or {}),
    )


def _agent_request(row: dict[str, Any]) -> OpenAgentRequest:
    return OpenAgentRequest(
        request_key=str(row["request_key"]),
        request_type=str(row["request_type"]),
        status=str(row["status"]),
        requested_by_role=str(row["requested_by_role"]),
        requested_by=str(row["requested_by"]),
        title=str(row["title"]),
        created_at=row.get("created_at"),
        metadata=dict(row.get("metadata_json") or {}),
    )


class ResearchSchedulerRepository:
    def __init__(self, connection_factory: ConnectionFactory = get_connection) -> None:
        self.connection_factory = connection_factory

    def ensure_schema(self) -> None:
        with self.connection_factory() as conn:
            ensure_research_scheduler_schema(conn)

    def list_queue(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        open_only: bool = False,
    ) -> list[SchedulerQueueItem]:
        where = "WHERE queue_status NOT IN ('completed', 'blocked')" if open_only else ""
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"""
                SELECT * FROM research_scheduler_queue
                {where}
                ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()
        return [_queue_item(dict(row)) for row in rows]

    def latest_queue_item(self) -> SchedulerQueueItem | None:
        items = self.list_queue(limit=1)
        return items[0] if items else None

    def open_agent_requests(self, *, limit: int = 100) -> list[OpenAgentRequest]:
        terminal = sorted(TERMINAL_AGENT_REQUEST_STATUSES)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT request_key, request_type, status, requested_by_role, requested_by,
                       title, created_at, metadata_json
                FROM agent_requests
                WHERE NOT (status = ANY(%s))
                ORDER BY created_at, id LIMIT %s
                """,
                (terminal, limit),
            ).fetchall()
        return [_agent_request(dict(row)) for row in rows]

    def latest_training_round(self) -> dict[str, Any] | None:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT run_id, round_index, created_at
                FROM training_round_results
                ORDER BY created_at DESC, id DESC LIMIT 1
                """
            ).fetchall()
        return dict(rows[0]) if rows else None

    def count_queue_actions_today(self, action: ResearchAction | None = None) -> int:
        clauses = ["created_at::date = %s"]
        params: list[Any] = [date.today()]
        if action is not None:
            clauses.append("action = %s")
            params.append(action.value)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                f"""
                SELECT count(*)::int AS count
                FROM research_scheduler_queue
                WHERE {' AND '.join(clauses)}
                """,
                tuple(params),
            ).fetchone()
        return int(row["count"] if row else 0)

    def upsert_queue_item(self, item: SchedulerQueueItem) -> SchedulerQueueItem:
        try:
            with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    """
                    INSERT INTO research_scheduler_queue (
                      queue_key, queue_status, action, priority_score, target_hypothesis_key,
                      target_family_key, target_experiment_key, request_key, context_fingerprint,
                      reason_json, budget_json, policy_json, created_by, metadata_json
                    ) VALUES (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb
                    )
                    ON CONFLICT (queue_key) DO UPDATE
                    SET updated_at = now()
                    RETURNING *
                    """,
                    (
                        item.queue_key,
                        item.queue_status.value,
                        item.action.value,
                        item.priority_score,
                        item.target_hypothesis_key,
                        item.target_family_key,
                        item.target_experiment_key,
                        item.request_key,
                        item.context_fingerprint,
                        _json(item.reason),
                        _json(item.budget),
                        _json(item.policy),
                        item.created_by,
                        _json(item.metadata),
                    ),
                ).fetchone()
        except UniqueViolation:
            duplicate = self.find_open_duplicate(
                action=item.action,
                target_hypothesis_key=item.target_hypothesis_key,
                target_family_key=item.target_family_key,
                target_experiment_key=item.target_experiment_key,
            )
            if duplicate is None:
                raise
            return duplicate
        assert row is not None
        return _queue_item(dict(row))

    def attach_request(self, *, queue_key: str, request_key: str) -> SchedulerQueueItem:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                UPDATE research_scheduler_queue
                SET request_key = COALESCE(request_key, %s), updated_at = now()
                WHERE queue_key = %s
                RETURNING *
                """,
                (request_key, queue_key),
            ).fetchone()
        if row is None:
            raise ValueError(f"scheduler queue item not found: {queue_key}")
        return _queue_item(dict(row))

    def complete_queue(self, *, queue_key: str) -> SchedulerQueueItem:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                UPDATE research_scheduler_queue
                SET queue_status = 'completed', completed_at = now(), updated_at = now()
                WHERE queue_key = %s
                RETURNING *
                """,
                (queue_key,),
            ).fetchone()
        if row is None:
            raise ValueError(f"scheduler queue item not found: {queue_key}")
        return _queue_item(dict(row))

    def find_open_duplicate(
        self,
        *,
        action: ResearchAction,
        target_hypothesis_key: str | None,
        target_family_key: str | None,
        target_experiment_key: str | None,
    ) -> SchedulerQueueItem | None:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                SELECT * FROM research_scheduler_queue
                WHERE queue_status NOT IN ('completed', 'blocked')
                  AND action = %s
                  AND COALESCE(target_hypothesis_key, '') = COALESCE(%s, '')
                  AND COALESCE(target_family_key, '') = COALESCE(%s, '')
                  AND COALESCE(target_experiment_key, '') = COALESCE(%s, '')
                ORDER BY created_at, id LIMIT 1
                """,
                (
                    action.value,
                    target_hypothesis_key,
                    target_family_key,
                    target_experiment_key,
                ),
            ).fetchone()
        return None if row is None else _queue_item(dict(row))
