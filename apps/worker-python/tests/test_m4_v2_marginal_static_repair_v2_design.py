from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2 import (
    marginal_static_repair_v2_design as design_module,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_design import (
    J1_FIXTURE_ID,
    J1_NULL_FAMILY,
    M1_FIXTURE_ID,
    MARGINAL_STATIC_REPAIR_V2_DESIGN_CAPABILITY,
    MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_V2_DESIGN_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY,
    MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
    MarginalStaticRepairV2DesignError,
    calibration_null_family,
    independent_block_conformal_p_value,
    independent_block_conformal_reject,
    largest_passing_wilson_count,
    load_marginal_static_repair_v2_design_source_contract,
    presample_operating_characteristics,
    verify_marginal_static_repair_v2_design_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.progress import (
    M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_REPAIR_FACT,
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    M4MarginalStaticRepairV2DesignCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
SOURCE_PATH = ROOT / MARGINAL_STATIC_REPAIR_V2_DESIGN_SOURCE_CONTRACT_PATH


def _copy_source_tree(target_root: Path) -> dict:
    contract = load_marginal_static_repair_v2_design_source_contract(SOURCE_PATH)
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = (
        target_root / MARGINAL_STATIC_REPAIR_V2_DESIGN_SOURCE_CONTRACT_PATH
    )
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PATH, target_contract)
    return contract


def _task():
    manifest = load_m4_manifest(MANIFEST_PATH)
    return next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY
    )


def test_repair_v2_presample_proof_and_independent_blocks_are_frozen() -> None:
    proof = presample_operating_characteristics()
    assert largest_passing_wilson_count(256) == 14
    assert largest_passing_wilson_count(1024) == 74
    assert proof["old"][
        "six_independent_controls_all_pass_probability_at_p_0_05"
    ] == pytest.approx(0.11617520660518783)
    assert proof["repair_v2"]["six_control_union_bound"] < 0.005
    assert calibration_null_family(J1_FIXTURE_ID) == J1_NULL_FAMILY
    assert calibration_null_family(M1_FIXTURE_ID) == "IID_UNIFORM"
    references = [0.0] * 19
    assert independent_block_conformal_p_value(references, 1.0) == 0.05
    assert independent_block_conformal_reject(references, 1.0) is True
    assert independent_block_conformal_reject([1.0] * 19, 1.0) is False


def test_repair_v2_source_detects_byte_and_contract_tamper(tmp_path: Path) -> None:
    contract = _copy_source_tree(tmp_path)
    verify_marginal_static_repair_v2_design_source_bytes(
        root_dir=tmp_path,
        contract=contract,
    )
    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(MarginalStaticRepairV2DesignError, match="source_modified"):
        verify_marginal_static_repair_v2_design_source_bytes(
            root_dir=tmp_path,
            contract=contract,
        )

    drifted = deepcopy(contract)
    drifted["frozen_contract"]["future_workload"]["duplicate_validation"] = True
    drifted["artifact_digest"] = "0" * 64
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(MarginalStaticRepairV2DesignError, match="source_invalid"):
        load_marginal_static_repair_v2_design_source_contract(drift_path)


def test_repair_v2_capability_is_zero_work_and_never_duplicates_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_tree(tmp_path)
    task = _task()
    decision_execution = {
        "execution_id": design_module.REPAIR_HEALTH_DECISION_EXECUTION_ID,
        "artifact_digest": task.input_artifact_digests[1],
    }
    decision = {
        "artifact_type": "m4_v2_marginal_static_measurement_repair_health_decision",
        "artifact_digest": task.input_artifact_digests[2],
        "failed_control_cell_ids": list(design_module.EXPECTED_FAILED_CONTROL_CELL_IDS),
        "failed_control_cell_count": 3,
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, decision_execution, "decision-registrations"),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **_: decision,
    )
    monkeypatch.setattr(design_module, "_validate_parent_decision", lambda **_: None)
    monkeypatch.setattr(
        supervisor_module,
        "build_marginal_static_repair_v2_design_artifacts",
        design_module.build_marginal_static_repair_v2_design_artifacts,
    )
    result = M4MarginalStaticRepairV2DesignCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )

    assert result.completion_facts == (
        MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_FACT,
    )
    assert len(result.registrations) == 4
    execution = result.execution_artifact
    assert execution["formal_replicates_executed"] == 0
    assert execution["generated_issues"] == 0
    assert execution["checkpoint_reads"] == 0
    assert execution["raw_replicates_regenerated"] == 0
    assert execution["sentinel_replicates_recomputed"] == 0
    assert execution["duplicate_validation"] is False
    assert execution["future_total_replicates"] == 131072
    assert execution["future_generated_issues"] == 291110912
    assert execution["downstream_consumer"] == (
        MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
    )


def test_additive_repair_v2_design_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    normalized = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live = deepcopy(normalized)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
    ]
    live_design = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY
    )
    live_design.pop("requested_capability")
    live_design.pop("input_artifact_digests")
    live_design["dependencies"] = live_design["dependencies"][:2]
    source_fact = next(
        fact
        for fact in live["facts"]["artifacts"]
        if fact.startswith("m4-v2-marginal-static-repair-v2-design-source:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=normalized,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,),
        allowlisted_revised_task_keys=(MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )

    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY]
    assert dry_run["existing_task_deletions"] == 0
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_repair_v2_design_projects_preregistration_as_next() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    design_task = next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY
    )
    for task in payload["tasks"]:
        if task["task_key"] == MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            M4_V2_MARGINAL_REPAIR_HEALTH_DECISION_REPAIR_FACT,
            MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_FACT,
            mainline_completion_fact(task=design_task, execution_id="e" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY,
            "execution_artifact_digest": "f" * 64,
            "registered_artifact_count": 4,
            "actual_fold_count": 0,
            "measurement_health": "REPAIR",
            "decision": "REPAIR_MEASUREMENT_SYSTEM",
            "failed_control_cell_ids": ["a", "b", "c"],
            "failed_control_cell_count": 3,
            "presample_feasibility_digest": "1" * 64,
            "repair_v2_design_digest": "2" * 64,
            "repair_v2_design_completion_digest": "3" * 64,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_REPAIR_V2_DESIGN_VALIDATED_IN_MAINLINE"
    )
    design = projection["marginal_static_repair_v2_design"]
    assert design["completed"] is True
    assert design["formal_replicates_executed"] == 0
    assert design["duplicate_validation"] is False
    assert design["next_consumer"] == MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY


def test_supervisor_registers_repair_v2_design_capability() -> None:
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert MARGINAL_STATIC_REPAIR_V2_DESIGN_CAPABILITY in supervisor.capabilities
