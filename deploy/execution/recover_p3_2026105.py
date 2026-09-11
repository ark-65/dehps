"""Exact 2026105 operational adapter; completion stays with the frozen Supervisor.

The failed attempt stays failed. An append-only manifest and observation make
the same settlement task Ready for ONE new execution under the retained source.
No source contract, task definition, result, artifact, or execution is rewritten.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import (
    ControlPlaneManifest,
    ExternalExecutorObservation,
    MainlineExecutionEvent,
    jsonable,
)
from psycopg.rows import dict_row

CONTROL = "m4-information-theory-mainline"
TASK = "m4-p3-forward-prequential-2026105-settlement"
TASK_DIGEST = "50f8addf67452b9dcc7e095b68816e115ccd6e0ce7cb3f9cd7e8f4f94d925713"
OLD_HEAD = "06f24250da4e1dc49bf31a53996ab671533e26cc876f684843848a05d6769cf3"
OLD_EXECUTION = "03ac1de3ef19cd0b4f7090381f0cea974c6506cf08072fd8b4d663a5116c07d5"
STARTED = "695de4c44cf4e89888c99954a0e4aec27d37fbf4b6c43e13414c23835ad201bf"
FAILED = "aadbf3604b793d1ce06fa15d16b716ad5b9c0eb84ed439ff3e4b3bf9c802cc25"
SOURCE = "139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493"
OWNER = "p3-2026105-deadlock-recovery-v1"
FROZEN_SOURCE_COMMIT = "ac0ef7832c6f13c7500b3f7d67731420b575c0f4"
UPSTREAM = [
    (
        "m4-p3-forward-prequential-2026105-predraw",
        "73d04671e92856db45aa78cc1763a16e3add7deb4c127ac17586e76a0f6ae7a9",
        "3b398853153313ed4ab7e8ef1987aa01d3d936002f8acebc00eec5385c2a5558",
        "M4P3ForwardPrequentialCheckpoint",
    ),
    (
        "m4-p3-forward-prequential-2026105-predraw",
        "73d04671e92856db45aa78cc1763a16e3add7deb4c127ac17586e76a0f6ae7a9",
        "a2f7b29b09ff899ea5acfb604787889051331e04b0807dea596f2b4850dfcb29",
        "M4P3ForwardPrequentialModelCandidateSet",
    ),
    (
        "m4-p3-forward-prequential-2026105-predraw",
        "73d04671e92856db45aa78cc1763a16e3add7deb4c127ac17586e76a0f6ae7a9",
        "d62c9089fcab97ecc8757a2ec4cefec6f1e3799078a1ef10fdd342db627e875c",
        "M4P3ForwardPrequentialPreDrawReport",
    ),
    (
        "m4-p3-forward-prequential-2026105-predraw",
        "73d04671e92856db45aa78cc1763a16e3add7deb4c127ac17586e76a0f6ae7a9",
        "ede8b74bc075b4b40835e9e148a352a3b3e3f5667b9aba699634555628ab3af8",
        "research_os_mainline_execution",
    ),
    (
        "m4-p3-forward-prequential-2026105-predraw",
        "73d04671e92856db45aa78cc1763a16e3add7deb4c127ac17586e76a0f6ae7a9",
        "fb0fd98e363a21cad7d2c98b7d41019a13b0e48df7886888d337bee8280d1938",
        "M4P3ForwardPrequentialRandomBaselineSet",
    ),
    (
        "m4-p3-forward-prequential-2026105-predraw-replay",
        "3117cec98f0b4f53803ba1ca66a3d08de23a8ac56ee13a2a7a853ea3f25098cf",
        "09450bbd10eb481b8a2bb3c490c41ef247c83d26a7f2860b0efd792ef4056eea",
        "research_os_mainline_execution",
    ),
    (
        "m4-p3-forward-prequential-2026105-predraw-replay",
        "3117cec98f0b4f53803ba1ca66a3d08de23a8ac56ee13a2a7a853ea3f25098cf",
        "7405b7b5227785c626cde0ed453a3a22f7f4c1d7c97101dfc025481a4b02fe0c",
        "M4P3ForwardPrequentialPreDrawReplay",
    ),
    (
        "m4-p3-forward-prequential-2026105-refit",
        "0bd77df2ea8255d68cb51457a3b86111e75c8ed8e41849349402be3618aebbec",
        "185c0b411f18d1a693018f6ee71361a1faadf2e9e1d0e83e4776bfdd6ef2d1d1",
        "research_os_mainline_execution",
    ),
    (
        "m4-p3-forward-prequential-2026105-refit",
        "0bd77df2ea8255d68cb51457a3b86111e75c8ed8e41849349402be3618aebbec",
        "9c23c3c3252d9bc53782af2dc85f11d936dd1478bcc43050adc104385870af21",
        "M4P3ForwardPrequentialDataset",
    ),
    (
        "m4-p3-forward-prequential-2026105-refit",
        "0bd77df2ea8255d68cb51457a3b86111e75c8ed8e41849349402be3618aebbec",
        "ce3e2caa4c76d9ce56357e3d185019caf7b6a23e819fe67e01347d59b0e518c2",
        "M4P3ForwardPrequentialModel",
    ),
]
AUDITED_DRAW = (
    [2, 4, 13, 14, 15, 30],
    8,
    "draw-issue-2026105-360ec34fd76a742ed8dc",
    "3931755594562fe3c2ca0172459283107833fcdf731cab3ea9392f6631f880a5",
)
RECOVERY_CONTRACT = {
    "incident_execution": OLD_EXECUTION,
    "failed_event": FAILED,
    "task": TASK,
    "source_contract": SOURCE,
    "old_manifest": OLD_HEAD,
    "operation": "append_ready_manifest_then_retained_canonical_settlement_once",
    "preserve_failed_execution": True,
    "frozen_source_commit": FROZEN_SOURCE_COMMIT,
    "retrain": False,
    "rewrite_history": False,
}


class RecoveryError(RuntimeError):
    pass


def _json(value: Any) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))


def validate_events(events: list[Mapping[str, Any]]) -> None:
    """Digest-verify the exact original pair; reject any later attempt."""
    if len(events) != 2:
        raise RecoveryError("incident_event_set_changed")
    for row, digest, kind, sequence in zip(
        events, (STARTED, FAILED), ("started", "failed"), (0, 1), strict=True
    ):
        raw = dict(row["event_json"])
        record = MainlineExecutionEvent(
            **{**raw, "payload": tuple((k, v) for k, v in raw["payload"])}
        )
        if (
            row["event_digest"] != digest
            or record.artifact_digest != digest
            or record.execution_id != OLD_EXECUTION
            or record.manifest_digest != OLD_HEAD
            or record.control_plane_key != CONTROL
            or record.task_key != TASK
            or record.task_digest != TASK_DIGEST
            or record.event_type != kind
            or record.sequence != sequence
        ):
            raise RecoveryError("incident_event_identity_changed")


def ready_manifest(current: ControlPlaneManifest) -> ControlPlaneManifest:
    if current.artifact_digest != OLD_HEAD:
        raise RecoveryError("incident_head_changed")
    task = next((t for t in current.tasks if t.task_key == TASK), None)
    if task is None or task.artifact_digest != TASK_DIGEST:
        raise RecoveryError("incident_task_changed")
    state = current.task_state_by_digest[TASK_DIGEST]
    if state.declared_status.value != "running":
        raise RecoveryError("incident_not_running")
    if task.input_artifact_digests != (SOURCE,):
        raise RecoveryError("incident_source_changed")
    payload = current.to_dict(include_digest=False)
    for item in payload["tasks"]:
        if item["task_key"] == TASK:
            item["status"] = "draft"
            item["completion_classification"] = "INTEGRATION_PENDING"
    ready = ControlPlaneManifest.from_dict(payload)
    if [t.to_dict() for t in ready.tasks] != [t.to_dict() for t in current.tasks]:
        raise RecoveryError("incident_definition_changed")
    resolved = ResearchOSControlPlane().resolve(ready)
    if TASK not in {t.task_key for t in resolved.ready_queue}:
        raise RecoveryError("incident_upstream_not_ready")
    return ready


def verify_sources(root: Path) -> None:
    from dehps.notifications.p3_top100 import load_source_contract as mail_source
    from dehps.research_os.information_theory.measurement_system_v2 import (
        forward_prequential_confirmatory as p3,
    )

    if p3.load_source_contract(root_dir=root)["artifact_digest"] != SOURCE:
        raise RecoveryError("incident_source_changed")
    mail_source(root_dir=root)


def verify_operator(cursor, *, request_key: str, executor_id: str, commit: str) -> int:
    """Bind to a live, separately reviewed Operator execution, never owner consent.

    The host operation wrapper must additionally validate the protected human
    receipt and quiescent services. This DB check is not a human identity broker.
    """
    import hashlib

    request = cursor.execute(
        "SELECT id,request_type,status,requested_by,payload_json FROM agent_requests "
        "WHERE request_key=%s FOR SHARE",
        (request_key,),
    ).fetchone()
    if (
        not request
        or request["request_type"] != "operator_release"
        or request["status"] != "executing"
        or request["payload_json"].get("commit") != commit
        or commit == FROZEN_SOURCE_COMMIT
        or len(commit) != 40
        or any(c not in "0123456789abcdef" for c in commit)
        or request["payload_json"].get("recovery") != RECOVERY_CONTRACT
    ):
        raise RecoveryError("no_authorized_operator_recovery")
    approvals = cursor.execute(
        "SELECT decided_by_role,decided_by,reason_json FROM agent_request_decisions "
        "WHERE request_id=%s AND decision_code='request_approved'",
        (request["id"],),
    ).fetchall()
    payload_sha = hashlib.sha256(
        json.dumps(
            request["payload_json"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    if (
        len(approvals) != 1
        or approvals[0]["decided_by_role"] != "reviewer"
        or approvals[0]["decided_by"] in (request["requested_by"], executor_id)
        or approvals[0]["reason_json"].get("request_payload_sha256") != payload_sha
    ):
        raise RecoveryError("independent_exact_review_missing")
    try:
        expires = datetime.fromisoformat(approvals[0]["reason_json"]["expires_at"])
        valid = expires.tzinfo is not None and expires > datetime.now(UTC)
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise RecoveryError("operator_review_expired")
    executions = cursor.execute(
        "SELECT id,executor_role,executor_id,environment,run_id FROM agent_request_executions "
        "WHERE request_id=%s AND status='running' FOR SHARE",
        (request["id"],),
    ).fetchall()
    if (
        len(executions) != 1
        or executions[0]["executor_role"] != "operator"
        or executions[0]["executor_id"] != executor_id
        or executions[0]["environment"] != "production"
        or not executions[0]["run_id"]
    ):
        raise RecoveryError("operator_execution_identity_changed")
    return int(executions[0]["id"])


def prepare_retry(
    repository, *, root: Path, request_key: str, executor_id: str, commit: str
) -> dict[str, Any]:
    """Atomic, exact migration. It does not create completion or Evidence facts."""
    verify_sources(root)
    with (
        repository.connection_factory() as conn,
        conn.cursor(row_factory=dict_row) as cursor,
    ):
        operator_execution = verify_operator(
            cursor, request_key=request_key, executor_id=executor_id, commit=commit
        )
        head = cursor.execute(
            "SELECT current_manifest_digest FROM research_os_control_planes "
            "WHERE control_plane_key=%s FOR UPDATE",
            (CONTROL,),
        ).fetchone()
        if head is None:
            raise RecoveryError("incident_control_missing")
        prior = cursor.execute(
            "SELECT observation_json FROM research_os_external_executor_observations "
            "WHERE control_plane_key=%s AND owner=%s",
            (CONTROL, OWNER),
        ).fetchall()
        if prior:
            if len(prior) != 1:
                raise RecoveryError("recovery_attestation_duplicated")
            metadata = dict(prior[0]["observation_json"]["metadata"])
            if (
                metadata.get("runtime_commit") != commit
                or metadata.get("operator_request") != request_key
                or metadata.get("operator_execution") != operator_execution
            ):
                raise RecoveryError("recovery_runtime_commit_changed")
            return {"status": "ALREADY_PREPARED", **metadata}
        if head["current_manifest_digest"] != OLD_HEAD:
            raise RecoveryError("incident_head_changed")
        stored = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest=%s",
            (OLD_HEAD,),
        ).fetchone()
        current = ControlPlaneManifest.from_dict(dict(stored["manifest_json"]))
        ready = ready_manifest(current)
        events = cursor.execute(
            "SELECT event_digest,event_json FROM research_os_mainline_execution_events "
            "WHERE control_plane_key=%s AND task_key=%s ORDER BY sequence FOR UPDATE",
            (CONTROL, TASK),
        ).fetchall()
        validate_events(events)
        if cursor.execute(
            "SELECT 1 FROM research_os_mainline_artifacts WHERE control_plane_key=%s "
            "AND task_key=%s",
            (CONTROL, TASK),
        ).fetchone():
            raise RecoveryError("incident_partial_or_complete_registration")
        upstream = cursor.execute(
            "SELECT task_key,execution_id,artifact_digest,artifact_type "
            "FROM research_os_mainline_artifacts WHERE control_plane_key=%s "
            "AND task_key IN ('m4-p3-forward-prequential-2026105-refit',"
            "'m4-p3-forward-prequential-2026105-predraw',"
            "'m4-p3-forward-prequential-2026105-predraw-replay')",
            (CONTROL,),
        ).fetchall()
        if (
            sorted(
                tuple(
                    r[k]
                    for k in (
                        "task_key",
                        "execution_id",
                        "artifact_digest",
                        "artifact_type",
                    )
                )
                for r in upstream
            )
            != UPSTREAM
        ):
            raise RecoveryError("incident_sealed_upstream_changed")
        draw = cursor.execute(
            "SELECT h.red_numbers,h.blue_number,e.event_key,e.history_fingerprint "
            "FROM ssq_history h JOIN draw_issue_events e ON e.new_issue=h.issue "
            "JOIN draw_sync_runs r ON r.event_key=e.event_key WHERE h.issue='2026105' "
            "AND r.completed_at IS NOT NULL AND r.audit_passed IS TRUE "
            "AND r.status='new_issue' ORDER BY r.completed_at DESC LIMIT 1"
        ).fetchone()
        if (
            draw is None
            or tuple(
                draw[k]
                for k in (
                    "red_numbers",
                    "blue_number",
                    "event_key",
                    "history_fingerprint",
                )
            )
            != AUDITED_DRAW
        ):
            raise RecoveryError("incident_audited_draw_changed")
        projection = cursor.execute(
            "SELECT declared_status,resolved_status FROM research_os_task_states "
            "WHERE control_plane_key=%s AND task_digest=%s FOR UPDATE",
            (CONTROL, TASK_DIGEST),
        ).fetchone()
        if projection != {"declared_status": "running", "resolved_status": "running"}:
            raise RecoveryError("incident_projection_changed")
        metadata = {
            **RECOVERY_CONTRACT,
            "old_manifest": OLD_HEAD,
            "ready_manifest": ready.artifact_digest,
            "runtime_commit": commit,
            "operator_request": request_key,
            "operator_execution": operator_execution,
            "engineering_authority": "owner_continuing_R0_R5_consent",
            "frozen_source_commit": FROZEN_SOURCE_COMMIT,
            "scientific_contract_changed": False,
        }
        observation = ExternalExecutorObservation(
            capability="p3_2026105_incident_recovery",
            owner=OWNER,
            status="READY_FOR_ONE_CANONICAL_SETTLEMENT",
            observed_at=datetime.now(UTC).isoformat(),
            metadata=tuple(metadata.items()),
        )
        # Append a manifest; copy its unchanged Goal/Task links. The exact
        # before/after pair above is the whole scope of this approved migration.
        cursor.execute(
            "INSERT INTO research_os_manifests "
            "(manifest_digest,schema_version,manifest_json,source) VALUES (%s,%s,%s::jsonb,%s) "
            "ON CONFLICT (manifest_digest) DO NOTHING",
            (
                ready.artifact_digest,
                ready.schema_version,
                _json(ready.to_dict(include_digest=False)),
                OWNER,
            ),
        )
        saved = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest=%s",
            (ready.artifact_digest,),
        ).fetchone()
        if dict(saved["manifest_json"]) != ready.to_dict(include_digest=False):
            raise RecoveryError("ready_manifest_content_changed")
        for table, column in (
            ("research_os_manifest_goals", "goal_digest"),
            ("research_os_manifest_tasks", "task_digest"),
        ):
            cursor.execute(
                f"INSERT INTO {table} (manifest_digest,{column},ordinal) "
                f"SELECT %s,{column},ordinal FROM {table} WHERE manifest_digest=%s "
                "ON CONFLICT DO NOTHING",
                (ready.artifact_digest, OLD_HEAD),
            )
        resolution = next(
            r
            for r in repository.control_plane.resolve(ready).resolutions
            if r.task_key == TASK
        )
        cursor.execute(
            "UPDATE research_os_task_states SET declared_status='draft', resolved_status=%s, "
            "completion_classification='INTEGRATION_PENDING', reason_code=%s, "
            "dependency_state_json=%s::jsonb, updated_at=now() "
            "WHERE control_plane_key=%s AND task_digest=%s",
            (
                resolution.status.value,
                resolution.reason_code,
                _json(resolution.unsatisfied_dependencies),
                CONTROL,
                TASK_DIGEST,
            ),
        )
        cursor.execute(
            "UPDATE research_os_control_planes SET current_manifest_digest=%s,source=%s, "
            "updated_at=now() WHERE control_plane_key=%s AND current_manifest_digest=%s",
            (ready.artifact_digest, OWNER, CONTROL, OLD_HEAD),
        )
        cursor.execute(
            "INSERT INTO research_os_external_executor_observations "
            "(observation_digest,control_plane_key,capability,owner,status,pid,observed_at,observation_json) "
            "VALUES (%s,%s,%s,%s,%s,NULL,%s,%s::jsonb)",
            (
                observation.artifact_digest,
                CONTROL,
                observation.capability,
                OWNER,
                observation.status,
                observation.observed_at,
                _json(observation),
            ),
        )
    return {"status": "PREPARED", **metadata}
