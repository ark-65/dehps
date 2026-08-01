from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest

P261_TASK_KEY = "m4-p2-false-positive-and-power-runs"
P27_TASK_KEY = "m4-p2-automatic-gate-and-report"
LEGACY_P3_TASK_KEY = "m4-p3-strict-historical-walk-forward"
RUNTIME_SLOT_RELEASE_EVENT = "m4-runtime-slot:p2-6-1-released"
EXPECTED_P261_TASK_DIGEST = (
    "80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa"
)
EXPECTED_P261_EXECUTION_ID = (
    "cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3"
)
EXPECTED_P261_MANIFEST_DIGEST = (
    "a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58"
)
EXPECTED_P261_CAPABILITY = "m4_p2_6_1_false_positive_and_power"


class CompletionGuardError(RuntimeError):
    pass


@dataclass(frozen=True)
class GuardDecision:
    state: str
    stop_service: bool
    publish_slot_event: bool
    reason: str
    completion_artifact_digest: str | None = None

    def to_artifact(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "dehps-m4-p2-6-1-completion-guard-decision.v1",
            "artifact_type": "p261_completion_guard_decision",
            "artifact_digest": "",
            "state": self.state,
            "stop_service": self.stop_service,
            "publish_slot_event": self.publish_slot_event,
            "reason": self.reason,
            "completion_artifact_digest": self.completion_artifact_digest,
            "statistical_results_read": False,
            "result_blind": True,
            "production_action": "service_stop_only_when_operator_authorized",
            "promotion_gate_opened": False,
        }
        identity = dict(payload)
        identity.pop("artifact_digest")
        payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.m4.p261-completion-guard-decision.v1",
        )
        return payload


def evaluate_terminal_boundary(
    *,
    p261_events: Sequence[Mapping[str, Any]],
    all_events: Sequence[Mapping[str, Any]],
    registrations: Sequence[Mapping[str, Any]],
    root_dir: Path,
) -> GuardDecision:
    """Evaluate only durable identity/status metadata; never open result artifacts."""

    forbidden_started = [
        event
        for event in all_events
        if event.get("task_key") in {P27_TASK_KEY, LEGACY_P3_TASK_KEY}
        and event.get("event_type") == "started"
    ]
    if forbidden_started:
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="DOWNSTREAM_DISPATCH_RACE",
        )
    matching = [
        event
        for event in p261_events
        if event.get("task_key") == P261_TASK_KEY
        and event.get("task_digest") == EXPECTED_P261_TASK_DIGEST
        and event.get("execution_id") == EXPECTED_P261_EXECUTION_ID
        and event.get("capability") == EXPECTED_P261_CAPABILITY
    ]
    drifted_terminal = [
        event
        for event in p261_events
        if event.get("event_type") in {"completed", "failed"}
        and event not in matching
    ]
    if drifted_terminal:
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="P261_IDENTITY_DRIFT",
        )
    failed = [event for event in matching if event.get("event_type") == "failed"]
    if failed:
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="P261_FAILED",
        )
    completed = [
        event for event in matching if event.get("event_type") == "completed"
    ]
    if not completed:
        return GuardDecision(
            state="WAITING",
            stop_service=False,
            publish_slot_event=False,
            reason="P261_TERMINAL_EVENT_NOT_AVAILABLE",
        )
    if len(completed) != 1:
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="P261_COMPLETED_EVENT_NOT_UNIQUE",
        )
    event = completed[0]
    started = [event for event in matching if event.get("event_type") == "started"]
    if (
        len(started) != 1
        or event.get("manifest_digest") is None
        or event.get("manifest_digest") != started[0].get("manifest_digest")
    ):
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="P261_COMPLETION_MANIFEST_IDENTITY_MISSING",
        )
    completion = [
        item
        for item in registrations
        if item.get("task_key") == P261_TASK_KEY
        and item.get("task_digest") == EXPECTED_P261_TASK_DIGEST
        and item.get("execution_id") == EXPECTED_P261_EXECUTION_ID
        and item.get("artifact_type") == "measurement_validation_completion"
    ]
    if len(completion) != 1:
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="IMMUTABLE_COMPLETION_ARTIFACT_NOT_UNIQUE",
        )
    registration = completion[0]
    path = root_dir / str(registration.get("artifact_path") or "")
    digest = str(registration.get("artifact_digest") or "")
    if len(digest) != 64 or not path.is_file():
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="IMMUTABLE_COMPLETION_ARTIFACT_MISSING",
        )
    return GuardDecision(
        state="STOP_REQUIRED",
        stop_service=True,
        publish_slot_event=False,
        reason="DURABLE_P261_COMPLETION_OBSERVED",
        completion_artifact_digest=digest,
    )


def evaluate_post_stop_boundary(
    *,
    service_active_state: str,
    worker_cgroup_empty: bool,
    downstream_started_events: Sequence[Mapping[str, Any]],
    completion_artifact_digest: str,
) -> GuardDecision:
    if downstream_started_events:
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="DOWNSTREAM_DISPATCH_RACE",
            completion_artifact_digest=completion_artifact_digest,
        )
    if service_active_state != "inactive" or not worker_cgroup_empty:
        return GuardDecision(
            state="STOP_VERIFICATION_FAILED",
            stop_service=True,
            publish_slot_event=False,
            reason="SERVICE_OR_WORKER_CGROUP_STILL_ACTIVE",
            completion_artifact_digest=completion_artifact_digest,
        )
    return GuardDecision(
        state="SAFE_TO_RELEASE_SLOT",
        stop_service=False,
        publish_slot_event=True,
        reason="SERVICE_INACTIVE_CGROUP_EMPTY_NO_DOWNSTREAM_START",
        completion_artifact_digest=completion_artifact_digest,
    )
