from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

import build_m4_v2_bounded_operational_forward_manifest as builder
from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.research_os.information_theory.measurement_system_v2 import (
    bounded_operational_forward as bounded,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_task_manifest,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import ResearchEvidenceSupervisor
from dehps.storage.postgres_store import load_history_with_dates

CONTROL_PLANE_KEY = builder.CONTROL_PLANE_KEY
OUTPUT_ROOT = ROOT_DIR / "data/output/m4-v2-bounded-operational-forward"


def _unit_active(unit: str) -> bool:
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", unit],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _snapshot(repository: PostgresResearchOSRepository):
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    return manifest, repository.control_plane.resolve(manifest)


def _task_statuses(repository: PostgresResearchOSRepository) -> dict[str, str]:
    _, snapshot = _snapshot(repository)
    return {item.task_key: item.status.value for item in snapshot.resolutions}


def _run_pending(
    repository: PostgresResearchOSRepository,
    task_keys: Sequence[str],
) -> list[dict[str, Any]]:
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,
        control_plane_key=CONTROL_PLANE_KEY,
    )
    output: list[dict[str, Any]] = []
    for key in task_keys:
        status = _task_statuses(repository).get(key)
        if status == "completed":
            output.append({"task_key": key, "status": "ALREADY_COMPLETED"})
            continue
        if status != "ready":
            raise RuntimeError(f"bounded forward task is not Ready: {key}:{status}")
        execution = supervisor.run_once(task_key=key)
        replay = supervisor.replay(task_key=key)
        output.append(
            {
                "task_key": key,
                "status": "REPLAY_VERIFIED",
                "execution_id": execution["execution_id"],
                "execution_artifact_digest": execution["execution_artifact_digest"],
                "registered_artifact_count": replay["registered_artifact_count"],
            }
        )
    return output


def _registered_payload(
    repository: PostgresResearchOSRepository,
    *,
    task_key: str,
    artifact_type: str,
) -> tuple[dict[str, Any], str]:
    events = repository.list_mainline_execution_events(
        control_plane_key=CONTROL_PLANE_KEY,
        task_key=task_key,
    )
    completed = [item for item in events if item.get("event_type") == "completed"]
    if len(completed) != 1:
        raise RuntimeError(f"expected one completed bounded execution: {task_key}")
    registrations = repository.list_mainline_artifacts(
        control_plane_key=CONTROL_PLANE_KEY,
        execution_id=str(completed[0]["execution_id"]),
    )
    matches = [item for item in registrations if item["artifact_type"] == artifact_type]
    if len(matches) != 1:
        raise RuntimeError(f"expected one registered {artifact_type}: {task_key}")
    path = (ROOT_DIR / str(matches[0]["artifact_path"])).resolve()
    if not path.is_relative_to(ROOT_DIR.resolve()) or not path.is_file():
        raise RuntimeError(
            f"registered bounded artifact is unavailable: {artifact_type}"
        )
    return json.loads(path.read_text(encoding="utf-8")), str(path)


def _publish_predraw_report(
    repository: PostgresResearchOSRepository,
    *,
    issue: str,
) -> str:
    keys = bounded.issue_task_keys(issue)
    report, _ = _registered_payload(
        repository,
        task_key=keys["predraw"],
        artifact_type=bounded.PREDRAW_REPORT_ARTIFACT_TYPE,
    )
    markdown = report.get("body", {}).get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise RuntimeError("registered bounded pre-draw Markdown is missing")
    output = OUTPUT_ROOT / issue / "pre-draw-report.md"
    atomic_write_text(output, markdown.rstrip() + "\n")
    return str(output)


def _current_issue_groups(
    repository: PostgresResearchOSRepository,
) -> dict[str, dict[str, str]]:
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    groups: dict[str, dict[str, str]] = {}
    for task in manifest.tasks:
        contract = task.to_dict().get("metric_contract", {})
        issue = str(contract.get("target_issue") or "")
        if issue and task.task_key in bounded.issue_task_keys(issue).values():
            groups[issue] = bounded.issue_task_keys(issue)
    return dict(sorted(groups.items()))


def _initial_manifest(
    repository: PostgresResearchOSRepository,
    *,
    apply: bool,
) -> tuple[str, str, dict[str, Any]]:
    with get_connection() as connection:
        history = load_history_with_dates(connection)
    issue, draw_date, _, _ = bounded.target_for_now(history)
    source = bounded.load_source_contract(root_dir=ROOT_DIR)
    live = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    output, dry_run = builder.build_manifest(
        live,
        source_contract_digest=str(source["artifact_digest"]),
        target_issue=issue,
        target_draw_date=draw_date.isoformat(),
    )
    if apply:
        repository.import_manifest(
            control_plane_key=CONTROL_PLANE_KEY,
            payload=output,
            source=f"m4-v2-bounded-forward-launch:{issue}",
        )
    return issue, draw_date.isoformat(), dry_run


