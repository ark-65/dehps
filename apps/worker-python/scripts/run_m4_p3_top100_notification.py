from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import build_m4_p3_top100_notification_manifest as builder
from dehps.agents.repository import AgentRequestRepository
from dehps.crawler.ssq_client import ZhcwSsqDataSource
from dehps.notifications import p3_top100 as notification
from dehps.notifications.mail import QqMailConfig
from dehps.research_os.models import ResearchOSValidationError
from dehps.research_os.repository import PostgresResearchOSRepository


class P3Top100RunnerError(RuntimeError):
    pass


def _recipient_digest(config: QqMailConfig) -> str:
    return hashlib.sha256(
        config.destination.strip().lower().encode("utf-8")
    ).hexdigest()


def _p3_issue_statuses(
    repository: PostgresResearchOSRepository,
) -> dict[str, dict[str, str]]:
    manifest = repository.load_manifest(
        control_plane_key=notification.P3_CONTROL_PLANE_KEY
    )
    snapshot = repository.control_plane.resolve(manifest)
    resolved = {item.task_key: item.status.value for item in snapshot.resolutions}
    output: dict[str, dict[str, str]] = {}
    for task in manifest.tasks:
        contract = json.loads(task.metric_contract)
        issue = str(contract.get("target_issue") or "")
        if not issue:
            continue
        keys = notification.p3.issue_task_keys(issue)
        output[issue] = {
            name: resolved.get(key, "missing") for name, key in keys.items()
        }
    return dict(sorted(output.items()))


def _latest_issue(
    repository: PostgresResearchOSRepository, *, phase: str, minimum_issue: str = "0"
) -> str | None:
    statuses = _p3_issue_statuses(repository)
    required = "predraw_replay" if phase == "pre" else "settlement_replay"
    matches = [
        issue
        for issue, values in statuses.items()
        if issue >= minimum_issue and values.get(required) == "completed"
    ]
    return max(matches) if matches else None


def _notification_manifest(repository: PostgresResearchOSRepository):
    return repository.load_manifest(control_plane_key=notification.CONTROL_PLANE_KEY)


def _goal_target(repository: PostgresResearchOSRepository) -> dict[str, Any]:
    manifest = _notification_manifest(repository)
    if len(manifest.goals) != 1 or manifest.goals[0].goal_key != notification.GOAL_KEY:
        raise P3Top100RunnerError("notification goal changed")
    return json.loads(manifest.goals[0].target_metric_manifest)


def install(
    *,
    apply: bool,
    repository: PostgresResearchOSRepository | None = None,
    config: QqMailConfig | None = None,
) -> dict[str, Any]:
    repository = repository or PostgresResearchOSRepository()
    repository.ensure_schema()
    config = config or QqMailConfig.from_environment()
    source = notification.load_source_contract()
    notification.verify_governance(AgentRequestRepository())
    recipient_digest = _recipient_digest(config)
    minimum_issue = _latest_issue(repository, phase="pre")
    if minimum_issue is None:
        raise P3Top100RunnerError(
            "no completed successor-P3 predraw replay is available"
        )
    payload = builder.build_initial_manifest(
        minimum_issue=minimum_issue,
        recipient_digest=recipient_digest,
        source_digest=str(source["artifact_digest"]),
    )
    if not apply:
        return {
            "status": "INSTALL_DRY_RUN_VALIDATED",
            "apply_requested": False,
            "minimum_issue": minimum_issue,
            "manifest_digest": payload["manifest_digest"],
            "external_delivery": False,
            "dispatch_performed": False,
        }
    try:
        existing = repository.load_manifest(
            control_plane_key=notification.CONTROL_PLANE_KEY
        )
    except ResearchOSValidationError:
        existing = None
    if existing is not None:
        if existing.to_dict(include_digest=True) != payload:
            raise P3Top100RunnerError(
                "notification control plane already exists with drift"
            )
        result = "ALREADY_INSTALLED"
    else:
        imported = repository.import_manifest(
            control_plane_key=notification.CONTROL_PLANE_KEY,
            payload=payload,
            source="m4-p3-top100-notification-v1-install",
        )
        result = str(imported)
    return {
        "status": "INSTALLED",
        "minimum_issue": minimum_issue,
        "manifest_digest": payload["manifest_digest"],
        "manifest_import": result,
        "external_delivery": False,
        "dispatch_performed": False,
    }


