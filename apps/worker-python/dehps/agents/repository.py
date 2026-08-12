from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg import Connection
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.rows import dict_row

from dehps.agents.decisions import AgentRequestDecision
from dehps.agents.errors import AgentRequestConflictError, AgentRequestNotFoundError
from dehps.agents.requests import (
    AgentExecutionStatus,
    AgentRequest,
    AgentRequestExecution,
    AgentRequestStatus,
    AgentRequestType,
    AgentRiskLevel,
)
from dehps.agents.roles import AgentRole
from dehps.db import get_connection
from dehps.storage.postgres_store import ensure_agent_authority_schema

ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]
REQUEST_METADATA_COLUMNS = """
id, request_key, request_type, requested_by_role, requested_by,
hypothesis_id, experiment_id, parent_request_id, title, summary, status,
risk_level, requires_review, created_at, updated_at, submitted_at, resolved_at,
metadata_json
"""
EXECUTION_METADATA_COLUMNS = """
id, request_id, executor_role, executor_id, execution_type, status,
environment, run_id, started_at, completed_at, created_at
"""


@dataclass(frozen=True)
class AgentRequestExecutionMetadata:
    id: int
    request_id: int
    executor_role: AgentRole
    executor_id: str
    execution_type: str
    status: AgentExecutionStatus
    environment: str
    run_id: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
