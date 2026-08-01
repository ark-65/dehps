from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.notifications.mail import QqMailConfig, QqMailService
from dehps.notifications.prediction_v2_shadow import PredictionV2NotificationLedger
from dehps.prediction.v2.issues import issue_task_keys
from dehps.prediction.v2.mainline import CONTROL_PLANE_KEY
from dehps.prediction.v2.scheduling import (
    additive_migration_dry_run,
    infer_target_issue,
    materialize_post_draw_extension,
    materialize_pre_draw_extension,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import ResearchEvidenceSupervisor
from dehps.storage.postgres_store import load_history_with_dates


def _run_tasks(repository: PostgresResearchOSRepository, keys: list[str]) -> list[dict]:
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,
        control_plane_key=CONTROL_PLANE_KEY,
    )
    return [supervisor.run_once(task_key=key) for key in keys]


def _deliver_latest_envelope(
    repository: PostgresResearchOSRepository,
    *,
    replay_task_key: str,
) -> dict:
    events = repository.list_mainline_execution_events(
        control_plane_key=CONTROL_PLANE_KEY,
        task_key=replay_task_key,
    )
    completed = [item for item in events if item.get("event_type") == "completed"]
    if len(completed) != 1:
        raise RuntimeError("notification requires exactly one replay completion")
    registrations = repository.list_mainline_artifacts(
        control_plane_key=CONTROL_PLANE_KEY,
        execution_id=str(completed[0]["execution_id"]),
    )
    matches = [item for item in registrations if item["artifact_type"] == "PredictionV2NotificationEnvelope.v1"]
    if len(matches) != 1:
        raise RuntimeError("notification requires one registered replay envelope")
    envelope = json.loads((ROOT_DIR / str(matches[0]["artifact_path"])).read_text(encoding="utf-8"))
    mail = QqMailService(QqMailConfig.from_environment())
    ledger = PredictionV2NotificationLedger(
        ROOT_DIR / "runtime/notifications/prediction-v2-shadow-mail.json"
    )
    return ledger.deliver(
        envelope,
        sender=lambda subject, body: mail.send(subject=subject, text=body).message_id,
    )


def _pre(repository: PostgresResearchOSRepository, *, target_issue: str, apply: bool, send: bool) -> dict:
    with get_connection() as conn:
        history = load_history_with_dates(conn)
    if not history:
        raise RuntimeError("ssq_history is empty")
    issue = target_issue or infer_target_issue(history)
    before = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    after, plan = materialize_pre_draw_extension(
        root_dir=ROOT_DIR,
        base_manifest=before,
        history_rows=history,
        target_issue=issue,
        persist=apply,
    )
    dry_run = additive_migration_dry_run(before=before, after=after)
    if dry_run["status"] != "VERIFIED":
        raise RuntimeError("pre-draw manifest migration is not additive")
    if not apply:
        return {"status": "DRY_RUN", "plan": plan, "migration": dry_run}
    repository.import_manifest(
        control_plane_key=CONTROL_PLANE_KEY,
        payload=after,
        source=f"prediction-v2-shadow-pre-draw:{issue}",
    )
    keys = issue_task_keys(issue)
    executions = _run_tasks(repository, [keys["pre"], keys["pre_replay"]])
    delivery = _deliver_latest_envelope(repository, replay_task_key=keys["pre_replay"]) if send else {"status": "WITHHELD_NOT_REQUESTED"}
    return {"status": "PRE_DRAW_REPLAY_VERIFIED", "issue": issue, "executions": executions, "delivery": delivery}


def _post(repository: PostgresResearchOSRepository, *, issue: str, apply: bool, send: bool) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT h.issue, h.red_numbers, e.event_key, e.history_fingerprint
              FROM ssq_history h
              JOIN draw_issue_events e ON e.new_issue = h.issue
              JOIN draw_sync_runs r ON r.event_key = e.event_key
             WHERE h.issue = %s AND r.completed_at IS NOT NULL
               AND r.audit_passed IS TRUE AND r.status = 'new_issue'
             ORDER BY r.completed_at DESC
            """,
            (issue,),
        ).fetchall()
    identities = {(str(item[0]), tuple(item[1]), str(item[2]), str(item[3])) for item in row}
    if len(identities) != 1:
        raise RuntimeError("post-draw requires exactly one durable audited synchronized event")
    actual_issue, red_numbers, event_key, fingerprint = next(iter(identities))
    before = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    after, plan = materialize_post_draw_extension(
        root_dir=ROOT_DIR,
        base_manifest=before,
        issue=actual_issue,
        red_numbers=red_numbers,
        durable_event_key=event_key,
        history_fingerprint=fingerprint,
        persist=apply,
    )
    dry_run = additive_migration_dry_run(before=before, after=after)
    if dry_run["status"] != "VERIFIED":
        raise RuntimeError("post-draw manifest migration is not additive")
    if not apply:
        return {"status": "DRY_RUN", "plan": plan, "migration": dry_run}
    repository.import_manifest(
        control_plane_key=CONTROL_PLANE_KEY,
        payload=after,
        source=f"prediction-v2-shadow-post-draw:{issue}",
    )
    keys = issue_task_keys(issue)
    executions = _run_tasks(repository, [keys["post"], keys["post_replay"]])
    delivery = _deliver_latest_envelope(repository, replay_task_key=keys["post_replay"]) if send else {"status": "WITHHELD_NOT_REQUESTED"}
    return {"status": "POST_DRAW_REPLAY_VERIFIED", "issue": issue, "executions": executions, "delivery": delivery}


def settle_synchronized_issue(issue: str) -> dict:
    """Draw-sync consumer used only after the Operator activates Prediction v2 shadow."""
    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    return _post(repository, issue=issue, apply=True, send=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize and run one canonical Prediction v2 shadow issue DAG.")
    parser.add_argument("mode", choices=("pre", "post"))
    parser.add_argument("--issue", default="")
    parser.add_argument("--apply", action="store_true", help="Import and run; default is a non-mutating control-plane dry run.")
    parser.add_argument("--send", action="store_true", help="Send only the replay-verified envelope; requires --apply.")
    args = parser.parse_args(argv)
    if args.send and not args.apply:
        parser.error("--send requires --apply")
    if args.mode == "post" and not args.issue:
        parser.error("post mode requires --issue")
    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    result = (
        _pre(repository, target_issue=args.issue, apply=args.apply, send=args.send)
        if args.mode == "pre"
        else _post(repository, issue=args.issue, apply=args.apply, send=args.send)
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
