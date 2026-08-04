from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.models import MainlineArtifactRegistration

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
EXPECTED_P261_MEASUREMENT_VALIDATION_MANIFEST_DIGEST = (
    "a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58"
)
EXPECTED_P261_RUNNING_CONTROL_PLANE_MANIFEST_DIGEST = (
    "dd9a2a0106fe17787cb57a6293bd1e9eea9cb8c30771f6a7e27b0ecc30c18ce3"
)
EXPECTED_P261_CAPABILITY = "m4_p2_6_1_false_positive_and_power"
EXPECTED_P261_RECOVERED_FAILED_EVENT_DIGEST = (
    "c003525e63c6570f74dbde06c2cb8ed67e79886829c7a4be52f13f2bede9544e"
)
EXPECTED_CONTROL_PLANE_KEY = "m4-information-theory-mainline"
EXPECTED_P261_COMPLETION_SCHEMA = "dehps-m4-p2-measurement-validation-completion.v1"
GUARD_DECISION_SCHEMA = "dehps-m4-p2-6-1-completion-guard-decision.v1"
GUARD_DECISION_TYPE = "p261_completion_guard_decision"
GUARD_DECISION_DOMAIN = "dehps.m4.p261-completion-guard-decision.v1"
SAFE_RELEASE_REASON = "SERVICE_INACTIVE_CGROUP_EMPTY_NO_DOWNSTREAM_START"
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

_GUARD_CONTRACT = {
    "p261_task_key": P261_TASK_KEY,
    "p261_task_digest": EXPECTED_P261_TASK_DIGEST,
    "p261_execution_id": EXPECTED_P261_EXECUTION_ID,
    "p261_measurement_validation_manifest_digest": (
        EXPECTED_P261_MEASUREMENT_VALIDATION_MANIFEST_DIGEST
    ),
    "p261_running_control_plane_manifest_digest": (
        EXPECTED_P261_RUNNING_CONTROL_PLANE_MANIFEST_DIGEST
    ),
    "p261_capability": EXPECTED_P261_CAPABILITY,
    "p261_recovered_failed_event_digest": (
        EXPECTED_P261_RECOVERED_FAILED_EVENT_DIGEST
    ),
    "slot_release_event": RUNTIME_SLOT_RELEASE_EVENT,
}
GUARD_CONTRACT_DIGEST = canonical_digest(
    _GUARD_CONTRACT,
    domain="dehps.m4.p261-completion-guard-contract.v1",
)


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
            "schema_version": GUARD_DECISION_SCHEMA,
            "artifact_type": GUARD_DECISION_TYPE,
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
            "guard_contract_digest": GUARD_CONTRACT_DIGEST,
            "slot_release_event": RUNTIME_SLOT_RELEASE_EVENT,
            "parent_digests": sorted(
                {
                    GUARD_CONTRACT_DIGEST,
                    *(
                        [self.completion_artifact_digest]
                        if self.completion_artifact_digest is not None
                        else []
                    ),
                }
            ),
        }
        identity = dict(payload)
        identity.pop("artifact_digest")
        payload["artifact_digest"] = canonical_digest(
            identity,
            domain=GUARD_DECISION_DOMAIN,
        )
        return payload


