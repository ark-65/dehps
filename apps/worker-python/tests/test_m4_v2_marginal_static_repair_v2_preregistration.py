from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2 import (
    marginal_static_repair_v2_preregistration as prereg_module,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_preregistration import (
    EVALUATION_CELLS,
    EVALUATION_CHILDREN,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
    MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
    NULL_FAMILIES,
    REFERENCE_CHILDREN,
    SCALES,
    TOTAL_CHILDREN,
    MarginalStaticRepairV2PreregistrationError,
    evaluation_child_identity,
    load_marginal_static_repair_v2_preregistration_source_contract,
    reference_child_identity,
    verify_marginal_static_repair_v2_preregistration_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.progress import (
    M4_V2_MARGINAL_REPAIR_V2_DESIGN_COMPLETION_FACT,
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    M4MarginalStaticRepairV2PreregistrationCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
SOURCE_PATH = ROOT / MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_SOURCE_CONTRACT_PATH


def _copy_source_tree(target_root: Path) -> dict:
    contract = load_marginal_static_repair_v2_preregistration_source_contract(
        SOURCE_PATH
    )
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = (
        target_root / MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PATH, target_contract)
    return contract


def _task():
    manifest = load_m4_manifest(MANIFEST_PATH)
    return next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
    )


def test_repair_v2_child_identity_and_workload_are_layout_independent() -> None:
    preregistration_digest = "a" * 64
    reference = reference_child_identity(
        preregistration_digest=preregistration_digest,
        null_family=NULL_FAMILIES[0],
        scale_id=SCALES[0],
        evaluation_index=0,
        reference_index=0,
    )
    assert reference == reference_child_identity(
        preregistration_digest=preregistration_digest,
        null_family=NULL_FAMILIES[0],
        scale_id=SCALES[0],
        evaluation_index=0,
        reference_index=0,
    )
    assert reference != reference_child_identity(
        preregistration_digest=preregistration_digest,
        null_family=NULL_FAMILIES[0],
        scale_id=SCALES[0],
        evaluation_index=0,
        reference_index=1,
    )
    evaluation = evaluation_child_identity(
        preregistration_digest=preregistration_digest,
        cell_id=EVALUATION_CELLS[0],
        scale_id=SCALES[0],
        evaluation_index=0,
    )
    assert evaluation != reference
    assert REFERENCE_CHILDREN == 3 * 2 * 1024 * 19
    assert EVALUATION_CHILDREN == 7 * 2 * 1024
    assert TOTAL_CHILDREN == REFERENCE_CHILDREN + EVALUATION_CHILDREN == 131072
    with pytest.raises(MarginalStaticRepairV2PreregistrationError):
        reference_child_identity(
            preregistration_digest=preregistration_digest,
            null_family=NULL_FAMILIES[0],
            scale_id=SCALES[0],
            evaluation_index=1024,
            reference_index=0,
        )


def test_repair_v2_preregistration_detects_source_and_contract_tamper(
    tmp_path: Path,
) -> None:
    contract = _copy_source_tree(tmp_path)
    verify_marginal_static_repair_v2_preregistration_source_bytes(
        root_dir=tmp_path,
        contract=contract,
    )
    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(
        MarginalStaticRepairV2PreregistrationError, match="source_modified"
    ):
        verify_marginal_static_repair_v2_preregistration_source_bytes(
            root_dir=tmp_path,
            contract=contract,
        )

    drifted = deepcopy(contract)
    drifted["frozen_contract"]["resume_and_uniqueness"]["duplicate_validation"] = True
    drifted["artifact_digest"] = "0" * 64
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(
        MarginalStaticRepairV2PreregistrationError, match="source_invalid"
    ):
        load_marginal_static_repair_v2_preregistration_source_contract(drift_path)


def test_repair_v2_preregistration_capability_is_zero_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_tree(tmp_path)
    task = _task()
    design_execution = {
        "execution_id": prereg_module.MARGINAL_STATIC_REPAIR_V2_DESIGN_EXECUTION_ID,
        "artifact_digest": task.input_artifact_digests[1],
    }
    parents = {
        "m4_v2_marginal_static_repair_v2_presample_feasibility": {
            "artifact_type": ("m4_v2_marginal_static_repair_v2_presample_feasibility"),
            "artifact_digest": task.input_artifact_digests[2],
        },
        "m4_v2_marginal_static_measurement_repair_v2_design": {
            "artifact_type": "m4_v2_marginal_static_measurement_repair_v2_design",
            "artifact_digest": task.input_artifact_digests[3],
        },
        "m4_v2_marginal_static_repair_v2_design_completion": {
            "artifact_type": "m4_v2_marginal_static_repair_v2_design_completion",
            "artifact_digest": task.input_artifact_digests[4],
        },
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, design_execution, "design-registrations"),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **kwargs: parents[kwargs["artifact_type"]],
    )
    monkeypatch.setattr(prereg_module, "_validate_design_lineage", lambda **_: None)
    monkeypatch.setattr(
        supervisor_module,
        "build_marginal_static_repair_v2_preregistration_artifacts",
        prereg_module.build_marginal_static_repair_v2_preregistration_artifacts,
    )
    result = M4MarginalStaticRepairV2PreregistrationCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )
    execution = result.execution_artifact
    assert result.completion_facts == (
        MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_COMPLETION_FACT,
    )
    assert len(result.registrations) == 5
    assert execution["formal_replicates_executed"] == 0
    assert execution["generated_issues"] == 0
    assert execution["compact_index_reads"] == 0
    assert execution["raw_replicates_regenerated"] == 0
    assert execution["sentinel_replicates_recomputed"] == 0
    assert execution["duplicate_validation"] is False
    assert execution["future_total_children"] == 131072
    assert execution["future_completion_index_loads"] == 1
    assert execution["completed_matching_child_action"] == (
        "skip_without_generation_or_revalidation"
    )
    assert execution["downstream_consumer"] == (
        MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
    )