def _run_exact_tasks(
    repository: PostgresResearchOSRepository, *, task_keys: tuple[str, str]
) -> list[dict[str, Any]]:
    supervisor = notification.P3Top100NotificationSupervisor(repository=repository)
    allowed = set(task_keys)
    output: list[dict[str, Any]] = []
    for key in task_keys:
        manifest = repository.load_manifest(
            control_plane_key=notification.CONTROL_PLANE_KEY
        )
        snapshot = repository.control_plane.resolve(manifest)
        status = {
            item.task_key: item.status.value for item in snapshot.resolutions
        }.get(key)
        if key not in allowed:
            raise P3Top100RunnerError("notification task escaped exact allowlist")
        if status == "completed":
            generic = supervisor.replay(task_key=key)
            output.append(
                {
                    "task_key": key,
                    "status": "ALREADY_COMPLETED",
                    "generic_replay": generic,
                }
            )
            continue
        if status != "ready":
            raise P3Top100RunnerError(f"notification task is not Ready: {key}:{status}")
        execution = supervisor.run_once(task_key=key)
        generic = supervisor.replay(task_key=key)
        output.append(
            {
                "task_key": key,
                "status": "REPLAY_VERIFIED",
                "execution_id": execution["execution_id"],
                "execution_artifact_digest": execution["execution_artifact_digest"],
                "generic_replay": generic,
            }
        )
    return output


def _delivery(
    repository: PostgresResearchOSRepository,
    *,
    issue: str,
    kind: str,
    config: QqMailConfig,
) -> dict[str, Any]:
    email = notification.registered_delivery_email(
        repository,
        issue=issue,
        kind=kind,
        recipient=config.destination,
    )
    return notification.P3Top100NotificationDeliveryService(config).deliver(email)


def pre(
    *,
    apply: bool,
    deliver: bool,
    now: datetime | None = None,
    repository: PostgresResearchOSRepository | None = None,
    config: QqMailConfig | None = None,
) -> dict[str, Any]:
    if deliver and not apply:
        raise P3Top100RunnerError("delivery requires --apply")
    repository = repository or PostgresResearchOSRepository()
    repository.ensure_schema()
    config = config or QqMailConfig.from_environment()
    source = notification.load_source_contract()
    notification.verify_governance(AgentRequestRepository())
    target = _goal_target(repository)
    recipient_digest = _recipient_digest(config)
    if target.get("recipient_digest") != recipient_digest:
        raise P3Top100RunnerError("notification recipient binding changed")
    issue = _latest_issue(
        repository, phase="pre", minimum_issue=str(target["minimum_issue"])
    )
    if issue is None:
        return {"status": "WAITING_FOR_P3_PREDRAW_REPLAY", "dispatch_performed": False}
    bundle = notification.load_predraw_bundle(repository, issue=issue)
    moment = now or datetime.now(UTC)
    notification.require_pre_draw_window(
        moment, official_draw_time=str(bundle.checkpoint["body"]["official_draw_time"])
    )
    keys = notification.issue_task_keys(issue)
    manifest = _notification_manifest(repository)
    task_keys = {task.task_key for task in manifest.tasks}
    if keys["pre"] not in task_keys:
        envelope = notification.build_pre_envelope(
            bundle=bundle, recipient_digest=recipient_digest
        )
        payload, dry_run = builder.add_pre_tasks(
            manifest.to_dict(include_digest=True),
            issue=issue,
            recipient_digest=recipient_digest,
            source_digest=str(source["artifact_digest"]),
            predraw_input_digests=bundle.input_digests,
            envelope_digest=str(envelope["artifact_digest"]),
        )
        if not apply:
            return {
                "status": "PRE_DRY_RUN_VALIDATED",
                "issue": issue,
                "candidate_count": 100,
                "hypothetical_cost_cny": "200.00",
                "manifest_dry_run": dry_run,
                "dispatch_performed": False,
                "external_delivery": False,
            }
        repository.import_manifest(
            control_plane_key=notification.CONTROL_PLANE_KEY,
            payload=payload,
            source=f"m4-p3-top100-notification-pre-{issue}",
        )
    elif keys["pre_replay"] not in task_keys:
        raise P3Top100RunnerError("notification pre task pair is partial")
    executions = _run_exact_tasks(
        repository, task_keys=(keys["pre"], keys["pre_replay"])
    )
    delivery = (
        _delivery(repository, issue=issue, kind="pre", config=config)
        if deliver
        else None
    )
    return {
        "status": "PRE_REPLAY_VERIFIED" if not deliver else "PRE_DELIVERY_SETTLED",
        "issue": issue,
        "candidate_count": 100,
        "hypothetical_cost_cny": "200.00",
        "executions": executions,
        "delivery": delivery,
        "dispatch_performed": True,
        "external_delivery": bool(deliver),
    }