def validate_slot_release_guard_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the exact result-blind authorization consumed by publisher."""

    expected_fields = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "state",
        "stop_service",
        "publish_slot_event",
        "reason",
        "completion_artifact_digest",
        "statistical_results_read",
        "result_blind",
        "production_action",
        "promotion_gate_opened",
        "guard_contract_digest",
        "slot_release_event",
        "parent_digests",
    }
    identity = dict(payload)
    digest = identity.pop("artifact_digest", None)
    completion_digest = str(payload.get("completion_artifact_digest") or "")
    if (
        set(payload) != expected_fields
        or payload.get("schema_version") != GUARD_DECISION_SCHEMA
        or payload.get("artifact_type") != GUARD_DECISION_TYPE
        or digest != canonical_digest(identity, domain=GUARD_DECISION_DOMAIN)
        or payload.get("state") != "SAFE_TO_RELEASE_SLOT"
        or payload.get("stop_service") is not False
        or payload.get("publish_slot_event") is not True
        or payload.get("reason") != SAFE_RELEASE_REASON
        or _SHA256_PATTERN.fullmatch(completion_digest) is None
        or payload.get("statistical_results_read") is not False
        or payload.get("result_blind") is not True
        or payload.get("production_action")
        != "service_stop_only_when_operator_authorized"
        or payload.get("promotion_gate_opened") is not False
        or payload.get("guard_contract_digest") != GUARD_CONTRACT_DIGEST
        or payload.get("slot_release_event") != RUNTIME_SLOT_RELEASE_EVENT
        or payload.get("parent_digests")
        != sorted({GUARD_CONTRACT_DIGEST, completion_digest})
    ):
        raise CompletionGuardError("slot_release_guard_artifact_invalid")
    return dict(payload)


def evaluate_terminal_boundary(
    *,
    p261_events: Sequence[Mapping[str, Any]],
    all_events: Sequence[Mapping[str, Any]],
    registrations: Sequence[Mapping[str, Any]],
    root_dir: Path,
) -> GuardDecision:
    """Evaluate only durable identity/status metadata; never open result artifacts."""

    expected_event_fields = {
        "event_digest",
        "execution_id",
        "control_plane_key",
        "manifest_digest",
        "task_digest",
        "task_key",
        "capability",
        "event_type",
        "sequence",
        "recorded_at",
    }
    recovered_failures = [
        event
        for event in p261_events
        if event.get("event_type") == "failed"
        and event.get("event_digest")
        == EXPECTED_P261_RECOVERED_FAILED_EVENT_DIGEST
    ]
    recovered_history = len(recovered_failures) == 1
    invalid_p261_metadata = [
        event
        for event in p261_events
        if (
            set(event) != expected_event_fields
            or event.get("control_plane_key") != EXPECTED_CONTROL_PLANE_KEY
            or _SHA256_PATTERN.fullmatch(str(event.get("event_digest") or "")) is None
            or not str(event.get("recorded_at") or "")
            or event.get("sequence")
            != (
                0
                if event.get("event_type") == "started"
                else 2
                if event.get("event_type") == "completed" and recovered_history
                else 1
            )
        )
    ]
    if invalid_p261_metadata:
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="P261_EVENT_METADATA_INVALID",
        )
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
        if event.get("event_type") in {"completed", "failed"} and event not in matching
    ]
    if drifted_terminal:
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="P261_IDENTITY_DRIFT",
        )
    failed = [event for event in matching if event.get("event_type") == "failed"]
    if failed and not (
        len(failed) == 1
        and failed[0].get("event_digest")
        == EXPECTED_P261_RECOVERED_FAILED_EVENT_DIGEST
    ):
        return GuardDecision(
            state="GOVERNANCE_INCIDENT",
            stop_service=True,
            publish_slot_event=False,
            reason="P261_FAILED",
        )
    completed = [event for event in matching if event.get("event_type") == "completed"]
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
        or event.get("manifest_digest")
        != EXPECTED_P261_RUNNING_CONTROL_PLANE_MANIFEST_DIGEST
        or started[0].get("manifest_digest")
        != EXPECTED_P261_RUNNING_CONTROL_PLANE_MANIFEST_DIGEST
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
    expected_registration_fields = {
        "registration_digest",
        "execution_id",
        "control_plane_key",
        "task_key",
        "task_digest",
        "artifact_digest",
        "artifact_type",
        "schema_version",
        "artifact_path",
        "parent_digests",
        "git_commit",
    }
    relative_path = Path(str(registration.get("artifact_path") or ""))
    expected_execution_dir = (
        root_dir
        / "runtime/research-os/mainline/tasks"
        / P261_TASK_KEY
        / EXPECTED_P261_EXECUTION_ID
    ).resolve()
    path = (root_dir / relative_path).resolve()
    digest = str(registration.get("artifact_digest") or "")
    parent_digests = registration.get("parent_digests")
    try:
        path.relative_to(expected_execution_dir)
        reconstructed_registration = MainlineArtifactRegistration(
            execution_id=str(registration.get("execution_id") or ""),
            control_plane_key=str(registration.get("control_plane_key") or ""),
            task_key=str(registration.get("task_key") or ""),
            task_digest=str(registration.get("task_digest") or ""),
            artifact_digest=digest,
            artifact_type=str(registration.get("artifact_type") or ""),
            schema_version=str(registration.get("schema_version") or ""),
            artifact_path=relative_path.as_posix(),
            parent_digests=tuple(str(value) for value in parent_digests),
            git_commit=str(registration.get("git_commit") or ""),
        )
    except (TypeError, ValueError):
        reconstructed_registration = None
    if (
        set(registration) != expected_registration_fields
        or relative_path.is_absolute()
        or ".." in relative_path.parts
        or _SHA256_PATTERN.fullmatch(digest) is None
        or not isinstance(parent_digests, list)
        or any(
            _SHA256_PATTERN.fullmatch(str(value)) is None for value in parent_digests
        )
        or registration.get("schema_version") != EXPECTED_P261_COMPLETION_SCHEMA
        or re.fullmatch(r"[0-9a-f]{40}", str(registration.get("git_commit") or ""))
        is None
        or registration.get("control_plane_key") != EXPECTED_CONTROL_PLANE_KEY
        or reconstructed_registration is None
        or registration.get("registration_digest")
        != reconstructed_registration.registration_digest
        or not path.is_file()
    ):
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
        reason=SAFE_RELEASE_REASON,
        completion_artifact_digest=completion_artifact_digest,
    )
