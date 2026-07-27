from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import (
    ControlPlaneManifest,
    GoalStatus,
    ResolutionSnapshot,
    Task,
    TaskStatus,
)


M4_GOAL_KEY = "M4_INFORMATION_THEORY_EVIDENCE"
LEGACY_GOAL_KEY = "ADAPTIVE_TRAINING_SIGNAL_OPTIMIZATION"
M4_FORWARD_EVENT_KEY = "draw:2026085"
M4_CONTRACT_REPAIR_TASK_KEY = (
    "m4-p1-repair-injected-signal-preregistration-contract"
)
M4_PREREGISTRATION_V1_0_3_DIGEST = (
    "4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9"
)
M4_SYNTHETIC_MANIFEST_V1_0_1_DIGEST = (
    "f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c"
)
M4_MANIFEST_RELATIVE_PATH = Path(
    "configs/research-os/m4-information-theory-evidence-v1.json"
)

PHASE_TASK_KEYS = {
    "M4-P0": "m4-p0-mainline-migration",
    "M4-P1": "m4-p1-contract-and-preregistration",
    "M4-P2": "m4-p2-synthetic-measurement-validation",
    "M4-P3": "m4-p3-strict-historical-walk-forward",
    "M4-P4": "m4-p4-negative-controls-and-robustness",
    "M4-P5": "m4-p5-forward-evidence",
    "M4-P6": "m4-p6-information-bound-and-decision",
}
P2_SUBTASK_KEYS = (
    "m4-p2-synthetic-contracts-and-null-generator",
    "m4-p2-metric-kernel",
    "m4-p2-walk-forward-probe-harness",
    "m4-p2-injected-signal-calibration",
    "m4-p2-resampling",
    "m4-p2-false-positive-and-power-runs",
    "m4-p2-automatic-gate-and-report",
)


def load_m4_manifest(path: Path) -> ControlPlaneManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("M4 manifest root must be an object")
    return ControlPlaneManifest.from_dict(payload)


def manifest_with_external_event(
    manifest: ControlPlaneManifest,
    *,
    event_key: str,
) -> ControlPlaneManifest:
    payload = manifest.to_dict(include_digest=False)
    events = set(payload["facts"]["external_events"])
    events.add(event_key)
    payload["facts"]["external_events"] = sorted(events)
    return ControlPlaneManifest.from_dict(payload)


def manifest_with_contract_repair_pending(
    manifest: ControlPlaneManifest,
) -> ControlPlaneManifest:
    """Reconstruct the frozen pre-repair projection for contract acceptance tests."""
    payload = manifest.to_dict(include_digest=False)
    repair = next(
        task
        for task in payload["tasks"]
        if task["task_key"] == M4_CONTRACT_REPAIR_TASK_KEY
    )
    repair["status"] = "draft"
    payload["facts"]["artifacts"] = [
        fact
        for fact in payload["facts"]["artifacts"]
        if fact not in {
            f"m4-preregistration:{M4_PREREGISTRATION_V1_0_3_DIGEST}",
            (
                "m4-p2-1-synthetic-run-manifest:"
                f"{M4_SYNTHETIC_MANIFEST_V1_0_1_DIGEST}"
            ),
        }
    ]
    return ControlPlaneManifest.from_dict(payload)


