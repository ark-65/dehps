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
from dehps.research_os.information_theory.measurement_system_v2 import (
    marginal_static_repair_v2_health_execution as health_module,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_execution import (
    _generate_sequence,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_health_execution import (
    _score_sequence_with_identity,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_execution import (
    EVALUATION_CHILDREN,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
    PLANNED_GENERATED_ISSUES,
    REFERENCE_CHILDREN,
    SHARD_COUNT,
    SHARD_SIZE,
    TOTAL_CHILDREN,
    MarginalStaticRepairV2HealthExecutionError,
    RepairV2HealthExecutionRun,
    _completion_row,
    _preregistered_cell_id,
    build_child_specs,
    build_evaluation_cells,
    load_completion_index_once,
    load_marginal_static_repair_v2_health_execution_source_contract,
    run_child_shard,
    score_sequence_vectorized_identity,
    verify_marginal_static_repair_v2_health_execution_source_bytes,
    wilson_interval,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_preregistration import (
    evaluation_child_identity,
    reference_child_identity,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    M4MarginalStaticRepairV2HealthExecutionCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
SOURCE_PATH = ROOT / MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH


def _copy_source_tree(target_root: Path) -> dict:
    contract = load_marginal_static_repair_v2_health_execution_source_contract(
        SOURCE_PATH
    )
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = (
        target_root / MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
    )
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PATH, target_contract)
    return contract


def _task():
    manifest = load_m4_manifest(MANIFEST_PATH)
    return next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
    )


def _summary(spec, score: float = 0.0) -> dict:
    cell = health_module._cell_for_spec(spec)
    payload = {
        "schema_version": ("dehps-m4-v2-marginal-static-repair-v2-health-child.v1"),
        "artifact_type": ("m4_v2_marginal_static_repair_v2_health_child_summary"),
        "artifact_digest": "",
        "child_digest": spec.child_digest,
        "child_seed_digest": spec.child_seed_digest,
        "lane": spec.lane,
        "null_family": spec.null_family,
        "scale_id": spec.scale_id,
        "evaluation_index": spec.evaluation_index,
        "reference_index": spec.reference_index,
        "cell_id": spec.cell_id,
        "cell": asdict(cell),
        "sequence_issues": spec.sequence_issues,
        "evaluation_issues": spec.evaluation_issues,
        "observed_endpoint_bits_per_issue": score,
        "conditional_truth_bits_per_issue": 0.0,
        "score_residual_bits_per_issue": score,
        "score_residual_rmse_bits_per_issue": abs(score),
        "conditional_identity_max_abs_error": 0.0,
        "probability_sum_max_abs_error": 0.0,
        "legal_draw_count": spec.sequence_issues,
        "illegal_draw_count": 0,
        "database_reads_during_child": 0,
        "database_writes_during_child": 0,
        "csv_materialized": False,
        "raw_draws_retained": False,
        "historical_outcomes_read": False,
        "numpy_version": np.__version__,
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain=("dehps.m4.v2.marginal-static-repair-v2-health-child-summary.v1"),
    )
    return payload


def test_repair_v2_health_source_contract_and_tamper_detection(
    tmp_path: Path,
) -> None:
    contract = _copy_source_tree(tmp_path)
    verify_marginal_static_repair_v2_health_execution_source_bytes(
        root_dir=tmp_path,
        contract=contract,
    )
    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(
        MarginalStaticRepairV2HealthExecutionError, match="source_modified"
    ):
        verify_marginal_static_repair_v2_health_execution_source_bytes(
            root_dir=tmp_path,
            contract=contract,
        )

    drifted = deepcopy(contract)
    drifted["frozen_contract"]["resume"]["duplicate_validation"] = True
    drifted["artifact_digest"] = "0" * 64
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(
        MarginalStaticRepairV2HealthExecutionError, match="source_invalid"
    ):
        load_marginal_static_repair_v2_health_execution_source_contract(drift_path)


def test_repair_v2_health_child_set_matches_preregistered_identity() -> None:
    specs = build_child_specs()
    assert len(specs) == TOTAL_CHILDREN == 131_072
    assert REFERENCE_CHILDREN == 3 * 2 * 1024 * 19
    assert EVALUATION_CHILDREN == 7 * 2 * 1024
    assert SHARD_COUNT * SHARD_SIZE == TOTAL_CHILDREN
    assert len({spec.child_digest for spec in specs}) == TOTAL_CHILDREN

    reference = specs[0]
    assert reference.child_digest == reference_child_identity(
        preregistration_digest=reference.preregistration_digest,
        null_family=reference.null_family,
        scale_id=reference.scale_id,
        evaluation_index=reference.evaluation_index,
        reference_index=int(reference.reference_index),
    )
    evaluation = specs[REFERENCE_CHILDREN]
    assert evaluation.child_digest == evaluation_child_identity(
        preregistration_digest=evaluation.preregistration_digest,
        cell_id=_preregistered_cell_id(str(evaluation.cell_id)),
        scale_id=evaluation.scale_id,
        evaluation_index=evaluation.evaluation_index,
    )


def test_vectorized_identity_matches_scalar_oracle_for_all_base_cells() -> None:
    cells = [cell for cell in build_evaluation_cells() if cell.family == "BASE_FIXTURE"]
    assert len(cells) == 8
    for index, cell in enumerate(cells):
        rng = np.random.Generator(np.random.PCG64DXSM(10_000 + index))
        draws, conditional_truth = _generate_sequence(cell, rng)
        vectorized = score_sequence_vectorized_identity(
            draws=draws,
            cell=cell,
            conditional_truth=conditional_truth,
        )
        scalar = _score_sequence_with_identity(
            draws=draws,
            cell=cell,
            conditional_truth=conditional_truth,
        )
        np.testing.assert_allclose(vectorized[0], scalar[0], atol=0.0, rtol=0.0)
        np.testing.assert_allclose(vectorized[1], scalar[1], atol=1e-12, rtol=0.0)
        assert vectorized[2] <= 1e-12
        assert vectorized[3] <= 1e-12


def test_load_once_index_skips_matching_rows_without_duplicate_validation(
    tmp_path: Path,
) -> None:
    spec = build_child_specs()[0]
    context_digest = "c" * 64
    first = _completion_row(
        context_digest=context_digest,
        spec=spec,
        summary=_summary(spec, 0.0),
    )
    second = _completion_row(
        context_digest=context_digest,
        spec=spec,
        summary=_summary(spec, 0.1),
    )
    path = tmp_path / "index.jsonl"
    path.write_text(
        "\n".join(json.dumps(row) for row in (first, second)) + "\n",
        encoding="utf-8",
    )
    loaded = load_completion_index_once(
        path,
        context_digest=context_digest,
        expected_specs={spec.child_digest: spec},
    )
    assert len(loaded) == 1
    assert (
        loaded[spec.child_digest]["summary"]["observed_endpoint_bits_per_issue"] == 0.1
    )

    drifted = deepcopy(second)
    drifted["summary"]["child_seed_digest"] = "f" * 64
    path.write_text(json.dumps(drifted) + "\n", encoding="utf-8")
    with pytest.raises(
        MarginalStaticRepairV2HealthExecutionError,
        match="registered_summary_mismatch",
    ):
        load_completion_index_once(
            path,
            context_digest=context_digest,
            expected_specs={spec.child_digest: spec},
        )


def test_shard_dispatches_each_missing_child_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = build_child_specs()[:SHARD_SIZE]
    calls: list[str] = []

    def fake_run(spec):
        calls.append(spec.child_digest)
        return {"child_digest": spec.child_digest}

    monkeypatch.setattr(health_module, "run_child", fake_run)
    summaries = run_child_shard(specs)
    assert len(summaries) == SHARD_SIZE
    assert calls == [spec.child_digest for spec in specs]
    assert len(set(calls)) == SHARD_SIZE


def test_wilson_negative_control_boundary_is_frozen() -> None:
    assert wilson_interval(74, 1024)[1] <= 0.09
    assert wilson_interval(75, 1024)[1] > 0.09


def test_repair_v2_health_capability_packages_mainline_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_contract = _copy_source_tree(tmp_path)
    task = _task()
    preregistration_execution = {
        "execution_id": health_module.PREREGISTRATION_EXECUTION_ID,
        "artifact_digest": task.input_artifact_digests[1],
    }
    types = (
        "m4_v2_marginal_static_repair_v2_health_workload_seeds",
        "m4_v2_marginal_static_repair_v2_health_inference_gates",
        "m4_v2_marginal_static_repair_v2_health_preregistration",
        "m4_v2_marginal_static_repair_v2_health_preregistration_completion",
    )
    parents = {
        artifact_type: {
            "artifact_type": artifact_type,
            "artifact_digest": task.input_artifact_digests[index + 2],
        }
        for index, artifact_type in enumerate(types)
    }
    artifacts = (
        {
            "schema_version": "index.v1",
            "artifact_type": (
                "m4_v2_marginal_static_repair_v2_health_completion_index"
            ),
            "artifact_digest": "7" * 64,
        },
        {
            "schema_version": "health.v1",
            "artifact_type": (
                "m4_v2_marginal_static_repair_v2_measurement_health_result"
            ),
            "artifact_digest": "8" * 64,
            "preliminary_measurement_health": "PASS",
            "failed_required_gate_cell_ids": [],
            "failed_required_gate_cell_count": 0,
        },
        {
            "schema_version": "completion.v1",
            "artifact_type": (
                "m4_v2_marginal_static_repair_v2_health_execution_completion"
            ),
            "artifact_digest": "9" * 64,
        },
    )
    run = RepairV2HealthExecutionRun(
        index_artifact=artifacts[0],
        health_result=artifacts[1],
        completion=artifacts[2],
        runtime_seconds=1.0,
        completed_before_run=64,
        completed_during_run=TOTAL_CHILDREN - 64,
        completed_shards_during_run=SHARD_COUNT - 1,
        worker_count=4,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, preregistration_execution, "registrations"),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **kwargs: parents[kwargs["artifact_type"]],
    )
    monkeypatch.setattr(
        supervisor_module,
        "execute_repair_v2_health_program",
        lambda **_: run,
    )
    result = M4MarginalStaticRepairV2HealthExecutionCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )
    execution = result.execution_artifact
    assert source_contract["artifact_digest"] == task.input_artifact_digests[0]
    assert result.completion_facts == (
        MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT,
    )
    assert len(result.registrations) == 4
    assert execution["completed_children_before_run"] == 64
    assert execution["duplicate_validation"] is False
    assert execution["checkpoint_mode"] == "compact_index_load_once_no_revalidation"
    assert execution["downstream_consumer"] == (
        MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY
    )


def test_repair_v2_health_projects_decision_as_next_consumer() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
    )
    for item in payload["tasks"]:
        if item["task_key"] == MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT,
            mainline_completion_fact(task=task, execution_id="e" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
            "execution_artifact_digest": "f" * 64,
            "registered_artifact_count": 4,
            "actual_fold_count": 0,
            "repair_v2_preliminary_measurement_health": "PASS",
            "repair_v2_health_result_digest": "1" * 64,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_VALIDATED_IN_MAINLINE"
    )
    health = projection["marginal_static_repair_v2_health_execution"]
    assert health["completed"] is True
    assert health["next_consumer"] == MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY


def test_supervisor_registers_repair_v2_health_capability() -> None:
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert (
        MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_CAPABILITY in supervisor.capabilities
    )
    assert PLANNED_GENERATED_ISSUES == 291_110_912
