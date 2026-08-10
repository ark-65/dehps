from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.structural_utility.m4_p3_result_blind_preregistration import (
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
)

FAILED_MANIFEST_DIGEST = (
    "a96333328326e9876a9bca514447f09d8fc72d2804bb3805e39c5fb7b29e9d41"
)
FAILED_TASK_DIGEST = "fb7933747fdff10bf9cfe88f10dbaf57e6e551b31400e0feaa56373f52b67218"
FAILED_EXECUTION_ID = "f5491f273bb09dda3c093f0286ca574f1fa3233f4e67ea8e1c00e0d0acee06a4"
FAILED_STARTED_EVENT_DIGEST = (
    "996846eaaa8d983816d950e4ad1c80ea2294a8a51a8f3a071f32020db6222d00"
)
FAILED_EVENT_DIGEST = "9bded78f38a6ea0a23cdf3665a07c0d962566528948b787c225567123221aade"
FAILED_ERROR = "'actual_fold_count'"
FAILED_REGISTRATIONS = {
    "m4_p3_result_blind_structural_utility_preregistration": (
        "a82b1d9f37818ac5ecf8345070734c0be128cac0f3de7422e4b6675cc595f6f4",
        "89d0c2c9d4fdeec96241ad1543d06a39bfd822f63042cdecf6703cd7e67ae4e8",
    ),
    "m4_p3_result_blind_structural_utility_blind_execution_handoff": (
        "2ad8ce0f94876d6a0af29d9b9237d89e06a4816e94922618396dc74436d5c292",
        "310a13a11d0ba3dd6289cf085cb5fb95d2383a4771aa515beea1a1a518bd47d7",
    ),
    "m4_p3_result_blind_structural_utility_preregistration_completion": (
        "1c56bc0a349d1a2b5e79c39e64b0d3fc0f2e717312dee359ee229b860231bc16",
        "79bcdaaed4dd0ffe9321b5de211e97467bcc221c5c8db8b68b7aae82597a247d",
    ),
    "research_os_mainline_execution": (
        "0ce4f649840d90650f7ef3d02b48f12f815d8f9080cbc7a66527414aa23e3efd",
        "6f672e80f340ab1667f814aeda47defe5d7ccce6c89ddd37a36c821feb09c262",
    ),
}


class M4P3ResultBlindPreregistrationRecoveryError(RuntimeError):
    pass


