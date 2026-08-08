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
MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-execution"
)
MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_TASK_DIGEST = (
    "3f5a3250aaec1a1e02516734ad8f7ce49c5e8e0c18fafd098cb08bb9f2b103f0"
)
MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EXECUTION_ID = (
    "d0e5f7ee972ab33d899ca46d8d59cb718c1748888374bccf521273466663bfdf"
)
MARGINAL_STATIC_HEALTH_EXECUTION_STARTED_EVENT_DIGEST = (
    "01445142e807fd3d0e996f7bc8818123ded5aa9860b5a28d6f562329bad79919"
)
MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EVENT_DIGEST = (
    "83cf08c7ef24550d932ef15d4439cac26ca48ff546c445874ef4b19a0db16ddc"
)
MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_ERROR = (
    "M4 v2 marginal-static health execution source identities changed"
)
MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-gate-compiler"
)
MARGINAL_STATIC_HISTORICAL_GATE_FAILED_TASK_DIGEST = (
    "a109c223111b622d8b6e7c468ca878de6eda3c2e472e7632520571c5dba3eafd"
)
MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EXECUTION_ID = (
    "b95f468614ab3af0b7bfac75bbd3ad31daf45625bb0023ffd7bc4c051cc07cc5"
)
MARGINAL_STATIC_HISTORICAL_GATE_STARTED_EVENT_DIGEST = (
    "e3027eb300291958b5f876f197b9bfd9e56c1526bac3206a1445ed08b7e59469"
)
MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EVENT_DIGEST = (
    "83f53a2182415ad9eed9b4dbf6704287dcd60d9028505a5cbe2d56a74b84423a"
)
MARGINAL_STATIC_HISTORICAL_GATE_FAILED_ERROR = (
    "registered artifact type is not unique: "
    "measurement_v2_gate_compiler_contract"
)


class RawReplayRecoveryError(RuntimeError):
    pass


class MarginalStaticHealthDesignRecoveryError(RuntimeError):
    pass


class MarginalStaticHealthExecutionRecoveryError(RuntimeError):
    pass


class MarginalStaticHistoricalGateRecoveryError(RuntimeError):
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


