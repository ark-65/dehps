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
M4_V2_DESIGN_TASK_KEY = "m4-v2-measurement-contract-design"
M4_V2_DESIGN_REPLAY_TASK_KEY = "m4-v2-measurement-contract-design-replay"
M4_P263_COMPATIBILITY_TASK_KEY = "m4-p2-6-3-superseding-compatibility-acceptance"
M4_P263_COMPATIBILITY_FACT = "m4-p2-6-3-compatibility:VERIFIED"
M4_V2_PREFLIGHT_DESIGN_TASK_KEY = "m4-v2-branch-identifiability-preflight-design"
PREFLIGHT_DESIGN_COMPLETION_FACT = (
    "m4-v2-branch-identifiability-preflight-design:FROZEN"
)
M4_V2_PREFLIGHT_FIXTURE_TASK_KEY = "m4-v2-branch-identifiability-fixture-freeze"
M4_V2_PREFLIGHT_FIXTURE_COMPLETION_FACT = (
    "m4-v2-branch-identifiability-fixture-freeze:FROZEN"
)
M4_V2_PREFLIGHT_EXECUTION_TASK_KEY = "m4-v2-branch-identifiability-preflight-execution"
M4_V2_PREFLIGHT_EXECUTION_COMPLETION_FACT = (
    "m4-v2-branch-identifiability-preflight-execution:EXECUTED"
)
M4_V2_PREFLIGHT_EXECUTION_PASS_FACT = (
    "m4-v2-branch-identifiability-preflight-execution:ALL_BRANCHES_PASS"
)
M4_V2_MARGINAL_CONTRACT_FREEZE_TASK_KEY = (
    "m4-v2-marginal-static-measurement-contract-freeze"
)
M4_V2_MARGINAL_CONTRACT_FREEZE_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-contract-freeze:FROZEN"
)
M4_V2_MARGINAL_FIXTURE_FREEZE_TASK_KEY = (
    "m4-v2-marginal-static-measurement-fixture-freeze"
)
M4_V2_MARGINAL_FIXTURE_FREEZE_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-fixture-freeze:FROZEN"
)
M4_V2_MARGINAL_HEALTH_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-design"
)
M4_V2_MARGINAL_HEALTH_DESIGN_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-health-design:FROZEN"
)
M4_V2_MARGINAL_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-execution"
)
M4_V2_MARGINAL_HEALTH_EXECUTION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-health-execution:COMPLETE"
)
M4_V2_MARGINAL_HEALTH_DECISION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-decision"
)
M4_V2_MARGINAL_HEALTH_DECISION_REPAIR_FACT = (
    "m4-v2-marginal-static-measurement-health-decision:REPAIR"
)
M4_V2_MARGINAL_HEALTH_DECISION_PASS_FACT = (
    "m4-v2-marginal-static-measurement-health-decision:PASS"
)
M4_V2_MARGINAL_HEALTH_DECISION_INCONCLUSIVE_FACT = (
    "m4-v2-marginal-static-measurement-health-decision:INCONCLUSIVE"
)
M4_V2_MARGINAL_REPAIR_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-design"
)
M4_V2_MARGINAL_REPAIR_DESIGN_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-design:FROZEN"
)
M4_V2_MARGINAL_REPAIR_PREREGISTRATION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-preregistration"
)
M4_V2_MARGINAL_REPAIR_PREREGISTRATION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-preregistration:FROZEN"
)
M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-health-execution"
)
M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-health-execution:COMPLETE"
)
M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-health-decision"
)
M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_REPAIR_FACT = (
    "m4-v2-marginal-static-measurement-repair-health-decision:REPAIR"
)
M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_PASS_FACT = (
    "m4-v2-marginal-static-measurement-repair-health-decision:PASS"
)
M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_INCONCLUSIVE_FACT = (
    "m4-v2-marginal-static-measurement-repair-health-decision:INCONCLUSIVE"
)
M4_V2_MARGINAL_REPAIR_V2_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-design"
)
M4_V2_MARGINAL_REPAIR_V2_DESIGN_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-v2-design:FROZEN"
)
M4_V2_MARGINAL_REPAIR_V2_PREREGISTRATION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-preregistration"
)
M4_V2_MARGINAL_BINDING_TASK_KEY = "m4-v2-p2-6-1-marginal-binding"
M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY = "m4-v2-p2-6-1-marginal-decision-replay"
M4_P29_P261_GOLDEN_REFERENCE_TASK_KEY = "m4-p2-9-golden-reference-freeze"
M4_P29_P261_RUNTIME_AUDIT_TASK_KEY = "m4-p2-9-measurement-runtime-audit"
M4_P29_P263_FAILED_RUNTIME_AUDIT_TASK_KEY = "m4-p2-9-p263-measurement-runtime-audit"
M4_P29_GOLDEN_REFERENCE_TASK_KEY = "m4-p2-9-p263-golden-reference-freeze"
M4_P29_RUNTIME_AUDIT_TASK_KEY = "m4-p2-9-p263-runtime-observation-arithmetic-fix"
M4_P263_SLOT_ELIGIBILITY_TASK_KEY = "m4-p2-9-p263-runtime-slot-release-eligibility"
M4_P263_SLOT_ELIGIBILITY_FACT = "m4-p263-runtime-slot-release-eligibility:VERIFIED"
M4_P263_TASK_DIGEST = "85a08402a4a0c37f75ee1675f4970ef00a7a0b0992b4204251c0c2cc79324de4"
M4_P263_POLICY_DIGEST = (
    "ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99"
)
M4_P29_CANONICAL_EXECUTOR_FINGERPRINT_DIGEST = (
    "e804e4eedf3c67ad9d35207367a096f6b830a6ab2ac29cc03501392d8430af32"
)
M4_P29_CANONICAL_EXECUTOR_EVENT = (
    f"m4-canonical-executor:{M4_P29_CANONICAL_EXECUTOR_FINGERPRINT_DIGEST}"
)
M4_P29_ACCELERATION_BOUNDARY_SCOPE = "literal_behavior_path_and_fresh_import_closure"
M4_V2_CONTRACT_DIGEST = (
    "a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b"
)
M4_V2_RUNTIME_RELEASE_EVENT = "m4-runtime-slot:p2-6-1-released"
M4_CONTRACT_REPAIR_TASK_KEY = "m4-p1-repair-injected-signal-preregistration-contract"
M4_PREREGISTRATION_V1_0_3_DIGEST = (
    "4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9"
)
M4_SYNTHETIC_MANIFEST_V1_0_1_DIGEST = (
    "f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c"
)
M4_P2_3_MAINLINE_EXECUTION_ARTIFACT_DIGEST = (
    "4e3d81cbee28b529091a11603e3a5683c1f265d9accc4f01d4c7076192c20363"
)
M4_P2_4_CALIBRATION_MANIFEST_DIGEST = (
    "f30186e3f5aeefb07565d25c4e0de68d955a07e87d1894fdaedbe8bedf4a2317"
)
M4_P2_4_CALIBRATION_RUN_DIGEST = (
    "98c75e62af6fb9fbafa11645f34a2ab69b23a60ab038788ea130eb91f3ad910c"
)
M4_P2_4_COMPLETION_DIGEST = (
    "328144fa1abebfee88d46dbbce6d9deb7b9f1f5834fb9a0c83cc55adef32a353"
)
M4_P2_4_TRUTH_DIGESTS = (
    "23a41f005f369e762f26c728eb13a5fa4888b9c04590d6e0d2410506956c7e2f",
    "709133b116c40ba95d10018c94160786c554186b94a0fc9dfaeef539d30eb58e",
    "6c8a2c30941255e617205f4a59e594e4ac894dd8057accaa6b538026263654e2",
    "a3516898188a0e8b22d0cd61f9a8b1412e4f14e80096f34a437ad720731cd179",
    "97e126b5ec61cb8bc8599f35754b3968fec037cc1349a419196238849eef87ab",
    "0a04a7251b982c80af0c8944ecf96f6faa224ad408a2f92207c4fe5fbf603e06",
    "dbc2f7a58f5b506fc911f6b9d1f27a4b3fb18215db961b50ea519baf3668b3be",
    "9623cdf111538f1883f1ed1b2b2f33ca852517744812e16e9f4f2fb4acf51f97",
    "dee510d7ebee2e3a8248657f2c71c984250a842626d3c3e3e29e917ff5025320",
    "025befa6028bb19f9cf79ea368a214f1228242ce6e05009845c6621332bc2537",
    "1a5401cbe3acd347a0a617dc3b8b153db61b995f759e229cbab77e4a4f45e44c",
    "0ce5a4353051ab8dd6e033e33508f050274a5b0166f9169a4c90f0124f7a2e5d",
)
M4_P2_5_RESAMPLING_KERNEL_DIGEST = (
    "1cde473524d7d6dcafba64ab7b0a1d2862b56149d5f6f198c73d88b406c3071b"
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
    "m4-p2-measurement-identifiability-preflight",
    "m4-p2-false-positive-and-power-runs",
    "m4-p2-automatic-gate-and-report",
)
P2_SUBPHASE_LABELS = (
    "M4-P2.1",
    "M4-P2.2",
    "M4-P2.3",
    "M4-P2.4",
    "M4-P2.5",
    "M4-P2.6-PREFLIGHT",
    "M4-P2.6.3",
    "M4-P2.7",
)


def load_m4_manifest(path: Path) -> ControlPlaneManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("M4 manifest root must be an object")
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
    p24 = next(
        task
        for task in payload["tasks"]
        if task["task_key"] == "m4-p2-injected-signal-calibration"
    )
    p24["status"] = "draft"
    p24["completion_classification"] = "INTEGRATION_PENDING"
    p25 = next(
        task for task in payload["tasks"] if task["task_key"] == "m4-p2-resampling"
    )
    p25["status"] = "draft"
    p25["completion_classification"] = "INTEGRATION_PENDING"
    preflight = next(
        task
        for task in payload["tasks"]
        if task["task_key"] == "m4-p2-measurement-identifiability-preflight"
    )
    preflight["status"] = "draft"
    preflight["completion_classification"] = "INTEGRATION_PENDING"
    payload["facts"]["artifacts"] = [
        fact
        for fact in payload["facts"]["artifacts"]
        if not fact.startswith("mainline-execution:m4-p2-injected-signal-calibration:")
        and not fact.startswith("mainline-execution:m4-p2-resampling:")
        and not fact.startswith(
            "mainline-execution:m4-p2-measurement-identifiability-preflight:"
        )
        and fact
        not in {
            f"m4-preregistration:{M4_PREREGISTRATION_V1_0_3_DIGEST}",
            (f"m4-p2-1-synthetic-run-manifest:{M4_SYNTHETIC_MANIFEST_V1_0_1_DIGEST}"),
            (
                "m4-p2-4-injected-signal-completion:"
                "328144fa1abebfee88d46dbbce6d9deb7b9f1f5834fb9a0c83cc55adef32a353"
            ),
            (f"m4-p2-5-resampling-kernel-manifest:{M4_P2_5_RESAMPLING_KERNEL_DIGEST}"),
            ("m4-p2-identifiability-decision:MEASUREMENT_CONTRACT_REPAIR_REQUIRED"),
        }
    ]
    return ControlPlaneManifest.from_dict(payload)


