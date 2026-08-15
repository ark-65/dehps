from __future__ import annotations

import json
import math
import shutil
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_preregistration import (
    CALIBRATION_REPLICATES,
    CALIBRATION_REPLICATES_PER_SCALE,
    EVALUATION_REPLICATES,
    EVALUATION_REPLICATES_PER_CELL,
    EXECUTION_SHARDS,
    MARGINAL_STATIC_REPAIR_ANALYTIC_FEASIBILITY_DIGEST,
    MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_DIGEST,
    MARGINAL_STATIC_REPAIR_DESIGN_DIGEST,
    MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_DIGEST,
    MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_ID,
    MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
    MAX_REJECTING_EXCEEDANCE_COUNT,
    OLD_ROUND_42_REPLICATES,
    TOTAL_GENERATED_ISSUES,
    TOTAL_OUTER_EVALUATION_ISSUES,
    TOTAL_REPLICATES,
    MarginalStaticRepairPreregistrationError,
    build_marginal_static_repair_preregistration_artifacts,
    load_marginal_static_repair_preregistration_source_contract,
    mean_student_t_interval,
    repair_health_child_identity,
    split_conformal_p_value,
    split_conformal_reject,
    verify_marginal_static_repair_preregistration_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    M4MarginalStaticRepairPreregistrationCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
INDEX_PATH = ROOT / "configs/research-os/m4-information-theory-artifact-index-v1.json"
SOURCE_PATH = ROOT / MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE_CONTRACT_PATH
REPAIR_DESIGN_TASK_KEY = "m4-v2-marginal-static-measurement-repair-design"
REPAIR_DESIGN_COMPLETION_FACT = "m4-v2-marginal-static-measurement-repair-design:FROZEN"


def _copy_source_tree(target_root: Path) -> dict:
    contract = load_marginal_static_repair_preregistration_source_contract(SOURCE_PATH)
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = (
        target_root / MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PATH, target_contract)
    return contract


def _task():
    manifest = load_m4_manifest(MANIFEST_PATH)
    return next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
    )


def _parents() -> tuple[dict, dict, dict, dict]:
    execution = {
        "execution_id": MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_ID,
        "artifact_digest": MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_DIGEST,
        "task_key": REPAIR_DESIGN_TASK_KEY,
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
        "decision": "REPAIR_MEASUREMENT_SYSTEM",
        "decision_fact": ("m4-v2-marginal-static-measurement-health-decision:REPAIR"),
        "failed_cell_ids": [
            "BASE:V2_M1_GROUP_ODDS_2_STATIONARY:FORWARD_61",
            "LOCAL_M1:0.010:FORWARD_61",
            "LOCAL_M1:0.010:HISTORICAL_2581",
            "LOCAL_M1:0.050:FORWARD_61",
        ],
        "failed_cell_count": 4,
        "duplicate_validation": False,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "promotion_gate_opened": False,
    }
    feasibility = {
        "artifact_type": "m4_v2_marginal_static_repair_analytic_feasibility",
        "artifact_digest": MARGINAL_STATIC_REPAIR_ANALYTIC_FEASIBILITY_DIGEST,
        "duplicate_validation": False,
    }
    design = {
        "artifact_type": "m4_v2_marginal_static_measurement_repair_design",
        "artifact_digest": MARGINAL_STATIC_REPAIR_DESIGN_DIGEST,
        "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
        "automatic_pass_from_reanalysis": False,
        "duplicate_validation": False,
    }
    completion = {
        "artifact_type": "m4_v2_marginal_static_repair_design_completion",
        "artifact_digest": MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_DIGEST,
        "completion_fact": REPAIR_DESIGN_COMPLETION_FACT,
        "duplicate_validation": False,
    }
    return execution, feasibility, design, completion