def build_marginal_static_health_execution_recovery_manifest(
    *,
    live_payload: Mapping[str, Any],
    execution_events: Sequence[Mapping[str, Any]],
    execution_artifacts: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reset only the exact zero-replicate health-execution failure."""

    live = ControlPlaneManifest.from_dict(dict(live_payload))
    matching = [
        task
        for task in live.tasks
        if task.task_key == MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
    ]
    if (
        len(matching) != 1
        or matching[0].artifact_digest
        != MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_TASK_DIGEST
    ):
        raise MarginalStaticHealthExecutionRecoveryError(
            "marginal_static_health_execution_recovery_task_identity_changed"
        )
    state = live.task_state_by_digest[
        MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_TASK_DIGEST
    ]
    if (
        state.declared_status.value != "failed"
        or state.completion_classification.value != "INTEGRATED"
    ):
        raise MarginalStaticHealthExecutionRecoveryError(
            "marginal_static_health_execution_recovery_task_is_not_exact_failure"
        )

    related = [
        dict(event)
        for event in execution_events
        if event.get("task_digest")
        == MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_TASK_DIGEST
        and event.get("execution_id")
        == MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EXECUTION_ID
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
        != MARGINAL_STATIC_HEALTH_EXECUTION_STARTED_EVENT_DIGEST
        or failed[0].get("event_digest")
        != MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EVENT_DIGEST
        or _event_payload(failed[0]).get("error")
        != MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_ERROR
    ):
        raise MarginalStaticHealthExecutionRecoveryError(
            "marginal_static_health_execution_recovery_event_history_changed"
        )
    if execution_artifacts:
        raise MarginalStaticHealthExecutionRecoveryError(
            "marginal_static_health_execution_recovery_artifacts_exist"
        )

    output = live.to_dict(include_digest=False)
    changed = 0
    for task in output["tasks"]:
        if task["task_key"] != MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY:
            continue
        task["status"] = "draft"
        task["completion_classification"] = "INTEGRATION_PENDING"
        changed += 1
    if changed != 1:
        raise MarginalStaticHealthExecutionRecoveryError(
            "marginal_static_health_execution_recovery_transition_count_changed"
        )
    recovered = ControlPlaneManifest.from_dict(output)
    recovered_payload = recovered.to_dict(include_digest=True)
    report = {
        "schema_version": ("dehps-m4-v2-marginal-static-health-execution-recovery.v1"),
        "status": "SAFE_TO_RECOVER",
        "input_manifest_digest": live.artifact_digest,
        "output_manifest_digest": recovered.artifact_digest,
        "task_key": MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
        "task_digest": MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_TASK_DIGEST,
        "failed_execution_id": MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EXECUTION_ID,
        "preserved_started_event_digest": (
            MARGINAL_STATIC_HEALTH_EXECUTION_STARTED_EVENT_DIGEST
        ),
        "preserved_failed_event_digest": (
            MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EVENT_DIGEST
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
        "duplicate_raw_replay": False,
        "physical_checkpoint_scan": False,
    }
    return recovered_payload, report


def build_marginal_static_historical_gate_recovery_manifest(
    *,
    live_payload: Mapping[str, Any],
    execution_events: Sequence[Mapping[str, Any]],
    execution_artifacts: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reset only the exact zero-artifact historical Gate failure."""

    live = ControlPlaneManifest.from_dict(dict(live_payload))
    matching = [
        task
        for task in live.tasks
        if task.task_key == MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
    ]
    if (
        len(matching) != 1
        or matching[0].artifact_digest
        != MARGINAL_STATIC_HISTORICAL_GATE_FAILED_TASK_DIGEST
    ):
        raise MarginalStaticHistoricalGateRecoveryError(
            "marginal_static_historical_gate_recovery_task_identity_changed"
        )
    state = live.task_state_by_digest[
        MARGINAL_STATIC_HISTORICAL_GATE_FAILED_TASK_DIGEST
    ]
    if (
        state.declared_status.value != "failed"
        or state.completion_classification.value != "INTEGRATED"
    ):
        raise MarginalStaticHistoricalGateRecoveryError(
            "marginal_static_historical_gate_recovery_task_is_not_exact_failure"
        )

    related = [
        dict(event)
        for event in execution_events
        if event.get("task_digest")
        == MARGINAL_STATIC_HISTORICAL_GATE_FAILED_TASK_DIGEST
        and event.get("execution_id")
        == MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EXECUTION_ID
    ]
    started = [event for event in related if event.get("event_type") == "started"]
    failed = [event for event in related if event.get("event_type") == "failed"]
    completed = [event for event in related if event.get("event_type") == "completed"]
    if (
        len(execution_events) != 2
        or len(related) != 2
        or len(started) != 1
        or len(failed) != 1
        or completed
        or started[0].get("event_digest")
        != MARGINAL_STATIC_HISTORICAL_GATE_STARTED_EVENT_DIGEST
        or failed[0].get("event_digest")
        != MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EVENT_DIGEST
        or _event_payload(failed[0]).get("error")
        != MARGINAL_STATIC_HISTORICAL_GATE_FAILED_ERROR
    ):
        raise MarginalStaticHistoricalGateRecoveryError(
            "marginal_static_historical_gate_recovery_event_history_changed"
        )
    if execution_artifacts:
        raise MarginalStaticHistoricalGateRecoveryError(
            "marginal_static_historical_gate_recovery_artifacts_exist"
        )

    output = live.to_dict(include_digest=False)
    changed = 0
    for task in output["tasks"]:
        if task["task_key"] != MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY:
            continue
        task["status"] = "draft"
        task["completion_classification"] = "INTEGRATION_PENDING"
        changed += 1
    if changed != 1:
        raise MarginalStaticHistoricalGateRecoveryError(
            "marginal_static_historical_gate_recovery_transition_count_changed"
        )
    recovered = ControlPlaneManifest.from_dict(output)
    recovered_payload = recovered.to_dict(include_digest=True)
    report = {
        "schema_version": "dehps-m4-v2-marginal-static-historical-gate-recovery.v1",
        "status": "SAFE_TO_RECOVER",
        "input_manifest_digest": live.artifact_digest,
        "output_manifest_digest": recovered.artifact_digest,
        "task_key": MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
        "task_digest": MARGINAL_STATIC_HISTORICAL_GATE_FAILED_TASK_DIGEST,
        "failed_execution_id": MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EXECUTION_ID,
        "preserved_started_event_digest": (
            MARGINAL_STATIC_HISTORICAL_GATE_STARTED_EVENT_DIGEST
        ),
        "preserved_failed_event_digest": (
            MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EVENT_DIGEST
        ),
        "state_transition": "failed/INTEGRATED -> draft/INTEGRATION_PENDING",
        "changed_task_count": 1,
        "deleted_task_count": 0,
        "deleted_event_count": 0,
        "rewritten_event_count": 0,
        "completed_task_regression_count": 0,
        "preexisting_execution_artifact_count": 0,
        "historical_artifact_payloads_read": False,
        "statistical_result_payloads_read": False,
        "formal_historical_folds_executed": 0,
        "bootstrap_children_executed": 0,
        "database_queries_during_recovery": 0,
        "gate_compilation_executed": False,
        "evidence_created": False,
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
