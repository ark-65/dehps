from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dehps.research_os.models import ControlPlaneManifest

RAW_REPLAY_TASK_KEY = "m4-v2-p2-6-1-raw-execution-replay"
FAILED_TASK_DIGEST = "5b33879347e5a0092341a0cd1b9ccf45ceffe4a51fdde9c873a5bde1f6823ae9"
FAILED_EXECUTION_ID = (
    "fa31459228db15b5a7f19263bda951c3ef0b85b714b32f9b9393a36cb76058ad"
)
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


class RawReplayRecoveryError(RuntimeError):
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
    completed = [
        event for event in related if event.get("event_type") == "completed"
    ]
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
