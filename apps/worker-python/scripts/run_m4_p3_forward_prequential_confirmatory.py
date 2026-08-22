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

import build_m4_p3_forward_prequential_confirmatory_manifest as builder
from dehps.agents.repository import AgentRequestRepository
from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as successor,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_task_manifest,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.storage.postgres_store import load_history_with_dates

CONTROL_PLANE_KEY = builder.CONTROL_PLANE_KEY
OUTPUT_ROOT = ROOT_DIR / "data/output/m4-p3-forward-prequential-confirmatory"


def _snapshot(repository: PostgresResearchOSRepository):
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    return manifest, repository.control_plane.resolve(manifest)


def _task_statuses(repository: PostgresResearchOSRepository) -> dict[str, str]:
    _, snapshot = _snapshot(repository)
    return {item.task_key: item.status.value for item in snapshot.resolutions}


def _run_pending(
    repository: PostgresResearchOSRepository, task_keys: Sequence[str]
) -> list[dict[str, Any]]:
    supervisor = successor.ForwardPrequentialSupervisor(
        repository=repository, control_plane_key=CONTROL_PLANE_KEY
    )
    output: list[dict[str, Any]] = []
    for key in task_keys:
        status = _task_statuses(repository).get(key)
        if status == "completed":
            output.append({"task_key": key, "status": "ALREADY_COMPLETED"})
            continue
        if status != "ready":
            raise RuntimeError(f"successor task is not Ready: {key}:{status}")
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
        control_plane_key=CONTROL_PLANE_KEY, task_key=task_key
    )
    completed = [item for item in events if item.get("event_type") == "completed"]
    if len(completed) != 1:
        raise RuntimeError(f"expected one completed successor execution: {task_key}")
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
            f"registered successor artifact is unavailable: {artifact_type}"
        )
    return json.loads(path.read_text(encoding="utf-8")), str(path)


def _issue_groups(
    repository: PostgresResearchOSRepository,
) -> dict[str, dict[str, str]]:
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    groups: dict[str, dict[str, str]] = {}
    for task in manifest.tasks:
        if task.requested_capability != successor.REFIT_CAPABILITY:
            continue
        contract = task.to_dict().get("metric_contract", {})
        issue = str(contract.get("target_issue") or "")
        if issue:
            groups[issue] = successor.issue_task_keys(issue)
    return dict(sorted(groups.items()))


def _publish_predraw_report(
    repository: PostgresResearchOSRepository, *, issue: str
) -> str:
    report, _ = _registered_payload(
        repository,
        task_key=successor.issue_task_keys(issue)["predraw"],
        artifact_type=successor.PREDRAW_REPORT_ARTIFACT_TYPE,
    )
    markdown = report.get("body", {}).get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise RuntimeError("registered successor pre-draw Markdown is missing")
    output = OUTPUT_ROOT / issue / "pre-draw-report.md"
    atomic_write_text(output, markdown.rstrip() + "\n")
    return str(output)


def _activate_predraw(
    repository: PostgresResearchOSRepository, *, issue: str
) -> dict[str, Any]:
    keys = successor.issue_task_keys(issue)
    executions = _run_pending(
        repository, [keys["refit"], keys["predraw"], keys["predraw_replay"]]
    )
    report_path = _publish_predraw_report(repository, issue=issue)
    model, _ = _registered_payload(
        repository, task_key=keys["refit"], artifact_type=successor.MODEL_ARTIFACT_TYPE
    )
    candidates, _ = _registered_payload(
        repository,
        task_key=keys["predraw"],
        artifact_type=successor.MODEL_CANDIDATE_ARTIFACT_TYPE,
    )
    baseline, _ = _registered_payload(
        repository,
        task_key=keys["predraw"],
        artifact_type=successor.RANDOM_BASELINE_ARTIFACT_TYPE,
    )
    checkpoint, _ = _registered_payload(
        repository,
        task_key=keys["predraw"],
        artifact_type=successor.CHECKPOINT_ARTIFACT_TYPE,
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
        "old_checkpoint_reused": checkpoint["body"]["old_checkpoint_reused"],
        "pre_draw_report_path": report_path,
        "executions": executions,
    }