def test_source_contract_workload_and_zero_duplicate_validation_are_frozen(
    tmp_path: Path,
) -> None:
    contract = _copy_source_tree(tmp_path)
    verify_marginal_static_repair_preregistration_source_bytes(
        root_dir=tmp_path,
        contract=contract,
    )
    frozen = contract["frozen_contract"]
    workload = frozen["workload"]
    assert workload["calibration_replicates"] == 2 * 512 == CALIBRATION_REPLICATES
    assert workload["evaluation_replicates"] == 2 * 7 * 256 == (EVALUATION_REPLICATES)
    assert workload["total_replicates"] == TOTAL_REPLICATES == 4608
    assert workload["execution_shards"] == EXECUTION_SHARDS == 72
    assert workload["total_generated_issues_if_executed"] == (TOTAL_GENERATED_ISSUES)
    assert workload["total_outer_evaluation_issues_if_executed"] == (
        TOTAL_OUTER_EVALUATION_ISSUES
    )
    assert workload["replicate_reduction_fraction"] == pytest.approx(
        (OLD_ROUND_42_REPLICATES - TOTAL_REPLICATES) / OLD_ROUND_42_REPLICATES
    )
    assert workload["nested_bootstrap_replicates_per_formal_replicate"] == 0
    assert workload["duplicate_validation"] is False

    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(
        MarginalStaticRepairPreregistrationError,
        match="source_modified",
    ):
        verify_marginal_static_repair_preregistration_source_bytes(
            root_dir=tmp_path,
            contract=contract,
        )


def test_split_conformal_boundary_ties_and_nonfinite_values_fail_closed() -> None:
    calibration = [0.0] * CALIBRATION_REPLICATES_PER_SCALE
    calibration[:MAX_REJECTING_EXCEEDANCE_COUNT] = [2.0] * (
        MAX_REJECTING_EXCEEDANCE_COUNT
    )
    assert split_conformal_p_value(calibration, 1.0) == 25 / 513
    assert split_conformal_reject(calibration, 1.0) is True

    calibration[MAX_REJECTING_EXCEEDANCE_COUNT] = 1.0
    assert split_conformal_p_value(calibration, 1.0) == 26 / 513
    assert split_conformal_reject(calibration, 1.0) is False

    with pytest.raises(
        MarginalStaticRepairPreregistrationError,
        match="score_non_finite",
    ):
        split_conformal_reject(calibration, math.nan)


def test_student_t_interval_uses_exact_independent_replicate_count() -> None:
    zero = [0.25] * EVALUATION_REPLICATES_PER_CELL
    assert mean_student_t_interval(zero) == (0.25, 0.25)
    values = [float(index) for index in range(EVALUATION_REPLICATES_PER_CELL)]
    lower, upper = mean_student_t_interval(values)
    assert lower < 127.5 < upper
    with pytest.raises(
        MarginalStaticRepairPreregistrationError,
        match="interval_count_invalid",
    ):
        mean_student_t_interval(values[:-1])
    values[-1] = math.inf
    with pytest.raises(
        MarginalStaticRepairPreregistrationError,
        match="interval_non_finite",
    ):
        mean_student_t_interval(values)


def test_seed_child_identities_are_disjoint_and_worker_independent() -> None:
    preregistration_digest = "a" * 64
    calibration = {
        repair_health_child_identity(
            preregistration_digest=preregistration_digest,
            lane="calibration",
            cell_id="NULL_UNIFORM_LEGAL_SIX_OF_33",
            scale_id=scale,
            replicate_index=index,
        )
        for scale in ("FORWARD_61", "HISTORICAL_2581")
        for index in range(CALIBRATION_REPLICATES_PER_SCALE)
    }
    evaluation = {
        repair_health_child_identity(
            preregistration_digest=preregistration_digest,
            lane="evaluation",
            cell_id=cell,
            scale_id=scale,
            replicate_index=index,
        )
        for cell in ("NULL_UNIFORM_LEGAL_SIX_OF_33", "LOCAL_M1:0.010")
        for scale in ("FORWARD_61", "HISTORICAL_2581")
        for index in range(EVALUATION_REPLICATES_PER_CELL)
    }
    assert len(calibration) == CALIBRATION_REPLICATES
    assert len(evaluation) == 2 * 2 * EVALUATION_REPLICATES_PER_CELL
    assert calibration.isdisjoint(evaluation)