def build_m4_status(
    manifest: ControlPlaneManifest,
    *,
    snapshot: ResolutionSnapshot | None = None,
    mainline_execution: dict[str, Any] | None = None,
    dispatch_performed: bool = False,
) -> dict[str, Any]:
    snapshot = snapshot or ResearchOSControlPlane().resolve(manifest)
    goals = {goal.goal_key: goal for goal in manifest.goals}
    if M4_GOAL_KEY not in goals or LEGACY_GOAL_KEY not in goals:
        raise ValueError("M4 status requires both the active M4 and legacy Goal")
    goal_states = manifest.goal_state_by_digest
    m4_goal = goals[M4_GOAL_KEY]
    legacy_goal = goals[LEGACY_GOAL_KEY]
    if goal_states[m4_goal.artifact_digest].status is not GoalStatus.ACTIVE:
        raise ValueError("M4 Goal must be active")

    tasks = {task.task_key: task for task in manifest.tasks}
    task_states = manifest.task_state_by_digest
    resolutions = {item.task_key: item for item in snapshot.resolutions}
    repair_resolution = resolutions.get(M4_CONTRACT_REPAIR_TASK_KEY)
    repair_complete = (
        repair_resolution is not None
        and repair_resolution.status is TaskStatus.COMPLETED
    )
    current_phase = "M4-P1" if not repair_complete else _current_phase(tasks)
    current_task_key = (
        "m4-p2-injected-signal-calibration"
        if not repair_complete
        else PHASE_TASK_KEYS[current_phase]
    )
    current_resolution = resolutions[current_task_key]
    current_state = current_resolution.status.value.upper()
    if not repair_complete:
        current_state = "BLOCKED"
    if (
        current_phase == "M4-P2"
        and resolutions[P2_SUBTASK_KEYS[0]].status is TaskStatus.COMPLETED
        and resolutions[P2_SUBTASK_KEYS[-1]].status is not TaskStatus.COMPLETED
    ):
        current_state = "RUNNING"
    forward_intake = resolutions["m4-forward-evidence-intake-2026085"]
    if current_phase == "M4-P5":
        if forward_intake.status is TaskStatus.EXTERNAL_WAIT:
            current_state = "WAIT_FORWARD"
        elif forward_intake.status is TaskStatus.READY:
            current_state = "SETTLING"

    next_ready = next(
        (
            item
            for item in snapshot.ready_queue
            if item.goal_key == M4_GOAL_KEY
        ),
        None,
    )
    engineering_progress = sum(
        _metric(task).get("engineering_weight_percent", 0)
        for task in _phase_tasks(tasks)
        if _metric(task).get("engineering_complete") is True
    )
    engineering_progress += sum(
        _metric(tasks[task_key]).get("engineering_increment_percent", 0)
        for task_key in P2_SUBTASK_KEYS
        if resolutions[task_key].status is TaskStatus.COMPLETED
    )
    evidence_progress = sum(
        _metric(task).get("evidence_weight_percent", 0)
        for task in _phase_tasks(tasks)
        if _metric(task).get("evidence_complete") is True
    )
    blocked_by = [
        {
            "dependency_type": item.dependency_type.value,
            "target_key": item.target_key,
            "required_status": item.required_status,
        }
        for item in current_resolution.unsatisfied_dependencies
    ]
    legacy_target = json.loads(legacy_goal.target_metric_manifest)
    m4_baseline = json.loads(m4_goal.baseline_metric_manifest)
    active_preregistration = dict(m4_baseline)
    if repair_complete:
        repair_metric = _metric(tasks[M4_CONTRACT_REPAIR_TASK_KEY])
        active_preregistration.update(
            {
                "preregistration_status": "FROZEN",
                "preregistration_version": "1.0.3",
                "preregistration_digest": repair_metric[
                    "new_preregistration_digest"
                ],
            }
        )
    p1_complete = (
        _metric(tasks["m4-p1-contract-and-preregistration"]).get(
            "engineering_complete"
        )
        is True
    )

    completed = [
        "old training hypothesis recorded as rejected",
        "legacy final baseline and commit recorded",
        "2026084 settlement digest recorded",
        "legacy adaptive tuning tasks superseded",
        "M4 Goal and P0-P6 dependency graph activated",
    ]
    if p1_complete:
        completed.extend(
            [
                "information-theory contract version frozen",
                "preregistration and decision policy frozen",
                "P2 input contract validated",
            ]
        )
    p2_1_complete = resolutions[P2_SUBTASK_KEYS[0]].status is TaskStatus.COMPLETED
    p2_2_complete = resolutions[P2_SUBTASK_KEYS[1]].status is TaskStatus.COMPLETED
    p2_3_complete = resolutions[P2_SUBTASK_KEYS[2]].status is TaskStatus.COMPLETED
    if p2_1_complete:
        completed.extend(
            [
                "P2.1 synthetic contracts and schemas frozen",
                "uniform six-of-33 null generator replay contract verified",
                "P2 fixed workload manifest frozen without formal execution",
            ]
        )
    if p2_2_complete:
        completed.extend(
            [
                "P2.2 deterministic metric kernel frozen",
                "issue-cluster and bits-per-issue unit contracts verified",
                "PE2 explicitly remains not implemented",
            ]
        )
    if p2_3_complete:
        completed.extend(
            [
                "P2.3 strict synthetic walk-forward harness validated in mainline",
                "blind exactly-once prediction checkpoint boundary verified",
                "chronological inner validation and fold-local preprocessing verified",
                "theoretical and logistic null smoke marked non-Evidence",
                "unified Research Evidence Supervisor execution and replay verified",
            ]
        )
    if repair_complete:
        completed.append(
            "injected-signal calibration truth and tolerance contract repaired"
        )

    return {
        "schema_version": "dehps-m4-information-theory-status.v1",
        "manifest_digest": manifest.artifact_digest,
        "snapshot_digest": snapshot.snapshot_digest,
        "goal": M4_GOAL_KEY,
        "goal_status": "ACTIVE",
        "previous_goal": LEGACY_GOAL_KEY,
        "previous_goal_lifecycle": goal_states[
            legacy_goal.artifact_digest
        ].status.value.upper(),
        "previous_goal_research_status": legacy_target["research_status"].upper(),
        "old_training_mainline": legacy_target["mainline_status"].upper(),
        "current_phase": current_phase,
        "current_state": current_state,
        "completed": completed,
        "evidence_changed": [],
        "tests": {"status": "not_recorded_in_control_plane"},
        "artifacts": {
            "preregistration_digest": active_preregistration.get(
                "preregistration_digest"
            ),
            "decision_policy_digest": m4_baseline.get("decision_policy_digest"),
            "p2_input_contract_digest": m4_baseline.get("p2_input_contract_digest"),
            "p2_synthetic_run_manifest_digest": (
                M4_SYNTHETIC_MANIFEST_V1_0_1_DIGEST
                if p2_1_complete
                else None
            ),
            "p2_metric_kernel_manifest_digest": (
                "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2"
                if p2_2_complete
                else None
            ),
            "p2_walk_forward_harness_manifest_digest": (
                "177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca"
                if p2_3_complete
                else None
            ),
            "p2_walk_forward_mainline_execution_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("execution_artifact_digest")
            ),
            "control_plane_manifest_digest": manifest.artifact_digest,
            "legacy_settlement_digest": json.loads(
                legacy_goal.baseline_metric_manifest
            )["last_settlement_digest"],
        },
        "preregistration": {
            "status": active_preregistration.get(
                "preregistration_status", "NOT_STARTED"
            ),
            "version": active_preregistration.get("preregistration_version"),
        },
        "p2_input_contract": m4_baseline.get(
            "p2_input_contract_status",
            "NOT_CREATED",
        ),
        "gate_status": {
            "promotion_gate": "CLOSED",
            "adaptive_supervisor": "STOPPED",
            "production_action": "none",
        },
        "progress": {
            "engineering_percent": engineering_progress,
            "evidence_percent": evidence_progress,
            "historical_walk_forward": {"completed": 0, "total": None},
            "forward_samples": {
                "completed": 0,
                "since_issue": None,
                "eligibility_rule": "first post-P2 issue with a complete pre-draw checkpoint",
                "retroactively_ineligible_issues": ["2026085"],
            },
            "synthetic_scenarios": {"completed": 0, "total": 13},
            "negative_controls": {"completed": 0, "total": 6},
            "robustness_sensitivities": {"completed": 0, "total": 5},
            "feature_families": {"completed": 0, "total": 7},
        },
        "current_statistics": {
            "primary_endpoint": "out_of_sample_log_loss_improvement",
            "oos_log_loss_improvement": None,
            "bits_gain_per_issue": None,
            "confidence_interval": None,
            "practical_null": (
                "[-0.01,+0.01] bits/issue"
                if p1_complete
                else "NOT_PREREGISTERED"
            ),
            "minimum_detectable_effect": None,
            "power": "NOT_EVALUATED",
            "evidence_state": "NOT_STARTED",
        },
        "formal_real_data_run": "NOT_STARTED",
        "synthetic_validation": (
            "P2.3_HARNESS_READY"
            if p2_3_complete
            else (
                "P2.2_KERNEL_READY"
                if p2_2_complete
                else ("P2.1_CONTRACT_READY" if p2_1_complete else "NOT_STARTED")
            )
        ),
        "p2_subphase": {
            "completed": (
                ["M4-P2.1", "M4-P2.2", "M4-P2.3"]
                if p2_3_complete
                else (
                    ["M4-P2.1", "M4-P2.2"]
                    if p2_2_complete
                    else (["M4-P2.1"] if p2_1_complete else [])
                )
            ),
            "current": (
                "M4-P1-CONTRACT-REPAIR"
                if not repair_complete
                else (
                    "M4-P2.4"
                    if p2_3_complete
                    else (
                        "M4-P2.3"
                        if p2_2_complete
                        else ("M4-P2.2" if p2_1_complete else "M4-P2.1")
                    )
                )
            ),
            "gate": "NOT_EVALUATED",
            "completion_classification": (
                None
                if task_states[
                    tasks["m4-p2-walk-forward-probe-harness"].artifact_digest
                ].completion_classification
                is None
                else task_states[
                    tasks["m4-p2-walk-forward-probe-harness"].artifact_digest
                ].completion_classification.value
            ),
        },
        "mainline_integration": {
            "goal_integration": M4_GOAL_KEY,
            "ready_queue_integration": "PASS",
            "runner_integration": "research_evidence_supervisor",
            "task_key": "m4-p2-walk-forward-probe-harness",
            "actual_fold_count": (
                None
                if mainline_execution is None
                else mainline_execution.get("actual_fold_count")
            ),
            "registered_artifact_count": (
                None
                if mainline_execution is None
                else mainline_execution.get("registered_artifact_count")
            ),
            "execution_artifact_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("execution_artifact_digest")
            ),
            "downstream_consumer": "m4-p2-injected-signal-calibration",
            "legacy_manual_path_canonical": False,
        },
        "blocked_by": blocked_by,
        "next_ready_task": None if next_ready is None else next_ready.task_key,
        "next_external_dependency": (
            M4_FORWARD_EVENT_KEY
            if forward_intake.status is TaskStatus.EXTERNAL_WAIT
            else None
        ),
        "forward_event_2026085": {
            "resolver_status": forward_intake.status.value,
            "m4_forward_evidence_eligible": False,
            "reason": "no complete M4 pre-draw checkpoint after P1 freeze and P2 passage",
        },
        "stop_condition_status": "NOT_EVALUATED",
        "dispatch_performed": dispatch_performed,
        "production_impact": "none",
    }


def _phase_tasks(tasks: dict[str, Task]) -> tuple[Task, ...]:
    return tuple(tasks[PHASE_TASK_KEYS[phase]] for phase in PHASE_TASK_KEYS)


def _current_phase(tasks: dict[str, Task]) -> str:
    for phase, task_key in PHASE_TASK_KEYS.items():
        if _metric(tasks[task_key]).get("engineering_complete") is not True:
            return phase
    return "M4-P6"


def _metric(task: Task) -> dict[str, Any]:
    value = json.loads(task.metric_contract)
    assert isinstance(value, dict)
    return value
