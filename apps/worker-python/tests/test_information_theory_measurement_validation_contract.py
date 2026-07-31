import json
from pathlib import Path

import pytest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory import load_m4_manifest
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_validation import (
    MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
    MeasurementValidationContractError,
    load_measurement_validation_manifest,
    validate_measurement_validation_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest, ResearchOSValidationError

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-p2-6-measurement-validation-v1.json"
)
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
PASS_FACT = "m4-p2-measurement-decision:PASS_TO_P3"
REPAIR_FACT = "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM"
IDENTIFIABLE_FACT = "m4-p2-identifiability-decision:MEASUREMENT_CONTRACT_IDENTIFIABLE"
IDENTIFIABILITY_REPAIR_FACT = (
    "m4-p2-identifiability-decision:MEASUREMENT_CONTRACT_REPAIR_REQUIRED"
)
PREFLIGHT_TASK = "m4-p2-measurement-identifiability-preflight"


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _payload() -> dict:
    manifest = load_m4_manifest(MANIFEST_PATH)
    return manifest.to_dict(include_digest=False)


def _set_task_complete(payload: dict, task_key: str, execution_id: str) -> None:
    manifest = ControlPlaneManifest.from_dict(payload)
    task = next(item for item in manifest.tasks if item.task_key == task_key)
    raw = next(item for item in payload["tasks"] if item["task_key"] == task_key)
    raw["status"] = "completed"
    raw["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].append(
        mainline_completion_fact(task=task, execution_id=execution_id)
    )


def _states(payload: dict) -> tuple[list[str], dict[str, str]]:
    manifest = ControlPlaneManifest.from_dict(payload)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    return (
        [item.task_key for item in snapshot.ready_queue],
        {item.task_key: item.status.value for item in snapshot.resolutions},
    )


def test_frozen_measurement_validation_contract_is_result_blind_and_complete() -> None:
    manifest = load_measurement_validation_manifest(CONTRACT_PATH)
    assert manifest.artifact_digest == MEASUREMENT_VALIDATION_MANIFEST_DIGEST
    assert manifest.scenario_replicates == 31000
    assert manifest.outer_issue_predictions == 64656000
    assert manifest.bootstrap_replicates == manifest.permutation_replicates == 2000
    assert (manifest.coverage_lower, manifest.coverage_upper) == (0.925, 0.975)
    assert manifest.practical_power_min == 0.8
    assert manifest.strong_power_min == 0.95
    assert set(manifest.payload["result_blind_freeze"].values()) == {False}


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("interval_contract", "coverage_acceptance_interval"), [0.9, 1.0]),
        (("power_gates", "practical_0_01_bits_per_issue_min"), 0.7),
        (("power_gates", "strong_0_05_bits_per_issue_min"), 0.8),
        (("mde_contract", "interpolation"), "linear"),
        (("workload", "scenario_replicates"), 30999),
        (("estimator_contract", "PE2", "definition"), "PE1"),
        (("automatic_gate", "manual_override"), "allowed"),
    ],
)
def test_contract_mutations_fail_even_with_recomputed_self_digest(
    path: tuple[str, ...],
    value,
) -> None:
    payload = _contract()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    payload["artifact_digest"] = config_digest(payload)
    with pytest.raises(
        MeasurementValidationContractError,
        match="measurement_validation_manifest_digest_mismatch",
    ):
        validate_measurement_validation_manifest(payload)


def test_revised_p26_waits_for_identifiable_repaired_contract() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == "m4-p2-false-positive-and-power-runs"
    )
    metric = json.loads(task.metric_contract)
    assert task.requested_capability == "m4_p2_6_1_false_positive_and_power"
    assert MEASUREMENT_VALIDATION_MANIFEST_DIGEST not in task.input_artifact_digests
    assert (
        metric["approved_repair_strategy"]
        == "SCHEME_A_MARGINAL_TRUTH_TO_MARGINAL_METRIC"
    )
    assert metric["old_execution_status"] == "SUPERSEDED"
    assert set(metric["mainline_integration"]) == {
        "goal",
        "ready_condition",
        "runner",
        "upstream_artifacts",
        "downstream_artifacts",
        "status_projection",
        "downstream_consumer",
        "evidence_progress_rule",
        "decision_consumer",
    }


def test_measurement_repair_is_unique_ready_after_completed_preflight() -> None:
    payload = _payload()
    ready, states = _states(payload)
    assert ready == ["m4-p2-repair-measurement-system"]
    assert states[PREFLIGHT_TASK] == "completed"
    assert states["m4-p2-false-positive-and-power-runs"] == "dependency_wait"
    assert states["m4-p2-automatic-gate-and-report"] == "dependency_wait"
    assert states["m4-p2-repair-measurement-system"] == "ready"
    assert states["m4-p3-strict-historical-walk-forward"] == "dependency_wait"


def test_pass_fact_opens_only_p3_branch_after_p2_completion() -> None:
    payload = _payload()
    _set_task_complete(
        payload,
        "m4-p2-repair-measurement-system",
        "0" * 64,
    )
    payload["facts"]["artifacts"].append(
        "m4-p2-repaired-measurement-contract:AVAILABLE"
    )
    _set_task_complete(payload, "m4-p2-false-positive-and-power-runs", "1" * 64)
    _set_task_complete(payload, "m4-p2-automatic-gate-and-report", "2" * 64)
    payload["facts"]["artifacts"].append(PASS_FACT)
    umbrella = next(
        item
        for item in payload["tasks"]
        if item["task_key"] == "m4-p2-synthetic-measurement-validation"
    )
    umbrella["status"] = "completed"
    ready, states = _states(payload)
    assert states["m4-p3-strict-historical-walk-forward"] == "ready"
    assert states["m4-p2-repair-measurement-system"] == "completed"
    assert "m4-p3-strict-historical-walk-forward" in ready


def test_identifiability_repair_fact_opens_only_repair_and_keeps_p3_closed() -> None:
    payload = _payload()
    ready, states = _states(payload)
    assert ready == ["m4-p2-repair-measurement-system"]
    assert states["m4-p3-strict-historical-walk-forward"] == "dependency_wait"
    assert states["m4-p2-synthetic-measurement-validation"] == "dependency_wait"


def test_pass_and_repair_facts_cannot_coexist() -> None:
    payload = _payload()
    payload["facts"]["artifacts"].extend([PASS_FACT, REPAIR_FACT])
    with pytest.raises(
        ResearchOSValidationError,
        match="mutually exclusive",
    ):
        ControlPlaneManifest.from_dict(payload)


def test_identifiability_facts_cannot_coexist() -> None:
    payload = _payload()
    payload["facts"]["artifacts"].append(IDENTIFIABLE_FACT)
    with pytest.raises(
        ResearchOSValidationError,
        match="mutually exclusive",
    ):
        ControlPlaneManifest.from_dict(payload)


def test_contract_round_does_not_change_accepted_upstream_digests() -> None:
    payload = _contract()
    assert payload["upstream_identities"] == {
        "preregistration_digest": "4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9",
        "decision_policy_digest": "824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d",
        "synthetic_manifest_digest": "f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c",
        "metric_kernel_digest": "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2",
        "walk_forward_harness_digest": "177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca",
        "injected_signal_completion_digest": "328144fa1abebfee88d46dbbce6d9deb7b9f1f5834fb9a0c83cc55adef32a353",
        "resampling_kernel_digest": "1cde473524d7d6dcafba64ab7b0a1d2862b56149d5f6f198c73d88b406c3071b",
    }
