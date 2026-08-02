from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from dehps.input_contracts.history_window import HistorySnapshotArtifact
from dehps.prediction.v2.contracts import require_issue, seal_artifact, verify_artifact

ISSUE_GOAL_KEY = "prediction-v2-shadow-per-issue"
PRE_CAPABILITY = "prediction_v2_shadow_issue_pre_draw"
PRE_REPLAY_CAPABILITY = "prediction_v2_shadow_issue_pre_draw_replay"
POST_CAPABILITY = "prediction_v2_shadow_issue_post_draw"
POST_REPLAY_CAPABILITY = "prediction_v2_shadow_issue_post_draw_replay"
_TASK_PROJECTION_FIELDS = frozenset(
    {
        "status",
        "completion_classification",
        "goal_digest",
        "superseded_by_task_digest",
    }
)


def issue_task_keys(issue: str) -> dict[str, str]:
    target = require_issue(issue, field="target_issue")
    prefix = f"prediction-v2-shadow-{target}"
    return {
        "pre": f"{prefix}-pre-draw",
        "pre_replay": f"{prefix}-pre-draw-replay",
        "post": f"{prefix}-post-draw",
        "post_replay": f"{prefix}-post-draw-replay",
    }


def issue_facts(issue: str) -> dict[str, str]:
    target = require_issue(issue, field="target_issue")
    prefix = f"prediction-v2-shadow:{target}"
    return {
        "pre_complete": f"{prefix}:PRE_DRAW:COMPLETED",
        "pre_replay": f"{prefix}:PRE_DRAW_REPLAY:VERIFIED",
        "draw_synced": f"{prefix}:DRAW_SYNCED",
        "post_complete": f"{prefix}:POST_DRAW:COMPLETED",
        "post_replay": f"{prefix}:POST_DRAW_REPLAY:VERIFIED",
    }


def build_history_artifact(history: HistorySnapshotArtifact) -> dict[str, Any]:
    history.verify()
    return seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-history-snapshot-artifact.v1",
            "artifact_type": "PredictionV2HistorySnapshotArtifact.v1",
            "history_snapshot": history.as_dict(include_records=True),
            "prior_only": True,
            "historical_evidence": "NOT_RUN",
            "parent_digests": [history.history_digest],
        },
        domain="dehps.prediction-v2.history-snapshot-artifact.v1",
    )


def history_from_artifact(payload: Mapping[str, Any]) -> HistorySnapshotArtifact:
    verified = verify_artifact(
        payload,
        domain="dehps.prediction-v2.history-snapshot-artifact.v1",
    )
    snapshot = verified.get("history_snapshot")
    if not isinstance(snapshot, Mapping) or not isinstance(snapshot.get("records"), list):
        raise TypeError("history artifact must contain canonical records")
    history = HistorySnapshotArtifact.from_history(
        snapshot["records"],
        source=str(snapshot.get("source") or "ssq_history"),
    )
    if history.as_dict(include_records=True) != dict(snapshot):
        raise ValueError("history snapshot content or identity changed")
    return history


def build_issue_manifest(
    *,
    history_artifact: Mapping[str, Any],
    target_issue: str,
) -> dict[str, Any]:
    history_payload = verify_artifact(
        history_artifact,
        domain="dehps.prediction-v2.history-snapshot-artifact.v1",
    )
    history = history_from_artifact(history_payload)
    target = require_issue(target_issue, field="target_issue")
    if history.latest_issue is None or target <= history.latest_issue:
        raise ValueError("target_issue must be strictly later than the prior-only snapshot")
    if any(record.issue == target for record in history.records):
        raise ValueError("target_issue must not exist in the prior-only snapshot")
    return seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-issue-manifest.v1",
            "artifact_type": "PredictionV2IssueManifest.v1",
            "issue": target,
            "as_of_issue": history.latest_issue,
            "history_artifact_digest": history_payload["artifact_digest"],
            "history_digest": history.history_digest,
            "route": "BASELINE_ONLY",
            "task_keys": issue_task_keys(target),
            "facts": issue_facts(target),
            "historical_evidence": "NOT_RUN",
            "evidence_progress_delta": 0,
            "promotion_gate_opened": False,
            "parent_digests": [history_payload["artifact_digest"]],
        },
        domain="dehps.prediction-v2.issue-manifest.v1",
    )