def _append_next_issue(
    repository: PostgresResearchOSRepository,
    *,
    previous_issue: str | None,
) -> tuple[str, str, dict[str, Any]]:
    with get_connection() as connection:
        history = load_history_with_dates(connection)
    issue, draw_date, _, _ = bounded.target_for_now(history)
    groups = _current_issue_groups(repository)
    if issue in groups:
        return issue, draw_date.isoformat(), {"status": "ALREADY_PRESENT"}
    live = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    source = bounded.load_source_contract(root_dir=ROOT_DIR)
    new_tasks = builder.issue_tasks(
        source_digest=str(source["artifact_digest"]),
        target_issue=issue,
        target_draw_date=draw_date.isoformat(),
        previous_settlement_replay_fact=(
            bounded.issue_facts(previous_issue)["settlement_replay"]
            if previous_issue is not None
            else None
        ),
    )
    output, dry_run = build_additive_task_manifest(
        live_payload=live,
        new_tasks=new_tasks,
    )
    repository.import_manifest(
        control_plane_key=CONTROL_PLANE_KEY,
        payload=output,
        source=f"m4-v2-bounded-forward-next-issue:{issue}",
    )
    return issue, draw_date.isoformat(), dry_run


def _activate_predraw(
    repository: PostgresResearchOSRepository,
    *,
    issue: str,
) -> dict[str, Any]:
    keys = bounded.issue_task_keys(issue)
    executions = _run_pending(
        repository,
        [keys["refit"], keys["predraw"], keys["predraw_replay"]],
    )
    report_path = _publish_predraw_report(repository, issue=issue)
    model, _ = _registered_payload(
        repository,
        task_key=keys["refit"],
        artifact_type=bounded.MODEL_ARTIFACT_TYPE,
    )
    candidates, _ = _registered_payload(
        repository,
        task_key=keys["predraw"],
        artifact_type=bounded.MODEL_CANDIDATE_ARTIFACT_TYPE,
    )
    baseline, _ = _registered_payload(
        repository,
        task_key=keys["predraw"],
        artifact_type=bounded.RANDOM_BASELINE_ARTIFACT_TYPE,
    )
    checkpoint, _ = _registered_payload(
        repository,
        task_key=keys["predraw"],
        artifact_type=bounded.CHECKPOINT_ARTIFACT_TYPE,
    )
    return {
        "status": "PRE_DRAW_REPLAY_VERIFIED",
        "issue": issue,
        "training_end_issue": model["body"]["training_end_issue"],
        "model_digest": model["artifact_digest"],
        "probability_vector_length": len(model["body"]["probabilities_q_1_to_33"]),
        "model_ticket_count": candidates["body"]["candidate_count"],
        "random_baseline_ticket_count": baseline["body"]["candidate_count"],
        "same_blue_strategy": checkpoint["body"]["same_blue_strategy"],
        "checkpoint_status": checkpoint["body"]["status"],
        "configuration_drift": checkpoint["body"]["configuration_drift"],
        "pre_draw_report_path": report_path,
        "executions": executions,
    }


def launch(*, apply: bool) -> dict[str, Any]:
    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    goal_present = any(goal.goal_key == bounded.GOAL_KEY for goal in manifest.goals)
    if not goal_present:
        issue, draw_date, migration = _initial_manifest(repository, apply=apply)
        if not apply:
            return {
                "status": "DRY_RUN_VERIFIED",
                "issue": issue,
                "draw_date": draw_date,
                "migration": migration,
            }
    else:
        groups = _current_issue_groups(repository)
        if not groups:
            raise RuntimeError("bounded forward goal has no issue tasks")
        draw_date = ""
        migration = {"status": "ALREADY_IMPORTED"}
        statuses = _task_statuses(repository)
        latest = next(reversed(groups))
        latest_keys = groups[latest]
        if statuses.get(latest_keys["predraw"]) == "completed":
            issue = latest
        else:
            with get_connection() as connection:
                history = load_history_with_dates(connection)
            eligible, _, _, _ = bounded.target_for_now(history)
            if eligible not in groups:
                settled = [
                    candidate
                    for candidate, keys in groups.items()
                    if statuses.get(keys["settlement_replay"]) == "completed"
                ]
                issue, draw_date, migration = _append_next_issue(
                    repository,
                    previous_issue=settled[-1] if settled else None,
                )
            else:
                issue = eligible
    if not apply:
        raise RuntimeError("launch dry run did not return")
    executions = _run_pending(repository, [bounded.PREREGISTRATION_TASK_KEY])
    predraw = _activate_predraw(repository, issue=issue)
    return {
        "status": "AUTONOMOUS_WAIT_FORWARD",
        "issue": issue,
        "draw_date": draw_date,
        "migration": migration,
        "preregistration": executions,
        "predraw": predraw,
        "post_draw_settlement": "ARMED",
        "automatic_next_issue_refit": "ACTIVE",
    }


