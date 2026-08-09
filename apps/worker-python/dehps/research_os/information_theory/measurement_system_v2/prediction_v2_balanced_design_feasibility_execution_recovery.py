from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_feasibility_execution import (
    EXECUTION_HANDOFF_DIGEST,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_CAPABILITY,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
    PREREGISTRATION_COMPLETION_DIGEST,
    PREREGISTRATION_DIGEST,
    PREREGISTRATION_MAINLINE_EXECUTION_DIGEST,
    REPETITION_SCAN,
)
from dehps.research_os.models import ControlPlaneManifest

FAILED_MANIFEST_DIGEST = (
    "5c0b5fa4e4833df5ad0cfe532e6f9e80a8eb18f8259a17379d0fd34a2d8b9fc8"
)
FAILED_SOURCE_CONTRACT_DIGEST = (
    "46ee7d03cab54a3d0b6dfd210058aec8e56494f7a48e20ce43eb6c7578bb65f6"
)
CORRECTED_SOURCE_CONTRACT_DIGEST = (
    "c54ee87e5b9d6e513945204bea0413e8d34a51206e587f3662d8123eb03b9538"
)
FAILED_TASK_DIGEST = "113a96ee0ceac7dd53cfd212e50e0ef7ecfe0de8c12eb0c59da08be0128cea22"
CORRECTED_TASK_DIGEST = (
    "9e26bb42afd132ea381804d972a59fbd8df71b1f837a464159cdd48a51e875f4"
)
FAILED_EXECUTION_ID = "92f0062bbaff69f9a81d11b65c70cbf84efea97077f94ad043a6e8d8da4df41e"
FAILED_STARTED_EVENT_DIGEST = (
    "6ffe902ecdb01847bb12e1ca0b8bdda1eb64379d3c388668d84f7e4f1b43cf24"
)
FAILED_EVENT_DIGEST = "59068e014557d0931f2081f998701440ba71f98938d89c99712fa787b989b082"
FAILED_ERROR = (
    "runtime_budget_infeasible_before_first_checkpoint: 16773 signature groups; "
    "1451.012 wall seconds; zero checkpoints; frozen 100000000-node "
    "implementation has no defensible two-week upper bound"
)
EXPECTED_RECOVERED_MANIFEST_DIGEST = (
    "4100df19e9601efd1bbf08e900e55ec4a7929ad16696238de551cb0d5215b396"
)

_CORRECTED_SOURCE_FACT = (
    "prediction-v2-balanced-design-feasibility-execution-source:"
    f"{CORRECTED_SOURCE_CONTRACT_DIGEST}"
)
_EXPECTED_FAILED_INPUTS = (
    FAILED_SOURCE_CONTRACT_DIGEST,
    PREREGISTRATION_DIGEST,
    EXECUTION_HANDOFF_DIGEST,
    PREREGISTRATION_COMPLETION_DIGEST,
    PREREGISTRATION_MAINLINE_EXECUTION_DIGEST,
)
_EXPECTED_CORRECTED_INPUTS = (
    CORRECTED_SOURCE_CONTRACT_DIGEST,
    PREREGISTRATION_DIGEST,
    EXECUTION_HANDOFF_DIGEST,
    PREREGISTRATION_COMPLETION_DIGEST,
    PREREGISTRATION_MAINLINE_EXECUTION_DIGEST,
)


class BalancedDesignExecutionRecoveryError(RuntimeError):
    pass