def post(
    *,
    apply: bool,
    deliver: bool,
    now: datetime | None = None,
    repository: PostgresResearchOSRepository | None = None,
    config: QqMailConfig | None = None,
    source_client: ZhcwSsqDataSource | None = None,
) -> dict[str, Any]:
    if deliver and not apply:
        raise P3Top100RunnerError("delivery requires --apply")
    repository = repository or PostgresResearchOSRepository()
    repository.ensure_schema()
    config = config or QqMailConfig.from_environment()
    source = notification.load_source_contract()
    notification.verify_governance(AgentRequestRepository())
    target = _goal_target(repository)
    recipient_digest = _recipient_digest(config)
    if target.get("recipient_digest") != recipient_digest:
        raise P3Top100RunnerError("notification recipient binding changed")
    issue = _latest_issue(
        repository, phase="post", minimum_issue=str(target["minimum_issue"])
    )
    if issue is None:
        return {
            "status": "WAITING_FOR_P3_SETTLEMENT_REPLAY",
            "dispatch_performed": False,
        }
    bundle = notification.load_postdraw_bundle(repository, issue=issue)
    official = datetime.fromisoformat(
        str(bundle.predraw.checkpoint["body"]["official_draw_time"])
    )
    moment = now or datetime.now(UTC)
    if moment.astimezone(UTC) < official.astimezone(UTC):
        return {"status": "WAITING_FOR_OFFICIAL_DRAW_TIME", "dispatch_performed": False}
    keys = notification.issue_task_keys(issue)
    manifest = _notification_manifest(repository)
    task_keys = {task.task_key for task in manifest.tasks}
    if keys["post"] not in task_keys:
        record = (source_client or ZhcwSsqDataSource()).fetch_issue_with_prizes(issue)
        if record is None:
            return {
                "status": "WAITING_FOR_COMPLETE_PAYOUT_SOURCE",
                "dispatch_performed": False,
            }
        payout = notification.normalize_payout_record(record=record, bundle=bundle)
        report = notification.build_post_report(
            bundle=bundle, payout=payout, recipient_digest=recipient_digest
        )
        payload, dry_run = builder.add_post_tasks(
            manifest.to_dict(include_digest=True),
            issue=issue,
            recipient_digest=recipient_digest,
            source_digest=str(source["artifact_digest"]),
            postdraw_input_digests=bundle.input_digests,
            payout_source=payout,
            report_digest=str(report["artifact_digest"]),
        )
        if not apply:
            return {
                "status": "POST_DRY_RUN_VALIDATED",
                "issue": issue,
                "accounting": report["body"]["accounting"],
                "manifest_dry_run": dry_run,
                "dispatch_performed": False,
                "external_delivery": False,
            }
        repository.import_manifest(
            control_plane_key=notification.CONTROL_PLANE_KEY,
            payload=payload,
            source=f"m4-p3-top100-notification-post-{issue}",
        )
    elif keys["post_replay"] not in task_keys:
        raise P3Top100RunnerError("notification post task pair is partial")
    executions = _run_exact_tasks(
        repository, task_keys=(keys["post"], keys["post_replay"])
    )
    delivery = (
        _delivery(repository, issue=issue, kind="post", config=config)
        if deliver
        else None
    )
    report = notification._completed_children(
        repository,
        root_dir=notification.ROOT_DIR,
        control_plane_key=notification.CONTROL_PLANE_KEY,
        task_key=keys["post"],
        expected_types={
            notification.PAYOUT_SOURCE_ARTIFACT_TYPE,
            notification.POST_REPORT_ARTIFACT_TYPE,
        },
        validator=notification.validate_notification_artifact,
    )[notification.POST_REPORT_ARTIFACT_TYPE]
    return {
        "status": "POST_REPLAY_VERIFIED" if not deliver else "POST_DELIVERY_SETTLED",
        "issue": issue,
        "accounting": report["body"]["accounting"],
        "executions": executions,
        "delivery": delivery,
        "dispatch_performed": True,
        "external_delivery": bool(deliver),
    }


def status(*, repository: PostgresResearchOSRepository | None = None) -> dict[str, Any]:
    repository = repository or PostgresResearchOSRepository()
    repository.ensure_schema()
    try:
        manifest = _notification_manifest(repository)
    except ResearchOSValidationError:
        return {"status": "NOT_INSTALLED", "automatic_mail": False}
    snapshot = repository.control_plane.resolve(manifest)
    tasks = {item.task_key: item.status.value for item in snapshot.resolutions}
    target = json.loads(manifest.goals[0].target_metric_manifest)
    return {
        "status": "ARMED",
        "control_plane_key": notification.CONTROL_PLANE_KEY,
        "manifest_digest": manifest.artifact_digest,
        "minimum_issue": target["minimum_issue"],
        "task_count": len(tasks),
        "ready_queue": [item.task_key for item in snapshot.ready_queue],
        "tasks": tasks,
        "p3_dispatch_allowed": False,
        "p4_dispatch_allowed": False,
        "p5_dispatch_allowed": False,
        "unkeyed_dispatch_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    install_parser = commands.add_parser("install")
    install_parser.add_argument("--apply", action="store_true")
    for name in ("pre", "post"):
        command = commands.add_parser(name)
        command.add_argument("--apply", action="store_true")
        command.add_argument("--deliver", action="store_true")
    args = parser.parse_args()
    if args.command == "status":
        result = status()
    elif args.command == "install":
        result = install(apply=args.apply)
    elif args.command == "pre":
        result = pre(apply=args.apply, deliver=args.deliver)
    else:
        result = post(apply=args.apply, deliver=args.deliver)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