def test_additive_repair_v2_preregistration_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest", None)
    normalized = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live = deepcopy(normalized)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
    ]
    live_preregistration = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
    )
    live_preregistration.pop("requested_capability")
    live_preregistration.pop("input_artifact_digests")
    live_preregistration["dependencies"] = live_preregistration["dependencies"][:2]
    live_preregistration["metric_contract"] = {
        **live_preregistration["metric_contract"],
        "engineering_complete": False,
        "engineering_increment_percent": 0,
    }
    for key in (
        "planned_reference_children",
        "planned_evaluation_children",
        "planned_total_children",
        "planned_execution_shards",
        "planned_shard_size",
        "planned_generated_issues",
        "planned_outer_evaluation_issues",
        "future_completion_index_loads",
        "completed_matching_child_action",
        "new_child_dispatch",
        "raw_replay",
        "sentinel_replay",
    ):
        live_preregistration["metric_contract"].pop(key, None)
    source_fact = next(
        fact
        for fact in live["facts"]["artifacts"]
        if fact.startswith("m4-v2-marginal-static-repair-v2-preregistration-source:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=normalized,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_repair_v2_preregistration_projects_health_execution_as_next() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
    )
    for item in payload["tasks"]:
        if item["task_key"] == MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            M4_V2_MARGINAL_REPAIR_V2_DESIGN_COMPLETION_FACT,
            MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_COMPLETION_FACT,
            mainline_completion_fact(task=task, execution_id="e" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
            "execution_artifact_digest": "f" * 64,
            "registered_artifact_count": 5,
            "actual_fold_count": 0,
            "repair_v2_workload_seed_digest": "1" * 64,
            "repair_v2_inference_gate_digest": "2" * 64,
            "repair_v2_preregistration_digest": "3" * 64,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_VALIDATED_IN_MAINLINE"
    )
    preregistration = projection["marginal_static_repair_v2_preregistration"]
    assert preregistration["completed"] is True
    assert preregistration["duplicate_validation"] is False
    assert preregistration["next_consumer"] == (
        MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
    )


def test_supervisor_registers_repair_v2_preregistration_capability() -> None:
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert (
        MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_CAPABILITY in supervisor.capabilities
    )