def test_preregistration_artifacts_preserve_repair_and_do_zero_work() -> None:
    contract = load_marginal_static_repair_preregistration_source_contract(SOURCE_PATH)
    execution, feasibility, design, completion = _parents()
    run = build_marginal_static_repair_preregistration_artifacts(
        source_contract=contract,
        repair_design_execution=execution,
        analytic_feasibility=feasibility,
        repair_design=design,
        repair_design_completion=completion,
        execution_id="b" * 64,
        git_commit="c" * 40,
    )
    assert run.preregistration["old_decision_preserved"] == (
        "REPAIR_MEASUREMENT_SYSTEM"
    )
    assert run.preregistration["formal_execution_authorized"] is False
    assert run.preregistration["automatic_pass_from_preregistration"] is False
    assert run.preregistration["next_consumer"] == (
        MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
    )
    for artifact in run.artifacts:
        assert artifact["generated_issues"] == 0
        assert artifact["duplicate_validation"] is False
        assert artifact["historical_outcomes_read"] is False
        assert artifact["evidence_created"] is False
        assert artifact["production_action"] == "none"


def test_capability_and_replay_reconstruct_preregistration_without_samples(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_tree(tmp_path)
    task = _task()
    execution, feasibility, design, completion = _parents()
    parent_by_type = {
        feasibility["artifact_type"]: feasibility,
        design["artifact_type"]: design,
        completion["artifact_type"]: completion,
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, execution, "repair-registrations"),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **kwargs: parent_by_type[kwargs["artifact_type"]],
    )
    result = M4MarginalStaticRepairPreregistrationCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="d" * 64,
        git_commit="e" * 40,
    )
    assert result.completion_facts == (
        MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT,
    )
    assert len(result.registrations) == 5
    mainline = result.execution_artifact
    assert mainline["registered_artifact_count"] == 5
    assert mainline["planned_total_replicates"] == TOTAL_REPLICATES
    assert mainline["generated_issues"] == 0
    assert mainline["bootstrap_replicates_executed"] == 0
    assert mainline["checkpoint_reads"] == 0
    assert mainline["duplicate_validation"] is False
    assert mainline["formal_execution_authorized"] is False
    assert mainline["decision"] == "REPAIR_MEASUREMENT_SYSTEM"
    assert mainline["decision_fact"] == (
        "m4-v2-marginal-static-measurement-health-decision:REPAIR"
    )
    assert mainline["failed_cell_count"] == 4
    assert mainline["repair_required"] is True
    assert mainline["downstream_consumer"] == (
        MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
    )

    registered_by_type = {
        item.artifact_type: json.loads(
            (tmp_path / item.artifact_path).read_text(encoding="utf-8")
        )
        for item in result.registrations
        if item.artifact_type != "research_os_mainline_execution"
    }

    def load_registered(**kwargs):
        artifact_type = kwargs["artifact_type"]
        if artifact_type in registered_by_type:
            return registered_by_type[artifact_type]
        return parent_by_type[artifact_type]

    monkeypatch.setattr(supervisor_module, "_load_registered_type", load_registered)

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "d" * 64,
                    "payload": [
                        [
                            "execution_artifact_path",
                            result.execution_artifact_path.relative_to(
                                tmp_path
                            ).as_posix(),
                        ],
                        ["registered_artifact_count", 5],
                    ],
                }
            ]

        def list_mainline_artifacts(self, **_: object) -> list[dict]:
            return [asdict(item) for item in result.registrations]

    replay = ResearchEvidenceSupervisor(
        repository=ReplayRepository(),
        root_dir=tmp_path,
        require_clean_tree=False,
    ).replay(
        task_key=MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
        execution_id="d" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["preregistration_only"] is True
    assert capability_replay["formal_replicates_executed"] == 0
    assert capability_replay["generated_issues_during_replay"] == 0
    assert capability_replay["duplicate_validation"] is False


def test_additive_preregistration_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    normalized = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live = deepcopy(normalized)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
    ]
    live_preregistration = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
    )
    live_preregistration.pop("requested_capability")
    live_preregistration.pop("input_artifact_digests")
    live_preregistration["dependencies"] = live_preregistration["dependencies"][:2]
    source_fact = next(
        fact
        for fact in live["facts"]["artifacts"]
        if fact.startswith("m4-v2-marginal-static-repair-preregistration-source:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=normalized,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,),
        allowlisted_revised_task_keys=(
            MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_completed_preregistration_projects_only_repair_health_ready() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    design_task = next(
        task for task in manifest.tasks if task.task_key == REPAIR_DESIGN_TASK_KEY
    )
    preregistration_task = next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
    )
    for task in payload["tasks"]:
        if task["task_key"] in {
            REPAIR_DESIGN_TASK_KEY,
            MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
        }:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            REPAIR_DESIGN_COMPLETION_FACT,
            MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT,
            mainline_completion_fact(task=design_task, execution_id="f" * 64),
            mainline_completion_fact(
                task=preregistration_task,
                execution_id="1" * 64,
            ),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
            "execution_artifact_digest": "2" * 64,
            "registered_artifact_count": 5,
            "actual_fold_count": 0,
            "measurement_health": "REPAIR",
            "decision": "REPAIR_MEASUREMENT_SYSTEM",
            "decision_fact": (
                "m4-v2-marginal-static-measurement-health-decision:REPAIR"
            ),
            "failed_cell_ids": [
                "BASE:V2_M1_GROUP_ODDS_2_STATIONARY:FORWARD_61",
                "LOCAL_M1:0.010:FORWARD_61",
                "LOCAL_M1:0.010:HISTORICAL_2581",
                "LOCAL_M1:0.050:FORWARD_61",
            ],
            "failed_cell_count": 4,
            "marginal_static_repair_analytic_feasibility_digest": "3" * 64,
            "marginal_static_repair_design_artifact_digest": "4" * 64,
            "marginal_static_repair_design_completion_digest": "5" * 64,
            "planned_calibration_replicates": CALIBRATION_REPLICATES,
            "planned_evaluation_replicates": EVALUATION_REPLICATES,
            "planned_total_replicates": TOTAL_REPLICATES,
            "planned_total_generated_issues": TOTAL_GENERATED_ISSUES,
            "marginal_static_repair_health_workload_seed_digest": "6" * 64,
            "marginal_static_repair_health_inference_gate_digest": "7" * 64,
            "marginal_static_repair_health_preregistration_digest": "8" * 64,
            "marginal_static_repair_health_preregistration_completion_digest": (
                "9" * 64
            ),
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_REPAIR_PREREGISTRATION_VALIDATED_IN_MAINLINE"
    )
    preregistration = projection["marginal_static_repair_preregistration"]
    assert preregistration["completed"] is True
    assert preregistration["planned_total_replicates"] == TOTAL_REPLICATES
    assert preregistration["generated_issues"] == 0
    assert preregistration["duplicate_validation"] is False
    decision = projection["marginal_static_health_decision"]
    assert decision["measurement_health"] == "REPAIR"
    assert decision["decision"] == "REPAIR_MEASUREMENT_SYSTEM"
    assert decision["decision_fact"] == (
        "m4-v2-marginal-static-measurement-health-decision:REPAIR"
    )
    assert decision["failed_cell_count"] == 4
    health = projection["marginal_static_repair_health_execution"]
    assert health["resolver_status"] == "ready"
    assert projection["next_consumer"] == (
        MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
    )


def test_artifact_index_and_supervisor_register_preregistration() -> None:
    contract = load_marginal_static_repair_preregistration_source_contract(SOURCE_PATH)
    manifest = load_m4_manifest(MANIFEST_PATH)
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[contract["artifact_digest"]]["path"] == (
        MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE_CONTRACT_PATH.as_posix()
    )
    assert index[manifest.artifact_digest]["identity_field"] == "manifest_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert MARGINAL_STATIC_REPAIR_PREREGISTRATION_CAPABILITY in (
        supervisor.capabilities
    )
