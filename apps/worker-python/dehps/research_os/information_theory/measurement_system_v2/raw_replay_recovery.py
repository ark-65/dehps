from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dehps.research_os.models import ControlPlaneManifest

RAW_REPLAY_TASK_KEY = "m4-v2-p2-6-1-raw-execution-replay"
FAILED_TASK_DIGEST = "5b33879347e5a0092341a0cd1b9ccf45ceffe4a51fdde9c873a5bde1f6823ae9"
FAILED_EXECUTION_ID = "fa31459228db15b5a7f19263bda951c3ef0b85b714b32f9b9393a36cb76058ad"
FAILED_STARTED_EVENT_DIGEST = (
    "74dc67824fb96577611a6aeed9c597341bf2107e59ea896d4fe7739d4b007d2f"
)
FAILED_TERMINAL_EVENT_DIGEST = (
    "c6a8c8541f3b8555a81786035ab2ae8de15f7222e523d3cbf48386ed6d69a60a"
)
FAILED_ERROR = (
    "measurement_validation_update_policy_mismatch: replicate update policy "
    "does not match its task execution"
)

MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-design"
)
MARGINAL_STATIC_HEALTH_DESIGN_FAILED_TASK_DIGEST = (
    "b2ae3d49de0eb1f8714d1636c4b6a3a05de2f66de99bef5bb1d4134dc85e78c4"
)
MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EXECUTION_ID = (
    "14e0c7c93fc41406154a23de1c842d979706090b6e302b45b6551b75d3fffa04"
)
MARGINAL_STATIC_HEALTH_DESIGN_STARTED_EVENT_DIGEST = (
    "6cd0e06ab7d75a1e00d44fac8171be0bde5d10dfafc3e5b56ceafec5678d5fca"
)
MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EVENT_DIGEST = (
    "ea3073f7d0f696d95607843c5de60d3d2794ca5fee826efa385dcd76c38caa25"
)
MARGINAL_STATIC_HEALTH_DESIGN_FAILED_ERROR = (
    "registered artifact type is missing: m4_v2_marginal_static_fixture"
)


class RawReplayRecoveryError(RuntimeError):
    pass


class MarginalStaticHealthDesignRecoveryError(RuntimeError):
    pass