def settle_synchronized_issue(issue: str) -> dict[str, Any]:
    """Idempotent audited draw-sync consumer for the active bounded cohort."""

    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    groups = _current_issue_groups(repository)
    if issue not in groups:
        return {"status": "NOT_TARGET_ISSUE", "issue": issue}
    keys = groups[issue]
    statuses = _task_statuses(repository)
    if statuses.get(keys["settlement_replay"]) == "completed":
        return {"status": "ALREADY_SETTLED", "issue": issue}
    if statuses.get(keys["predraw_replay"]) != "completed":
        raise RuntimeError(
            f"target issue lacks a replay-verified pre-draw seal: {issue}"
        )
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT h.issue, e.event_key, e.history_fingerprint
              FROM ssq_history h
              JOIN draw_issue_events e ON e.new_issue = h.issue
              JOIN draw_sync_runs r ON r.event_key = e.event_key
             WHERE h.issue = %s AND r.completed_at IS NOT NULL
               AND r.audit_passed IS TRUE AND r.status = 'new_issue'
             ORDER BY r.completed_at DESC
            """,
            (issue,),
        ).fetchall()
    identities = {(str(row[0]), str(row[1]), str(row[2])) for row in rows}
    if len(identities) != 1:
        raise RuntimeError("bounded settlement requires one audited synchronized issue")
    live = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    event_fact = bounded.issue_facts(issue)["draw_synced"]
    output, _ = build_additive_task_manifest(
        live_payload=live,
        new_tasks=(),
        add_external_events=(event_fact,),
    )
    repository.import_manifest(
        control_plane_key=CONTROL_PLANE_KEY,
        payload=output,
        source=f"m4-v2-bounded-forward-draw-synced:{issue}",
    )
    settlement = _run_pending(
        repository,
        [keys["settlement"], keys["settlement_replay"]],
    )
    next_issue, next_draw_date, migration = _append_next_issue(
        repository,
        previous_issue=issue,
    )
    predraw = _activate_predraw(repository, issue=next_issue)
    return {
        "status": "SETTLED_AND_NEXT_SEALED",
        "issue": issue,
        "settlement": settlement,
        "next_issue": next_issue,
        "next_draw_date": next_draw_date,
        "next_issue_migration": migration,
        "next_predraw": predraw,
    }


def compact_status() -> dict[str, Any]:
    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    groups = _current_issue_groups(repository)
    statuses = _task_statuses(repository)
    settled = [
        issue
        for issue, keys in groups.items()
        if statuses.get(keys["settlement_replay"]) == "completed"
    ]
    active_issue = next(reversed(groups), None)
    active: dict[str, Any] = {}
    if active_issue is not None:
        keys = groups[active_issue]
        active = {
            "issue": active_issue,
            "checkpoint_status": statuses.get(keys["predraw"]),
            "replay_status": statuses.get(keys["predraw_replay"]),
            "settlement_status": statuses.get(keys["settlement"]),
            "configuration_drift": False,
            "pre_draw_report_path": str(
                OUTPUT_ROOT / active_issue / "pre-draw-report.md"
            ),
        }
    draw_scheduler_active = _unit_active("dehps-draw-sync.timer")
    predraw_scheduler_active = _unit_active("dehps-prediction-v2-shadow-pre-draw.timer")
    automatic_active = draw_scheduler_active and predraw_scheduler_active
    return {
        "status": "AUTONOMOUS_WAIT_FORWARD",
        "operational_model": "MARGINAL_STATIC",
        "mode": "SHADOW_ONLY / AUTONOMOUS_REFIT",
        "preregistration": statuses.get(bounded.PREREGISTRATION_TASK_KEY),
        "cohort_a_count": len(settled),
        "cohort_a_target": bounded.TARGET_COUNT,
        "active": active,
        "automatic_settlement": "ACTIVE" if draw_scheduler_active else "INACTIVE",
        "automatic_next_issue_refit": "ACTIVE" if automatic_active else "INACTIVE",
        "automatic_scheduler": "ACTIVE" if automatic_active else "INACTIVE",
        "draw_sync_timer_active": draw_scheduler_active,
        "predraw_safety_timer_active": predraw_scheduler_active,
        "normal_codex_invocations_per_issue": 0,
        "p3": "INCONCLUSIVE_DUE_TO_POWER / UNCHANGED",
        "formal_p4": "DEPENDENCY_WAIT",
        "promotion": "NOT_TRIGGERED",
        "aggregate_outcome_exposed": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Launch and operate the frozen bounded MARGINAL_STATIC shadow cohort."
    )
    parser.add_argument("mode", choices=("launch", "post", "status"))
    parser.add_argument("--issue", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.mode == "post" and not args.issue:
        parser.error("post mode requires --issue")
    if args.mode in {"launch", "post"} and not args.apply:
        result = (
            launch(apply=False)
            if args.mode == "launch"
            else {
                "status": "DRY_RUN_ONLY",
                "issue": args.issue,
            }
        )
    elif args.mode == "launch":
        result = launch(apply=True)
    elif args.mode == "post":
        result = settle_synchronized_issue(args.issue)
    else:
        result = compact_status()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
