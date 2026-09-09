"""One reviewed incident migration; completion remains the frozen Supervisor's job.

The failed attempt stays failed. An append-only manifest and observation make
the same replay task Ready for ONE new execution under the repaired commit.
No source contract, task definition, result, artifact, or execution is rewritten.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from psycopg.rows import dict_row

from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import (
    ControlPlaneManifest, ExternalExecutorObservation, MainlineExecutionEvent,
    jsonable,
)

CONTROL = "m4-information-theory-mainline"
TASK = "m4-p3-forward-prequential-2026103-settlement-replay"
TASK_DIGEST = "24c71b069f42afb069d3e1eeba347e9e1421c0577dc6d594f1e4f8a06a78894a"
OLD_HEAD = "c868353673facb6219f033252555750b0e5f2a3ed4f9707b3b43200d861d045b"
OLD_EXECUTION = "62bef55f17cb2d2cb6dee639afc2b6128c77a7ab32743495477715ec66b7ef5f"
STARTED = "f94db494ca52cdbd5bb86c8d664b4586e457c9838901e3557228df86b11cd018"
FAILED = "dfe22cc7acbeb84baa585616540a25b583e88a7750e4371748e1ca0bbbeff1cb"
SOURCE = "139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493"
SETTLEMENT_EXECUTION = "28797766d92a8fbf724fea22bb4427fd5a4f177beec4463ccf8abe6117035adc"
SETTLEMENT_DIGEST = "f58de9b214e6ace1229e8635324098344db4d75b2f8936cd0e5aa65204b42644"
ENGINEERING_REQUEST = "engineering-p3-2026103-deadlock-replay-recovery-20260907-v1"
ENGINEERING_PAYLOAD = "07cb0fdd55677f11bff8cc6cb32ad3e5e769fc2d95585cf6f52f96b69e401c86"
OWNER = "p3-2026103-deadlock-recovery-v1"
RECOVERY_CONTRACT = {
    "incident_execution": OLD_EXECUTION,
    "failed_event": FAILED,
    "task": TASK,
    "source_contract": SOURCE,
    "operation": "append_ready_manifest_then_canonical_replay_once",
    "preserve_failed_execution": True,
    "next_issue_dispatch": False,
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
            row["event_digest"] != digest or record.artifact_digest != digest
            or record.execution_id != OLD_EXECUTION
            or record.manifest_digest != OLD_HEAD
            or record.control_plane_key != CONTROL
            or record.task_key != TASK or record.task_digest != TASK_DIGEST
            or record.event_type != kind or record.sequence != sequence
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
    engineering = cursor.execute(
        "SELECT id,status,metadata_json FROM agent_requests WHERE request_key=%s",
        (ENGINEERING_REQUEST,),
    ).fetchone()
    if (not engineering or engineering["id"] != 812
            or engineering["status"] != "completed"
            or engineering["metadata_json"].get("payload_sha256") != ENGINEERING_PAYLOAD):
        raise RecoveryError("engineering_recovery_not_completed")
    request = cursor.execute(
        "SELECT id,request_type,status,parent_request_id,payload_json FROM agent_requests "
        "WHERE request_key=%s FOR SHARE", (request_key,),
    ).fetchone()
    if (not request or request["request_type"] != "operator_release"
            or request["status"] != "executing" or request["parent_request_id"] != 812
            or request["payload_json"].get("commit") != commit
            or request["payload_json"].get("recovery") != RECOVERY_CONTRACT):
        raise RecoveryError("no_authorized_operator_recovery")
    executions = cursor.execute(
        "SELECT id,executor_role,executor_id,environment,run_id FROM agent_request_executions "
        "WHERE request_id=%s AND status='running' FOR SHARE", (request["id"],),
    ).fetchall()
    if (len(executions) != 1 or executions[0]["executor_role"] != "operator"
            or executions[0]["executor_id"] != executor_id
            or executions[0]["environment"] != "production" or not executions[0]["run_id"]):
        raise RecoveryError("operator_execution_identity_changed")
    return int(executions[0]["id"])


def prepare_retry(repository, *, root: Path, request_key: str,
                  executor_id: str, commit: str) -> dict[str, Any]:
    """Atomic, exact migration. It does not create completion or Evidence facts."""
    verify_sources(root)
    with repository.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
        operator_execution = verify_operator(
            cursor, request_key=request_key, executor_id=executor_id, commit=commit
        )
        head = cursor.execute(
            "SELECT current_manifest_digest FROM research_os_control_planes "
            "WHERE control_plane_key=%s FOR UPDATE", (CONTROL,),
        ).fetchone()
        if head is None:
            raise RecoveryError("incident_control_missing")
        prior = cursor.execute(
            "SELECT observation_json FROM research_os_external_executor_observations "
            "WHERE control_plane_key=%s AND owner=%s", (CONTROL, OWNER),
        ).fetchall()
        if prior:
            if len(prior) != 1:
                raise RecoveryError("recovery_attestation_duplicated")
            metadata = dict(prior[0]["observation_json"]["metadata"])
            if metadata.get("runtime_commit") != commit:
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
            "AND task_key=%s", (CONTROL, TASK),
        ).fetchone():
            raise RecoveryError("incident_partial_or_complete_registration")
        upstream = cursor.execute(
            "SELECT artifact_digest FROM research_os_mainline_artifacts "
            "WHERE control_plane_key=%s AND execution_id=%s "
            "AND artifact_type='M4P3ForwardPrequentialSettlement'",
            (CONTROL, SETTLEMENT_EXECUTION),
        ).fetchall()
        if [r["artifact_digest"] for r in upstream] != [SETTLEMENT_DIGEST]:
            raise RecoveryError("incident_settlement_changed")
        projection = cursor.execute(
            "SELECT declared_status,resolved_status FROM research_os_task_states "
            "WHERE control_plane_key=%s AND task_digest=%s FOR UPDATE",
            (CONTROL, TASK_DIGEST),
        ).fetchone()
        if projection != {"declared_status": "running", "resolved_status": "running"}:
            raise RecoveryError("incident_projection_changed")
        metadata = {
            **RECOVERY_CONTRACT, "old_manifest": OLD_HEAD,
            "ready_manifest": ready.artifact_digest, "runtime_commit": commit,
            "operator_request": request_key, "operator_execution": operator_execution,
            "engineering_request": ENGINEERING_REQUEST,
            "upstream_settlement": SETTLEMENT_DIGEST,
            "scientific_contract_changed": False,
        }
        observation = ExternalExecutorObservation(
            capability="p3_2026103_incident_recovery", owner=OWNER,
            status="READY_FOR_ONE_CANONICAL_REPLAY",
            observed_at=datetime.now(UTC).isoformat(),
            metadata=tuple(metadata.items()),
        )
        # Append a manifest; copy its unchanged Goal/Task links. The exact
        # before/after pair above is the whole scope of this approved migration.
        cursor.execute(
            "INSERT INTO research_os_manifests "
            "(manifest_digest,schema_version,manifest_json,source) VALUES (%s,%s,%s::jsonb,%s) "
            "ON CONFLICT (manifest_digest) DO NOTHING",
            (ready.artifact_digest, ready.schema_version,
             _json(ready.to_dict(include_digest=False)), OWNER),
        )
        saved = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest=%s",
            (ready.artifact_digest,),
        ).fetchone()
        if dict(saved["manifest_json"]) != ready.to_dict(include_digest=False):
            raise RecoveryError("ready_manifest_content_changed")
        for table, column in (("research_os_manifest_goals", "goal_digest"),
                              ("research_os_manifest_tasks", "task_digest")):
            cursor.execute(
                f"INSERT INTO {table} (manifest_digest,{column},ordinal) "
                f"SELECT %s,{column},ordinal FROM {table} WHERE manifest_digest=%s "
                "ON CONFLICT DO NOTHING",
                (ready.artifact_digest, OLD_HEAD),
            )
        resolution = next(r for r in repository.control_plane.resolve(ready).resolutions
                          if r.task_key == TASK)
        cursor.execute(
            "UPDATE research_os_task_states SET declared_status='draft', resolved_status=%s, "
            "completion_classification='INTEGRATION_PENDING', reason_code=%s, "
            "dependency_state_json=%s::jsonb, updated_at=now() "
            "WHERE control_plane_key=%s AND task_digest=%s",
            (resolution.status.value, resolution.reason_code,
             _json(resolution.unsatisfied_dependencies), CONTROL, TASK_DIGEST),
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
            (observation.artifact_digest, CONTROL, observation.capability, OWNER,
             observation.status, observation.observed_at, _json(observation)),
        )
    return {"status": "PREPARED", **metadata}
