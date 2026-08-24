from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.notifications import p3_top100 as notification
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_task_manifest,
)
from dehps.research_os.models import ControlPlaneManifest


class P3Top100ManifestError(ValueError):
    pass


def _integration(*, phase: str, next_consumer: str) -> dict[str, Any]:
    return {
        "goal": notification.GOAL_KEY,
        "ready_condition": (
            "exact registered successor-P3 replay parents are available; post also "
            "requires exact settlement replay and complete issue payout source"
        ),
        "runner": (
            "P3Top100NotificationSupervisor exact notification-only task dispatch "
            "through the unified ResearchEvidenceSupervisor"
        ),
        "upstream_artifacts": [
            "registered successor-P3 candidate/checkpoint/predraw replay",
            "registered successor-P3 settlement replay for post-draw only",
            "exact issue payout source for post-draw only",
        ],
        "downstream_artifacts": [phase],
        "status_projection": "p3-top100-notification status",
        "downstream_consumer": next_consumer,
        "evidence_progress_rule": "zero; notification and payout have no P3 decision credit",
        "decision_consumer": "none; delivery requires typed plus generic replay",
    }


def _task(
    *,
    key: str,
    task_type: str,
    capability: str,
    priority: int,
    input_digests: Sequence[str],
    dependencies: Sequence[Mapping[str, str]],
    issue: str,
    recipient_digest: str,
    next_consumer: str,
    payout_source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metric: dict[str, Any] = {
        "issue": issue,
        "recipient_digest": recipient_digest,
        "lineage_id": notification.p3.LINEAGE_ID,
        "configuration_drift": False,
        "external_delivery": False,
        "p3_decision_credit": False,
        "mainline_integration": _integration(
            phase=task_type, next_consumer=next_consumer
        ),
    }
    if payout_source is not None:
        metric["payout_source"] = deepcopy(dict(payout_source))
    return {
        "task_key": key,
        "goal_key": notification.GOAL_KEY,
        "task_type": task_type,
        "lane": "maintenance",
        "dependencies": [dict(item) for item in dependencies],
        "priority": priority,
        "input_artifact_digests": list(input_digests),
        "requested_capability": capability,
        "metric_contract": metric,
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def build_initial_manifest(
    *, minimum_issue: str, recipient_digest: str, source_digest: str
) -> dict[str, Any]:
    minimum_issue = notification._issue(minimum_issue)
    payload = {
        "schema_version": "research-os-control-plane-v1",
        "goals": [
            {
                "goal_key": notification.GOAL_KEY,
                "semantic_version": "1.0.0",
                "objective_class": "runtime_capability",
                "success_evidence": [
                    "pre and post envelopes compile from exact registered P3 parents",
                    "typed and generic replay verify before the delivery ledger",
                ],
                "owner_lane": "maintenance",
                "question": (
                    "Can the frozen successor-P3 Top-100 be reported before and after "
                    "draw without changing P3 science or claiming an edge?"
                ),
                "baseline_metric_manifest": {
                    "automatic_p3_top100_mail": False,
                    "p3_scientific_lineage": notification.p3.LINEAGE_ID,
                },
                "target_metric_manifest": {
                    "minimum_issue": minimum_issue,
                    "recipient_digest": recipient_digest,
                    "source_contract_digest": source_digest,
                    "hypothetical_cost_cny": "200.00",
                    "tax_free_boundary_cny": "10000.00",
                    "typed_and_generic_replay_required": True,
                },
                "guardrails": [
                    "notification_only",
                    "p3_source_bytes_frozen",
                    "no_legacy_static_100",
                    "no_p3_p4_p5_or_promotion_dispatch",
                    "no_expected_profit_or_probability_edge_claim",
                ],
                "status": "active",
            }
        ],
        "tasks": [],
        "facts": {
            "artifacts": [],
            "evidence": [],
            "external_events": [],
            "authorities": [],
        },
    }
    return ControlPlaneManifest.from_dict(payload).to_dict(include_digest=True)


def _assert_goal_identity(
    live: Mapping[str, Any], *, recipient_digest: str, source_digest: str
) -> ControlPlaneManifest:
    manifest = ControlPlaneManifest.from_dict(deepcopy(dict(live)))
    if len(manifest.goals) != 1 or manifest.goals[0].goal_key != notification.GOAL_KEY:
        raise P3Top100ManifestError("notification_goal_changed")
    target = json.loads(manifest.goals[0].target_metric_manifest)
    if (
        target.get("recipient_digest") != recipient_digest
        or target.get("source_contract_digest") != source_digest
        or target.get("hypothetical_cost_cny") != "200.00"
        or target.get("tax_free_boundary_cny") != "10000.00"
    ):
        raise P3Top100ManifestError("notification_goal_binding_changed")
    return manifest


def add_pre_tasks(
    live: Mapping[str, Any],
    *,
    issue: str,
    recipient_digest: str,
    source_digest: str,
    predraw_input_digests: Sequence[str],
    envelope_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _assert_goal_identity(
        live, recipient_digest=recipient_digest, source_digest=source_digest
    )
    minimum_issue = json.loads(manifest.goals[0].target_metric_manifest)[
        "minimum_issue"
    ]
    issue = notification._issue(issue)
    if issue < minimum_issue:
        raise P3Top100ManifestError("notification_issue_precedes_activation")
    keys = notification.issue_task_keys(issue)
    facts = notification.issue_facts(issue)
    if any(
        task.task_key in {keys["pre"], keys["pre_replay"]} for task in manifest.tasks
    ):
        raise P3Top100ManifestError("notification_pre_tasks_already_exist")
    tasks = (
        _task(
            key=keys["pre"],
            task_type="p3_top100_pre_mail_envelope_v1",
            capability=notification.PRE_ENVELOPE_CAPABILITY,
            priority=100,
            input_digests=(*predraw_input_digests, source_digest),
            dependencies=(),
            issue=issue,
            recipient_digest=recipient_digest,
            next_consumer=keys["pre_replay"],
        ),
        _task(
            key=keys["pre_replay"],
            task_type="p3_top100_pre_mail_replay_v1",
            capability=notification.PRE_REPLAY_CAPABILITY,
            priority=99,
            input_digests=(envelope_digest, source_digest),
            dependencies=(
                {
                    "dependency_type": "task",
                    "target_key": keys["pre"],
                    "required_status": "completed",
                },
                {
                    "dependency_type": "artifact",
                    "target_key": facts["pre"],
                    "required_status": "available",
                },
            ),
            issue=issue,
            recipient_digest=recipient_digest,
            next_consumer="idempotent QQ pre-draw delivery ledger",
        ),
    )
    return build_additive_task_manifest(live_payload=dict(live), new_tasks=tasks)


def add_post_tasks(
    live: Mapping[str, Any],
    *,
    issue: str,
    recipient_digest: str,
    source_digest: str,
    postdraw_input_digests: Sequence[str],
    payout_source: Mapping[str, Any],
    report_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _assert_goal_identity(
        live, recipient_digest=recipient_digest, source_digest=source_digest
    )
    minimum_issue = json.loads(manifest.goals[0].target_metric_manifest)[
        "minimum_issue"
    ]
    issue = notification._issue(issue)
    if issue < minimum_issue:
        raise P3Top100ManifestError("notification_issue_precedes_activation")
    payout = notification.validate_notification_artifact(payout_source)
    if payout["artifact_type"] != notification.PAYOUT_SOURCE_ARTIFACT_TYPE:
        raise P3Top100ManifestError("notification_payout_source_changed")
    keys = notification.issue_task_keys(issue)
    facts = notification.issue_facts(issue)
    if any(
        task.task_key in {keys["post"], keys["post_replay"]} for task in manifest.tasks
    ):
        raise P3Top100ManifestError("notification_post_tasks_already_exist")
    tasks = (
        _task(
            key=keys["post"],
            task_type="p3_top100_post_return_report_v1",
            capability=notification.POST_REPORT_CAPABILITY,
            priority=98,
            input_digests=(
                *postdraw_input_digests,
                payout["artifact_digest"],
                source_digest,
            ),
            dependencies=(),
            issue=issue,
            recipient_digest=recipient_digest,
            next_consumer=keys["post_replay"],
            payout_source=payout,
        ),
        _task(
            key=keys["post_replay"],
            task_type="p3_top100_post_return_replay_v1",
            capability=notification.POST_REPLAY_CAPABILITY,
            priority=97,
            input_digests=(report_digest, payout["artifact_digest"], source_digest),
            dependencies=(
                {
                    "dependency_type": "task",
                    "target_key": keys["post"],
                    "required_status": "completed",
                },
                {
                    "dependency_type": "artifact",
                    "target_key": facts["post"],
                    "required_status": "available",
                },
            ),
            issue=issue,
            recipient_digest=recipient_digest,
            next_consumer="idempotent QQ post-draw delivery ledger",
        ),
    )
    return build_additive_task_manifest(live_payload=dict(live), new_tasks=tasks)


def activation_simulation(
    *, minimum_issue: str, recipient_digest: str, source_digest: str
) -> dict[str, Any]:
    manifest = ControlPlaneManifest.from_dict(
        build_initial_manifest(
            minimum_issue=minimum_issue,
            recipient_digest=recipient_digest,
            source_digest=source_digest,
        )
    )
    snapshot = ResearchOSControlPlane().resolve(manifest)
    return {
        "status": "VALIDATED",
        "control_plane_key": notification.CONTROL_PLANE_KEY,
        "manifest_digest": manifest.artifact_digest,
        "goal_status": manifest.goal_states[0].status.value,
        "ready_queue": [item.task_key for item in snapshot.ready_queue],
        "dispatch_performed": False,
        "external_delivery": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimum-issue", required=True)
    parser.add_argument("--recipient-digest", required=True)
    args = parser.parse_args()
    source = notification.load_source_contract()
    print(
        json.dumps(
            activation_simulation(
                minimum_issue=args.minimum_issue,
                recipient_digest=args.recipient_digest,
                source_digest=str(source["artifact_digest"]),
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