def build_balanced_design_execution_recovery_manifest(
    *,
    live_payload: Mapping[str, Any],
    corrected_source_payload: Mapping[str, Any],
    execution_events: Sequence[Mapping[str, Any]],
    execution_artifacts: Sequence[Mapping[str, Any]],
    require_registered_failure: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Revise only the exact zero-artifact runtime-budget failure."""

    live = ControlPlaneManifest.from_dict(dict(live_payload))
    source = ControlPlaneManifest.from_dict(dict(corrected_source_payload))
    if require_registered_failure and live.artifact_digest != FAILED_MANIFEST_DIGEST:
        raise BalancedDesignExecutionRecoveryError(
            "balanced_design_execution_recovery_manifest_identity_changed"
        )

    live_task = _single_task(
        live, PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
    )
    corrected_task = _single_task(
        source,
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
    )
    if (
        live_task.artifact_digest != FAILED_TASK_DIGEST
        or live_task.requested_capability
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_CAPABILITY
        or live_task.input_artifact_digests != _EXPECTED_FAILED_INPUTS
        or corrected_task.artifact_digest != CORRECTED_TASK_DIGEST
        or corrected_task.requested_capability
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_CAPABILITY
        or corrected_task.input_artifact_digests != _EXPECTED_CORRECTED_INPUTS
    ):
        raise BalancedDesignExecutionRecoveryError(
            "balanced_design_execution_recovery_task_identity_changed"
        )
    live_state = live.task_state_by_digest[FAILED_TASK_DIGEST]
    if (
        live_state.declared_status.value != "failed"
        or live_state.completion_classification is None
        or live_state.completion_classification.value != "INTEGRATED"
    ):
        raise BalancedDesignExecutionRecoveryError(
            "balanced_design_execution_recovery_task_is_not_exact_failure"
        )

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
        len(related) != 2
        or len(started) != 1
        or len(failed) != 1
        or completed
        or started[0].get("event_digest") != FAILED_STARTED_EVENT_DIGEST
        or failed[0].get("event_digest") != FAILED_EVENT_DIGEST
        or _event_payload(failed[0]).get("error") != FAILED_ERROR
    ):
        raise BalancedDesignExecutionRecoveryError(
            "balanced_design_execution_recovery_event_history_changed"
        )
    if execution_artifacts:
        raise BalancedDesignExecutionRecoveryError(
            "balanced_design_execution_recovery_artifacts_exist"
        )

    output = live.to_dict(include_digest=False)
    source_definition = next(
        task
        for task in source.to_dict(include_digest=False)["tasks"]
        if task["task_key"]
        == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
    )
    source_definition["status"] = "draft"
    source_definition["completion_classification"] = "INTEGRATION_PENDING"
    source_definition["superseded_by_task_digest"] = None
    changed = 0
    for task_index, task in enumerate(output["tasks"]):
        if (
            task["task_key"]
            != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
        ):
            continue
        output["tasks"][task_index] = source_definition
        changed += 1
    old_facts = tuple(output["facts"]["artifacts"])
    output["facts"]["artifacts"] = sorted({*old_facts, _CORRECTED_SOURCE_FACT})
    if (
        changed != 1
        or _CORRECTED_SOURCE_FACT in old_facts
        or len(output["facts"]["artifacts"]) != len(old_facts) + 1
    ):
        raise BalancedDesignExecutionRecoveryError(
            "balanced_design_execution_recovery_scope_changed"
        )

    recovered = ControlPlaneManifest.from_dict(output)
    recovered_task = _single_task(
        recovered,
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
    )
    recovered_state = recovered.task_state_by_digest[CORRECTED_TASK_DIGEST]
    if (
        recovered_task.artifact_digest != CORRECTED_TASK_DIGEST
        or recovered_state.declared_status.value != "draft"
        or recovered_state.completion_classification is None
        or recovered_state.completion_classification.value != "INTEGRATION_PENDING"
        or (
            require_registered_failure
            and recovered.artifact_digest != EXPECTED_RECOVERED_MANIFEST_DIGEST
        )
    ):
        raise BalancedDesignExecutionRecoveryError(
            "balanced_design_execution_recovery_output_changed"
        )
    live_tasks = {task.task_key: task for task in live.tasks}
    recovered_tasks = {task.task_key: task for task in recovered.tasks}
    if any(
        recovered_tasks[task_key].artifact_digest != live_other.artifact_digest
        for task_key, live_other in live_tasks.items()
        if task_key != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
    ):
        raise BalancedDesignExecutionRecoveryError(
            "balanced_design_execution_recovery_other_task_changed"
        )

    return recovered.to_dict(include_digest=True), {
        "schema_version": ("dehps-prediction-v2-balanced-design-execution-recovery.v1"),
        "status": "SAFE_TO_RECOVER",
        "input_manifest_digest": live.artifact_digest,
        "output_manifest_digest": recovered.artifact_digest,
        "task_key": PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
        "failed_task_digest": FAILED_TASK_DIGEST,
        "corrected_task_digest": CORRECTED_TASK_DIGEST,
        "failed_execution_id": FAILED_EXECUTION_ID,
        "preserved_started_event_digest": FAILED_STARTED_EVENT_DIGEST,
        "preserved_failed_event_digest": FAILED_EVENT_DIGEST,
        "state_transition": "failed/INTEGRATED -> draft/INTEGRATION_PENDING",
        "changed_task_count": 1,
        "added_source_fact_count": 1,
        "deleted_task_count": 0,
        "deleted_fact_count": 0,
        "deleted_event_count": 0,
        "rewritten_event_count": 0,
        "preexisting_execution_artifact_count": 0,
        "checkpoint_count": 0,
        "solver_nodes_executed_during_recovery": 0,
        "historical_outcomes_read": False,
        "statistical_result_payloads_read": False,
        "repetition_scan": REPETITION_SCAN,
        "evidence_created": False,
        "prediction_v2_promotion": False,
        "p3_execution": False,
        "production_action": "none",
    }


def _single_task(manifest: ControlPlaneManifest, task_key: str):
    matches = [task for task in manifest.tasks if task.task_key == task_key]
    if len(matches) != 1:
        raise BalancedDesignExecutionRecoveryError(
            "balanced_design_execution_recovery_task_not_singular"
        )
    return matches[0]


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