def launch(*, apply: bool) -> dict[str, Any]:
    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    source = successor.load_source_contract(root_dir=ROOT_DIR)
    successor.verify_governance(AgentRequestRepository())
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    goal_present = any(item.goal_key == successor.GOAL_KEY for item in manifest.goals)
    with get_connection() as connection:
        history = load_history_with_dates(connection)
    issue, draw_date, _, _ = successor.target_for_now(history)
    if not goal_present:
        output, dry_run = builder.build_initial_manifest(
            repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY),
            source_digest=str(source["artifact_digest"]),
            target_issue=issue,
            target_draw_date=draw_date.isoformat(),
        )
        if not apply:
            return {
                "status": "DRY_RUN_VERIFIED",
                "issue": issue,
                "draw_date": draw_date.isoformat(),
                "migration": dry_run,
                "old_source": successor.old_source_digest_verification(),
            }
        repository.import_manifest(
            control_plane_key=CONTROL_PLANE_KEY,
            payload=output,
            source=f"m4-p3-forward-prequential-launch:{issue}",
        )
        migration = dry_run
    else:
        if not apply:
            return compact_status(repository=repository)
        groups = _issue_groups(repository)
        if not groups:
            raise RuntimeError("successor goal has no issue tasks")
        issue = next(reversed(groups))
        migration = {"status": "ALREADY_IMPORTED"}
    preregistration = _run_pending(repository, [successor.PREREGISTRATION_TASK_KEY])
    predraw = _activate_predraw(repository, issue=issue)
    return {
        "status": "AUTONOMOUS_WAIT_FORWARD",
        "current_route": successor.LINEAGE_ID,
        "old_lineage_projection": "IMMUTABLE_HISTORY_NOT_CURRENT_ROUTE",
        "issue": issue,
        "draw_date": draw_date.isoformat(),
        "migration": migration,
        "preregistration": preregistration,
        "predraw": predraw,
        "post_draw_settlement": "ARMED",
        "automatic_next_issue_refit": "ACTIVE",
        "formal_p4": "PREREGISTRATION_FROZEN_NOT_EXECUTED / DEPENDENCY_WAIT",
    }


