from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from dehps.input_contracts.history_window import HistorySnapshotArtifact
from dehps.models.frequency_ranker import next_ssq_draw_date
from dehps.prediction.v2.contracts import seal_artifact
from dehps.prediction.v2.issues import (
    build_actual_draw_artifact,
    build_history_artifact,
    build_issue_manifest,
    extend_manifest_for_issue,
    issue_facts,
    issue_task_keys,
)
from dehps.prediction.v2.runtime import persist_immutable_json
from dehps.research_os.models import ControlPlaneManifest


def source_paths(*, issue: str) -> dict[str, str]:
    prefix = f"runtime/research-os/prediction-v2-shadow/issue-inputs/{issue}"
    return {
        "history": f"{prefix}/history-artifact.json",
        "issue_manifest": f"{prefix}/issue-manifest.json",
        "actual_draw": f"{prefix}/actual-draw-artifact.json",
        "scheduler_plan": f"{prefix}/live-scheduler-plan.json",
    }


def infer_target_issue(history_rows: Sequence[object]) -> str:
    history = HistorySnapshotArtifact.from_history(history_rows, source="ssq_history")
    if not history.records or history.latest_issue is None:
        raise ValueError("ssq_history is empty")
    latest = history.records[-1]
    if latest.draw_date is not None:
        target_date = next_ssq_draw_date(latest.draw_date)
        latest_year = int(latest.issue[:4])
        if target_date.year < latest_year or target_date.year > latest_year + 1:
            raise ValueError("draw date and issue year are inconsistent")
        if target_date.year == latest_year + 1:
            return f"{target_date.year}001"
    return str(int(latest.issue) + 1)


def materialize_pre_draw_extension(
    *,
    root_dir: Path,
    base_manifest: Mapping[str, Any],
    history_rows: Sequence[object],
    target_issue: str,
    persist: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    history = HistorySnapshotArtifact.from_history(history_rows, source="ssq_history")
    history_artifact = build_history_artifact(history)
    issue_manifest = build_issue_manifest(
        history_artifact=history_artifact,
        target_issue=target_issue,
    )
    paths = source_paths(issue=str(issue_manifest["issue"]))
    plan = seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-live-scheduler-plan.v1",
            "artifact_type": "PredictionV2LiveSchedulerPlan.v1",
            "mode": "SHADOW_PER_ISSUE",
            "issue": issue_manifest["issue"],
            "task_keys": issue_task_keys(str(issue_manifest["issue"])),
            "source_paths": paths,
            "pre_draw_schedule": "Tue,Thu,Sun 17:00 Asia/Shanghai",
            "post_draw_trigger": "durable audited draw-sync completion",
            "legacy_cutover": "OPERATOR_REQUIRED",
            "operator_sequence": [
                "capture_active_unit_and_cron_snapshot",
                "stop_and_disable_legacy_training_and_three_line_report_units",
                "verify_legacy_worker_cgroups_empty",
                "install_prediction_v2_pre_draw_and_draw_sync_source_units",
                "daemon_reload",
                "enable_prediction_v2_pre_draw_timer",
                "restart_draw_sync_timer_with_prediction_v2_post_consumer",
                "verify_no_legacy_started_event_after_activation",
            ],
            "rollback_sequence": [
                "stop_prediction_v2_pre_draw_timer_and_draw_sync_v2_consumer",
                "restore_captured_unit_and_cron_snapshot",
                "remove_retirement_activation_only_if_no_v2_delivery_is_uncertain",
                "daemon_reload",
                "verify_legacy_state_matches_snapshot_before_optional_restart",
            ],
            "source_units": [
                "deploy/systemd/dehps-prediction-v2-shadow-pre-draw.service",
                "deploy/systemd/dehps-prediction-v2-shadow-pre-draw.timer",
                "deploy/systemd/dehps-draw-sync.service",
            ],
            "legacy_stop_precedes_v2_activation": True,
            "additive_only": True,
            "live_service_operations": [],
            "historical_evidence": "NOT_RUN",
            "evidence_progress_delta": 0,
            "promotion_gate_opened": False,
            "parent_digests": [issue_manifest["artifact_digest"]],
        },
        domain="dehps.prediction-v2.live-scheduler-plan.v1",
    )
    if persist:
        persist_immutable_json(root_dir / paths["history"], history_artifact)
        persist_immutable_json(root_dir / paths["issue_manifest"], issue_manifest)
        persist_immutable_json(root_dir / paths["scheduler_plan"], plan)
    extended = extend_manifest_for_issue(
        base_manifest,
        issue_manifest=issue_manifest,
        issue_manifest_path=paths["issue_manifest"],
        history_artifact_path=paths["history"],
        actual_draw_path=paths["actual_draw"],
        scheduler_plan_path=paths["scheduler_plan"],
        scheduler_plan_digest=str(plan["artifact_digest"]),
    )
    ControlPlaneManifest.from_dict(extended)
    return extended, plan