TERMINAL_REQUEST_STATUSES = frozenset(
    {
        AgentRequestStatus.REJECTED,
        AgentRequestStatus.CANCELLED,
        AgentRequestStatus.COMPLETED,
        AgentRequestStatus.FAILED,
        AgentRequestStatus.INVALIDATED,
    }
)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _request(row: Mapping[str, Any]) -> AgentRequest:
    return AgentRequest(
        id=int(row["id"]),
        request_key=str(row["request_key"]),
        request_type=AgentRequestType(row["request_type"]),
        requested_by_role=AgentRole(row["requested_by_role"]),
        requested_by=str(row["requested_by"]),
        hypothesis_id=None if row.get("hypothesis_id") is None else int(row["hypothesis_id"]),
        experiment_id=None if row.get("experiment_id") is None else int(row["experiment_id"]),
        parent_request_id=(
            None if row.get("parent_request_id") is None else int(row["parent_request_id"])
        ),
        title=str(row["title"]),
        summary=str(row["summary"]),
        payload=dict(row.get("payload_json") or {}),
        status=AgentRequestStatus(row["status"]),
        risk_level=AgentRiskLevel(row["risk_level"]),
        requires_review=bool(row["requires_review"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        submitted_at=row.get("submitted_at"),
        resolved_at=row.get("resolved_at"),
        metadata=dict(row.get("metadata_json") or {}),
    )


def _decision(row: Mapping[str, Any]) -> AgentRequestDecision:
    return AgentRequestDecision(
        id=int(row["id"]),
        request_id=int(row["request_id"]),
        previous_status=str(row["previous_status"]),
        new_status=str(row["new_status"]),
        decision_code=str(row["decision_code"]),
        summary=str(row["summary"]),
        reason=dict(row.get("reason_json") or {}),
        decided_by_role=AgentRole(row["decided_by_role"]),
        decided_by=str(row["decided_by"]),
        decided_at=row["decided_at"],
        created_at=row["created_at"],
    )


def _execution(row: Mapping[str, Any]) -> AgentRequestExecution:
    return AgentRequestExecution(
        id=int(row["id"]),
        request_id=int(row["request_id"]),
        executor_role=AgentRole(row["executor_role"]),
        executor_id=str(row["executor_id"]),
        execution_type=str(row["execution_type"]),
        status=AgentExecutionStatus(row["status"]),
        environment=str(row["environment"]),
        run_id=row.get("run_id"),
        started_at=row["started_at"],
        completed_at=row.get("completed_at"),
        result=dict(row.get("result_json") or {}),
        artifact_paths=list(row.get("artifact_paths_json") or []),
        error=dict(row.get("error_json") or {}),
        created_at=row["created_at"],
    )


def _execution_metadata(row: Mapping[str, Any]) -> AgentRequestExecutionMetadata:
    return AgentRequestExecutionMetadata(
        id=int(row["id"]),
        request_id=int(row["request_id"]),
        executor_role=AgentRole(row["executor_role"]),
        executor_id=str(row["executor_id"]),
        execution_type=str(row["execution_type"]),
        status=AgentExecutionStatus(row["status"]),
        environment=str(row["environment"]),
        run_id=row.get("run_id"),
        started_at=row["started_at"],
        completed_at=row.get("completed_at"),
        created_at=row["created_at"],
    )


class AgentRequestRepository:
    def __init__(self, connection_factory: ConnectionFactory = get_connection) -> None:
        self._connection_factory = connection_factory

    def ensure_schema(self) -> None:
        with self._connection_factory() as conn:
            ensure_agent_authority_schema(conn)

    def create_draft(
        self,
        *,
        request_key: str,
        request_type: AgentRequestType,
        requested_by_role: AgentRole,
        requested_by: str,
        title: str,
        summary: str,
        payload: Mapping[str, Any],
        risk_level: AgentRiskLevel,
        requires_review: bool,
        hypothesis_key: str | None = None,
        experiment_key: str | None = None,
        parent_request_key: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> AgentRequest:
        try:
            with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
                hypothesis_id, experiment_id = self._resolve_research_links(
                    cursor,
                    hypothesis_key=hypothesis_key,
                    experiment_key=experiment_key,
                )
                parent_request_id = self._resolve_parent(cursor, parent_request_key)
                row = cursor.execute(
                    """
                    INSERT INTO agent_requests (
                      request_key, request_type, requested_by_role, requested_by,
                      hypothesis_id, experiment_id, parent_request_id, title, summary,
                      payload_json, risk_level, requires_review, metadata_json
                    ) VALUES (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb
                    ) RETURNING *
                    """,
                    (
                        request_key,
                        request_type.value,
                        requested_by_role.value,
                        requested_by,
                        hypothesis_id,
                        experiment_id,
                        parent_request_id,
                        title,
                        summary,
                        _json(dict(payload)),
                        risk_level.value,
                        requires_review,
                        _json(dict(metadata or {})),
                    ),
                ).fetchone()
        except UniqueViolation as exc:
            raise AgentRequestConflictError(f"request key already exists: {request_key}") from exc
        except ForeignKeyViolation as exc:
            raise AgentRequestConflictError("request references a missing record") from exc
        assert row is not None
        return _request(row)

    def get_request(self, request_key: str) -> AgentRequest:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                "SELECT * FROM agent_requests WHERE request_key = %s",
                (request_key,),
            ).fetchone()
        if row is None:
            raise AgentRequestNotFoundError(f"agent request not found: {request_key}")
        return _request(row)

    def get_request_contract(
        self,
        request_key: str,
        *,
        include_payload: bool,
    ) -> Mapping[str, Any]:
        """Read one request from one table with an auditable payload boundary."""
        columns = REQUEST_METADATA_COLUMNS
        if include_payload:
            columns = f"{columns}, payload_json"
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                f"SELECT {columns} FROM agent_requests WHERE request_key = %s",
                (request_key,),
            ).fetchone()
        if row is None:
            raise AgentRequestNotFoundError(f"agent request not found: {request_key}")
        return dict(row)

    def list_decision_metadata(self, request_key: str) -> list[Mapping[str, Any]]:
        """Return decision audit metadata without selecting reason_json."""
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            request_id = self._request_id(cursor, request_key)
            rows = cursor.execute(
                """
                SELECT id, request_id, previous_status, new_status, decision_code,
                       summary, decided_by_role, decided_by, decided_at, created_at
                FROM agent_request_decisions
                WHERE request_id = %s ORDER BY decided_at, id
                """,
                (request_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_execution_metadata(
        self,
        request_key: str,
    ) -> list[AgentRequestExecutionMetadata]:
        """Return execution identity/state without touching result-bearing columns."""
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            request_id = self._request_id(cursor, request_key)
            rows = cursor.execute(
                f"""
                SELECT {EXECUTION_METADATA_COLUMNS}
                FROM agent_request_executions
                WHERE request_id = %s ORDER BY started_at, id
                """,
                (request_id,),
            ).fetchall()
        return [_execution_metadata(row) for row in rows]

    def get_execution_metadata(
        self,
        request_key: str,
        execution_id: int,
    ) -> AgentRequestExecutionMetadata:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            request_id = self._request_id(cursor, request_key)
            row = cursor.execute(
                f"""
                SELECT {EXECUTION_METADATA_COLUMNS}
                FROM agent_request_executions
                WHERE id = %s AND request_id = %s
                """,
                (execution_id, request_id),
            ).fetchone()
        if row is None:
            raise AgentRequestNotFoundError(f"execution not found: {execution_id}")
        return _execution_metadata(row)

    def list_requests(
        self,
        *,
        status: AgentRequestStatus | None = None,
        request_type: AgentRequestType | None = None,
        requested_by_role: AgentRole | None = None,
        risk_level: AgentRiskLevel | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AgentRequest]:
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("status", status),
            ("request_type", request_type),
            ("requested_by_role", requested_by_role),
            ("risk_level", risk_level),
        ):
            if value is not None:
                clauses.append(f"{column} = %s")
                params.append(value.value)
        if created_after is not None:
            clauses.append("created_at >= %s")
            params.append(created_after)
        if created_before is not None:
            clauses.append("created_at <= %s")
            params.append(created_before)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"SELECT * FROM agent_requests {where} "
                "ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
                tuple(params),
            ).fetchall()
        return [_request(row) for row in rows]

    def update_payload(
        self,
        *,
        request_key: str,
        payload: Mapping[str, Any],
    ) -> AgentRequest:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                UPDATE agent_requests
                SET payload_json = %s::jsonb, updated_at = now()
                WHERE request_key = %s AND status = 'draft'
                RETURNING *
                """,
                (_json(dict(payload)), request_key),
            ).fetchone()
        if row is None:
            existing = self.get_request(request_key)
            raise AgentRequestConflictError(
                f"request payload is frozen in status {existing.status.value}"
            )
        return _request(row)

    def transition(
        self,
        *,
        request_key: str,
        expected_status: AgentRequestStatus,
        new_status: AgentRequestStatus,
        decision_code: str,
        summary: str,
        reason: Mapping[str, Any],
        decided_by_role: AgentRole,
        decided_by: str,
    ) -> AgentRequest:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = self._locked_request(cursor, request_key)
            current = AgentRequestStatus(row["status"])
            if current != expected_status:
                raise AgentRequestConflictError(
                    f"request status changed: expected {expected_status.value}, found {current.value}"
                )
            updated = self._transition_row(
                cursor,
                row=row,
                new_status=new_status,
                decision_code=decision_code,
                summary=summary,
                reason=reason,
                decided_by_role=decided_by_role,
                decided_by=decided_by,
            )
        return _request(updated)

    def begin_execution(
        self,
        *,
        request_key: str,
        executor_role: AgentRole,
        executor_id: str,
        execution_type: str,
        environment: str,
        run_id: str | None,
    ) -> tuple[AgentRequest, AgentRequestExecution]:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = self._locked_request(cursor, request_key)
            if AgentRequestStatus(row["status"]) != AgentRequestStatus.APPROVED:
                raise AgentRequestConflictError("only approved requests can begin execution")
            execution_row = cursor.execute(
                """
                INSERT INTO agent_request_executions (
                  request_id, executor_role, executor_id, execution_type, environment, run_id
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (row["id"], executor_role.value, executor_id, execution_type, environment, run_id),
            ).fetchone()
            updated = self._transition_row(
                cursor,
                row=row,
                new_status=AgentRequestStatus.EXECUTING,
                decision_code="execution_started",
                summary="approved request execution started",
                reason={"environment": environment, "execution_type": execution_type, "run_id": run_id},
                decided_by_role=executor_role,
                decided_by=executor_id,
            )
        assert execution_row is not None
        return _request(updated), _execution(execution_row)

    def begin_execution_metadata(
        self,
        *,
        request_key: str,
        executor_role: AgentRole,
        executor_id: str,
        execution_type: str,
        environment: str,
        run_id: str | None,
    ) -> tuple[AgentRequest, AgentRequestExecutionMetadata]:
        """Start an execution without selecting result/error/artifact columns."""
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = self._locked_request(cursor, request_key)
            if AgentRequestStatus(row["status"]) != AgentRequestStatus.APPROVED:
                raise AgentRequestConflictError("only approved requests can begin execution")
            execution_row = cursor.execute(
                f"""
                INSERT INTO agent_request_executions (
                  request_id, executor_role, executor_id, execution_type, environment, run_id
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING {EXECUTION_METADATA_COLUMNS}
                """,
                (row["id"], executor_role.value, executor_id, execution_type, environment, run_id),
            ).fetchone()
            updated = self._transition_row(
                cursor,
                row=row,
                new_status=AgentRequestStatus.EXECUTING,
                decision_code="execution_started",
                summary="approved request execution started",
                reason={"environment": environment, "execution_type": execution_type, "run_id": run_id},
                decided_by_role=executor_role,
                decided_by=executor_id,
            )
        assert execution_row is not None
        return _request(updated), _execution_metadata(execution_row)

    def finish_execution(
        self,
        *,
        request_key: str,
        execution_id: int,
        executor_role: AgentRole,
        executor_id: str,
        execution_status: AgentExecutionStatus,
        request_status: AgentRequestStatus,
        result: Mapping[str, Any],
        artifact_paths: list[str],
        error: Mapping[str, Any],
    ) -> tuple[AgentRequest, AgentRequestExecution]:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = self._locked_request(cursor, request_key)
            if AgentRequestStatus(row["status"]) != AgentRequestStatus.EXECUTING:
                raise AgentRequestConflictError("request is not executing")
            execution_row = cursor.execute(
                """
                SELECT * FROM agent_request_executions
                WHERE id = %s AND request_id = %s FOR UPDATE
                """,
                (execution_id, row["id"]),
            ).fetchone()
            if execution_row is None:
                raise AgentRequestNotFoundError(f"execution not found: {execution_id}")
            if AgentExecutionStatus(execution_row["status"]) != AgentExecutionStatus.RUNNING:
                raise AgentRequestConflictError("execution is not running")
            if execution_row["executor_role"] != executor_role.value or execution_row["executor_id"] != executor_id:
                raise AgentRequestConflictError("execution may only be finished by its recorded executor")
            finished_execution = cursor.execute(
                """
                UPDATE agent_request_executions
                SET status = %s, completed_at = now(), result_json = %s::jsonb,
                    artifact_paths_json = %s::jsonb, error_json = %s::jsonb
                WHERE id = %s
                RETURNING *
                """,
                (
                    execution_status.value,
                    _json(dict(result)),
                    _json(list(artifact_paths)),
                    _json(dict(error)),
                    execution_id,
                ),
            ).fetchone()
            updated = self._transition_row(
                cursor,
                row=row,
                new_status=request_status,
                decision_code=f"execution_{execution_status.value}",
                summary=f"request execution {execution_status.value}",
                reason={"execution_id": execution_id, "error": dict(error)},
                decided_by_role=executor_role,
                decided_by=executor_id,
            )
        assert finished_execution is not None
        return _request(updated), _execution(finished_execution)

    def finish_execution_metadata(
        self,
        *,
        request_key: str,
        execution_id: int,
        executor_role: AgentRole,
        executor_id: str,
        execution_status: AgentExecutionStatus,
        request_status: AgentRequestStatus,
        result: Mapping[str, Any],
        artifact_paths: list[str],
        error: Mapping[str, Any],
    ) -> tuple[AgentRequest, AgentRequestExecutionMetadata]:
        """Finish via parameterized writes while never reading sensitive payload columns."""
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = self._locked_request(cursor, request_key)
            if AgentRequestStatus(row["status"]) != AgentRequestStatus.EXECUTING:
                raise AgentRequestConflictError("request is not executing")
            execution_row = cursor.execute(
                f"""
                SELECT {EXECUTION_METADATA_COLUMNS}
                FROM agent_request_executions
                WHERE id = %s AND request_id = %s FOR UPDATE
                """,
                (execution_id, row["id"]),
            ).fetchone()
            if execution_row is None:
                raise AgentRequestNotFoundError(f"execution not found: {execution_id}")
            if AgentExecutionStatus(execution_row["status"]) != AgentExecutionStatus.RUNNING:
                raise AgentRequestConflictError("execution is not running")
            if (
                execution_row["executor_role"] != executor_role.value
                or execution_row["executor_id"] != executor_id
            ):
                raise AgentRequestConflictError(
                    "execution may only be finished by its recorded executor"
                )
            finished_execution = cursor.execute(
                f"""
                UPDATE agent_request_executions
                SET status = %s, completed_at = now(), result_json = %s::jsonb,
                    artifact_paths_json = %s::jsonb, error_json = %s::jsonb
                WHERE id = %s
                RETURNING {EXECUTION_METADATA_COLUMNS}
                """,
                (
                    execution_status.value,
                    _json(dict(result)),
                    _json(list(artifact_paths)),
                    _json(dict(error)),
                    execution_id,
                ),
            ).fetchone()
            updated = self._transition_row(
                cursor,
                row=row,
                new_status=request_status,
                decision_code=f"execution_{execution_status.value}",
                summary=f"request execution {execution_status.value}",
                reason={"execution_id": execution_id, "has_error": bool(error)},
                decided_by_role=executor_role,
                decided_by=executor_id,
            )
        assert finished_execution is not None
        return _request(updated), _execution_metadata(finished_execution)

    def stop_active_execution(
        self,
        *,
        request_key: str,
        request_status: AgentRequestStatus,
        decided_by_role: AgentRole,
        decided_by: str,
        decision_code: str,
        summary: str,
        reason: Mapping[str, Any],
    ) -> tuple[AgentRequest, AgentRequestExecution]:
        if request_status not in {AgentRequestStatus.CANCELLED, AgentRequestStatus.INVALIDATED}:
            raise AgentRequestConflictError("active execution can only be cancelled or invalidated")
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = self._locked_request(cursor, request_key)
            if AgentRequestStatus(row["status"]) != AgentRequestStatus.EXECUTING:
                raise AgentRequestConflictError("request is not executing")
            execution_row = cursor.execute(
                """
                SELECT * FROM agent_request_executions
                WHERE request_id = %s AND status = 'running'
                ORDER BY started_at DESC, id DESC
                LIMIT 1 FOR UPDATE
                """,
                (row["id"],),
            ).fetchone()
            if execution_row is None:
                raise AgentRequestConflictError("executing request has no running execution")
            stopped_execution = cursor.execute(
                """
                UPDATE agent_request_executions
                SET status = 'cancelled', completed_at = now(), error_json = %s::jsonb
                WHERE id = %s
                RETURNING *
                """,
                (_json({"stopped_by": decided_by, "reason": dict(reason)}), execution_row["id"]),
            ).fetchone()
            updated = self._transition_row(
                cursor,
                row=row,
                new_status=request_status,
                decision_code=decision_code,
                summary=summary,
                reason={**dict(reason), "execution_id": int(execution_row["id"])},
                decided_by_role=decided_by_role,
                decided_by=decided_by,
            )
        assert stopped_execution is not None
        return _request(updated), _execution(stopped_execution)

    def list_decisions(self, request_key: str) -> list[AgentRequestDecision]:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            request_id = self._request_id(cursor, request_key)
            rows = cursor.execute(
                """
                SELECT * FROM agent_request_decisions
                WHERE request_id = %s ORDER BY decided_at, id
                """,
                (request_id,),
            ).fetchall()
        return [_decision(row) for row in rows]

    def list_executions(self, request_key: str) -> list[AgentRequestExecution]:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            request_id = self._request_id(cursor, request_key)
            rows = cursor.execute(
                """
                SELECT * FROM agent_request_executions
                WHERE request_id = %s ORDER BY started_at, id
                """,
                (request_id,),
            ).fetchall()
        return [_execution(row) for row in rows]

    @staticmethod
    def _resolve_research_links(
        cursor: Any,
        *,
        hypothesis_key: str | None,
        experiment_key: str | None,
    ) -> tuple[int | None, int | None]:
        hypothesis_id: int | None = None
        experiment_id: int | None = None
        if hypothesis_key:
            row = cursor.execute(
                "SELECT id FROM research_hypotheses WHERE hypothesis_key = %s",
                (hypothesis_key,),
            ).fetchone()
            if row is None:
                raise AgentRequestNotFoundError(f"hypothesis not found: {hypothesis_key}")
            hypothesis_id = int(row["id"])
        if experiment_key:
            row = cursor.execute(
                "SELECT id, hypothesis_id FROM research_hypothesis_experiments WHERE experiment_key = %s",
                (experiment_key,),
            ).fetchone()
            if row is None:
                raise AgentRequestNotFoundError(f"experiment not found: {experiment_key}")
            experiment_id = int(row["id"])
            if hypothesis_id is None:
                hypothesis_id = int(row["hypothesis_id"])
            elif hypothesis_id != int(row["hypothesis_id"]):
                raise AgentRequestConflictError("experiment does not belong to the linked hypothesis")
        return hypothesis_id, experiment_id

    @staticmethod
    def _resolve_parent(cursor: Any, request_key: str | None) -> int | None:
        if request_key is None:
            return None
        row = cursor.execute(
            "SELECT id FROM agent_requests WHERE request_key = %s",
            (request_key,),
        ).fetchone()
        if row is None:
            raise AgentRequestNotFoundError(f"parent request not found: {request_key}")
        return int(row["id"])

    @staticmethod
    def _locked_request(cursor: Any, request_key: str) -> Mapping[str, Any]:
        row = cursor.execute(
            "SELECT * FROM agent_requests WHERE request_key = %s FOR UPDATE",
            (request_key,),
        ).fetchone()
        if row is None:
            raise AgentRequestNotFoundError(f"agent request not found: {request_key}")
        return row

    @staticmethod
    def _request_id(cursor: Any, request_key: str) -> int:
        row = cursor.execute(
            "SELECT id FROM agent_requests WHERE request_key = %s",
            (request_key,),
        ).fetchone()
        if row is None:
            raise AgentRequestNotFoundError(f"agent request not found: {request_key}")
        return int(row["id"])

    @staticmethod
    def _transition_row(
        cursor: Any,
        *,
        row: Mapping[str, Any],
        new_status: AgentRequestStatus,
        decision_code: str,
        summary: str,
        reason: Mapping[str, Any],
        decided_by_role: AgentRole,
        decided_by: str,
    ) -> Mapping[str, Any]:
        previous_status = AgentRequestStatus(row["status"])
        cursor.execute("SELECT set_config('dehps.agent_request_status_transition', 'allowed', true)")
        submitted_at_sql = "COALESCE(submitted_at, now())" if new_status == AgentRequestStatus.SUBMITTED else "submitted_at"
        resolved_at_sql = "now()" if new_status in TERMINAL_REQUEST_STATUSES else "NULL"
        updated = cursor.execute(
            f"""
            UPDATE agent_requests
            SET status = %s, updated_at = now(),
                submitted_at = {submitted_at_sql}, resolved_at = {resolved_at_sql}
            WHERE id = %s
            RETURNING *
            """,
            (new_status.value, row["id"]),
        ).fetchone()
        cursor.execute(
            """
            INSERT INTO agent_request_decisions (
              request_id, previous_status, new_status, decision_code, summary,
              reason_json, decided_by_role, decided_by
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            (
                row["id"],
                previous_status.value,
                new_status.value,
                decision_code,
                summary,
                _json(dict(reason)),
                decided_by_role.value,
                decided_by,
            ),
        )
        assert updated is not None
        return updated