def _audited_issue_identity(issue: str) -> tuple[str, str] | None:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT e.event_key, e.history_fingerprint
              FROM ssq_history h
              JOIN draw_issue_events e ON e.new_issue = h.issue
              JOIN draw_sync_runs r ON r.event_key = e.event_key
             WHERE h.issue = %s AND r.completed_at IS NOT NULL
               AND r.audit_passed IS TRUE AND r.status = 'new_issue'
             ORDER BY r.completed_at DESC
            """,
            (issue,),
        ).fetchall()
    identities = {(str(row[0]), str(row[1])) for row in rows}
    if not identities:
        return None
    if len(identities) != 1:
        raise RuntimeError("successor settlement requires one audited issue identity")
    return next(iter(identities))


def _terminal_decision(repository: PostgresResearchOSRepository) -> str | None:
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    facts = set(manifest.facts.to_dict()["artifacts"])
    for look in successor.LOOKS:
        for decision in (
            "PASS_TO_P4",
            "FAIL_NO_FORWARD_ADVANTAGE",
            "INVALID_FORWARD_EXECUTION",
            "INCONCLUSIVE_AT_MAX_N",
        ):
            if successor.decision_fact(look, decision) in facts:
                return decision
    return None


def _append_next_issue(
    repository: PostgresResearchOSRepository, *, previous_issue: str
) -> tuple[str, str, dict[str, Any]]:
    if _terminal_decision(repository) is not None:
        raise RuntimeError("successor lineage is terminal; next issue append forbidden")
    with get_connection() as connection:
        history = load_history_with_dates(connection)
    issue, draw_date, _, _ = successor.target_for_now(history)
    groups = _issue_groups(repository)
    if issue in groups:
        return issue, draw_date.isoformat(), {"status": "ALREADY_PRESENT"}
    source = successor.load_source_contract(root_dir=ROOT_DIR)
    output, dry_run = builder.append_issue_manifest(
        repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY),
        source_digest=str(source["artifact_digest"]),
        target_issue=issue,
        target_draw_date=draw_date.isoformat(),
        previous_issue=previous_issue,
    )
    repository.import_manifest(
        control_plane_key=CONTROL_PLANE_KEY,
        payload=output,
        source=f"m4-p3-forward-prequential-next-issue:{issue}",
    )
    return issue, draw_date.isoformat(), dry_run


def settle_and_advance(
    repository: PostgresResearchOSRepository, *, issue: str
) -> dict[str, Any]:
    groups = _issue_groups(repository)
    if issue not in groups:
        return {"status": "NOT_TARGET_ISSUE", "issue": issue}
    keys = groups[issue]
    statuses = _task_statuses(repository)
    if statuses.get(keys["settlement_replay"]) == "completed":
        terminal = _terminal_decision(repository)
        if terminal is not None:
            return {
                "status": "P3_TERMINAL",
                "issue": issue,
                "decision": terminal,
                "next_issue_prepared": False,
            }
        next_issue, next_draw_date, migration = _append_next_issue(
            repository, previous_issue=issue
        )
        predraw = _activate_predraw(repository, issue=next_issue)
        return {
            "status": "REGISTERED_SETTLEMENT_ADVANCED_TO_NEXT_SEAL",
            "issue": issue,
            "next_issue": next_issue,
            "next_draw_date": next_draw_date,
            "next_issue_migration": migration,
            "next_predraw": predraw,
        }
    if statuses.get(keys["predraw_replay"]) != "completed":
        raise RuntimeError("successor target lacks replay-verified pre-draw seal")
    if _audited_issue_identity(issue) is None:
        return {"status": "WAITING_FOR_AUDITED_DRAW", "issue": issue}
    live = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    output, _ = build_additive_task_manifest(
        live_payload=live,
        new_tasks=(),
        add_external_events=(successor.issue_facts(issue)["draw_synced"],),
    )
    repository.import_manifest(
        control_plane_key=CONTROL_PLANE_KEY,
        payload=output,
        source=f"m4-p3-forward-prequential-draw-synced:{issue}",
    )
    settlement = _run_pending(
        repository, [keys["settlement"], keys["settlement_replay"]]
    )
    settlement_payload, _ = _registered_payload(
        repository,
        task_key=keys["settlement"],
        artifact_type=successor.SETTLEMENT_ARTIFACT_TYPE,
    )
    cohort_index = int(settlement_payload["body"]["cohort_index"])
    review = None
    if cohort_index in successor.LOOKS:
        review = _run_pending(repository, [successor.review_task_key(cohort_index)])
    terminal = _terminal_decision(repository)
    if terminal is not None:
        return {
            "status": "P3_TERMINAL",
            "issue": issue,
            "cohort_index": cohort_index,
            "decision": terminal,
            "settlement": settlement,
            "review": review,
            "next_issue_prepared": False,
        }
    next_issue, next_draw_date, migration = _append_next_issue(
        repository, previous_issue=issue
    )
    predraw = _activate_predraw(repository, issue=next_issue)
    return {
        "status": "SETTLED_AND_NEXT_SEALED",
        "issue": issue,
        "cohort_index": cohort_index,
        "settlement": settlement,
        "review": review,
        "next_issue": next_issue,
        "next_draw_date": next_draw_date,
        "next_issue_migration": migration,
        "next_predraw": predraw,
    }


def cycle(*, sync_draws: bool) -> dict[str, Any]:
    if sync_draws:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_draw_sync_watch.py",
                "--once",
                "--no-resume-on-event",
                "--interval-seconds",
                "900",
                "--hot-interval-seconds",
                "300",
                "--cold-interval-seconds",
                "3600",
                "--timezone",
                "Asia/Shanghai",
            ],
            cwd=WORKER_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"draw sync failed: {completed.stderr.strip()}")
    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    groups = _issue_groups(repository)
    if not groups:
        return {"status": "NOT_LAUNCHED"}
    issue = next(reversed(groups))
    keys = groups[issue]
    statuses = _task_statuses(repository)
    if statuses.get(keys["predraw_replay"]) != "completed":
        return _activate_predraw(repository, issue=issue)
    return settle_and_advance(repository, issue=issue)


def compact_status(
    *, repository: PostgresResearchOSRepository | None = None
) -> dict[str, Any]:
    repository = repository or PostgresResearchOSRepository()
    repository.ensure_schema()
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    if not any(item.goal_key == successor.GOAL_KEY for item in manifest.goals):
        return {"status": "NOT_LAUNCHED"}
    groups = _issue_groups(repository)
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
    timer_active = successor.unit_active("dehps-forward-prequential-successor.timer")
    facts = set(manifest.facts.to_dict()["artifacts"])
    p4 = next(
        item
        for item in repository.control_plane.resolve(manifest).resolutions
        if item.task_key == successor.P4_TASK_KEY
    )
    return {
        "status": (
            "AUTONOMOUS_WAIT_FORWARD"
            if _terminal_decision(repository) is None
            else "P3_TERMINAL"
        ),
        "current_route": successor.LINEAGE_ID,
        "old_lineage_projection": "IMMUTABLE_HISTORY_NOT_CURRENT_ROUTE",
        "operational_model": "MARGINAL_STATIC",
        "preregistration": statuses.get(successor.PREREGISTRATION_TASK_KEY),
        "practical_threshold_bits_per_issue": successor.PRACTICAL_THRESHOLD,
        "interim_looks": list(successor.LOOKS),
        "settled_issue_count": len(settled),
        "maximum_issue_count": successor.MAX_N,
        "active": active,
        "automatic_settlement": "ACTIVE" if timer_active else "INACTIVE",
        "automatic_next_issue_refit": "ACTIVE" if timer_active else "INACTIVE",
        "automatic_scheduler": "ACTIVE" if timer_active else "INACTIVE",
        "normal_codex_invocations_per_issue": 0,
        "formal_p4_preregistration": (
            "FROZEN_NOT_EXECUTED"
            if successor.P4_PREREGISTRATION_FACT in facts
            else "PENDING"
        ),
        "formal_p4_status": p4.status.value,
        "pass_to_p4": successor.PASS_TO_P4_FACT in facts,
        "terminal_decision": _terminal_decision(repository),
        "old_p3": "0.01 bits/issue / 80% power / INCONCLUSIVE_DUE_TO_POWER / UNCHANGED",
        "aggregate_outcome_exposed_outside_frozen_look": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Launch and operate the frozen M4-P3 forward prequential successor"
    )
    parser.add_argument("mode", choices=("launch", "cycle", "post", "status"))
    parser.add_argument("--issue", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sync-draws", action="store_true")
    args = parser.parse_args(argv)
    if args.mode == "launch":
        result = launch(apply=args.apply)
    elif args.mode == "cycle":
        if not args.apply:
            result = compact_status()
        else:
            result = cycle(sync_draws=args.sync_draws)
    elif args.mode == "post":
        if not args.issue or not args.apply:
            parser.error("post mode requires --issue and --apply")
        result = settle_and_advance(PostgresResearchOSRepository(), issue=args.issue)
    else:
        result = compact_status()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