def build_actual_draw_artifact(
    *,
    issue: str,
    red_numbers: Sequence[object],
    durable_event_key: str,
    history_fingerprint: str,
) -> dict[str, Any]:
    from dehps.input_contracts.candidate_abi import validate_candidate_numbers
    from dehps.prediction.v2.generator import UNIVERSE

    target = require_issue(issue, field="issue")
    event_key = str(durable_event_key or "").strip()
    fingerprint = str(history_fingerprint or "").strip()
    if not event_key or not fingerprint:
        raise ValueError("actual draw requires durable event and history identities")
    return seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-actual-draw-artifact.v1",
            "artifact_type": "PredictionV2ActualDrawArtifact.v1",
            "issue": target,
            "red_numbers": list(validate_candidate_numbers(red_numbers, universe=UNIVERSE)),
            "durable_event_key": event_key,
            "history_fingerprint": fingerprint,
            "sync_status": "COMPLETED",
            "parent_digests": [],
        },
        domain="dehps.prediction-v2.actual-draw-artifact.v1",
    )


def _task(
    *,
    key: str,
    capability: str,
    inputs: list[str],
    dependencies: list[dict[str, str]],
    priority: int,
    issue_manifest_path: str,
    history_artifact_path: str,
    actual_draw_path: str,
    scheduler_plan_path: str,
    next_consumer: str,
) -> dict[str, Any]:
    return {
        "task_key": key,
        "goal_key": ISSUE_GOAL_KEY,
        "task_type": capability,
        "lane": "maintenance",
        "dependencies": dependencies,
        "priority": priority,
        "input_artifact_digests": inputs,
        "requested_capability": capability,
        "metric_contract": {
            "issue_manifest_path": issue_manifest_path,
            "history_artifact_path": history_artifact_path,
            "actual_draw_path": actual_draw_path,
            "scheduler_plan_path": scheduler_plan_path,
            "mainline_integration": {
                "goal": "Produce one replay-verified baseline-only Prediction v2 issue artifact.",
                "ready_condition": "Only declared artifact and durable-event dependencies are available.",
                "runner": "unified ResearchEvidenceSupervisor run-once",
                "upstream_artifacts": ["prior-only issue manifest", "registered parent execution"],
                "downstream_artifacts": ["immutable issue execution and replay artifacts"],
                "status_projection": "prediction-v2-shadow-status.json",
                "downstream_consumer": next_consumer,
                "evidence_progress_rule": "always zero",
                "decision_consumer": "shadow notification only after replay verification",
            },
            "route": "BASELINE_ONLY",
            "historical_evidence": "NOT_RUN",
            "promotion_gate_opened": False,
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def _source_task_identity(task: Mapping[str, Any]) -> dict[str, Any]:
    """Return only fields owned by the immutable source task definition."""
    return {
        key: value
        for key, value in task.items()
        if key not in _TASK_PROJECTION_FIELDS
    }


def extend_manifest_for_issue(
    base_payload: Mapping[str, Any],
    *,
    issue_manifest: Mapping[str, Any],
    issue_manifest_path: str,
    history_artifact_path: str,
    actual_draw_path: str,
    scheduler_plan_path: str,
    scheduler_plan_digest: str,
) -> dict[str, Any]:
    issue_value = verify_artifact(
        issue_manifest,
        domain="dehps.prediction-v2.issue-manifest.v1",
    )
    payload = json.loads(json.dumps(base_payload))
    payload.pop("artifact_digest", None)
    payload.pop("manifest_digest", None)
    goals = payload.setdefault("goals", [])
    if not any(item.get("goal_key") == ISSUE_GOAL_KEY for item in goals):
        goals.append(
            {
                "goal_key": ISSUE_GOAL_KEY,
                "semantic_version": "1.0.0",
                "objective_class": "runtime_capability",
                "success_evidence": ["per-issue pre/post physical replay verified"],
                "owner_lane": "maintenance",
                "question": "Can every future issue produce replay-verified shadow-only Top100 and settlement reports?",
                "baseline_metric_manifest": {"route": "BASELINE_ONLY"},
                "target_metric_manifest": {"pre_post_replay": True, "evidence_delta": 0},
                "guardrails": [
                    "prior_only_history",
                    "no_signal_experts",
                    "no_historical_evidence",
                    "no_promotion_gate",
                ],
                "status": "active",
            }
        )
    keys = dict(issue_value["task_keys"])
    facts = dict(issue_value["facts"])
    common_inputs = [
        str(issue_value["artifact_digest"]),
        str(issue_value["history_artifact_digest"]),
        str(scheduler_plan_digest),
    ]
    definitions = [
        _task(
            key=keys["pre"], capability=PRE_CAPABILITY, inputs=common_inputs,
            dependencies=[
                {"dependency_type": "artifact", "target_key": "prediction-v2-shadow:REFERENCE_REPLAY:VERIFIED", "required_status": "available"}
            ], priority=80, issue_manifest_path=issue_manifest_path,
            history_artifact_path=history_artifact_path, actual_draw_path=actual_draw_path,
            scheduler_plan_path=scheduler_plan_path,
            next_consumer=keys["pre_replay"],
        ),
        _task(
            key=keys["pre_replay"], capability=PRE_REPLAY_CAPABILITY, inputs=common_inputs,
            dependencies=[{"dependency_type": "artifact", "target_key": facts["pre_complete"], "required_status": "available"}],
            priority=70, issue_manifest_path=issue_manifest_path,
            history_artifact_path=history_artifact_path, actual_draw_path=actual_draw_path,
            scheduler_plan_path=scheduler_plan_path,
            next_consumer="replay-verified pre-draw notification",
        ),
        _task(
            key=keys["post"], capability=POST_CAPABILITY, inputs=common_inputs,
            dependencies=[
                {"dependency_type": "artifact", "target_key": facts["pre_replay"], "required_status": "available"},
                {"dependency_type": "external_event", "target_key": facts["draw_synced"], "required_status": "observed"},
            ], priority=60, issue_manifest_path=issue_manifest_path,
            history_artifact_path=history_artifact_path, actual_draw_path=actual_draw_path,
            scheduler_plan_path=scheduler_plan_path,
            next_consumer=keys["post_replay"],
        ),
        _task(
            key=keys["post_replay"], capability=POST_REPLAY_CAPABILITY, inputs=common_inputs,
            dependencies=[{"dependency_type": "artifact", "target_key": facts["post_complete"], "required_status": "available"}],
            priority=50, issue_manifest_path=issue_manifest_path,
            history_artifact_path=history_artifact_path, actual_draw_path=actual_draw_path,
            scheduler_plan_path=scheduler_plan_path,
            next_consumer="replay-verified post-draw notification",
        ),
    ]
    tasks = payload.setdefault("tasks", [])
    existing = {str(item.get("task_key")): item for item in tasks}
    for definition in definitions:
        current = existing.get(definition["task_key"])
        if current is not None:
            immutable_current = _source_task_identity(current)
            immutable_definition = _source_task_identity(definition)
            if immutable_current != immutable_definition:
                raise ValueError(f"issue task identity collision: {definition['task_key']}")
        if current is None:
            tasks.append(definition)
    return payload


def task_contract(task: Any) -> dict[str, Any]:
    value = json.loads(task.metric_contract)
    if not isinstance(value, dict):
        raise TypeError("issue task metric contract must be an object")
    return value


def load_json_artifact(root_dir: Path, relative_path: str) -> dict[str, Any]:
    path = root_dir / relative_path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load issue input artifact: {relative_path}") from exc
    if not isinstance(value, dict):
        raise TypeError(f"issue input artifact is not an object: {relative_path}")
    return value
