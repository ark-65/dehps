from __future__ import annotations

import json
import shutil
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest
from dehps.contracts import canonical_digest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_execution import (
    ReplicateSpec as Round42ReplicateSpec,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_health_execution import (
    CALIBRATION_REPLICATES_PER_SCALE,
    EVALUATION_REPLICATES_PER_CELL,
    EXPECTED_FEASIBILITY,
    IDENTITY_ABSOLUTE_ERROR_MAX,
    INFERENCE_GATE_DIGEST,
    MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY,
    MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
    MAX_REJECTING_EXCEEDANCE_COUNT,
    PREREGISTRATION_COMPLETION_DIGEST,
    PREREGISTRATION_DIGEST,
    PREREGISTRATION_EXECUTION_DIGEST,
    PREREGISTRATION_EXECUTION_ID,
    STUDENT_T_CRITICAL,
    TOTAL_GENERATED_ISSUES,
    TOTAL_OUTER_EVALUATION_ISSUES,
    TOTAL_REPLICATES,
    WILSON_Z,
    WORKLOAD_SEED_DIGEST,
    MarginalStaticRepairHealthExecutionError,
    RepairHealthExecutionRun,
    _persist_summary_and_build_entry,
    append_repair_health_completion_entries,
    build_pre_sample_feasibility_artifact,
    build_repair_health_completion,
    build_repair_health_completion_index_artifact,
    build_repair_health_replicate_specs,
    build_repair_health_result,
    conformal_exceedance_count,
    load_marginal_static_repair_health_execution_source_contract,
    load_repair_health_completion_index,
    run_repair_health_replicate,
    student_t_interval,
    verify_marginal_static_repair_health_execution_source_bytes,
    wilson_interval,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_preregistration import (
    MARGINAL_STATIC_REPAIR_ANALYTIC_FEASIBILITY_DIGEST,
    MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_DIGEST,
    MARGINAL_STATIC_REPAIR_DESIGN_DIGEST,
    MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_DIGEST,
    MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_ID,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    build_marginal_static_repair_preregistration_artifacts,
    load_marginal_static_repair_preregistration_source_contract,
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
    M4MarginalStaticRepairHealthExecutionCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
INDEX_PATH = ROOT / "configs/research-os/m4-information-theory-artifact-index-v1.json"
SOURCE_PATH = ROOT / MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
PREREG_SOURCE_PATH = (
    ROOT / MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE_CONTRACT_PATH
)
ROUND42_SOURCE_DIGEST = (
    "5fbeb6ab0533478ac097747ab73fb0188561849505a76cf7a63a3a02061b2354"
)


def _copy_source_tree(target_root: Path) -> dict:
    contract = load_marginal_static_repair_health_execution_source_contract(
        SOURCE_PATH
    )
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = (
        target_root / MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
    )
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PATH, target_contract)
    return contract


def _preregistration_artifacts():
    contract = load_marginal_static_repair_preregistration_source_contract(
        PREREG_SOURCE_PATH
    )
    execution = {
        "execution_id": MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_ID,
        "artifact_digest": MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_DIGEST,
        "task_key": "m4-v2-marginal-static-measurement-repair-design",
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
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
        "completion_fact": "m4-v2-marginal-static-measurement-repair-design:FROZEN",
        "duplicate_validation": False,
    }
    return build_marginal_static_repair_preregistration_artifacts(
        source_contract=contract,
        repair_design_execution=execution,
        analytic_feasibility=feasibility,
        repair_design=design,
        repair_design_completion=completion,
        execution_id=PREREGISTRATION_EXECUTION_ID,
        git_commit="abbec115ef964d23e47a415f9bfd85ad0841e7db",
    )


def _parents():
    prereg = _preregistration_artifacts()
    execution = {
        "execution_id": PREREGISTRATION_EXECUTION_ID,
        "artifact_digest": PREREGISTRATION_EXECUTION_DIGEST,
        "task_key": "m4-v2-marginal-static-measurement-repair-preregistration",
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "completion_fact": MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT,
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
        "generated_issues": 0,
        "synthetic_replicates": 0,
        "formal_execution_authorized": False,
        "duplicate_validation": False,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "promotion_gate_opened": False,
    }
    return (
        execution,
        prereg.workload_and_seeds,
        prereg.inference_and_gates,
        prereg.preregistration,
        prereg.completion,
    )


def _synthetic_summary(spec, score: float) -> dict:
    truth = 0.1 if spec.cell.role in {"POSITIVE_CONTROL", "LOCAL_POWER"} else 0.0
    payload = {
        "schema_version": (
            "dehps-m4-v2-marginal-static-repair-health-replicate.v1"
        ),
        "artifact_type": (
            "m4_v2_marginal_static_repair_health_replicate_summary"
        ),
        "artifact_digest": "",
        "replicate_digest": spec.replicate_digest,
        "child_seed_digest": spec.child_seed_digest,
        "lane": spec.lane,
        "cell": asdict(spec.cell),
        "replicate_index": spec.replicate_index,
        "sequence_issues": spec.cell.sequence_issues,
        "evaluation_issues": spec.cell.evaluation_issues,
        "observed_endpoint_bits_per_issue": score,
        "conditional_truth_bits_per_issue": truth,
        "score_residual_bits_per_issue": score - truth,
        "score_residual_rmse_bits_per_issue": abs(score - truth),
        "conditional_identity_max_abs_error": 0.0,
        "legal_draw_count": spec.cell.sequence_issues,
        "illegal_draw_count": 0,
        "probability_sum_max_abs_error": 0.0,
        "nested_bootstrap_replicates": 0,
        "database_reads_during_replicate": 0,
        "database_writes_during_replicate": 0,
        "csv_materialized": False,
        "historical_outcomes_read": False,
        "round_42_statistical_results_read": False,
        "raw_draws_retained": False,
        "numpy_version": np.__version__,
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain=(
            "dehps.m4.v2.marginal-static-repair-health-replicate-summary.v1"
        ),
    )
    return payload


def _task():
    manifest = load_m4_manifest(MANIFEST_PATH)
    return next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
    )


def _synthetic_formal_run(
    *,
    root_dir: Path,
    execution_id: str,
    git_commit: str,
) -> RepairHealthExecutionRun:
    task = _task()
    contract = load_marginal_static_repair_health_execution_source_contract(
        SOURCE_PATH
    )
    _, workload, _, _, _ = _parents()
    specs = build_repair_health_replicate_specs(
        workload_artifact=workload,
        preregistration_digest=PREREGISTRATION_DIGEST,
    )
    checkpoint = (
        root_dir
        / "runtime/research-os/mainline/tasks"
        / task.task_key
        / execution_id
        / "checkpoints"
    )
    entries = []
    for spec in specs:
        if spec.lane == "CALIBRATION":
            score = float(spec.replicate_index) / 10_000.0
        elif spec.cell.role == "NEGATIVE_CONTROL":
            score = -1.0
        else:
            score = 1.0
        summary = _synthetic_summary(spec, score)
        entries.append(
            _persist_summary_and_build_entry(
                checkpoint_root=checkpoint,
                context_digest="c" * 64,
                spec=spec,
                summary=summary,
            )
        )
    index_path = checkpoint / "completion-index.jsonl"
    append_repair_health_completion_entries(index_path, entries)
    feasibility = build_pre_sample_feasibility_artifact(
        source_contract=contract,
        preregistration_digest=PREREGISTRATION_DIGEST,
        parent_digests=task.input_artifact_digests,
    )
    index = build_repair_health_completion_index_artifact(
        entries=entries,
        context_digest="c" * 64,
        index_path=index_path,
        root_dir=root_dir,
        parent_digests=(*task.input_artifact_digests, feasibility["artifact_digest"]),
    )
    health = build_repair_health_result(
        summaries=tuple(entry["summary"] for entry in entries),
        feasibility_artifact=feasibility,
        index_digest=index["artifact_digest"],
        workload_digest=WORKLOAD_SEED_DIGEST,
        inference_digest=INFERENCE_GATE_DIGEST,
        preregistration_digest=PREREGISTRATION_DIGEST,
        parent_digests=task.input_artifact_digests,
    )
    completion = build_repair_health_completion(
        health_result=health,
        index_artifact=index,
        feasibility_artifact=feasibility,
        execution_id=execution_id,
        git_commit=git_commit,
        parent_digests=task.input_artifact_digests,
    )
    return RepairHealthExecutionRun(
        index_artifact=index,
        feasibility_artifact=feasibility,
        health_result=health,
        completion=completion,
        runtime_seconds=1.25,
        completed_before_run=0,
        completed_during_run=TOTAL_REPLICATES,
        worker_count=4,
    )


def test_source_contract_and_exact_workload_are_frozen(tmp_path: Path) -> None:
    contract = _copy_source_tree(tmp_path)
    verify_marginal_static_repair_health_execution_source_bytes(
        root_dir=tmp_path,
        contract=contract,
    )
    frozen = contract["frozen_contract"]
    assert frozen["task_key"] == MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
    assert frozen["capability"] == MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_CAPABILITY
    assert frozen["completion_fact"] == (
        MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT
    )
    assert frozen["next_consumer"] == MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY
    assert frozen["total_replicates"] == TOTAL_REPLICATES == 4608
    assert frozen["total_generated_issues"] == TOTAL_GENERATED_ISSUES
    assert frozen["total_outer_evaluation_issues"] == (
        TOTAL_OUTER_EVALUATION_ISSUES
    )
    assert frozen["nested_bootstrap_replicates"] == 0
    assert frozen["duplicate_validation"] is False

    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(
        MarginalStaticRepairHealthExecutionError,
        match="source_modified",
    ):
        verify_marginal_static_repair_health_execution_source_bytes(
            root_dir=tmp_path,
            contract=contract,
        )


def test_specs_are_complete_lane_disjoint_and_round42_disjoint() -> None:
    _, workload, _, preregistration, _ = _parents()
    assert workload["artifact_digest"] == WORKLOAD_SEED_DIGEST
    assert preregistration["artifact_digest"] == PREREGISTRATION_DIGEST
    specs = build_repair_health_replicate_specs(
        workload_artifact=workload,
        preregistration_digest=PREREGISTRATION_DIGEST,
    )
    calibration = {spec.child_seed_digest for spec in specs if spec.lane == "CALIBRATION"}
    evaluation = {spec.child_seed_digest for spec in specs if spec.lane == "EVALUATION"}
    assert len(calibration) == 1024
    assert len(evaluation) == 3584
    assert calibration.isdisjoint(evaluation)

    round42 = {
        Round42ReplicateSpec(
            cell=spec.cell,
            replicate_index=(spec.replicate_index % 512),
            source_contract_digest=ROUND42_SOURCE_DIGEST,
        ).child_seed_digest
        for spec in specs
    }
    assert calibration.isdisjoint(round42)
    assert evaluation.isdisjoint(round42)


def test_pre_sample_feasibility_is_exact_and_result_blind() -> None:
    contract = load_marginal_static_repair_health_execution_source_contract(
        SOURCE_PATH
    )
    artifact = build_pre_sample_feasibility_artifact(
        source_contract=contract,
        preregistration_digest=PREREGISTRATION_DIGEST,
        parent_digests=("a" * 64,),
    )
    assert artifact["upper_power"] == EXPECTED_FEASIBILITY
    assert artifact["computed_before_evaluation_dispatch"] is True
    assert artifact["alternative_results_read"] is False
    assert artifact["round_42_statistical_results_read"] is False
    assert artifact["generated_issues"] == 0


def test_conformal_tie_boundary_student_t_and_wilson_are_exact() -> None:
    calibration = [0.0] * CALIBRATION_REPLICATES_PER_SCALE
    calibration[:MAX_REJECTING_EXCEEDANCE_COUNT] = [2.0] * (
        MAX_REJECTING_EXCEEDANCE_COUNT
    )
    assert conformal_exceedance_count(calibration, 1.0) == (24, 25 / 513, True)
    calibration[MAX_REJECTING_EXCEEDANCE_COUNT] = 1.0
    assert conformal_exceedance_count(calibration, 1.0) == (25, 26 / 513, False)

    zero = student_t_interval([0.25] * EVALUATION_REPLICATES_PER_CELL)
    assert zero["lower"] == zero["upper"] == 0.25
    assert zero["critical_value"] == STUDENT_T_CRITICAL
    varied = student_t_interval(range(EVALUATION_REPLICATES_PER_CELL))
    assert varied["lower"] < 127.5 < varied["upper"]
    with pytest.raises(MarginalStaticRepairHealthExecutionError, match="t_interval"):
        student_t_interval(range(EVALUATION_REPLICATES_PER_CELL - 1))

    low, high = wilson_interval(13, 256, z=WILSON_Z)
    assert low < 13 / 256 < high < 0.09


def test_real_short_and_long_replicates_preserve_temporal_truth_identity() -> None:
    _, workload, _, _, _ = _parents()
    specs = build_repair_health_replicate_specs(
        workload_artifact=workload,
        preregistration_digest=PREREGISTRATION_DIGEST,
    )
    selected = [
        next(
            spec
            for spec in specs
            if spec.lane == "EVALUATION"
            and spec.cell.fixture_id == fixture
            and spec.cell.scale_id == scale
        )
        for fixture, scale in (
            ("V2_T1_OVERLAP_ODDS_2_MARKOV", "FORWARD_61"),
            ("V2_J1_HISTORY_IS4_LAMBDA_HALF", "HISTORICAL_2581"),
        )
    ]
    for spec in selected:
        summary = run_repair_health_replicate(spec)
        assert summary["conditional_identity_max_abs_error"] <= (
            IDENTITY_ABSOLUTE_ERROR_MAX
        )
        assert summary["illegal_draw_count"] == 0
        assert summary["nested_bootstrap_replicates"] == 0
        assert summary["raw_draws_retained"] is False


def test_compact_index_resume_rejects_duplicate_and_tamper(tmp_path: Path) -> None:
    _, workload, _, _, _ = _parents()
    spec = build_repair_health_replicate_specs(
        workload_artifact=workload,
        preregistration_digest=PREREGISTRATION_DIGEST,
    )[0]
    summary = run_repair_health_replicate(spec)
    checkpoint = tmp_path / "task/checkpoints"
    entry = _persist_summary_and_build_entry(
        checkpoint_root=checkpoint,
        context_digest="b" * 64,
        spec=spec,
        summary=summary,
    )
    index = checkpoint / "completion-index.jsonl"
    append_repair_health_completion_entries(index, [entry])
    loaded = load_repair_health_completion_index(
        index,
        context_digest="b" * 64,
        expected_specs={spec.replicate_digest: spec},
    )
    assert list(loaded) == [spec.replicate_digest]

    append_repair_health_completion_entries(index, [entry])
    with pytest.raises(
        MarginalStaticRepairHealthExecutionError,
        match="duplicate_index_entry",
    ):
        load_repair_health_completion_index(
            index,
            context_digest="b" * 64,
            expected_specs={spec.replicate_digest: spec},
        )

    tampered = json.loads(json.dumps(entry))
    tampered["summary"]["observed_endpoint_bits_per_issue"] += 1.0
    index.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
    with pytest.raises(
        MarginalStaticRepairHealthExecutionError,
        match="index_identity_changed|summary_invalid",
    ):
        load_repair_health_completion_index(
            index,
            context_digest="b" * 64,
            expected_specs={spec.replicate_digest: spec},
        )


def test_full_aggregate_uses_only_calibration_lane_and_separate_decision(
    tmp_path: Path,
) -> None:
    contract = load_marginal_static_repair_health_execution_source_contract(
        SOURCE_PATH
    )
    _, workload, inference, _, _ = _parents()
    assert inference["artifact_digest"] == INFERENCE_GATE_DIGEST
    specs = build_repair_health_replicate_specs(
        workload_artifact=workload,
        preregistration_digest=PREREGISTRATION_DIGEST,
    )
    summaries = []
    entries = []
    checkpoint = tmp_path / "runtime/task/checkpoints"
    for spec in specs:
        if spec.lane == "CALIBRATION":
            score = float(spec.replicate_index) / 10_000.0
        elif spec.cell.role == "NEGATIVE_CONTROL":
            score = -1.0
        else:
            score = 1.0
        summary = _synthetic_summary(spec, score)
        summaries.append(summary)
        entries.append(
            _persist_summary_and_build_entry(
                checkpoint_root=checkpoint,
                context_digest="c" * 64,
                spec=spec,
                summary=summary,
            )
        )
    index_path = checkpoint / "completion-index.jsonl"
    append_repair_health_completion_entries(index_path, entries)
    feasibility = build_pre_sample_feasibility_artifact(
        source_contract=contract,
        preregistration_digest=PREREGISTRATION_DIGEST,
        parent_digests=("a" * 64,),
    )
    index_artifact = build_repair_health_completion_index_artifact(
        entries=entries,
        context_digest="c" * 64,
        index_path=index_path,
        root_dir=tmp_path,
        parent_digests=("a" * 64, feasibility["artifact_digest"]),
    )
    result = build_repair_health_result(
        summaries=summaries,
        feasibility_artifact=feasibility,
        index_digest=index_artifact["artifact_digest"],
        workload_digest=WORKLOAD_SEED_DIGEST,
        inference_digest=INFERENCE_GATE_DIGEST,
        preregistration_digest=PREREGISTRATION_DIGEST,
        parent_digests=("a" * 64,),
    )
    completion = build_repair_health_completion(
        health_result=result,
        index_artifact=index_artifact,
        feasibility_artifact=feasibility,
        execution_id="d" * 64,
        git_commit="e" * 40,
        parent_digests=("a" * 64,),
    )
    assert result["authoritative_decision"] is None
    assert result["next_consumer"] == MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY
    assert result["nested_bootstrap_replicates"] == 0
    assert result["historical_outcomes_read"] is False
    assert completion["completion_fact"] == (
        MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT
    )
    assert completion["duplicate_validation"] is False
    assert completion["raw_replay"] is False


def test_parent_digests_are_exact() -> None:
    execution, workload, inference, preregistration, completion = _parents()
    assert execution["artifact_digest"] == PREREGISTRATION_EXECUTION_DIGEST
    assert workload["artifact_digest"] == WORKLOAD_SEED_DIGEST
    assert inference["artifact_digest"] == INFERENCE_GATE_DIGEST
    assert preregistration["artifact_digest"] == PREREGISTRATION_DIGEST
    assert completion["artifact_digest"] == PREREGISTRATION_COMPLETION_DIGEST
    assert completion["completion_fact"] == (
        MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT
    )


def test_capability_and_compact_index_replay_without_raw_regeneration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_tree(tmp_path)
    task = _task()
    execution_id = "d" * 64
    git_commit = "e" * 40
    preregistration_execution, workload, inference, preregistration, completion = (
        _parents()
    )
    parent_by_type = {
        workload["artifact_type"]: workload,
        inference["artifact_type"]: inference,
        preregistration["artifact_type"]: preregistration,
        completion["artifact_type"]: completion,
    }
    run = _synthetic_formal_run(
        root_dir=tmp_path,
        execution_id=execution_id,
        git_commit=git_commit,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, preregistration_execution, "preregistration-registrations"),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **kwargs: parent_by_type[kwargs["artifact_type"]],
    )
    monkeypatch.setattr(
        supervisor_module,
        "execute_repair_health_program",
        lambda **_: run,
    )
    result = M4MarginalStaticRepairHealthExecutionCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id=execution_id,
        git_commit=git_commit,
    )
    assert result.completion_facts == (
        MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT,
    )
    assert len(result.registrations) == 5
    mainline = result.execution_artifact
    assert mainline["replicate_count"] == TOTAL_REPLICATES
    assert mainline["generated_issues"] == TOTAL_GENERATED_ISSUES
    assert mainline["repair_health_authoritative_decision"] is None
    assert mainline["measurement_health"] == "REPAIR"
    assert mainline["duplicate_validation"] is False
    assert mainline["sentinel_replicates_recomputed"] == 0
    assert mainline["replay_status"] == "COMPACT_INDEX_AGGREGATE_ONLY"
    assert mainline["downstream_consumer"] == (
        MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY
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
                    "execution_id": execution_id,
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
        task_key=MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
        execution_id=execution_id,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["raw_replicates_regenerated"] == 0
    assert capability_replay["compact_index_reads"] == 1
    assert capability_replay["sentinel_replicates_recomputed"] == 0
    assert capability_replay["duplicate_validation"] is False


def test_additive_execution_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    normalized = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live = deepcopy(normalized)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY
    ]
    live_execution = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
    )
    live_execution.pop("requested_capability")
    live_execution.pop("input_artifact_digests")
    live_execution["dependencies"] = live_execution["dependencies"][:2]
    for key in (
        "formal_replicates",
        "calibration_replicates",
        "evaluation_replicates",
        "execution_shards",
        "generated_issues",
        "outer_evaluation_issues",
        "nested_bootstrap_replicates_per_formal_replicate",
        "checkpoint_mode",
    ):
        live_execution["metric_contract"].pop(key)
    live_execution["metric_contract"]["formal_execution_allowed"] = False
    source_fact = next(
        fact
        for fact in live["facts"]["artifacts"]
        if fact.startswith(
            "m4-v2-marginal-static-repair-health-execution-source:"
        )
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=normalized,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_completed_execution_projects_only_separate_decision_ready() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    preregistration_task = next(
        task
        for task in manifest.tasks
        if task.task_key
        == "m4-v2-marginal-static-measurement-repair-preregistration"
    )
    execution_task = _task()
    for task in payload["tasks"]:
        if task["task_key"] in {
            preregistration_task.task_key,
            execution_task.task_key,
        }:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT,
            MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT,
            mainline_completion_fact(
                task=preregistration_task,
                execution_id="f" * 64,
            ),
            mainline_completion_fact(task=execution_task, execution_id="1" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
            "execution_artifact_digest": "2" * 64,
            "registered_artifact_count": 5,
            "actual_fold_count": 0,
            "measurement_health": "REPAIR",
            "decision": "REPAIR_MEASUREMENT_SYSTEM",
            "decision_fact": (
                "m4-v2-marginal-static-measurement-health-decision:REPAIR"
            ),
            "failed_cell_ids": ["legacy-failed-cell"],
            "failed_cell_count": 4,
            "repair_health_preliminary_measurement_health": "PASS",
            "repair_health_authoritative_decision": None,
            "replicate_count": TOTAL_REPLICATES,
            "calibration_replicates": 1024,
            "evaluation_replicates": 3584,
            "generated_issues": TOTAL_GENERATED_ISSUES,
            "outer_evaluation_issues": TOTAL_OUTER_EVALUATION_ISSUES,
            "marginal_static_repair_health_completion_index_digest": "3" * 64,
            "marginal_static_repair_health_feasibility_digest": "4" * 64,
            "marginal_static_repair_health_result_digest": "5" * 64,
            "marginal_static_repair_health_execution_completion_digest": (
                "6" * 64
            ),
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "MARGINAL_STATIC_REPAIR_HEALTH_DECISION"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_VALIDATED_IN_MAINLINE"
    )
    execution = projection["marginal_static_repair_health_execution"]
    assert execution["completed"] is True
    assert execution["formal_execution_status"] == "COMPLETE_PENDING_DECISION"
    assert execution["preliminary_measurement_health"] == "PASS"
    assert execution["authoritative_decision"] is None
    assert execution["replicate_count"] == TOTAL_REPLICATES
    decision = projection["marginal_static_repair_health_decision"]
    assert decision["resolver_status"] == "ready"
    assert decision["authoritative_decision"] is None


def test_artifact_index_and_supervisor_register_execution() -> None:
    contract = load_marginal_static_repair_health_execution_source_contract(
        SOURCE_PATH
    )
    manifest = load_m4_manifest(MANIFEST_PATH)
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[contract["artifact_digest"]]["path"] == (
        MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH.as_posix()
    )
    assert index[manifest.artifact_digest]["identity_field"] == "manifest_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_CAPABILITY in (
        supervisor.capabilities
    )
