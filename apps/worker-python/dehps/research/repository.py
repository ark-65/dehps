from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from typing import Any, ContextManager

from psycopg import Connection
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.research.errors import (
    RegistryConflictError,
    RegistryNotFoundError,
    ReopenError,
)
from dehps.research.models import (
    Hypothesis,
    HypothesisDecision,
    HypothesisEvidence,
    HypothesisExperiment,
    HypothesisFamily,
)
from dehps.research.status import (
    ACTIVE_HYPOTHESIS_STATUSES,
    EvidenceDirection,
    ExperimentStatus,
    HypothesisFamilyStatus,
    HypothesisStatus,
    RejectionScope,
)
from dehps.research.transitions import (
    validate_experiment_transition,
    validate_family_reopen,
    validate_family_transition,
    validate_hypothesis_transition,
)
from dehps.storage.postgres_store import ensure_hypothesis_registry_schema


ConnectionFactory = Callable[[], ContextManager[Connection[Any]]]


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _family(row: Mapping[str, Any]) -> HypothesisFamily:
    return HypothesisFamily(
        id=int(row["id"]),
        family_key=str(row["family_key"]),
        title=str(row["title"]),
        description=str(row["description"]),
        mechanism=str(row["mechanism"]),
        status=HypothesisFamilyStatus(row["status"]),
        rejection_scope=RejectionScope(row["rejection_scope"]),
        rejection_reason=row.get("rejection_reason"),
        reopen_condition=row.get("reopen_condition"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        resolved_at=row.get("resolved_at"),
        metadata=dict(row.get("metadata_json") or {}),
    )


def _hypothesis(row: Mapping[str, Any]) -> Hypothesis:
    return Hypothesis(
        id=int(row["id"]),
        hypothesis_key=str(row["hypothesis_key"]),
        family_id=int(row["family_id"]),
        parent_hypothesis_id=(
            None if row.get("parent_hypothesis_id") is None else int(row["parent_hypothesis_id"])
        ),
        title=str(row["title"]),
        statement=str(row["statement"]),
        mechanism=str(row["mechanism"]),
        null_hypothesis=str(row["null_hypothesis"]),
        minimal_non_null=str(row["minimal_non_null"]),
        invariants=list(row.get("invariants_json") or []),
        baseline_definition=dict(row.get("baseline_definition_json") or {}),
        metric_definition=dict(row.get("metric_definition_json") or {}),
        failure_condition=dict(row.get("failure_condition_json") or {}),
        self_deception_risk=list(row.get("self_deception_risk_json") or []),
        status=HypothesisStatus(row["status"]),
        rejection_scope=RejectionScope(row["rejection_scope"]),
        rejection_reason=row.get("rejection_reason"),
        reopen_condition=row.get("reopen_condition"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        preregistered_at=row.get("preregistered_at"),
        started_at=row.get("started_at"),
        resolved_at=row.get("resolved_at"),
        metadata=dict(row.get("metadata_json") or {}),
    )


def _experiment(row: Mapping[str, Any]) -> HypothesisExperiment:
    return HypothesisExperiment(
        id=int(row["id"]),
        hypothesis_id=int(row["hypothesis_id"]),
        experiment_key=str(row["experiment_key"]),
        experiment_type=str(row["experiment_type"]),
        external_run_id=row.get("external_run_id"),
        training_run_id=row.get("training_run_id"),
        training_round_index=(
            None if row.get("training_round_index") is None else int(row["training_round_index"])
        ),
        report_path=row.get("report_path"),
        artifact_paths=list(row.get("artifact_paths_json") or []),
        config_snapshot=dict(row.get("config_snapshot_json") or {}),
        status=ExperimentStatus(row["status"]),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        created_at=row["created_at"],
        metadata=dict(row.get("metadata_json") or {}),
    )


def _evidence(row: Mapping[str, Any]) -> HypothesisEvidence:
    return HypothesisEvidence(
        id=int(row["id"]),
        hypothesis_id=int(row["hypothesis_id"]),
        experiment_id=None if row.get("experiment_id") is None else int(row["experiment_id"]),
        evidence_type=str(row["evidence_type"]),
        direction=EvidenceDirection(row["direction"]),
        summary=str(row["summary"]),
        metrics=dict(row.get("metrics_json") or {}),
        artifact_path=row.get("artifact_path"),
        content_hash=row.get("content_hash"),
        observed_at=row["observed_at"],
        created_at=row["created_at"],
        metadata=dict(row.get("metadata_json") or {}),
    )


def _decision(row: Mapping[str, Any]) -> HypothesisDecision:
    return HypothesisDecision(
        id=int(row["id"]),
        hypothesis_id=None if row.get("hypothesis_id") is None else int(row["hypothesis_id"]),
        family_id=None if row.get("family_id") is None else int(row["family_id"]),
        previous_status=str(row["previous_status"]),
        new_status=str(row["new_status"]),
        decision_code=str(row["decision_code"]),
        summary=str(row["summary"]),
        reason=dict(row.get("reason_json") or {}),
        evidence_ids=[int(value) for value in (row.get("evidence_ids_json") or [])],
        decided_by=str(row["decided_by"]),
        decided_at=row["decided_at"],
        created_at=row["created_at"],
    )


class HypothesisRepository:
    def __init__(self, connection_factory: ConnectionFactory = get_connection) -> None:
        self._connection_factory = connection_factory

    def ensure_schema(self) -> None:
        with self._connection_factory() as conn:
            ensure_hypothesis_registry_schema(conn)

    def create_family(
        self,
        *,
        family_key: str,
        title: str,
        mechanism: str,
        description: str = "",
        status: HypothesisFamilyStatus = HypothesisFamilyStatus.ACTIVE,
        rejection_scope: RejectionScope = RejectionScope.NONE,
        rejection_reason: str | None = None,
        reopen_condition: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HypothesisFamily:
        try:
            with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    """
                    INSERT INTO research_hypothesis_families (
                      family_key, title, description, mechanism, status, rejection_scope,
                      rejection_reason, reopen_condition, metadata_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING *
                    """,
                    (
                        family_key,
                        title,
                        description,
                        mechanism,
                        status.value,
                        rejection_scope.value,
                        rejection_reason,
                        reopen_condition,
                        _json(dict(metadata or {})),
                    ),
                ).fetchone()
        except UniqueViolation as exc:
            raise RegistryConflictError(f"family key already exists: {family_key}") from exc
        assert row is not None
        return _family(row)

    def get_family(self, family_key: str, *, for_update: bool = False) -> HypothesisFamily:
        suffix = " FOR UPDATE" if for_update else ""
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                f"SELECT * FROM research_hypothesis_families WHERE family_key = %s{suffix}",
                (family_key,),
            ).fetchone()
        if row is None:
            raise RegistryNotFoundError(f"hypothesis family not found: {family_key}")
        return _family(row)

    def list_families(
        self,
        *,
        status: HypothesisFamilyStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[HypothesisFamily]:
        where = "WHERE status = %s" if status else ""
        params: tuple[Any, ...] = ((status.value,) if status else ()) + (limit, offset)
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"SELECT * FROM research_hypothesis_families {where} "
                "ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
                params,
            ).fetchall()
        return [_family(row) for row in rows]

    def update_family_status(
        self,
        *,
        family_key: str,
        new_status: HypothesisFamilyStatus,
        decision_code: str,
        summary: str,
        decided_by: str,
        reason: Mapping[str, Any] | None = None,
        rejection_scope: RejectionScope | None = None,
        rejection_reason: str | None = None,
        reopen_condition: str | None = None,
    ) -> HypothesisFamily:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                "SELECT * FROM research_hypothesis_families WHERE family_key = %s FOR UPDATE",
                (family_key,),
            ).fetchone()
            if row is None:
                raise RegistryNotFoundError(f"hypothesis family not found: {family_key}")
            current = HypothesisFamilyStatus(row["status"])
            validate_family_transition(current, new_status)
            updated = self._update_family_and_decide(
                cursor,
                row=row,
                new_status=new_status,
                decision_code=decision_code,
                summary=summary,
                decided_by=decided_by,
                reason=reason,
                rejection_scope=rejection_scope,
                rejection_reason=rejection_reason,
                reopen_condition=reopen_condition,
            )
        return _family(updated)

    def create_hypothesis(
        self,
        *,
        hypothesis_key: str,
        family_key: str,
        title: str,
        mechanism: str,
        statement: str = "",
        null_hypothesis: str = "",
        minimal_non_null: str = "",
        invariants: Iterable[Any] | None = None,
        baseline_definition: Mapping[str, Any] | None = None,
        metric_definition: Mapping[str, Any] | None = None,
        failure_condition: Mapping[str, Any] | None = None,
        self_deception_risk: Iterable[Any] | None = None,
        parent_hypothesis_id: int | None = None,
        reopen_condition: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Hypothesis:
        try:
            with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
                family_row = cursor.execute(
                    "SELECT * FROM research_hypothesis_families WHERE family_key = %s FOR UPDATE",
                    (family_key,),
                ).fetchone()
                if family_row is None:
                    raise RegistryNotFoundError(f"hypothesis family not found: {family_key}")
                family_status = HypothesisFamilyStatus(family_row["status"])
                family_scope = RejectionScope(family_row["rejection_scope"])
                if family_status in {
                    HypothesisFamilyStatus.REJECTED,
                    HypothesisFamilyStatus.EXHAUSTED,
                } or family_scope == RejectionScope.MECHANISM_FAMILY:
                    raise RegistryConflictError(
                        f"family {family_key} is closed to active hypotheses; explicit family reopen is required"
                    )
                row = cursor.execute(
                    """
                    INSERT INTO research_hypotheses (
                      hypothesis_key, family_id, parent_hypothesis_id, title, statement, mechanism,
                      null_hypothesis, minimal_non_null, invariants_json, baseline_definition_json,
                      metric_definition_json, failure_condition_json, self_deception_risk_json,
                      reopen_condition, metadata_json
                    ) VALUES (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                      %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb
                    ) RETURNING *
                    """,
                    (
                        hypothesis_key,
                        family_row["id"],
                        parent_hypothesis_id,
                        title,
                        statement,
                        mechanism,
                        null_hypothesis,
                        minimal_non_null,
                        _json(list(invariants or [])),
                        _json(dict(baseline_definition or {})),
                        _json(dict(metric_definition or {})),
                        _json(dict(failure_condition or {})),
                        _json(list(self_deception_risk or [])),
                        reopen_condition,
                        _json(dict(metadata or {})),
                    ),
                ).fetchone()
        except UniqueViolation as exc:
            raise RegistryConflictError(f"hypothesis key already exists: {hypothesis_key}") from exc
        except ForeignKeyViolation as exc:
            raise RegistryConflictError("parent hypothesis does not exist") from exc
        assert row is not None
        return _hypothesis(row)

    def get_hypothesis(self, hypothesis_key: str) -> Hypothesis:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                "SELECT * FROM research_hypotheses WHERE hypothesis_key = %s",
                (hypothesis_key,),
            ).fetchone()
        if row is None:
            raise RegistryNotFoundError(f"hypothesis not found: {hypothesis_key}")
        return _hypothesis(row)

    def list_hypotheses(
        self,
        *,
        family_key: str | None = None,
        statuses: Iterable[HypothesisStatus] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Hypothesis]:
        clauses: list[str] = []
        params: list[Any] = []
        if family_key:
            clauses.append("f.family_key = %s")
            params.append(family_key)
        normalized_statuses = [status.value for status in (statuses or [])]
        if normalized_statuses:
            clauses.append("h.status = ANY(%s)")
            params.append(normalized_statuses)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"SELECT h.* FROM research_hypotheses h "
                f"JOIN research_hypothesis_families f ON f.id = h.family_id {where} "
                "ORDER BY h.created_at DESC, h.id DESC LIMIT %s OFFSET %s",
                tuple(params),
            ).fetchall()
        return [_hypothesis(row) for row in rows]

    def list_active_hypotheses(self, **kwargs: Any) -> list[Hypothesis]:
        return self.list_hypotheses(statuses=ACTIVE_HYPOTHESIS_STATUSES, **kwargs)

    def list_rejected_hypotheses(self, **kwargs: Any) -> list[Hypothesis]:
        return self.list_hypotheses(statuses=[HypothesisStatus.REJECTED], **kwargs)

    def create_experiment(
        self,
        *,
        hypothesis_key: str,
        experiment_key: str,
        experiment_type: str,
        external_run_id: str | None = None,
        training_run_id: str | None = None,
        training_round_index: int | None = None,
        report_path: str | None = None,
        artifact_paths: Iterable[str] | None = None,
        config_snapshot: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HypothesisExperiment:
        try:
            with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
                hypothesis_row = cursor.execute(
                    "SELECT id FROM research_hypotheses WHERE hypothesis_key = %s",
                    (hypothesis_key,),
                ).fetchone()
                if hypothesis_row is None:
                    raise RegistryNotFoundError(f"hypothesis not found: {hypothesis_key}")
                row = cursor.execute(
                    """
                    INSERT INTO research_hypothesis_experiments (
                      hypothesis_id, experiment_key, experiment_type, external_run_id,
                      training_run_id, training_round_index, report_path, artifact_paths_json,
                      config_snapshot_json, metadata_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                    RETURNING *
                    """,
                    (
                        hypothesis_row["id"],
                        experiment_key,
                        experiment_type,
                        external_run_id,
                        training_run_id,
                        training_round_index,
                        report_path,
                        _json(list(artifact_paths or [])),
                        _json(dict(config_snapshot or {})),
                        _json(dict(metadata or {})),
                    ),
                ).fetchone()
        except UniqueViolation as exc:
            raise RegistryConflictError(f"experiment key already exists: {experiment_key}") from exc
        assert row is not None
        return _experiment(row)

    def list_experiments(self, hypothesis_key: str) -> list[HypothesisExperiment]:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT e.* FROM research_hypothesis_experiments e
                JOIN research_hypotheses h ON h.id = e.hypothesis_id
                WHERE h.hypothesis_key = %s ORDER BY e.created_at, e.id
                """,
                (hypothesis_key,),
            ).fetchall()
        return [_experiment(row) for row in rows]

    def update_experiment_status(
        self, *, experiment_key: str, new_status: ExperimentStatus
    ) -> HypothesisExperiment:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                "SELECT * FROM research_hypothesis_experiments WHERE experiment_key = %s FOR UPDATE",
                (experiment_key,),
            ).fetchone()
            if row is None:
                raise RegistryNotFoundError(f"experiment not found: {experiment_key}")
            validate_experiment_transition(ExperimentStatus(row["status"]), new_status)
            updated = cursor.execute(
                """
                UPDATE research_hypothesis_experiments
                SET status = %s,
                    started_at = CASE WHEN %s = 'running' THEN COALESCE(started_at, now()) ELSE started_at END,
                    completed_at = CASE WHEN %s IN ('completed', 'failed', 'invalidated', 'cancelled')
                                        THEN now() ELSE completed_at END
                WHERE id = %s RETURNING *
                """,
                (new_status.value, new_status.value, new_status.value, row["id"]),
            ).fetchone()
        assert updated is not None
        return _experiment(updated)

    def attach_experiment_to_hypothesis(
        self, *, experiment_key: str, hypothesis_key: str
    ) -> HypothesisExperiment:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            hypothesis_row = cursor.execute(
                "SELECT id FROM research_hypotheses WHERE hypothesis_key = %s",
                (hypothesis_key,),
            ).fetchone()
            if hypothesis_row is None:
                raise RegistryNotFoundError(f"hypothesis not found: {hypothesis_key}")
            row = cursor.execute(
                """
                UPDATE research_hypothesis_experiments SET hypothesis_id = %s
                WHERE experiment_key = %s RETURNING *
                """,
                (hypothesis_row["id"], experiment_key),
            ).fetchone()
        if row is None:
            raise RegistryNotFoundError(f"experiment not found: {experiment_key}")
        return _experiment(row)

    def add_evidence(
        self,
        *,
        hypothesis_key: str,
        evidence_type: str,
        direction: EvidenceDirection,
        summary: str,
        observed_at: Any,
        experiment_key: str | None = None,
        metrics: Mapping[str, Any] | None = None,
        artifact_path: str | None = None,
        content_hash: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HypothesisEvidence:
        try:
            with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
                hypothesis_row = cursor.execute(
                    "SELECT id FROM research_hypotheses WHERE hypothesis_key = %s",
                    (hypothesis_key,),
                ).fetchone()
                if hypothesis_row is None:
                    raise RegistryNotFoundError(f"hypothesis not found: {hypothesis_key}")
                experiment_id = None
                if experiment_key:
                    experiment_row = cursor.execute(
                        """
                        SELECT id, hypothesis_id FROM research_hypothesis_experiments
                        WHERE experiment_key = %s
                        """,
                        (experiment_key,),
                    ).fetchone()
                    if experiment_row is None:
                        raise RegistryNotFoundError(f"experiment not found: {experiment_key}")
                    if int(experiment_row["hypothesis_id"]) != int(hypothesis_row["id"]):
                        raise RegistryConflictError("evidence experiment belongs to another hypothesis")
                    experiment_id = experiment_row["id"]
                row = cursor.execute(
                    """
                    INSERT INTO research_hypothesis_evidence (
                      hypothesis_id, experiment_id, evidence_type, direction, summary,
                      metrics_json, artifact_path, content_hash, observed_at, metadata_json
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb)
                    RETURNING *
                    """,
                    (
                        hypothesis_row["id"],
                        experiment_id,
                        evidence_type,
                        direction.value,
                        summary,
                        _json(dict(metrics or {})),
                        artifact_path,
                        content_hash,
                        observed_at,
                        _json(dict(metadata or {})),
                    ),
                ).fetchone()
        except UniqueViolation as exc:
            raise RegistryConflictError(
                "duplicate evidence content hash for hypothesis and evidence type"
            ) from exc
        assert row is not None
        return _evidence(row)

    def list_evidence(self, hypothesis_key: str) -> list[HypothesisEvidence]:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT e.* FROM research_hypothesis_evidence e
                JOIN research_hypotheses h ON h.id = e.hypothesis_id
                WHERE h.hypothesis_key = %s ORDER BY e.observed_at, e.id
                """,
                (hypothesis_key,),
            ).fetchall()
        return [_evidence(row) for row in rows]

    def transition_hypothesis(
        self,
        *,
        hypothesis_key: str,
        new_status: HypothesisStatus,
        decision_code: str,
        summary: str,
        decided_by: str,
        reason: Mapping[str, Any] | None = None,
        evidence_ids: Iterable[int] | None = None,
        rejection_scope: RejectionScope = RejectionScope.NONE,
        rejection_reason: str | None = None,
        reopen_condition: str | None = None,
    ) -> Hypothesis:
        evidence_id_list = [int(value) for value in (evidence_ids or [])]
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                "SELECT * FROM research_hypotheses WHERE hypothesis_key = %s FOR UPDATE",
                (hypothesis_key,),
            ).fetchone()
            if row is None:
                raise RegistryNotFoundError(f"hypothesis not found: {hypothesis_key}")
            current = HypothesisStatus(row["status"])
            validate_hypothesis_transition(current, new_status)
            self._validate_evidence_ids(cursor, int(row["id"]), evidence_id_list)
            cursor.execute("SELECT set_config('dehps.registry_status_transition', 'allowed', true)")
            updated = cursor.execute(
                """
                UPDATE research_hypotheses
                SET status = %s,
                    rejection_scope = %s,
                    rejection_reason = %s,
                    reopen_condition = COALESCE(%s, reopen_condition),
                    preregistered_at = CASE WHEN %s = 'preregistered' THEN now() ELSE preregistered_at END,
                    started_at = CASE WHEN %s = 'running' THEN now() ELSE started_at END,
                    resolved_at = CASE WHEN %s IN ('rejected', 'inconclusive', 'invalidated')
                                       THEN now() ELSE resolved_at END,
                    updated_at = now()
                WHERE id = %s RETURNING *
                """,
                (
                    new_status.value,
                    rejection_scope.value,
                    rejection_reason,
                    reopen_condition,
                    new_status.value,
                    new_status.value,
                    new_status.value,
                    row["id"],
                ),
            ).fetchone()
            self._insert_decision(
                cursor,
                hypothesis_id=int(row["id"]),
                family_id=None,
                previous_status=current.value,
                new_status=new_status.value,
                decision_code=decision_code,
                summary=summary,
                reason=reason,
                evidence_ids=evidence_id_list,
                decided_by=decided_by,
            )
            if new_status == HypothesisStatus.REJECTED and rejection_scope == RejectionScope.MECHANISM_FAMILY:
                family_row = cursor.execute(
                    "SELECT * FROM research_hypothesis_families WHERE id = %s FOR UPDATE",
                    (row["family_id"],),
                ).fetchone()
                assert family_row is not None
                family_current = HypothesisFamilyStatus(family_row["status"])
                if family_current != HypothesisFamilyStatus.REJECTED:
                    validate_family_transition(family_current, HypothesisFamilyStatus.REJECTED)
                    self._update_family_and_decide(
                        cursor,
                        row=family_row,
                        new_status=HypothesisFamilyStatus.REJECTED,
                        decision_code="mechanism_family_rejected",
                        summary=summary,
                        decided_by=decided_by,
                        reason=reason,
                        rejection_scope=RejectionScope.MECHANISM_FAMILY,
                        rejection_reason=rejection_reason,
                        reopen_condition=reopen_condition,
                    )
        assert updated is not None
        return _hypothesis(updated)

    def reopen_hypothesis(
        self,
        *,
        hypothesis_key: str,
        new_hypothesis_key: str,
        reopen_reason: str,
        decided_by: str,
        changed_basis: Mapping[str, Any],
        title: str | None = None,
    ) -> Hypothesis:
        if not reopen_reason.strip():
            raise ReopenError("reopen_reason is required")
        if not changed_basis:
            raise ReopenError("reopen requires recorded changed basis")
        try:
            with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    "SELECT * FROM research_hypotheses WHERE hypothesis_key = %s FOR UPDATE",
                    (hypothesis_key,),
                ).fetchone()
                if row is None:
                    raise RegistryNotFoundError(f"hypothesis not found: {hypothesis_key}")
                if HypothesisStatus(row["status"]) != HypothesisStatus.REJECTED:
                    raise ReopenError("only rejected hypotheses can reopen")
                if not str(row.get("reopen_condition") or "").strip():
                    raise ReopenError("rejected hypothesis has no reopen_condition")
                family_row = cursor.execute(
                    "SELECT * FROM research_hypothesis_families WHERE id = %s FOR UPDATE",
                    (row["family_id"],),
                ).fetchone()
                assert family_row is not None
                if HypothesisFamilyStatus(family_row["status"]) in {
                    HypothesisFamilyStatus.REJECTED,
                    HypothesisFamilyStatus.EXHAUSTED,
                }:
                    raise ReopenError("family must be reopened before creating a hypothesis version")
                metadata = dict(row.get("metadata_json") or {})
                metadata.update(
                    {
                        "reopened_from": hypothesis_key,
                        "reopen_reason": reopen_reason,
                        "changed_basis": dict(changed_basis),
                    }
                )
                new_row = cursor.execute(
                    """
                    INSERT INTO research_hypotheses (
                      hypothesis_key, family_id, parent_hypothesis_id, title, statement, mechanism,
                      null_hypothesis, minimal_non_null, invariants_json, baseline_definition_json,
                      metric_definition_json, failure_condition_json, self_deception_risk_json,
                      reopen_condition, metadata_json
                    ) VALUES (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                      %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb
                    ) RETURNING *
                    """,
                    (
                        new_hypothesis_key,
                        row["family_id"],
                        row["id"],
                        title or row["title"],
                        row["statement"],
                        row["mechanism"],
                        row["null_hypothesis"],
                        row["minimal_non_null"],
                        _json(row.get("invariants_json") or []),
                        _json(row.get("baseline_definition_json") or {}),
                        _json(row.get("metric_definition_json") or {}),
                        _json(row.get("failure_condition_json") or {}),
                        _json(row.get("self_deception_risk_json") or []),
                        row["reopen_condition"],
                        _json(metadata),
                    ),
                ).fetchone()
                self._insert_decision(
                    cursor,
                    hypothesis_id=int(row["id"]),
                    family_id=None,
                    previous_status=HypothesisStatus.REJECTED.value,
                    new_status="proposed_version_created",
                    decision_code="hypothesis_reopened_as_version",
                    summary=f"created hypothesis version {new_hypothesis_key}",
                    reason={"reopen_reason": reopen_reason, "changed_basis": dict(changed_basis)},
                    evidence_ids=[],
                    decided_by=decided_by,
                )
        except UniqueViolation as exc:
            raise RegistryConflictError(
                f"hypothesis key already exists: {new_hypothesis_key}"
            ) from exc
        assert new_row is not None
        return _hypothesis(new_row)

    def reject_family(
        self,
        *,
        family_key: str,
        rejection_reason: str,
        reopen_condition: str,
        decided_by: str,
        reason: Mapping[str, Any],
    ) -> HypothesisFamily:
        return self.update_family_status(
            family_key=family_key,
            new_status=HypothesisFamilyStatus.REJECTED,
            decision_code="mechanism_family_rejected",
            summary=rejection_reason,
            decided_by=decided_by,
            reason=reason,
            rejection_scope=RejectionScope.MECHANISM_FAMILY,
            rejection_reason=rejection_reason,
            reopen_condition=reopen_condition,
        )

    def reopen_family(
        self,
        *,
        family_key: str,
        reopen_reason: str,
        decided_by: str,
        changed_basis: Mapping[str, Any],
    ) -> HypothesisFamily:
        if not reopen_reason.strip():
            raise ReopenError("reopen_reason is required")
        if not changed_basis:
            raise ReopenError("family reopen requires new data, feature, causal variable, or protocol")
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                "SELECT * FROM research_hypothesis_families WHERE family_key = %s FOR UPDATE",
                (family_key,),
            ).fetchone()
            if row is None:
                raise RegistryNotFoundError(f"hypothesis family not found: {family_key}")
            validate_family_reopen(HypothesisFamilyStatus(row["status"]))
            if not str(row.get("reopen_condition") or "").strip():
                raise ReopenError("rejected family has no reopen_condition")
            updated = self._update_family_and_decide(
                cursor,
                row=row,
                new_status=HypothesisFamilyStatus.REOPENED,
                decision_code="mechanism_family_reopened",
                summary=reopen_reason,
                decided_by=decided_by,
                reason={"reopen_reason": reopen_reason, "changed_basis": dict(changed_basis)},
                rejection_scope=RejectionScope.NONE,
                rejection_reason=row.get("rejection_reason"),
                reopen_condition=row.get("reopen_condition"),
                skip_transition_validation=True,
            )
        return _family(updated)

    def list_decisions(self, hypothesis_key: str) -> list[HypothesisDecision]:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT d.* FROM research_hypothesis_decisions d
                JOIN research_hypotheses h ON h.id = d.hypothesis_id
                WHERE h.hypothesis_key = %s ORDER BY d.decided_at, d.id
                """,
                (hypothesis_key,),
            ).fetchall()
        return [_decision(row) for row in rows]

    @staticmethod
    def _validate_evidence_ids(cursor: Any, hypothesis_id: int, evidence_ids: list[int]) -> None:
        if not evidence_ids:
            return
        rows = cursor.execute(
            """
            SELECT id FROM research_hypothesis_evidence
            WHERE hypothesis_id = %s AND id = ANY(%s)
            """,
            (hypothesis_id, evidence_ids),
        ).fetchall()
        found = {int(row["id"]) for row in rows}
        if found != set(evidence_ids):
            raise RegistryConflictError("decision evidence_ids must belong to the hypothesis")

    @staticmethod
    def _insert_decision(
        cursor: Any,
        *,
        hypothesis_id: int | None,
        family_id: int | None,
        previous_status: str,
        new_status: str,
        decision_code: str,
        summary: str,
        reason: Mapping[str, Any] | None,
        evidence_ids: list[int],
        decided_by: str,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO research_hypothesis_decisions (
              hypothesis_id, family_id, previous_status, new_status, decision_code,
              summary, reason_json, evidence_ids_json, decided_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
            """,
            (
                hypothesis_id,
                family_id,
                previous_status,
                new_status,
                decision_code,
                summary,
                _json(dict(reason or {})),
                _json(evidence_ids),
                decided_by,
            ),
        )

    def _update_family_and_decide(
        self,
        cursor: Any,
        *,
        row: Mapping[str, Any],
        new_status: HypothesisFamilyStatus,
        decision_code: str,
        summary: str,
        decided_by: str,
        reason: Mapping[str, Any] | None,
        rejection_scope: RejectionScope | None,
        rejection_reason: str | None,
        reopen_condition: str | None,
        skip_transition_validation: bool = False,
    ) -> Mapping[str, Any]:
        current = HypothesisFamilyStatus(row["status"])
        if not skip_transition_validation:
            validate_family_transition(current, new_status)
        cursor.execute("SELECT set_config('dehps.registry_status_transition', 'allowed', true)")
        updated = cursor.execute(
            """
            UPDATE research_hypothesis_families
            SET status = %s,
                rejection_scope = COALESCE(%s, rejection_scope),
                rejection_reason = COALESCE(%s, rejection_reason),
                reopen_condition = COALESCE(%s, reopen_condition),
                resolved_at = CASE WHEN %s IN ('rejected', 'exhausted') THEN now() ELSE resolved_at END,
                updated_at = now()
            WHERE id = %s RETURNING *
            """,
            (
                new_status.value,
                None if rejection_scope is None else rejection_scope.value,
                rejection_reason,
                reopen_condition,
                new_status.value,
                row["id"],
            ),
        ).fetchone()
        assert updated is not None
        self._insert_decision(
            cursor,
            hypothesis_id=None,
            family_id=int(row["id"]),
            previous_status=current.value,
            new_status=new_status.value,
            decision_code=decision_code,
            summary=summary,
            reason=reason,
            evidence_ids=[],
            decided_by=decided_by,
        )
        return updated