def materialize_post_draw_extension(
    *,
    root_dir: Path,
    base_manifest: Mapping[str, Any],
    issue: str,
    red_numbers: Sequence[object],
    durable_event_key: str,
    history_fingerprint: str,
    persist: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    task_keys = issue_task_keys(issue)
    existing = {str(item.get("task_key")) for item in base_manifest.get("tasks", [])}
    if set(task_keys.values()) - existing:
        raise ValueError("post-draw settlement requires the frozen pre-draw issue DAG")
    actual = build_actual_draw_artifact(
        issue=issue,
        red_numbers=red_numbers,
        durable_event_key=durable_event_key,
        history_fingerprint=history_fingerprint,
    )
    paths = source_paths(issue=issue)
    if persist:
        persist_immutable_json(root_dir / paths["actual_draw"], actual)
    payload = json.loads(json.dumps(base_manifest))
    payload.pop("artifact_digest", None)
    payload.pop("manifest_digest", None)
    facts = payload.setdefault("facts", {})
    events = facts.setdefault("external_events", [])
    draw_fact = issue_facts(issue)["draw_synced"]
    if draw_fact not in events:
        events.append(draw_fact)
        events.sort()
    ControlPlaneManifest.from_dict(payload)
    plan = {
        "schema_version": "dehps-prediction-v2-live-scheduler-plan.v1",
        "artifact_type": "PredictionV2LiveSchedulerPlan.v1",
        "mode": "POST_DRAW",
        "issue": issue,
        "actual_draw_artifact_digest": actual["artifact_digest"],
        "durable_event_key": durable_event_key,
        "published_external_event": draw_fact,
        "source_paths": paths,
        "additive_only": True,
        "live_service_operations": [],
        "historical_evidence": "NOT_RUN",
        "evidence_progress_delta": 0,
        "promotion_gate_opened": False,
    }
    return payload, plan


def additive_migration_dry_run(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    before_goals = {item["goal_key"]: item for item in before.get("goals", [])}
    after_goals = {item["goal_key"]: item for item in after.get("goals", [])}
    before_tasks = {item["task_key"]: item for item in before.get("tasks", [])}
    after_tasks = {item["task_key"]: item for item in after.get("tasks", [])}
    removed_goals = sorted(set(before_goals) - set(after_goals))
    removed_tasks = sorted(set(before_tasks) - set(after_tasks))
    changed_goals = sorted(key for key, value in before_goals.items() if after_goals.get(key) != value)
    changed_tasks = sorted(key for key, value in before_tasks.items() if after_tasks.get(key) != value)
    before_facts = before.get("facts", {})
    after_facts = after.get("facts", {})
    removed_facts = {
        group: sorted(set(before_facts.get(group, [])) - set(after_facts.get(group, [])))
        for group in ("artifacts", "evidence", "external_events", "authorities")
    }
    verified = not removed_goals and not removed_tasks and not changed_goals and not changed_tasks and not any(removed_facts.values())
    return {
        "schema_version": "dehps-prediction-v2-additive-migration-dry-run.v1",
        "status": "VERIFIED" if verified else "REJECTED",
        "additive_only": verified,
        "removed_goals": removed_goals,
        "removed_tasks": removed_tasks,
        "changed_goals": changed_goals,
        "changed_tasks": changed_tasks,
        "removed_facts": removed_facts,
        "live_state_changed": False,
        "service_operations_executed": [],
    }