def build_m4_status(
    manifest: ControlPlaneManifest,
    *,
    snapshot: ResolutionSnapshot | None = None,
    mainline_execution: dict[str, Any] | None = None,
    measurement_v2_execution: dict[str, Any] | None = None,
    golden_reference_execution: dict[str, Any] | None = None,
    runtime_audit_execution: dict[str, Any] | None = None,
    dispatch_performed: bool = False,
) -> dict[str, Any]:
    if (
        measurement_v2_execution is None
        and mainline_execution is not None
        and mainline_execution.get("measurement_contract_v2_digest")
        == M4_V2_CONTRACT_DIGEST
    ):
        measurement_v2_execution = mainline_execution
        mainline_execution = None
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
    measurement_v2_task = tasks.get(M4_V2_DESIGN_TASK_KEY)
    measurement_v2_resolution = resolutions.get(M4_V2_DESIGN_TASK_KEY)
    measurement_v2_replay_resolution = resolutions.get(M4_V2_DESIGN_REPLAY_TASK_KEY)
    measurement_v2_preflight_resolution = resolutions.get(
        M4_V2_PREFLIGHT_DESIGN_TASK_KEY
    )
    measurement_v2_preflight_task = tasks.get(M4_V2_PREFLIGHT_DESIGN_TASK_KEY)
    measurement_v2_preflight_execution = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        == M4_V2_PREFLIGHT_DESIGN_TASK_KEY
        else None
    )
    measurement_v2_fixture_resolution = resolutions.get(
        M4_V2_PREFLIGHT_FIXTURE_TASK_KEY
    )
    measurement_v2_fixture_task = tasks.get(M4_V2_PREFLIGHT_FIXTURE_TASK_KEY)
    measurement_v2_preflight_execution_resolution = resolutions.get(
        M4_V2_PREFLIGHT_EXECUTION_TASK_KEY
    )
    measurement_v2_preflight_execution_task = tasks.get(
        M4_V2_PREFLIGHT_EXECUTION_TASK_KEY
    )
    measurement_v2_preflight_result = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        == M4_V2_PREFLIGHT_EXECUTION_TASK_KEY
        else None
    )
    measurement_v2_marginal_contract_resolution = resolutions.get(
        M4_V2_MARGINAL_CONTRACT_FREEZE_TASK_KEY
    )
    measurement_v2_marginal_contract_task = tasks.get(
        M4_V2_MARGINAL_CONTRACT_FREEZE_TASK_KEY
    )
    measurement_v2_marginal_contract_execution = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        in {
            M4_V2_MARGINAL_CONTRACT_FREEZE_TASK_KEY,
            M4_V2_MARGINAL_FIXTURE_FREEZE_TASK_KEY,
            M4_V2_MARGINAL_HEALTH_DESIGN_TASK_KEY,
        }
        else None
    )
    measurement_v2_marginal_fixture_resolution = resolutions.get(
        M4_V2_MARGINAL_FIXTURE_FREEZE_TASK_KEY
    )
    measurement_v2_marginal_fixture_task = tasks.get(
        M4_V2_MARGINAL_FIXTURE_FREEZE_TASK_KEY
    )
    measurement_v2_marginal_fixture_execution = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        in {
            M4_V2_MARGINAL_FIXTURE_FREEZE_TASK_KEY,
            M4_V2_MARGINAL_HEALTH_DESIGN_TASK_KEY,
            M4_V2_MARGINAL_HEALTH_EXECUTION_TASK_KEY,
        }
        else None
    )
    measurement_v2_marginal_health_design_resolution = resolutions.get(
        M4_V2_MARGINAL_HEALTH_DESIGN_TASK_KEY
    )
    measurement_v2_marginal_health_design_task = tasks.get(
        M4_V2_MARGINAL_HEALTH_DESIGN_TASK_KEY
    )
    measurement_v2_marginal_health_design_execution = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        in {
            M4_V2_MARGINAL_HEALTH_DESIGN_TASK_KEY,
            M4_V2_MARGINAL_HEALTH_EXECUTION_TASK_KEY,
        }
        else None
    )
    measurement_v2_marginal_health_execution_resolution = resolutions.get(
        M4_V2_MARGINAL_HEALTH_EXECUTION_TASK_KEY
    )
    measurement_v2_marginal_health_execution_task = tasks.get(
        M4_V2_MARGINAL_HEALTH_EXECUTION_TASK_KEY
    )
    measurement_v2_marginal_health_execution = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        == M4_V2_MARGINAL_HEALTH_EXECUTION_TASK_KEY
        else None
    )
    measurement_v2_marginal_health_decision_resolution = resolutions.get(
        M4_V2_MARGINAL_HEALTH_DECISION_TASK_KEY
    )
    measurement_v2_marginal_health_decision_task = tasks.get(
        M4_V2_MARGINAL_HEALTH_DECISION_TASK_KEY
    )
    measurement_v2_marginal_health_decision = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        in {
            M4_V2_MARGINAL_HEALTH_DECISION_TASK_KEY,
            M4_V2_MARGINAL_REPAIR_DESIGN_TASK_KEY,
            M4_V2_MARGINAL_REPAIR_PREREGISTRATION_TASK_KEY,
        }
        else None
    )
    measurement_v2_marginal_repair_design_resolution = resolutions.get(
        M4_V2_MARGINAL_REPAIR_DESIGN_TASK_KEY
    )
    measurement_v2_marginal_repair_design_task = tasks.get(
        M4_V2_MARGINAL_REPAIR_DESIGN_TASK_KEY
    )
    measurement_v2_marginal_repair_design = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        in {
            M4_V2_MARGINAL_REPAIR_DESIGN_TASK_KEY,
            M4_V2_MARGINAL_REPAIR_PREREGISTRATION_TASK_KEY,
        }
        else None
    )
    measurement_v2_marginal_repair_preregistration_resolution = resolutions.get(
        M4_V2_MARGINAL_REPAIR_PREREGISTRATION_TASK_KEY
    )
    measurement_v2_marginal_repair_preregistration_task = tasks.get(
        M4_V2_MARGINAL_REPAIR_PREREGISTRATION_TASK_KEY
    )
    measurement_v2_marginal_repair_preregistration = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        == M4_V2_MARGINAL_REPAIR_PREREGISTRATION_TASK_KEY
        else None
    )
    measurement_v2_marginal_repair_health_resolution = resolutions.get(
        M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_TASK_KEY
    )
    measurement_v2_marginal_repair_health_task = tasks.get(
        M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_TASK_KEY
    )
    measurement_v2_marginal_repair_health_execution = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        == M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_TASK_KEY
        else None
    )
    measurement_v2_marginal_repair_health_decision_resolution = resolutions.get(
        M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_TASK_KEY
    )
    measurement_v2_marginal_repair_health_decision_task = tasks.get(
        M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_TASK_KEY
    )
    measurement_v2_marginal_repair_health_decision = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        in {
            M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_TASK_KEY,
            M4_V2_MARGINAL_REPAIR_V2_DESIGN_TASK_KEY,
        }
        else None
    )
    measurement_v2_marginal_repair_v2_design_resolution = resolutions.get(
        M4_V2_MARGINAL_REPAIR_V2_DESIGN_TASK_KEY
    )
    measurement_v2_marginal_repair_v2_design_task = tasks.get(
        M4_V2_MARGINAL_REPAIR_V2_DESIGN_TASK_KEY
    )
    measurement_v2_marginal_repair_v2_design = (
        measurement_v2_execution
        if measurement_v2_execution is not None
        and measurement_v2_execution.get("execution_task_key")
        == M4_V2_MARGINAL_REPAIR_V2_DESIGN_TASK_KEY
        else None
    )
    measurement_compatibility_resolution = resolutions.get(
        M4_P263_COMPATIBILITY_TASK_KEY
    )
    marginal_binding_resolution = resolutions.get(M4_V2_MARGINAL_BINDING_TASK_KEY)
    marginal_decision_replay_resolution = resolutions.get(
        M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY
    )
    golden_reference_resolution = resolutions.get(M4_P29_GOLDEN_REFERENCE_TASK_KEY)
    runtime_audit_resolution = resolutions.get(M4_P29_RUNTIME_AUDIT_TASK_KEY)
    slot_eligibility_resolution = resolutions.get(M4_P263_SLOT_ELIGIBILITY_TASK_KEY)
    p261_golden_resolution = resolutions.get(M4_P29_P261_GOLDEN_REFERENCE_TASK_KEY)
    p261_runtime_audit_resolution = resolutions.get(M4_P29_P261_RUNTIME_AUDIT_TASK_KEY)
    p263_failed_runtime_audit_resolution = resolutions.get(
        M4_P29_P263_FAILED_RUNTIME_AUDIT_TASK_KEY
    )
    canonical_executor_available = (
        M4_P29_CANONICAL_EXECUTOR_EVENT in manifest.facts.external_events
    )
    if golden_reference_execution is not None and (
        golden_reference_execution.get("evidence_progress_before") != 0
        or golden_reference_execution.get("evidence_progress_after") != 0
        or golden_reference_execution.get("historical_outcomes_read") is not False
        or golden_reference_execution.get("p2_6_3_statistical_results_read")
        is not False
        or golden_reference_execution.get("measurement_update_policy_digest")
        != M4_P263_POLICY_DIGEST
        or golden_reference_execution.get("p2_6_3_task_digest") != M4_P263_TASK_DIGEST
        or golden_reference_execution.get("production_action") != "none"
        or golden_reference_execution.get("immutable_golden_fixture_is_oracle")
        is not True
        or golden_reference_execution.get("acceleration_boundary_independent")
        is not True
        or golden_reference_execution.get("acceleration_boundary_independence_scope")
        != M4_P29_ACCELERATION_BOUNDARY_SCOPE
        or golden_reference_execution.get("oracle_construction_process_isolated")
        is not False
        or golden_reference_execution.get(
            "oracle_construction_fully_implementation_independent"
        )
        is not False
        or len(
            str(
                golden_reference_execution.get(
                    "source_integrity_attestation_artifact_digest"
                )
                or ""
            )
        )
        != 64
        or not canonical_executor_available
    ):
        raise ValueError("golden reference execution governance changed")
    if runtime_audit_execution is not None and (
        runtime_audit_execution.get("evidence_progress_before") != 0
        or runtime_audit_execution.get("evidence_progress_after") != 0
        or runtime_audit_execution.get("historical_outcomes_read") is not False
        or runtime_audit_execution.get("p2_6_3_statistical_results_read") is not False
        or runtime_audit_execution.get("measurement_update_policy_digest")
        != M4_P263_POLICY_DIGEST
        or runtime_audit_execution.get("p2_6_3_task_digest") != M4_P263_TASK_DIGEST
        or runtime_audit_execution.get("production_action") != "none"
        or runtime_audit_execution.get("reference_evaluator_is_oracle") is not False
        or runtime_audit_execution.get("immutable_golden_fixture_is_oracle") is not True
        or runtime_audit_execution.get("acceleration_boundary_independent") is not True
        or runtime_audit_execution.get("acceleration_boundary_independence_scope")
        != M4_P29_ACCELERATION_BOUNDARY_SCOPE
        or runtime_audit_execution.get("oracle_construction_process_isolated")
        is not False
        or runtime_audit_execution.get(
            "oracle_construction_fully_implementation_independent"
        )
        is not False
        or runtime_audit_execution.get("exact_golden_replay_verified") is not True
        or runtime_audit_execution.get("actual_fold_count") != 61
        or runtime_audit_execution.get("audited_fold_count") != 61
        or runtime_audit_execution.get("correctness_replay_fold_count") != 61
        or runtime_audit_execution.get("total_execution_fold_count") != 122
        or runtime_audit_execution.get("correctness_boundary_snapshot_count") != 45
        or len(
            str(
                runtime_audit_execution.get("runtime_benchmark_attempt_artifact_digest")
                or ""
            )
        )
        != 64
        or len(
            str(
                runtime_audit_execution.get(
                    "source_integrity_attestation_artifact_digest"
                )
                or ""
            )
        )
        != 64
        or len(
            str(
                runtime_audit_execution.get(
                    "golden_source_integrity_attestation_artifact_digest"
                )
                or ""
            )
        )
        != 64
        or not runtime_audit_execution.get("benchmark_attempt_id")
        or runtime_audit_execution.get("journal_reused") is not False
        or runtime_audit_execution.get("fresh_workdir") is not True
        or runtime_audit_execution.get("shared_frozen_source_modified") is not False
        or type(runtime_audit_execution.get("backend_source_modified")) is not bool
        or not isinstance(
            runtime_audit_execution.get("acceleration_changed_paths"), list
        )
        or runtime_audit_execution.get("backend_optimization_applied") is not False
        or runtime_audit_execution.get("statistical_semantics_modified") is not False
        or not canonical_executor_available
    ):
        raise ValueError("runtime audit execution governance changed")
    repair_resolution = resolutions.get(M4_CONTRACT_REPAIR_TASK_KEY)
    repair_complete = (
        repair_resolution is not None
        and repair_resolution.status is TaskStatus.COMPLETED
    )
    current_phase = (
        "M4-P1"
        if not repair_complete
        else _current_phase(tasks, resolutions=resolutions)
    )
    current_task_key = (
        "m4-p2-injected-signal-calibration"
        if not repair_complete
        else PHASE_TASK_KEYS[current_phase]
    )
    measurement_contract_repaired = (
        "m4-p2-repaired-measurement-contract:AVAILABLE" in manifest.facts.artifacts
    )
    measurement_repair_required = not measurement_contract_repaired and (
        "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM"
        in manifest.facts.artifacts
        or ("m4-p2-identifiability-decision:MEASUREMENT_CONTRACT_REPAIR_REQUIRED")
        in manifest.facts.artifacts
    )
    if measurement_repair_required and current_phase == "M4-P2":
        current_task_key = "m4-p2-repair-measurement-system"
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
    if measurement_repair_required and current_phase == "M4-P2":
        current_state = "REPAIR_REQUIRED"
    forward_intake = resolutions["m4-forward-evidence-intake-2026085"]
    if current_phase == "M4-P5":
        if forward_intake.status is TaskStatus.EXTERNAL_WAIT:
            current_state = "WAIT_FORWARD"
        elif forward_intake.status is TaskStatus.READY:
            current_state = "SETTLING"

    next_ready = next(
        (item for item in snapshot.ready_queue if item.goal_key == M4_GOAL_KEY),
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
    evidence_progress += sum(
        _metric(tasks[task_key]).get("evidence_increment_percent", 0)
        for task_key in P2_SUBTASK_KEYS
        if resolutions[task_key].status is TaskStatus.COMPLETED
    )
    p2_measurement_repair_complete = (
        resolutions["m4-p2-repair-measurement-system"].status is TaskStatus.COMPLETED
    )
    if p2_measurement_repair_complete:
        engineering_progress += _metric(tasks["m4-p2-repair-measurement-system"]).get(
            "engineering_increment_percent", 0
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
                "preregistration_digest": repair_metric["new_preregistration_digest"],
            }
        )
    p1_complete = (
        _metric(tasks["m4-p1-contract-and-preregistration"]).get("engineering_complete")
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
    p2_4_complete = resolutions[P2_SUBTASK_KEYS[3]].status is TaskStatus.COMPLETED
    p2_5_complete = resolutions[P2_SUBTASK_KEYS[4]].status is TaskStatus.COMPLETED
    p2_preflight_complete = (
        resolutions[P2_SUBTASK_KEYS[5]].status is TaskStatus.COMPLETED
    )
    p2_6_complete = resolutions[P2_SUBTASK_KEYS[6]].status is TaskStatus.COMPLETED
    p2_7_complete = resolutions[P2_SUBTASK_KEYS[7]].status is TaskStatus.COMPLETED
    completed_p2_task_keys = [
        task_key
        for task_key in P2_SUBTASK_KEYS
        if resolutions[task_key].status is TaskStatus.COMPLETED
    ]
    latest_p2_task_key = (
        completed_p2_task_keys[-1] if completed_p2_task_keys else P2_SUBTASK_KEYS[0]
    )
    if p2_measurement_repair_complete and not p2_6_complete:
        latest_p2_task_key = "m4-p2-repair-measurement-system"
    projected_execution_task_key = (
        latest_p2_task_key
        if mainline_execution is None
        else str(mainline_execution.get("execution_task_key") or latest_p2_task_key)
    )
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
    if p2_4_complete:
        completed.extend(
            [
                "P2.4 all twelve injected-signal truth calibrations completed",
                "exact joint/composite/pair information diagnostics verified",
                "IS1-IS4 legal-space generators and null limits verified",
                "P2.3 blind checkpoint and P2.2 settlement smoke verified",
                "calibration datasets excluded from evaluation, power, and Evidence",
                "P2.4 unified supervisor execution and replay verified",
            ]
        )
    if p2_5_complete:
        completed.extend(
            [
                "P2.5 issue-level resampling kernel validated in mainline",
                "moving, stationary, and block-permutation plans replay verified",
                "NC1-NC6 registry and deterministic seed domains verified",
                "plus-one tail, percentile, aggregate, and sharding contracts frozen",
                "P2.5 smoke artifacts explicitly excluded from formal inference",
                "P2.5 unified supervisor execution and replay verified",
            ]
        )
    if p2_preflight_complete:
        completed.extend(
            [
                "P2.6 identifiability preflight validated in unified mainline",
                "joint truth versus composite marginal metric estimands compared",
                "old P2.6 execution archived as superseded without result inspection",
                "exactly one identifiability decision fact emitted",
                "preflight Evidence increment held at zero",
            ]
        )
    if p2_measurement_repair_complete:
        completed.extend(
            [
                "P2.6.1 Scheme A marginal truth-to-metric contract repaired",
                "eight feasible power truths, three joint-only controls, and one pair sentinel frozen",
                "synthetic-only state-by-number instrument validated",
                "development hyperparameters frozen outside formal evaluation seeds",
                "outer-fold estimator and calibrator fits reduced from 46 to 4",
                "measurement repair unified supervisor execution and replay verified",
            ]
        )
    if p2_6_complete:
        completed.extend(
            [
                "P2.6 all 31000 formal analysis replicates completed",
                "64656000 strict prior-only outer predictions completed",
                "false-positive, power, PE2 bias, RMSE, coverage, and MDE aggregated",
                "P2.6 formal workload validated in unified mainline",
            ]
        )
    if p2_7_complete:
        completed.extend(
            [
                "P2.7 automatic measurement gate executed",
                "exactly one PASS_TO_P3 or REPAIR_MEASUREMENT_SYSTEM fact emitted",
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
                M4_SYNTHETIC_MANIFEST_V1_0_1_DIGEST if p2_1_complete else None
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
                M4_P2_3_MAINLINE_EXECUTION_ARTIFACT_DIGEST if p2_3_complete else None
            ),
            "p2_injected_signal_calibration_manifest_digest": (
                M4_P2_4_CALIBRATION_MANIFEST_DIGEST
            ),
            "p2_injected_signal_calibration_run_digest": (
                (
                    mainline_execution.get("calibration_run_artifact_digest")
                    if mainline_execution is not None
                    else None
                )
                or (M4_P2_4_CALIBRATION_RUN_DIGEST if p2_4_complete else None)
            ),
            "p2_injected_signal_completion_digest": (
                (
                    mainline_execution.get("completion_artifact_digest")
                    if mainline_execution is not None
                    else None
                )
                or (M4_P2_4_COMPLETION_DIGEST if p2_4_complete else None)
            ),
            "p2_injected_signal_truth_digests": (
                (
                    mainline_execution.get("truth_artifact_digests")
                    if mainline_execution is not None
                    else None
                )
                or (list(M4_P2_4_TRUTH_DIGESTS) if p2_4_complete else [])
            ),
            "p2_resampling_kernel_digest": M4_P2_5_RESAMPLING_KERNEL_DIGEST,
            "p2_resampling_run_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("resampling_run_digest")
            ),
            "p2_resampling_completion_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("resampling_completion_digest")
            ),
            "p2_resampling_child_replicate_digests": (
                []
                if mainline_execution is None
                else mainline_execution.get("child_replicate_digests", [])
            ),
            "p2_resampling_aggregate_digests": (
                []
                if mainline_execution is None
                else mainline_execution.get("aggregate_digests", [])
            ),
            "p2_identifiability_preflight_manifest_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("identifiability_preflight_manifest_digest")
            ),
            "p2_identifiability_preflight_report_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("identifiability_preflight_report_digest")
            ),
            "p2_superseded_run_archive_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("superseded_run_archive_digest")
            ),
            "p2_measurement_validation_manifest_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("measurement_validation_manifest_digest")
            ),
            "p2_measurement_repair_manifest_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("measurement_repair_manifest_digest")
            ),
            "p2_repaired_measurement_validation_manifest_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get(
                    "repaired_measurement_validation_manifest_digest"
                )
            ),
            "p2_development_selection_artifact_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("development_selection_artifact_digest")
            ),
            "p2_repaired_truth_artifact_digests": (
                []
                if mainline_execution is None
                else mainline_execution.get("truth_artifact_digests", [])
            ),
            "p2_measurement_execution_plan_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("execution_plan_digest")
            ),
            "p2_measurement_completion_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("completion_artifact_digest")
            ),
            "p2_automatic_gate_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("automatic_gate_digest")
            ),
            "p2_mde_summary_digest": (
                None
                if mainline_execution is None
                else mainline_execution.get("mde_summary_digest")
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
            "synthetic_scenarios": {
                "completed": 13 if p2_4_complete else 0,
                "total": 13,
            },
            "injected_signal_truth_scenarios": {
                "completed": 12 if p2_4_complete else 0,
                "total": 12,
            },
            "negative_controls": {
                "completed": 6 if p2_5_complete else 0,
                "total": 6,
            },
            "robustness_sensitivities": {"completed": 0, "total": 5},
            "feature_families": {"completed": 0, "total": 7},
        },
        "current_statistics": {
            "primary_endpoint": "out_of_sample_log_loss_improvement",
            "oos_log_loss_improvement": None,
            "bits_gain_per_issue": None,
            "confidence_interval": None,
            "practical_null": (
                "[-0.01,+0.01] bits/issue" if p1_complete else "NOT_PREREGISTERED"
            ),
            "minimum_detectable_effect": (
                None
                if mainline_execution is None
                else mainline_execution.get("decision_policy_mde_at_61_bits_per_issue")
            ),
            "decision_policy_mde_at_61_bits_per_issue": (
                None
                if mainline_execution is None
                else mainline_execution.get("decision_policy_mde_at_61_bits_per_issue")
            ),
            "false_positive_by_scale": (
                []
                if mainline_execution is None
                else mainline_execution.get("false_positive_by_scale", [])
            ),
            "power_by_cell": (
                []
                if mainline_execution is None
                else mainline_execution.get("power_by_cell", [])
            ),
            "estimator_quality_by_cell": (
                []
                if mainline_execution is None
                else mainline_execution.get("estimator_quality_by_cell", [])
            ),
            "runtime_progress_path": (
                "runtime/logs/m4-p2-6-3-measurement-validation-progress.json"
                if resolutions[P2_SUBTASK_KEYS[6]].status is TaskStatus.RUNNING
                else None
            ),
            "power": (
                "EVALUATED"
                if p2_7_complete
                else (
                    "AGGREGATED_AWAITING_AUTOMATIC_GATE"
                    if p2_6_complete
                    else "NOT_EVALUATED"
                )
            ),
            "evidence_state": (
                "AUTOMATIC_GATE_COMPLETE"
                if p2_7_complete
                else (
                    "FORMAL_SYNTHETIC_EVIDENCE_COMPLETE"
                    if p2_6_complete
                    else "NOT_STARTED"
                )
            ),
        },
        "formal_real_data_run": "NOT_STARTED",
        "synthetic_validation": (
            "MEASUREMENT_CONTRACT_REPAIR_REQUIRED"
            if measurement_repair_required
            else (
                (
                    "PASS_TO_P3"
                    if "m4-p2-measurement-decision:PASS_TO_P3"
                    in manifest.facts.artifacts
                    else "REPAIR_MEASUREMENT_SYSTEM"
                )
                if p2_7_complete
                else (
                    (
                        "P2.6_FORMAL_MEASUREMENT_EVIDENCE_READY"
                        if p2_6_complete
                        else (
                            "P2.6.3_PERIODIC_REFIT_CONTRACT_READY"
                            if measurement_contract_repaired
                            else "P2.5_RESAMPLING_KERNEL_READY"
                        )
                    )
                    if p2_5_complete
                    else (
                        "P2.4_CALIBRATION_READY"
                        if p2_4_complete
                        else (
                            "P2.3_HARNESS_READY"
                            if p2_3_complete
                            else (
                                "P2.2_KERNEL_READY"
                                if p2_2_complete
                                else (
                                    "P2.1_CONTRACT_READY"
                                    if p2_1_complete
                                    else "NOT_STARTED"
                                )
                            )
                        )
                    )
                )
            )
        ),
        "p2_subphase": {
            "completed": [
                label
                for label, task_key in zip(
                    P2_SUBPHASE_LABELS,
                    P2_SUBTASK_KEYS,
                    strict=True,
                )
                if resolutions[task_key].status is TaskStatus.COMPLETED
            ],
            "current": (
                "M4-P1-CONTRACT-REPAIR"
                if not repair_complete
                else (
                    "M4-P2-REPAIR"
                    if measurement_repair_required
                    else (
                        "M4-P2-COMPLETE"
                        if p2_7_complete
                        else (
                            "M4-P2.7"
                            if p2_6_complete
                            else (
                                "M4-P2.6.3"
                                if p2_preflight_complete
                                else (
                                    "M4-P2.6-PREFLIGHT"
                                    if p2_5_complete
                                    else (
                                        "M4-P2.5"
                                        if p2_4_complete
                                        else (
                                            "M4-P2.4"
                                            if p2_3_complete
                                            else (
                                                "M4-P2.3"
                                                if p2_2_complete
                                                else (
                                                    "M4-P2.2"
                                                    if p2_1_complete
                                                    else "M4-P2.1"
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            ),
            "gate": (
                "PASS_TO_P3"
                if "m4-p2-measurement-decision:PASS_TO_P3" in manifest.facts.artifacts
                else (
                    "REPAIR_MEASUREMENT_SYSTEM"
                    if "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM"
                    in manifest.facts.artifacts
                    else (
                        "MEASUREMENT_CONTRACT_REPAIR_REQUIRED"
                        if measurement_repair_required
                        else "NOT_EVALUATED"
                    )
                )
            ),
            "completion_classification": (
                None
                if task_states[
                    tasks[latest_p2_task_key].artifact_digest
                ].completion_classification
                is None
                else task_states[
                    tasks[latest_p2_task_key].artifact_digest
                ].completion_classification.value
            ),
        },
        "measurement_system_v2": (
            {
                "phase": (
                    "MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION"
                    if M4_V2_MARGINAL_REPAIR_V2_DESIGN_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_REPAIR_V2_DESIGN"
                    if M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_REPAIR_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_HISTORICAL_MEASUREMENT"
                    if M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_PASS_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_REPAIR_HEALTH_DECISION"
                    if M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION"
                    if M4_V2_MARGINAL_REPAIR_PREREGISTRATION_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_REPAIR_PREREGISTRATION"
                    if M4_V2_MARGINAL_REPAIR_DESIGN_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_REPAIR_DESIGN"
                    if M4_V2_MARGINAL_HEALTH_DECISION_REPAIR_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_HISTORICAL_MEASUREMENT"
                    if M4_V2_MARGINAL_HEALTH_DECISION_PASS_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_HEALTH_DECISION"
                    if M4_V2_MARGINAL_HEALTH_EXECUTION_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_HEALTH_EXECUTION"
                    if M4_V2_MARGINAL_HEALTH_DESIGN_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_HEALTH_DESIGN"
                    if M4_V2_MARGINAL_FIXTURE_FREEZE_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_FIXTURE_FREEZE"
                    if M4_V2_MARGINAL_CONTRACT_FREEZE_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_CONTRACT_FREEZE"
                    if M4_V2_PREFLIGHT_EXECUTION_PASS_FACT in manifest.facts.artifacts
                    else "PREFLIGHT_EXECUTION_RESOLVED"
                    if measurement_v2_preflight_execution_resolution is not None
                    and measurement_v2_preflight_execution_resolution.status
                    is TaskStatus.COMPLETED
                    else "PREFLIGHT_EXECUTION"
                    if measurement_v2_fixture_resolution is not None
                    and measurement_v2_fixture_resolution.status is TaskStatus.COMPLETED
                    else "PREFLIGHT_FIXTURE_FREEZE"
                    if measurement_v2_preflight_resolution is not None
                    and measurement_v2_preflight_resolution.status
                    is TaskStatus.COMPLETED
                    else (
                        "PREFLIGHT_DESIGN"
                        if measurement_v2_replay_resolution is not None
                        and measurement_v2_replay_resolution.status
                        is TaskStatus.COMPLETED
                        else "DESIGN"
                    )
                ),
                "purpose": "hierarchical_information_measurement",
                "contract_digest": M4_V2_CONTRACT_DIGEST,
                "source_contract_status": "FROZEN",
                "compatibility": {
                    "task_key": M4_P263_COMPATIBILITY_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_compatibility_resolution is None
                        else measurement_compatibility_resolution.status.value
                    ),
                    "verified": (
                        M4_P263_COMPATIBILITY_FACT in manifest.facts.artifacts
                    ),
                    "p2_6_1_role": "FROZEN_HISTORICAL_BASELINE",
                    "p2_6_3_role": "SUPERSEDING_MEASUREMENT_IMPLEMENTATION",
                    "same_task_identity": False,
                    "result_blind": True,
                    "evidence_progress_increment": 0,
                },
                "task_key": M4_V2_DESIGN_TASK_KEY,
                "resolver_status": measurement_v2_resolution.status.value,
                "design_replay_task_key": M4_V2_DESIGN_REPLAY_TASK_KEY,
                "design_replay_resolver_status": (
                    None
                    if measurement_v2_replay_resolution is None
                    else measurement_v2_replay_resolution.status.value
                ),
                "design_replay_verified": (
                    "m4-measurement-contract-v2-design-replay:VERIFIED"
                    in manifest.facts.artifacts
                ),
                "branch_preflight_design": {
                    "task_key": M4_V2_PREFLIGHT_DESIGN_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_preflight_resolution is None
                        else measurement_v2_preflight_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_preflight_task is None
                        or task_states[
                            measurement_v2_preflight_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_preflight_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "design_frozen": (
                        PREFLIGHT_DESIGN_COMPLETION_FACT in manifest.facts.artifacts
                    ),
                    "branch_design_count": (
                        3
                        if PREFLIGHT_DESIGN_COMPLETION_FACT in manifest.facts.artifacts
                        else 0
                    ),
                    "formal_branch_runs_executed": (
                        0
                        if measurement_v2_preflight_execution is None
                        else measurement_v2_preflight_execution.get(
                            "formal_branch_runs_executed", 0
                        )
                    ),
                    "preflight_result_count": (
                        0
                        if measurement_v2_preflight_execution is None
                        else measurement_v2_preflight_execution.get(
                            "preflight_result_count", 0
                        )
                    ),
                    "historical_outcomes_read": False,
                    "statistical_results_read": False,
                    "evidence_progress_increment": 0,
                    "next_consumer": M4_V2_PREFLIGHT_FIXTURE_TASK_KEY,
                },
                "branch_preflight_fixture_freeze": {
                    "task_key": M4_V2_PREFLIGHT_FIXTURE_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_fixture_resolution is None
                        else measurement_v2_fixture_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_fixture_task is None
                        or task_states[
                            measurement_v2_fixture_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_fixture_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "fixtures_frozen": (
                        M4_V2_PREFLIGHT_FIXTURE_COMPLETION_FACT
                        in manifest.facts.artifacts
                    ),
                    "fixture_contract_count": (
                        3
                        if M4_V2_PREFLIGHT_FIXTURE_COMPLETION_FACT
                        in manifest.facts.artifacts
                        else 0
                    ),
                    "formal_branch_runs_executed": 0,
                    "preflight_result_count": 0,
                    "historical_outcomes_read": False,
                    "statistical_results_read": False,
                    "evidence_progress_increment": 0,
                    "next_consumer": M4_V2_PREFLIGHT_EXECUTION_TASK_KEY,
                },
                "branch_preflight_execution": {
                    "task_key": M4_V2_PREFLIGHT_EXECUTION_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_preflight_execution_resolution is None
                        else measurement_v2_preflight_execution_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_preflight_execution_task is None
                        or task_states[
                            measurement_v2_preflight_execution_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_preflight_execution_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "executed": (
                        M4_V2_PREFLIGHT_EXECUTION_COMPLETION_FACT
                        in manifest.facts.artifacts
                    ),
                    "all_branches_pass": (
                        M4_V2_PREFLIGHT_EXECUTION_PASS_FACT in manifest.facts.artifacts
                    ),
                    "preflight_execution_status": (
                        None
                        if measurement_v2_preflight_result is None
                        else measurement_v2_preflight_result.get(
                            "preflight_execution_status"
                        )
                    ),
                    "branch_preflight_statuses": (
                        {}
                        if measurement_v2_preflight_result is None
                        else measurement_v2_preflight_result.get(
                            "branch_preflight_statuses", {}
                        )
                    ),
                    "solver_preflight_status": (
                        None
                        if measurement_v2_preflight_result is None
                        else measurement_v2_preflight_result.get(
                            "solver_preflight_status"
                        )
                    ),
                    "orthogonal_endpoint_status": (
                        None
                        if measurement_v2_preflight_result is None
                        else measurement_v2_preflight_result.get(
                            "orthogonal_endpoint_status"
                        )
                    ),
                    "legacy_role_resolution_status": (
                        None
                        if measurement_v2_preflight_result is None
                        else measurement_v2_preflight_result.get(
                            "legacy_role_resolution_status"
                        )
                    ),
                    "preflight_result_count": (
                        0
                        if measurement_v2_preflight_result is None
                        else measurement_v2_preflight_result.get(
                            "preflight_result_count", 0
                        )
                    ),
                    "formal_branch_runs_executed": 0,
                    "monte_carlo_replicates": 0,
                    "historical_outcomes_read": False,
                    "statistical_results_read": False,
                    "evidence_progress_increment": 0,
                    "next_consumer": (
                        M4_V2_MARGINAL_CONTRACT_FREEZE_TASK_KEY
                        if M4_V2_PREFLIGHT_EXECUTION_PASS_FACT
                        in manifest.facts.artifacts
                        else None
                    ),
                },
                "marginal_static_contract_freeze": {
                    "task_key": M4_V2_MARGINAL_CONTRACT_FREEZE_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_marginal_contract_resolution is None
                        else measurement_v2_marginal_contract_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_marginal_contract_task is None
                        or task_states[
                            measurement_v2_marginal_contract_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_marginal_contract_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "completed": (
                        M4_V2_MARGINAL_CONTRACT_FREEZE_COMPLETION_FACT
                        in manifest.facts.artifacts
                    ),
                    "measurement_contract_digest": (
                        None
                        if measurement_v2_marginal_contract_execution is None
                        else measurement_v2_marginal_contract_execution.get(
                            "marginal_static_measurement_contract_digest"
                        )
                    ),
                    "estimator_id": (
                        None
                        if measurement_v2_marginal_contract_execution is None
                        else measurement_v2_marginal_contract_execution.get(
                            "estimator_id"
                        )
                    ),
                    "identifiability_preflight_status": (
                        None
                        if measurement_v2_marginal_contract_execution is None
                        else measurement_v2_marginal_contract_execution.get(
                            "identifiability_preflight_status"
                        )
                    ),
                    "legacy_measurement_health": "REPAIR",
                    "legacy_repair_overridden": False,
                    "accepted_model_artifact_digest": None,
                    "sampled_synthetic_execution_status": "NOT_AUTHORIZED",
                    "historical_execution_status": "NOT_AUTHORIZED",
                    "synthetic_replicates": 0,
                    "formal_branch_runs_executed": 0,
                    "actual_fold_count": 0,
                    "historical_outcomes_read": False,
                    "statistical_results_read": False,
                    "evidence_created": False,
                    "evidence_progress_increment": 0,
                    "next_consumer": M4_V2_MARGINAL_FIXTURE_FREEZE_TASK_KEY,
                },
                "marginal_static_fixture_freeze": {
                    "task_key": M4_V2_MARGINAL_FIXTURE_FREEZE_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_marginal_fixture_resolution is None
                        else measurement_v2_marginal_fixture_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_marginal_fixture_task is None
                        or task_states[
                            measurement_v2_marginal_fixture_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_marginal_fixture_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "completed": (
                        M4_V2_MARGINAL_FIXTURE_FREEZE_COMPLETION_FACT
                        in manifest.facts.artifacts
                    ),
                    "fixture_bundle_digest": (
                        None
                        if measurement_v2_marginal_fixture_execution is None
                        else measurement_v2_marginal_fixture_execution.get(
                            "marginal_static_fixture_bundle_digest"
                        )
                    ),
                    "fixture_count": (
                        0
                        if measurement_v2_marginal_fixture_execution is None
                        else measurement_v2_marginal_fixture_execution.get(
                            "fixture_count", 0
                        )
                    ),
                    "positive_fixture_count": (
                        0
                        if measurement_v2_marginal_fixture_execution is None
                        else measurement_v2_marginal_fixture_execution.get(
                            "positive_fixture_count", 0
                        )
                    ),
                    "negative_fixture_count": (
                        0
                        if measurement_v2_marginal_fixture_execution is None
                        else measurement_v2_marginal_fixture_execution.get(
                            "negative_fixture_count", 0
                        )
                    ),
                    "runtime_state": (
                        None
                        if measurement_v2_marginal_fixture_execution is None
                        else measurement_v2_marginal_fixture_execution.get(
                            "runtime_state"
                        )
                    ),
                    "database_reads_during_replicate": 0,
                    "database_writes_during_replicate": 0,
                    "csv_materialized": False,
                    "duplicate_raw_replay": False,
                    "routine_physical_checkpoint_scan": False,
                    "sampled_workload_status": "NOT_FROZEN",
                    "generated_issues": 0,
                    "synthetic_replicates": 0,
                    "formal_branch_runs_executed": 0,
                    "actual_fold_count": 0,
                    "historical_outcomes_read": False,
                    "statistical_results_read": False,
                    "evidence_created": False,
                    "evidence_progress_increment": 0,
                    "next_consumer": M4_V2_MARGINAL_HEALTH_DESIGN_TASK_KEY,
                },
                "marginal_static_health_design": {
                    "task_key": M4_V2_MARGINAL_HEALTH_DESIGN_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_marginal_health_design_resolution is None
                        else measurement_v2_marginal_health_design_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_marginal_health_design_task is None
                        or task_states[
                            measurement_v2_marginal_health_design_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_marginal_health_design_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "completed": (
                        M4_V2_MARGINAL_HEALTH_DESIGN_COMPLETION_FACT
                        in manifest.facts.artifacts
                    ),
                    "workload_digest": (
                        None
                        if measurement_v2_marginal_health_design_execution is None
                        else measurement_v2_marginal_health_design_execution.get(
                            "marginal_static_health_workload_digest"
                        )
                    ),
                    "inference_digest": (
                        None
                        if measurement_v2_marginal_health_design_execution is None
                        else measurement_v2_marginal_health_design_execution.get(
                            "marginal_static_health_inference_digest"
                        )
                    ),
                    "planned_total_replicates": (
                        0
                        if measurement_v2_marginal_health_design_execution is None
                        else measurement_v2_marginal_health_design_execution.get(
                            "planned_total_replicates", 0
                        )
                    ),
                    "planned_total_generated_issues": (
                        0
                        if measurement_v2_marginal_health_design_execution is None
                        else measurement_v2_marginal_health_design_execution.get(
                            "planned_total_generated_issues", 0
                        )
                    ),
                    "planned_total_outer_evaluation_issues": (
                        0
                        if measurement_v2_marginal_health_design_execution is None
                        else measurement_v2_marginal_health_design_execution.get(
                            "planned_total_outer_evaluation_issues", 0
                        )
                    ),
                    "planned_execution_shards": (
                        0
                        if measurement_v2_marginal_health_design_execution is None
                        else measurement_v2_marginal_health_design_execution.get(
                            "planned_execution_shards", 0
                        )
                    ),
                    "execution_shard_size": (
                        0
                        if measurement_v2_marginal_health_design_execution is None
                        else measurement_v2_marginal_health_design_execution.get(
                            "execution_shard_size", 0
                        )
                    ),
                    "legacy_replicates": 31000,
                    "legacy_outer_issue_predictions": 64656000,
                    "legacy_probe_fits_reused": False,
                    "legacy_results_reused": False,
                    "database_reads_during_replicate": 0,
                    "database_writes_during_replicate": 0,
                    "csv_materialized": False,
                    "duplicate_raw_replay": False,
                    "routine_physical_checkpoint_scan": False,
                    "sampled_workload_status": (
                        "FROZEN_NOT_EXECUTED"
                        if M4_V2_MARGINAL_HEALTH_DESIGN_COMPLETION_FACT
                        in manifest.facts.artifacts
                        else "NOT_FROZEN"
                    ),
                    "generated_issues": 0,
                    "synthetic_replicates": 0,
                    "bootstrap_replicates_executed": 0,
                    "formal_branch_runs_executed": 0,
                    "actual_fold_count": 0,
                    "historical_outcomes_read": False,
                    "statistical_results_read": False,
                    "evidence_created": False,
                    "evidence_progress_increment": 0,
                    "next_consumer": M4_V2_MARGINAL_HEALTH_EXECUTION_TASK_KEY,
                },
                "marginal_static_health_execution": {
                    "task_key": M4_V2_MARGINAL_HEALTH_EXECUTION_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_marginal_health_execution_resolution is None
                        else measurement_v2_marginal_health_execution_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_marginal_health_execution_task is None
                        or task_states[
                            measurement_v2_marginal_health_execution_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_marginal_health_execution_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "completed": (
                        M4_V2_MARGINAL_HEALTH_EXECUTION_COMPLETION_FACT
                        in manifest.facts.artifacts
                    ),
                    "measurement_health": (
                        None
                        if measurement_v2_marginal_health_execution is None
                        else measurement_v2_marginal_health_execution.get(
                            "measurement_health"
                        )
                    ),
                    "completion_index_digest": (
                        None
                        if measurement_v2_marginal_health_execution is None
                        else measurement_v2_marginal_health_execution.get(
                            "marginal_static_health_completion_index_digest"
                        )
                    ),
                    "health_result_digest": (
                        None
                        if measurement_v2_marginal_health_execution is None
                        else measurement_v2_marginal_health_execution.get(
                            "marginal_static_health_result_digest"
                        )
                    ),
                    "replicate_count": (
                        0
                        if measurement_v2_marginal_health_execution is None
                        else measurement_v2_marginal_health_execution.get(
                            "replicate_count", 0
                        )
                    ),
                    "generated_issues": (
                        0
                        if measurement_v2_marginal_health_execution is None
                        else measurement_v2_marginal_health_execution.get(
                            "generated_issues", 0
                        )
                    ),
                    "database_reads_during_replicate": 0,
                    "database_writes_during_replicate": 0,
                    "csv_materialized": False,
                    "duplicate_raw_replay": False,
                    "routine_physical_checkpoint_scan": False,
                    "historical_outcomes_read": False,
                    "statistical_results_read": False,
                    "production_action": "none",
                    "next_consumer": M4_V2_MARGINAL_HEALTH_DECISION_TASK_KEY,
                },
                "marginal_static_health_decision": {
                    "task_key": M4_V2_MARGINAL_HEALTH_DECISION_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_marginal_health_decision_resolution is None
                        else measurement_v2_marginal_health_decision_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_marginal_health_decision_task is None
                        or task_states[
                            measurement_v2_marginal_health_decision_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_marginal_health_decision_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "completed": any(
                        fact in manifest.facts.artifacts
                        for fact in (
                            M4_V2_MARGINAL_HEALTH_DECISION_REPAIR_FACT,
                            M4_V2_MARGINAL_HEALTH_DECISION_PASS_FACT,
                            M4_V2_MARGINAL_HEALTH_DECISION_INCONCLUSIVE_FACT,
                        )
                    ),
                    "measurement_health": (
                        None
                        if measurement_v2_marginal_health_decision is None
                        else measurement_v2_marginal_health_decision.get(
                            "measurement_health"
                        )
                    ),
                    "decision": (
                        None
                        if measurement_v2_marginal_health_decision is None
                        else measurement_v2_marginal_health_decision.get("decision")
                    ),
                    "decision_fact": (
                        None
                        if measurement_v2_marginal_health_decision is None
                        else measurement_v2_marginal_health_decision.get(
                            "decision_fact"
                        )
                    ),
                    "failed_cell_ids": (
                        []
                        if measurement_v2_marginal_health_decision is None
                        else measurement_v2_marginal_health_decision.get(
                            "failed_cell_ids", []
                        )
                    ),
                    "failed_cell_count": (
                        0
                        if measurement_v2_marginal_health_decision is None
                        else measurement_v2_marginal_health_decision.get(
                            "failed_cell_count", 0
                        )
                    ),
                    "eligible_for_historical_measurement": (
                        False
                        if measurement_v2_marginal_health_decision is None
                        else measurement_v2_marginal_health_decision.get(
                            "eligible_for_historical_measurement", False
                        )
                    ),
                    "historical_evidence": "NOT_RUN",
                    "historical_outcomes_read": False,
                    "statistical_results_read": (
                        measurement_v2_marginal_health_decision is not None
                    ),
                    "evidence_created": False,
                    "promotion_gate_opened": False,
                    "production_action": "none",
                    "duplicate_validation": False,
                    "next_consumer": (
                        M4_V2_MARGINAL_REPAIR_DESIGN_TASK_KEY
                        if M4_V2_MARGINAL_HEALTH_DECISION_REPAIR_FACT
                        in manifest.facts.artifacts
                        else None
                    ),
                },
                "marginal_static_repair_design": {
                    "task_key": M4_V2_MARGINAL_REPAIR_DESIGN_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_marginal_repair_design_resolution is None
                        else measurement_v2_marginal_repair_design_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_marginal_repair_design_task is None
                        or task_states[
                            measurement_v2_marginal_repair_design_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_marginal_repair_design_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "completed": (
                        M4_V2_MARGINAL_REPAIR_DESIGN_COMPLETION_FACT
                        in manifest.facts.artifacts
                    ),
                    "result_aware": True,
                    "new_preregistration_required": True,
                    "independent_seed_required": True,
                    "same_seed_tuning_forbidden": True,
                    "posthoc_threshold_change_forbidden": True,
                    "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
                    "forward_61_classification": (
                        None
                        if measurement_v2_marginal_repair_design is None
                        else measurement_v2_marginal_repair_design.get(
                            "forward_61_classification"
                        )
                    ),
                    "analytic_feasibility_digest": (
                        None
                        if measurement_v2_marginal_repair_design is None
                        else measurement_v2_marginal_repair_design.get(
                            "marginal_static_repair_analytic_feasibility_digest"
                        )
                    ),
                    "repair_design_digest": (
                        None
                        if measurement_v2_marginal_repair_design is None
                        else measurement_v2_marginal_repair_design.get(
                            "marginal_static_repair_design_artifact_digest"
                        )
                    ),
                    "completion_digest": (
                        None
                        if measurement_v2_marginal_repair_design is None
                        else measurement_v2_marginal_repair_design.get(
                            "marginal_static_repair_design_completion_digest"
                        )
                    ),
                    "generated_issues": 0,
                    "synthetic_replicates": 0,
                    "checkpoint_reads": 0,
                    "duplicate_validation": False,
                    "historical_outcomes_read": False,
                    "statistical_results_read": (
                        measurement_v2_marginal_repair_design is not None
                    ),
                    "evidence_created": False,
                    "promotion_gate_opened": False,
                    "production_action": "none",
                    "next_consumer": M4_V2_MARGINAL_REPAIR_PREREGISTRATION_TASK_KEY,
                },
                "marginal_static_repair_preregistration": {
                    "task_key": M4_V2_MARGINAL_REPAIR_PREREGISTRATION_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_marginal_repair_preregistration_resolution
                        is None
                        else measurement_v2_marginal_repair_preregistration_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_marginal_repair_preregistration_task is None
                        or task_states[
                            measurement_v2_marginal_repair_preregistration_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_marginal_repair_preregistration_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "completed": (
                        M4_V2_MARGINAL_REPAIR_PREREGISTRATION_COMPLETION_FACT
                        in manifest.facts.artifacts
                    ),
                    "independent_seed_required": True,
                    "same_seed_tuning_forbidden": True,
                    "posthoc_threshold_change_forbidden": True,
                    "planned_calibration_replicates": (
                        None
                        if measurement_v2_marginal_repair_preregistration is None
                        else measurement_v2_marginal_repair_preregistration.get(
                            "planned_calibration_replicates"
                        )
                    ),
                    "planned_evaluation_replicates": (
                        None
                        if measurement_v2_marginal_repair_preregistration is None
                        else measurement_v2_marginal_repair_preregistration.get(
                            "planned_evaluation_replicates"
                        )
                    ),
                    "planned_total_replicates": (
                        None
                        if measurement_v2_marginal_repair_preregistration is None
                        else measurement_v2_marginal_repair_preregistration.get(
                            "planned_total_replicates"
                        )
                    ),
                    "planned_total_generated_issues": (
                        None
                        if measurement_v2_marginal_repair_preregistration is None
                        else measurement_v2_marginal_repair_preregistration.get(
                            "planned_total_generated_issues"
                        )
                    ),
                    "workload_and_seed_digest": (
                        None
                        if measurement_v2_marginal_repair_preregistration is None
                        else measurement_v2_marginal_repair_preregistration.get(
                            "marginal_static_repair_health_workload_seed_digest"
                        )
                    ),
                    "inference_and_gate_digest": (
                        None
                        if measurement_v2_marginal_repair_preregistration is None
                        else measurement_v2_marginal_repair_preregistration.get(
                            "marginal_static_repair_health_inference_gate_digest"
                        )
                    ),
                    "preregistration_digest": (
                        None
                        if measurement_v2_marginal_repair_preregistration is None
                        else measurement_v2_marginal_repair_preregistration.get(
                            "marginal_static_repair_health_preregistration_digest"
                        )
                    ),
                    "completion_digest": (
                        None
                        if measurement_v2_marginal_repair_preregistration is None
                        else measurement_v2_marginal_repair_preregistration.get(
                            "marginal_static_repair_health_preregistration_completion_digest"
                        )
                    ),
                    "generated_issues": 0,
                    "synthetic_replicates": 0,
                    "bootstrap_replicates_executed": 0,
                    "checkpoint_reads": 0,
                    "duplicate_validation": False,
                    "historical_outcomes_read": False,
                    "statistical_results_read": False,
                    "evidence_created": False,
                    "promotion_gate_opened": False,
                    "production_action": "none",
                    "next_consumer": (M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_TASK_KEY),
                },
                "marginal_static_repair_health_execution": {
                    "task_key": M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_marginal_repair_health_resolution is None
                        else measurement_v2_marginal_repair_health_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_marginal_repair_health_task is None
                        or task_states[
                            measurement_v2_marginal_repair_health_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_marginal_repair_health_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "completed": (
                        M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT
                        in manifest.facts.artifacts
                    ),
                    "formal_execution_status": (
                        "COMPLETE_PENDING_DECISION"
                        if measurement_v2_marginal_repair_health_execution is not None
                        else "NOT_RUN"
                    ),
                    "preliminary_measurement_health": (
                        None
                        if measurement_v2_marginal_repair_health_execution is None
                        else measurement_v2_marginal_repair_health_execution.get(
                            "repair_health_preliminary_measurement_health"
                        )
                    ),
                    "authoritative_decision": None,
                    "replicate_count": (
                        0
                        if measurement_v2_marginal_repair_health_execution is None
                        else measurement_v2_marginal_repair_health_execution.get(
                            "replicate_count", 0
                        )
                    ),
                    "calibration_replicates": (
                        0
                        if measurement_v2_marginal_repair_health_execution is None
                        else measurement_v2_marginal_repair_health_execution.get(
                            "calibration_replicates", 0
                        )
                    ),
                    "evaluation_replicates": (
                        0
                        if measurement_v2_marginal_repair_health_execution is None
                        else measurement_v2_marginal_repair_health_execution.get(
                            "evaluation_replicates", 0
                        )
                    ),
                    "generated_issues": (
                        0
                        if measurement_v2_marginal_repair_health_execution is None
                        else measurement_v2_marginal_repair_health_execution.get(
                            "generated_issues", 0
                        )
                    ),
                    "outer_evaluation_issues": (
                        0
                        if measurement_v2_marginal_repair_health_execution is None
                        else measurement_v2_marginal_repair_health_execution.get(
                            "outer_evaluation_issues", 0
                        )
                    ),
                    "completion_index_digest": (
                        None
                        if measurement_v2_marginal_repair_health_execution is None
                        else measurement_v2_marginal_repair_health_execution.get(
                            "marginal_static_repair_health_completion_index_digest"
                        )
                    ),
                    "feasibility_digest": (
                        None
                        if measurement_v2_marginal_repair_health_execution is None
                        else measurement_v2_marginal_repair_health_execution.get(
                            "marginal_static_repair_health_feasibility_digest"
                        )
                    ),
                    "health_result_digest": (
                        None
                        if measurement_v2_marginal_repair_health_execution is None
                        else measurement_v2_marginal_repair_health_execution.get(
                            "marginal_static_repair_health_result_digest"
                        )
                    ),
                    "completion_digest": (
                        None
                        if measurement_v2_marginal_repair_health_execution is None
                        else measurement_v2_marginal_repair_health_execution.get(
                            "marginal_static_repair_health_execution_completion_digest"
                        )
                    ),
                    "checkpoint_mode": ("compact_index_direct_resume_without_scan"),
                    "nested_bootstrap_replicates": 0,
                    "duplicate_validation": False,
                    "historical_outcomes_read": False,
                    "round_42_statistical_results_read": False,
                    "evidence_created": False,
                    "promotion_gate_opened": False,
                    "production_action": "none",
                    "next_consumer": M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_TASK_KEY,
                },
                "marginal_static_repair_health_decision": {
                    "task_key": M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_marginal_repair_health_decision_resolution
                        is None
                        else measurement_v2_marginal_repair_health_decision_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_marginal_repair_health_decision_task is None
                        or task_states[
                            measurement_v2_marginal_repair_health_decision_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_marginal_repair_health_decision_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "completed": any(
                        fact in manifest.facts.artifacts
                        for fact in (
                            M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_REPAIR_FACT,
                            M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_PASS_FACT,
                            M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_INCONCLUSIVE_FACT,
                        )
                    ),
                    "measurement_health": (
                        None
                        if measurement_v2_marginal_repair_health_decision is None
                        else measurement_v2_marginal_repair_health_decision.get(
                            "measurement_health"
                        )
                    ),
                    "authoritative_decision": (
                        None
                        if measurement_v2_marginal_repair_health_decision is None
                        else measurement_v2_marginal_repair_health_decision.get(
                            "authoritative_decision"
                        )
                    ),
                    "decision_fact": (
                        None
                        if measurement_v2_marginal_repair_health_decision is None
                        else measurement_v2_marginal_repair_health_decision.get(
                            "decision_fact"
                        )
                    ),
                    "failed_control_cell_ids": (
                        []
                        if measurement_v2_marginal_repair_health_decision is None
                        else measurement_v2_marginal_repair_health_decision.get(
                            "failed_control_cell_ids", []
                        )
                    ),
                    "failed_control_cell_count": (
                        0
                        if measurement_v2_marginal_repair_health_decision is None
                        else measurement_v2_marginal_repair_health_decision.get(
                            "failed_control_cell_count", 0
                        )
                    ),
                    "instrument_limit_cell_count": (
                        0
                        if measurement_v2_marginal_repair_health_decision is None
                        else measurement_v2_marginal_repair_health_decision.get(
                            "instrument_limit_cell_count", 0
                        )
                    ),
                    "eligible_for_historical_measurement": (
                        False
                        if measurement_v2_marginal_repair_health_decision is None
                        else measurement_v2_marginal_repair_health_decision.get(
                            "eligible_for_historical_measurement", False
                        )
                    ),
                    "historical_outcomes_read": False,
                    "statistical_results_read": (
                        measurement_v2_marginal_repair_health_decision is not None
                    ),
                    "evidence_created": False,
                    "promotion_gate_opened": False,
                    "production_action": "none",
                    "duplicate_validation": False,
                    "next_consumer": (
                        M4_V2_MARGINAL_REPAIR_V2_DESIGN_TASK_KEY
                        if M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_REPAIR_FACT
                        in manifest.facts.artifacts
                        else None
                    ),
                },
                "marginal_static_repair_v2_design": {
                    "task_key": M4_V2_MARGINAL_REPAIR_V2_DESIGN_TASK_KEY,
                    "resolver_status": (
                        None
                        if measurement_v2_marginal_repair_v2_design_resolution is None
                        else measurement_v2_marginal_repair_v2_design_resolution.status.value
                    ),
                    "completion_classification": (
                        None
                        if measurement_v2_marginal_repair_v2_design_task is None
                        or task_states[
                            measurement_v2_marginal_repair_v2_design_task.artifact_digest
                        ].completion_classification
                        is None
                        else task_states[
                            measurement_v2_marginal_repair_v2_design_task.artifact_digest
                        ].completion_classification.value
                    ),
                    "completed": (
                        M4_V2_MARGINAL_REPAIR_V2_DESIGN_COMPLETION_FACT
                        in manifest.facts.artifacts
                    ),
                    "presample_feasibility_digest": (
                        None
                        if measurement_v2_marginal_repair_v2_design is None
                        else measurement_v2_marginal_repair_v2_design.get(
                            "presample_feasibility_digest"
                        )
                    ),
                    "repair_v2_design_digest": (
                        None
                        if measurement_v2_marginal_repair_v2_design is None
                        else measurement_v2_marginal_repair_v2_design.get(
                            "repair_v2_design_digest"
                        )
                    ),
                    "repair_v2_design_completion_digest": (
                        None
                        if measurement_v2_marginal_repair_v2_design is None
                        else measurement_v2_marginal_repair_v2_design.get(
                            "repair_v2_design_completion_digest"
                        )
                    ),
                    "reference_scores_per_block": 19,
                    "evaluation_replicates_per_cell": 1024,
                    "future_total_replicates": 131072,
                    "future_generated_issues": 291110912,
                    "formal_replicates_executed": 0,
                    "generated_issues": 0,
                    "compact_index_reads": 0,
                    "raw_replicates_regenerated": 0,
                    "sentinel_replicates_recomputed": 0,
                    "duplicate_validation": False,
                    "historical_outcomes_read": False,
                    "statistical_results_read": (
                        measurement_v2_marginal_repair_v2_design is not None
                    ),
                    "evidence_created": False,
                    "promotion_gate_opened": False,
                    "production_action": "none",
                    "next_consumer": M4_V2_MARGINAL_REPAIR_V2_PREREGISTRATION_TASK_KEY,
                },
                "completion_classification": (
                    None
                    if task_states[
                        measurement_v2_task.artifact_digest
                    ].completion_classification
                    is None
                    else task_states[
                        measurement_v2_task.artifact_digest
                    ].completion_classification.value
                ),
                "live_mainline_status": (
                    "MARGINAL_STATIC_REPAIR_V2_DESIGN_VALIDATED_IN_MAINLINE"
                    if M4_V2_MARGINAL_REPAIR_V2_DESIGN_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_REPAIR_HEALTH_DECISION_VALIDATED_IN_MAINLINE"
                    if any(
                        fact in manifest.facts.artifacts
                        for fact in (
                            M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_REPAIR_FACT,
                            M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_PASS_FACT,
                            M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_INCONCLUSIVE_FACT,
                        )
                    )
                    else "MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_VALIDATED_IN_MAINLINE"
                    if M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_REPAIR_PREREGISTRATION_VALIDATED_IN_MAINLINE"
                    if M4_V2_MARGINAL_REPAIR_PREREGISTRATION_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_REPAIR_DESIGN_VALIDATED_IN_MAINLINE"
                    if M4_V2_MARGINAL_REPAIR_DESIGN_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_HEALTH_DECISION_VALIDATED_IN_MAINLINE"
                    if any(
                        fact in manifest.facts.artifacts
                        for fact in (
                            M4_V2_MARGINAL_HEALTH_DECISION_REPAIR_FACT,
                            M4_V2_MARGINAL_HEALTH_DECISION_PASS_FACT,
                            M4_V2_MARGINAL_HEALTH_DECISION_INCONCLUSIVE_FACT,
                        )
                    )
                    else "MARGINAL_STATIC_HEALTH_EXECUTION_VALIDATED_IN_MAINLINE"
                    if M4_V2_MARGINAL_HEALTH_EXECUTION_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_HEALTH_DESIGN_VALIDATED_IN_MAINLINE"
                    if M4_V2_MARGINAL_HEALTH_DESIGN_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_FIXTURES_VALIDATED_IN_MAINLINE"
                    if M4_V2_MARGINAL_FIXTURE_FREEZE_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "MARGINAL_STATIC_CONTRACT_VALIDATED_IN_MAINLINE"
                    if M4_V2_MARGINAL_CONTRACT_FREEZE_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else "BRANCH_PREFLIGHT_VALIDATED_IN_MAINLINE"
                    if M4_V2_PREFLIGHT_EXECUTION_PASS_FACT in manifest.facts.artifacts
                    else "BRANCH_PREFLIGHT_RESOLVED_IN_MAINLINE"
                    if measurement_v2_preflight_execution_resolution is not None
                    and measurement_v2_preflight_execution_resolution.status
                    is TaskStatus.COMPLETED
                    else "PREFLIGHT_FIXTURES_VALIDATED_IN_MAINLINE"
                    if measurement_v2_fixture_resolution is not None
                    and measurement_v2_fixture_resolution.status is TaskStatus.COMPLETED
                    else "PREFLIGHT_DESIGN_VALIDATED_IN_MAINLINE"
                    if measurement_v2_preflight_resolution is not None
                    and measurement_v2_preflight_resolution.status
                    is TaskStatus.COMPLETED
                    else "VALIDATED_IN_MAINLINE"
                    if measurement_v2_replay_resolution is not None
                    and measurement_v2_replay_resolution.status is TaskStatus.COMPLETED
                    else (
                        "DESIGN_EXECUTED_REPLAY_PENDING"
                        if measurement_v2_resolution.status is TaskStatus.COMPLETED
                        else (
                            "SLOT_RELEASE_OPERATOR_PENDING"
                            if slot_eligibility_resolution is not None
                            and slot_eligibility_resolution.status
                            is TaskStatus.COMPLETED
                            else (
                                "SLOT_ELIGIBILITY_PENDING"
                                if slot_eligibility_resolution is not None
                                and slot_eligibility_resolution.status
                                in {
                                    TaskStatus.READY,
                                    TaskStatus.RUNNING,
                                    TaskStatus.DEPENDENCY_WAIT,
                                }
                                else "INTEGRATION_PENDING"
                            )
                        )
                    )
                ),
                "runtime_release_event": M4_V2_RUNTIME_RELEASE_EVENT,
                "runtime_release_available": (
                    M4_V2_RUNTIME_RELEASE_EVENT in manifest.facts.external_events
                ),
                "runtime_slot_eligibility": {
                    "task_key": M4_P263_SLOT_ELIGIBILITY_TASK_KEY,
                    "resolver_status": (
                        None
                        if slot_eligibility_resolution is None
                        else slot_eligibility_resolution.status.value
                    ),
                    "resolver_reason_code": (
                        None
                        if slot_eligibility_resolution is None
                        else slot_eligibility_resolution.reason_code
                    ),
                    "verified": (
                        M4_P263_SLOT_ELIGIBILITY_FACT in manifest.facts.artifacts
                    ),
                    "p2_6_1_status": "FROZEN_INCOMPLETE",
                    "p2_6_3_status": "SUPERSEDING_COMPLETE",
                    "result_blind": True,
                    "statistical_results_read": False,
                    "evidence_progress_increment": 0,
                    "promotion_gate_opened": False,
                    "next_consumer": (
                        M4_V2_DESIGN_TASK_KEY
                        if M4_V2_RUNTIME_RELEASE_EVENT in manifest.facts.external_events
                        else "approved_operator_post_stop_guard"
                    ),
                },
                "p2_6_1_semantic_purpose": (
                    "MARGINAL_OUTPUT_MEASUREMENT_ACCEPTANCE_BASELINE"
                ),
                "p2_6_1_identity_changed": False,
                "p2_6_1_runtime_operation": "none",
                "formal_temporal_or_joint_execution": "NOT_AUTHORIZED",
                "evidence_progress_increment": 0,
                "marginal_binding": {
                    "binding_contract_status": "FROZEN_RESULT_BLIND",
                    "resolver_status": (
                        None
                        if marginal_binding_resolution is None
                        else marginal_binding_resolution.status.value
                    ),
                    "decision_replay_resolver_status": (
                        None
                        if marginal_decision_replay_resolution is None
                        else marginal_decision_replay_resolution.status.value
                    ),
                    "historical_evidence": (
                        "NOT_RUN"
                        if measurement_v2_execution is None
                        else measurement_v2_execution.get(
                            "historical_evidence",
                            "NOT_RUN",
                        )
                    ),
                },
                "next_consumer": (
                    M4_V2_MARGINAL_REPAIR_HEALTH_EXECUTION_TASK_KEY
                    if M4_V2_MARGINAL_REPAIR_PREREGISTRATION_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else M4_V2_MARGINAL_REPAIR_PREREGISTRATION_TASK_KEY
                    if M4_V2_MARGINAL_REPAIR_DESIGN_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else M4_V2_MARGINAL_REPAIR_DESIGN_TASK_KEY
                    if M4_V2_MARGINAL_HEALTH_DECISION_REPAIR_FACT
                    in manifest.facts.artifacts
                    else M4_V2_MARGINAL_HEALTH_DECISION_TASK_KEY
                    if M4_V2_MARGINAL_HEALTH_EXECUTION_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else M4_V2_MARGINAL_HEALTH_EXECUTION_TASK_KEY
                    if M4_V2_MARGINAL_HEALTH_DESIGN_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else M4_V2_MARGINAL_HEALTH_DESIGN_TASK_KEY
                    if M4_V2_MARGINAL_FIXTURE_FREEZE_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else M4_V2_MARGINAL_FIXTURE_FREEZE_TASK_KEY
                    if M4_V2_MARGINAL_CONTRACT_FREEZE_COMPLETION_FACT
                    in manifest.facts.artifacts
                    else M4_V2_MARGINAL_CONTRACT_FREEZE_TASK_KEY
                    if M4_V2_PREFLIGHT_EXECUTION_PASS_FACT in manifest.facts.artifacts
                    else None
                    if measurement_v2_preflight_execution_resolution is not None
                    and measurement_v2_preflight_execution_resolution.status
                    is TaskStatus.COMPLETED
                    else M4_V2_PREFLIGHT_EXECUTION_TASK_KEY
                    if measurement_v2_fixture_resolution is not None
                    and measurement_v2_fixture_resolution.status is TaskStatus.COMPLETED
                    else M4_V2_PREFLIGHT_FIXTURE_TASK_KEY
                    if measurement_v2_preflight_resolution is not None
                    and measurement_v2_preflight_resolution.status
                    is TaskStatus.COMPLETED
                    else M4_V2_PREFLIGHT_DESIGN_TASK_KEY
                    if measurement_v2_replay_resolution is not None
                    and measurement_v2_replay_resolution.status is TaskStatus.COMPLETED
                    else M4_V2_DESIGN_REPLAY_TASK_KEY
                ),
                "mainline_execution": (
                    None
                    if measurement_v2_execution is None
                    else {
                        "execution_artifact_digest": (
                            measurement_v2_execution.get("execution_artifact_digest")
                        ),
                        "registered_artifact_count": (
                            measurement_v2_execution.get("registered_artifact_count")
                        ),
                        "actual_fold_count": measurement_v2_execution.get(
                            "actual_fold_count"
                        ),
                    }
                ),
            }
            if measurement_v2_task is not None and measurement_v2_resolution is not None
            else {
                "phase": "NOT_DECLARED",
                "live_mainline_status": "NOT_DECLARED",
            }
        ),
        "measurement_runtime_audit": {
            "task_key": M4_P29_RUNTIME_AUDIT_TASK_KEY,
            "lane": "maintenance",
            "agent_authority": "engineering",
            "supersession": {
                "status": "P2_6_3_SUPERSEDES_FROZEN_INCOMPLETE_P2_6_1",
                "p2_6_1_golden_task_key": M4_P29_P261_GOLDEN_REFERENCE_TASK_KEY,
                "p2_6_1_golden_resolver_status": (
                    None
                    if p261_golden_resolution is None
                    else p261_golden_resolution.status.value
                ),
                "p2_6_1_runtime_audit_task_key": (M4_P29_P261_RUNTIME_AUDIT_TASK_KEY),
                "p2_6_1_runtime_audit_resolver_status": (
                    None
                    if p261_runtime_audit_resolution is None
                    else p261_runtime_audit_resolution.status.value
                ),
                "p2_6_3_failed_runtime_audit_task_key": (
                    M4_P29_P263_FAILED_RUNTIME_AUDIT_TASK_KEY
                ),
                "p2_6_3_failed_runtime_audit_resolver_status": (
                    None
                    if p263_failed_runtime_audit_resolution is None
                    else p263_failed_runtime_audit_resolution.status.value
                ),
                "p2_6_3_task_digest": M4_P263_TASK_DIGEST,
                "measurement_update_policy_digest": M4_P263_POLICY_DIGEST,
                "old_results_or_checkpoints_reused": False,
            },
            "required_fingerprint_digest": (
                M4_P29_CANONICAL_EXECUTOR_FINGERPRINT_DIGEST
            ),
            "canonical_executor_event": M4_P29_CANONICAL_EXECUTOR_EVENT,
            "canonical_executor_available": canonical_executor_available,
            "golden_reference": {
                "task_key": M4_P29_GOLDEN_REFERENCE_TASK_KEY,
                "execution_status": (
                    "NOT_RUN"
                    if golden_reference_execution is None
                    else (
                        "REPLAY_VERIFIED"
                        if golden_reference_execution.get("exact_replay_verified")
                        is True
                        else "INCONCLUSIVE"
                    )
                ),
                "resolver_status": (
                    None
                    if golden_reference_resolution is None
                    else golden_reference_resolution.status.value
                ),
                "resolver_reason_code": (
                    None
                    if golden_reference_resolution is None
                    else golden_reference_resolution.reason_code
                ),
                "resolver_unsatisfied_dependencies": (
                    []
                    if golden_reference_resolution is None
                    else [
                        item.target_key
                        for item in golden_reference_resolution.unsatisfied_dependencies
                    ]
                ),
                "plan_artifact_digest": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get(
                        "golden_reference_plan_artifact_digest"
                    )
                ),
                "fixture_artifact_digest": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get(
                        "golden_reference_fixture_artifact_digest"
                    )
                ),
                "replay_artifact_digest": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get(
                        "golden_reference_replay_artifact_digest"
                    )
                ),
                "source_integrity_attestation_artifact_digest": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get(
                        "source_integrity_attestation_artifact_digest"
                    )
                ),
                "immutable_golden_fixture_is_oracle": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get(
                        "immutable_golden_fixture_is_oracle"
                    )
                ),
                "acceleration_boundary_independent": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get(
                        "acceleration_boundary_independent"
                    )
                ),
                "acceleration_boundary_independence_scope": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get(
                        "acceleration_boundary_independence_scope"
                    )
                ),
                "oracle_construction_process_isolated": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get(
                        "oracle_construction_process_isolated"
                    )
                ),
                "oracle_construction_fully_implementation_independent": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get(
                        "oracle_construction_fully_implementation_independent"
                    )
                ),
                "exact_replay_verified": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get("exact_replay_verified")
                ),
                "engineering_progress_before": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get("engineering_progress_before")
                ),
                "engineering_progress_after": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get("engineering_progress_after")
                ),
                "evidence_progress_before": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get("evidence_progress_before")
                ),
                "evidence_progress_after": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get("evidence_progress_after")
                ),
                "historical_outcomes_read": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get("historical_outcomes_read")
                ),
                "production_action": (
                    None
                    if golden_reference_execution is None
                    else golden_reference_execution.get("production_action")
                ),
                "next_consumer": M4_P29_RUNTIME_AUDIT_TASK_KEY,
            },
            "resolver_status": (
                None
                if runtime_audit_resolution is None
                else runtime_audit_resolution.status.value
            ),
            "resolver_reason_code": (
                None
                if runtime_audit_resolution is None
                else runtime_audit_resolution.reason_code
            ),
            "resolver_unsatisfied_dependencies": (
                []
                if runtime_audit_resolution is None
                else [
                    item.target_key
                    for item in runtime_audit_resolution.unsatisfied_dependencies
                ]
            ),
            "execution_status": (
                "NOT_RUN"
                if runtime_audit_execution is None
                else "EXACT_GOLDEN_EQUIVALENCE_VERIFIED"
            ),
            "golden_prerequisite_verified": bool(
                runtime_audit_execution is not None
                and runtime_audit_execution.get("golden_reference_plan_artifact_digest")
                and runtime_audit_execution.get(
                    "golden_reference_fixture_artifact_digest"
                )
                and runtime_audit_execution.get(
                    "golden_reference_replay_artifact_digest"
                )
                and runtime_audit_execution.get("exact_golden_replay_verified") is True
            ),
            "golden_reference_execution_artifact_digest": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get(
                    "golden_reference_execution_artifact_digest"
                )
            ),
            "golden_reference_plan_artifact_digest": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get(
                    "golden_reference_plan_artifact_digest"
                )
            ),
            "golden_reference_fixture_artifact_digest": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get(
                    "golden_reference_fixture_artifact_digest"
                )
            ),
            "golden_reference_replay_artifact_digest": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get(
                    "golden_reference_replay_artifact_digest"
                )
            ),
            "benchmark_plan_artifact_digest": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("benchmark_plan_artifact_digest")
            ),
            "runtime_observation_artifact_digest": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("runtime_observation_artifact_digest")
            ),
            "runtime_benchmark_attempt_artifact_digest": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get(
                    "runtime_benchmark_attempt_artifact_digest"
                )
            ),
            "source_integrity_attestation_artifact_digest": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get(
                    "source_integrity_attestation_artifact_digest"
                )
            ),
            "golden_source_integrity_attestation_artifact_digest": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get(
                    "golden_source_integrity_attestation_artifact_digest"
                )
            ),
            "equivalence_attestation_artifact_digest": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get(
                    "equivalence_attestation_artifact_digest"
                )
            ),
            "immutable_golden_fixture_is_oracle": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("immutable_golden_fixture_is_oracle")
            ),
            "acceleration_boundary_independent": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("acceleration_boundary_independent")
            ),
            "acceleration_boundary_independence_scope": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get(
                    "acceleration_boundary_independence_scope"
                )
            ),
            "oracle_construction_process_isolated": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("oracle_construction_process_isolated")
            ),
            "oracle_construction_fully_implementation_independent": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get(
                    "oracle_construction_fully_implementation_independent"
                )
            ),
            "exact_golden_replay_verified": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("exact_golden_replay_verified")
            ),
            "production_like_measured_fold_count": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("audited_fold_count")
            ),
            "correctness_replay_fold_count": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("correctness_replay_fold_count")
            ),
            "total_execution_fold_count": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("total_execution_fold_count")
            ),
            "correctness_boundary_snapshot_count": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("correctness_boundary_snapshot_count")
            ),
            "benchmark_attempt_id": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("benchmark_attempt_id")
            ),
            "journal_reused": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("journal_reused")
            ),
            "fresh_workdir": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("fresh_workdir")
            ),
            "shared_frozen_source_modified": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("shared_frozen_source_modified")
            ),
            "backend_source_modified": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("backend_source_modified")
            ),
            "acceleration_changed_paths": (
                []
                if runtime_audit_execution is None
                else runtime_audit_execution.get("acceleration_changed_paths", [])
            ),
            "backend_optimization_applied": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("backend_optimization_applied")
            ),
            "statistical_semantics_modified": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("statistical_semantics_modified")
            ),
            "formal_benchmark_before_slot_release": False,
            "evidence_progress_increment": 0,
            "historical_outcomes_read": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("historical_outcomes_read")
            ),
            "production_action": (
                None
                if runtime_audit_execution is None
                else runtime_audit_execution.get("production_action")
            ),
        },
        "mainline_integration": {
            "goal_integration": M4_GOAL_KEY,
            "ready_queue_integration": "PASS",
            "runner_integration": "research_evidence_supervisor",
            "task_key": projected_execution_task_key,
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
            "downstream_consumer": (
                "m4-p2-repair-measurement-system"
                if measurement_repair_required
                else (
                    (
                        "m4-p3-strict-historical-walk-forward"
                        if "m4-p2-measurement-decision:PASS_TO_P3"
                        in manifest.facts.artifacts
                        else "m4-p2-repair-measurement-system"
                    )
                    if p2_7_complete
                    else (
                        "m4-p2-automatic-gate-and-report"
                        if p2_6_complete
                        else (
                            "m4-p2-false-positive-and-power-runs"
                            if p2_preflight_complete
                            else (
                                "m4-p2-measurement-identifiability-preflight"
                                if p2_5_complete
                                else (
                                    "m4-p2-resampling"
                                    if p2_4_complete
                                    else "m4-p2-injected-signal-calibration"
                                )
                            )
                        )
                    )
                )
            ),
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


def _current_phase(
    tasks: dict[str, Task],
    *,
    resolutions: dict[str, Any],
) -> str:
    for phase, task_key in PHASE_TASK_KEYS.items():
        if resolutions[task_key].status is TaskStatus.COMPLETED:
            continue
        if _metric(tasks[task_key]).get("engineering_complete") is not True:
            return phase
    return "M4-P6"


def _metric(task: Task) -> dict[str, Any]:
    value = json.loads(task.metric_contract)
    assert isinstance(value, dict)
    return value