def build_m4_p3_result_blind_preregistration_recovery_manifest(
    *,
    live_payload: Mapping[str, Any],
    execution_events: Sequence[Mapping[str, Any]],
    execution_artifacts: Sequence[Mapping[str, Any]],
    require_registered_failure: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reset only the exact failed zero-work preregistration task."""

    live = ControlPlaneManifest.from_dict(dict(live_payload))
    tasks = {task.task_key: task for task in live.tasks}
    task = tasks.get(M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY)
    if (
        (require_registered_failure and live.artifact_digest != FAILED_MANIFEST_DIGEST)
        or len(live.goals) != 4
        or len(live.tasks) != 80
        or task is None
        or task.artifact_digest != FAILED_TASK_DIGEST
    ):
        raise M4P3ResultBlindPreregistrationRecoveryError(
            "m4_p3_preregistration_recovery_manifest_identity_changed"
        )
    state = live.task_state_by_digest[FAILED_TASK_DIGEST]
    if (
        state.declared_status.value != "failed"
        or state.completion_classification is None
        or state.completion_classification.value != "INTEGRATED"
    ):
        raise M4P3ResultBlindPreregistrationRecoveryError(
            "m4_p3_preregistration_recovery_task_is_not_exact_failure"
        )

    related = [
        dict(event)
        for event in execution_events
        if event.get("task_digest") == FAILED_TASK_DIGEST
        and event.get("execution_id") == FAILED_EXECUTION_ID
    ]
    started = [item for item in related if item.get("event_type") == "started"]
    failed = [item for item in related if item.get("event_type") == "failed"]
    completed = [item for item in related if item.get("event_type") == "completed"]
    if (
        len(related) != 2
        or len(started) != 1
        or len(failed) != 1
        or completed
        or started[0].get("event_digest") != FAILED_STARTED_EVENT_DIGEST
        or failed[0].get("event_digest") != FAILED_EVENT_DIGEST
        or _event_payload(failed[0]).get("error") != FAILED_ERROR
    ):
        raise M4P3ResultBlindPreregistrationRecoveryError(
            "m4_p3_preregistration_recovery_event_history_changed"
        )

    observed_registrations: dict[str, tuple[str, str]] = {}
    for item in execution_artifacts:
        if (
            item.get("execution_id") != FAILED_EXECUTION_ID
            or item.get("task_key") != M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY
            or item.get("task_digest") != FAILED_TASK_DIGEST
            or item.get("control_plane_key") != "m4-information-theory-mainline"
        ):
            raise M4P3ResultBlindPreregistrationRecoveryError(
                "m4_p3_preregistration_recovery_registration_identity_changed"
            )
        observed_registrations[str(item.get("artifact_type"))] = (
            str(item.get("registration_digest")),
            str(item.get("artifact_digest")),
        )
    if observed_registrations != FAILED_REGISTRATIONS:
        raise M4P3ResultBlindPreregistrationRecoveryError(
            "m4_p3_preregistration_recovery_registration_identity_changed"
        )

    output = live.to_dict(include_digest=False)
    changed = 0
    for item in output["tasks"]:
        if item["task_key"] != M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY:
            continue
        item["status"] = "draft"
        item["completion_classification"] = "INTEGRATION_PENDING"
        changed += 1
    if changed != 1:
        raise M4P3ResultBlindPreregistrationRecoveryError(
            "m4_p3_preregistration_recovery_transition_count_changed"
        )
    recovered = ControlPlaneManifest.from_dict(output)
    recovered_tasks = {item.task_key: item for item in recovered.tasks}
    recovered_task = recovered_tasks[M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY]
    recovered_state = recovered.task_state_by_digest[recovered_task.artifact_digest]
    if (
        recovered_task.artifact_digest != FAILED_TASK_DIGEST
        or recovered_state.declared_status.value != "draft"
        or recovered_state.completion_classification is None
        or recovered_state.completion_classification.value != "INTEGRATION_PENDING"
        or any(
            recovered_tasks[key].artifact_digest != other.artifact_digest
            or recovered.task_state_by_digest[recovered_tasks[key].artifact_digest]
            != live.task_state_by_digest[other.artifact_digest]
            for key, other in tasks.items()
            if key != M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY
        )
        or recovered.facts != live.facts
    ):
        raise M4P3ResultBlindPreregistrationRecoveryError(
            "m4_p3_preregistration_recovery_output_state_changed"
        )
    return recovered.to_dict(include_digest=True), {
        "schema_version": (
            "dehps-m4-p3-result-blind-structural-utility-preregistration-recovery.v1"
        ),
        "status": "SAFE_TO_RECOVER",
        "input_manifest_digest": live.artifact_digest,
        "output_manifest_digest": recovered.artifact_digest,
        "task_key": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
        "task_digest": FAILED_TASK_DIGEST,
        "failed_execution_id": FAILED_EXECUTION_ID,
        "preserved_started_event_digest": FAILED_STARTED_EVENT_DIGEST,
        "preserved_failed_event_digest": FAILED_EVENT_DIGEST,
        "preserved_registration_count": 4,
        "preserved_registration_digests": sorted(
            item[0] for item in FAILED_REGISTRATIONS.values()
        ),
        "state_transition": "failed/INTEGRATED -> draft/INTEGRATION_PENDING",
        "changed_task_count": 1,
        "deleted_event_count": 0,
        "rewritten_event_count": 0,
        "deleted_registration_count": 0,
        "rewritten_registration_count": 0,
        "completed_task_regression_count": 0,
        "artifact_payloads_read": False,
        "workload_rerun": False,
        "blind_execution_authorized": False,
        "prediction_v2_promotion": False,
        "predictive_p3_execution": False,
        "production_action": "none",
    }


def _event_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    raw = event.get("payload")
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return {str(key): value for key, value in raw}
    return {}