def build_raw_replay_recovery_manifest(
    *,
    live_payload: Mapping[str, Any],
    execution_events: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reset only the exact failed raw replay task; preserve immutable events."""

    live = ControlPlaneManifest.from_dict(dict(live_payload))
    matching = [task for task in live.tasks if task.task_key == RAW_REPLAY_TASK_KEY]
    if len(matching) != 1 or matching[0].artifact_digest != FAILED_TASK_DIGEST:
        raise RawReplayRecoveryError("raw_replay_recovery_task_identity_changed")
    state = live.task_state_by_digest[FAILED_TASK_DIGEST]
    if (
        state.declared_status.value != "failed"
        or state.completion_classification.value != "INTEGRATED"
    ):
        raise RawReplayRecoveryError("raw_replay_recovery_task_is_not_exact_failure")

    related = [
        dict(event)
        for event in execution_events
        if event.get("task_digest") == FAILED_TASK_DIGEST
        and event.get("execution_id") == FAILED_EXECUTION_ID
    ]
    started = [event for event in related if event.get("event_type") == "started"]
    failed = [event for event in related if event.get("event_type") == "failed"]
    completed = [event for event in related if event.get("event_type") == "completed"]
    if (
        len(started) != 1
        or len(failed) != 1
        or completed
        or started[0].get("event_digest") != FAILED_STARTED_EVENT_DIGEST
        or failed[0].get("event_digest") != FAILED_TERMINAL_EVENT_DIGEST
        or _event_payload(failed[0]).get("error") != FAILED_ERROR
    ):
        raise RawReplayRecoveryError("raw_replay_recovery_event_history_changed")

    output = live.to_dict(include_digest=False)
    changed = 0
    for task in output["tasks"]:
        if task["task_key"] != RAW_REPLAY_TASK_KEY:
            continue
        task["status"] = "draft"
        task["completion_classification"] = "INTEGRATION_PENDING"
        changed += 1
    if changed != 1:
        raise RawReplayRecoveryError("raw_replay_recovery_transition_count_changed")
    recovered = ControlPlaneManifest.from_dict(output)
    recovered_payload = recovered.to_dict(include_digest=True)
    report = {
        "schema_version": "dehps-m4-v2-raw-replay-recovery.v1",
        "status": "SAFE_TO_RECOVER",
        "input_manifest_digest": live.artifact_digest,
        "output_manifest_digest": recovered.artifact_digest,
        "task_key": RAW_REPLAY_TASK_KEY,
        "task_digest": FAILED_TASK_DIGEST,
        "failed_execution_id": FAILED_EXECUTION_ID,
        "preserved_started_event_digest": FAILED_STARTED_EVENT_DIGEST,
        "preserved_failed_event_digest": FAILED_TERMINAL_EVENT_DIGEST,
        "state_transition": "failed/INTEGRATED -> draft/INTEGRATION_PENDING",
        "changed_task_count": 1,
        "deleted_event_count": 0,
        "rewritten_event_count": 0,
        "completed_task_regression_count": 0,
        "statistical_result_payloads_read": False,
        "prediction_v2_promotion": False,
        "p3_execution": False,
    }
    return recovered_payload, report


def build_marginal_static_health_design_recovery_manifest(
    *,
    live_payload: Mapping[str, Any],
    execution_events: Sequence[Mapping[str, Any]],
    execution_artifacts: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reset only the exact zero-work health-design failure for fresh execution."""

    live = ControlPlaneManifest.from_dict(dict(live_payload))
    matching = [
        task
        for task in live.tasks
        if task.task_key == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY
    ]
    if (
        len(matching) != 1
        or matching[0].artifact_digest
        != MARGINAL_STATIC_HEALTH_DESIGN_FAILED_TASK_DIGEST
    ):
        raise MarginalStaticHealthDesignRecoveryError(
            "marginal_static_health_recovery_task_identity_changed"
        )
    state = live.task_state_by_digest[MARGINAL_STATIC_HEALTH_DESIGN_FAILED_TASK_DIGEST]
    if (
        state.declared_status.value != "failed"
        or state.completion_classification.value != "INTEGRATED"
    ):
        raise MarginalStaticHealthDesignRecoveryError(
            "marginal_static_health_recovery_task_is_not_exact_failure"
        )

    related = [
        dict(event)
        for event in execution_events
        if event.get("task_digest") == MARGINAL_STATIC_HEALTH_DESIGN_FAILED_TASK_DIGEST
        and event.get("execution_id")
        == MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EXECUTION_ID
    ]
    started = [event for event in related if event.get("event_type") == "started"]
    failed = [event for event in related if event.get("event_type") == "failed"]
    completed = [event for event in related if event.get("event_type") == "completed"]
    if (
        len(related) != 2
        or len(started) != 1
        or len(failed) != 1
        or completed
        or started[0].get("event_digest")
        != MARGINAL_STATIC_HEALTH_DESIGN_STARTED_EVENT_DIGEST
        or failed[0].get("event_digest")
        != MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EVENT_DIGEST
        or _event_payload(failed[0]).get("error")
        != MARGINAL_STATIC_HEALTH_DESIGN_FAILED_ERROR
    ):
        raise MarginalStaticHealthDesignRecoveryError(
            "marginal_static_health_recovery_event_history_changed"
        )
    if execution_artifacts:
        raise MarginalStaticHealthDesignRecoveryError(
            "marginal_static_health_recovery_artifacts_exist"
        )

    output = live.to_dict(include_digest=False)
    changed = 0
    for task in output["tasks"]:
        if task["task_key"] != MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY:
            continue
        task["status"] = "draft"
        task["completion_classification"] = "INTEGRATION_PENDING"
        changed += 1
    if changed != 1:
        raise MarginalStaticHealthDesignRecoveryError(
            "marginal_static_health_recovery_transition_count_changed"
        )
    recovered = ControlPlaneManifest.from_dict(output)
    recovered_payload = recovered.to_dict(include_digest=True)
    report = {
        "schema_version": "dehps-m4-v2-marginal-static-health-recovery.v1",
        "status": "SAFE_TO_RECOVER",
        "input_manifest_digest": live.artifact_digest,
        "output_manifest_digest": recovered.artifact_digest,
        "task_key": MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
        "task_digest": MARGINAL_STATIC_HEALTH_DESIGN_FAILED_TASK_DIGEST,
        "failed_execution_id": MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EXECUTION_ID,
        "preserved_started_event_digest": (
            MARGINAL_STATIC_HEALTH_DESIGN_STARTED_EVENT_DIGEST
        ),
        "preserved_failed_event_digest": (
            MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EVENT_DIGEST
        ),
        "state_transition": "failed/INTEGRATED -> draft/INTEGRATION_PENDING",
        "changed_task_count": 1,
        "deleted_task_count": 0,
        "deleted_event_count": 0,
        "rewritten_event_count": 0,
        "completed_task_regression_count": 0,
        "preexisting_execution_artifact_count": 0,
        "generated_issues": 0,
        "synthetic_replicates": 0,
        "historical_outcomes_read": False,
        "statistical_result_payloads_read": False,
        "evidence_created": False,
        "prediction_v2_promotion": False,
        "sampled_health_execution": False,
    }
    return recovered_payload, report


def _event_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    if isinstance(payload, Mapping):
        return dict(payload)
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        try:
            return dict(payload)
        except (TypeError, ValueError):
            return {}
    return {}
