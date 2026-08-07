from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.contracts import (
    load_measurement_contract_v2,
)
from dehps.research_os.information_theory.measurement_system_v2.execution import (
    DESIGN_COMPLETION_FACT,
)
from dehps.research_os.information_theory.measurement_system_v2.fixture_freeze import (
    FIXTURE_FREEZE_COMPLETION_FACT,
    FIXTURE_FREEZE_SOURCE_CONTRACT_PATH,
    FIXTURE_FREEZE_TASK_KEY,
    FixtureFreezeError,
    build_fixture_freeze_artifacts,
    load_fixture_freeze_source_contract,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.preflight_design import (
    PREFLIGHT_DESIGN_COMPLETION_FACT,
    PREFLIGHT_DESIGN_TASK_KEY,
    build_branch_preflight_design_artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2.preflight_execution import (
    MARGINAL_CONTRACT_FREEZE_TASK_KEY,
    PREFLIGHT_EXECUTION_CAPABILITY,
    PREFLIGHT_EXECUTION_COMPLETION_FACT,
    PREFLIGHT_EXECUTION_PASS_FACT,
    PREFLIGHT_EXECUTION_SOURCE_CONTRACT_PATH,
    PREFLIGHT_EXECUTION_TASK_KEY,
    PreflightExecutionError,
    build_preflight_execution_artifacts,
    load_preflight_execution_source_contract,
    verify_preflight_execution_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.replay import (
    DESIGN_REPLAY_COMPLETION_FACT,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    M4BranchIdentifiabilityPreflightExecutionCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
MEASUREMENT_CONTRACT_PATH = ROOT / "configs/research-os/m4-measurement-contract-v2.json"
SOURCE_CONTRACT_PATH = ROOT / PREFLIGHT_EXECUTION_SOURCE_CONTRACT_PATH
FIXTURE_SOURCE_CONTRACT_PATH = ROOT / FIXTURE_FREEZE_SOURCE_CONTRACT_PATH


def _copy_source_contract_tree(target_root: Path) -> dict:
    contract = load_preflight_execution_source_contract(SOURCE_CONTRACT_PATH)
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = target_root / PREFLIGHT_EXECUTION_SOURCE_CONTRACT_PATH
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_CONTRACT_PATH, target_contract)
    return contract


def _preflight_inputs() -> tuple[dict, object, object]:
    measurement_contract = load_measurement_contract_v2(MEASUREMENT_CONTRACT_PATH)
    designs = build_branch_preflight_design_artifacts(
        measurement_contract,
        design_execution_artifact_digest="1" * 64,
        design_replay_execution_artifact_digest="2" * 64,
        gate_compiler_replay_digest="3" * 64,
        execution_id="4" * 64,
        git_commit="5" * 40,
    )
    fixture_source = load_fixture_freeze_source_contract(
        FIXTURE_SOURCE_CONTRACT_PATH
    )
    fixtures = build_fixture_freeze_artifacts(
        source_contract=fixture_source,
        preflight_design_execution_artifact_digest="6" * 64,
        preflight_design_completion_digest=designs.completion["artifact_digest"],
        cross_branch_preflight_design_digest=designs.cross_branch_contract[
            "artifact_digest"
        ],
        execution_id="7" * 64,
        git_commit="8" * 40,
    )
    source = load_preflight_execution_source_contract(SOURCE_CONTRACT_PATH)
    return source, designs, fixtures


def _build_run() -> object:
    source, designs, fixtures = _preflight_inputs()
    return build_preflight_execution_artifacts(
        source_contract=source,
        fixture_execution_artifact_digest="9" * 64,
        solver_fixture=fixtures.solver_contract,
        orthogonal_fixture=fixtures.orthogonal_control_contract,
        legacy_fixture=fixtures.legacy_role_resolution_contract,
        fixture_completion=fixtures.completion,
        branch_designs=designs.branch_contracts,
        cross_branch_design=designs.cross_branch_contract,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )


def test_preflight_execution_is_deterministic_and_all_branches_pass() -> None:
    first = _build_run()
    second = _build_run()

    assert first == second
    assert first.all_branches_pass is True
    assert len(first.artifacts) == 7
    assert len({item["artifact_digest"] for item in first.artifacts}) == 7
    assert first.solver_result["status"] == "PASS"
    assert first.solver_result["valid_fixture_count"] == 3
    assert first.solver_result["invalid_boundary_case_count"] == 5
    assert all(
        item["status"] == "PASS"
        for item in first.solver_result["invalid_boundary_results"]
    )
    assert first.solver_result["permutation_equivariance_result"]["status"] == (
        "PASS"
    )
    assert first.orthogonal_result["status"] == "PASS"
    assert first.orthogonal_result["endpoint_count"] == 12
    assert first.legacy_result["status"] == "PASS"
    assert first.legacy_result["state_result_count"] == 4
    assert first.legacy_result["is3_decision_credit"] is False
    assert [item["status"] for item in first.branch_results] == [
        "PASS",
        "PASS",
        "PASS",
    ]
    assert first.completion["preflight_status"] == "ALL_BRANCHES_PASS"
    assert first.completion["all_branches_pass_fact"] == PREFLIGHT_EXECUTION_PASS_FACT
    assert first.completion["next_consumer"] == MARGINAL_CONTRACT_FREEZE_TASK_KEY
    assert first.completion["historical_outcomes_read"] is False
    assert first.completion["evidence_created"] is False


def test_preflight_execution_fails_closed_on_anchor_drift() -> None:
    source, designs, fixtures = _preflight_inputs()
    orthogonal = deepcopy(fixtures.orthogonal_control_contract)
    orthogonal["fixtures"][0]["truth_anchor_bits"]["marginal_static"] += 0.01
    run = build_preflight_execution_artifacts(
        source_contract=source,
        fixture_execution_artifact_digest="9" * 64,
        solver_fixture=fixtures.solver_contract,
        orthogonal_fixture=orthogonal,
        legacy_fixture=fixtures.legacy_role_resolution_contract,
        fixture_completion=fixtures.completion,
        branch_designs=designs.branch_contracts,
        cross_branch_design=designs.cross_branch_contract,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )

    assert run.orthogonal_result["status"] == "FAIL"
    assert run.all_branches_pass is False
    assert [item["status"] for item in run.branch_results] == [
        "FAIL",
        "FAIL",
        "FAIL",
    ]
    assert run.completion["preflight_status"] == "FAIL"
    assert run.completion["all_branches_pass_fact"] is None
    assert run.completion["next_consumer"] is None


def test_preflight_execution_marks_solver_failure_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, designs, fixtures = _preflight_inputs()

    def fail_solver(*_: object, **__: object) -> object:
        raise FixtureFreezeError("fixture_freeze_solver_not_converged")

    monkeypatch.setattr(
        "dehps.research_os.information_theory.measurement_system_v2."
        "preflight_execution._solve_maxent",
        fail_solver,
    )
    run = build_preflight_execution_artifacts(
        source_contract=source,
        fixture_execution_artifact_digest="9" * 64,
        solver_fixture=fixtures.solver_contract,
        orthogonal_fixture=fixtures.orthogonal_control_contract,
        legacy_fixture=fixtures.legacy_role_resolution_contract,
        fixture_completion=fixtures.completion,
        branch_designs=designs.branch_contracts,
        cross_branch_design=designs.cross_branch_contract,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )

    assert run.solver_result["status"] == "UNRESOLVED"
    assert [item["status"] for item in run.branch_results] == [
        "UNRESOLVED",
        "UNRESOLVED",
        "UNRESOLVED",
    ]
    assert run.completion["preflight_status"] == "UNRESOLVED"
    assert run.completion["all_branches_pass_fact"] is None


def test_preflight_execution_source_contract_detects_byte_and_contract_tamper(
    tmp_path: Path,
) -> None:
    contract = _copy_source_contract_tree(tmp_path)
    verify_preflight_execution_source_bytes(root_dir=tmp_path, contract=contract)

    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(PreflightExecutionError, match="source_modified"):
        verify_preflight_execution_source_bytes(root_dir=tmp_path, contract=contract)

    drifted = deepcopy(contract)
    drifted["frozen_contract"]["solver_acceptance"][
        "maximum_marginal_residual"
    ] = 1e-6
    drifted["artifact_digest"] = "0" * 64
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(PreflightExecutionError, match="source_contract_invalid"):
        load_preflight_execution_source_contract(drift_path)


def test_preflight_execution_capability_materializes_eight_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_contract_tree(tmp_path)
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item for item in manifest.tasks if item.task_key == PREFLIGHT_EXECUTION_TASK_KEY
    )
    _, designs, fixtures = _preflight_inputs()
    expected = task.input_artifact_digests
    fixture_execution = {
        "execution_id": "1" * 64,
        "artifact_digest": expected[1],
        "completion_fact": FIXTURE_FREEZE_COMPLETION_FACT,
        "fixture_contract_count": 3,
        "formal_branch_runs_executed": 0,
        "preflight_result_count": 0,
        "historical_outcomes_read": False,
        "p2_6_3_statistical_results_read": False,
        "evidence_created": False,
    }
    solver = deepcopy(fixtures.solver_contract)
    orthogonal = deepcopy(fixtures.orthogonal_control_contract)
    legacy = deepcopy(fixtures.legacy_role_resolution_contract)
    completion = deepcopy(fixtures.completion)
    solver["artifact_digest"] = expected[2]
    orthogonal["artifact_digest"] = expected[3]
    legacy["artifact_digest"] = expected[4]
    completion["artifact_digest"] = expected[5]
    completion["solver_fixture_contract_digest"] = expected[2]
    completion["orthogonal_control_fixture_contract_digest"] = expected[3]
    completion["legacy_role_resolution_fixture_contract_digest"] = expected[4]
    branch_designs = [deepcopy(item) for item in designs.branch_contracts]
    for item, digest in zip(branch_designs, expected[6:9], strict=True):
        item["artifact_digest"] = digest
    cross = deepcopy(designs.cross_branch_contract)
    cross["artifact_digest"] = expected[9]
    cross["branch_preflight_design_digests"] = list(expected[6:9])

    def fake_load_parent(**kwargs: object) -> tuple[dict, dict, list]:
        if kwargs["task_key"] == FIXTURE_FREEZE_TASK_KEY:
            return {}, fixture_execution, []
        assert kwargs["task_key"] == PREFLIGHT_DESIGN_TASK_KEY
        return {}, {}, []

    def fake_registered_type(**kwargs: object) -> dict:
        return {
            "m4_v2_joint_maxent_fixture_contract": solver,
            "m4_v2_orthogonal_control_fixture_contract": orthogonal,
            "m4_v2_legacy_role_resolution_fixture_contract": legacy,
            "m4_v2_branch_fixture_freeze_completion": completion,
            "m4_v2_cross_branch_preflight_design": cross,
        }[kwargs["artifact_type"]]

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        fake_load_parent,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        fake_registered_type,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type_group",
        lambda **_: tuple(branch_designs),
    )
    result = M4BranchIdentifiabilityPreflightExecutionCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="2" * 64,
        git_commit="3" * 40,
    )

    assert result.completion_facts == (
        PREFLIGHT_EXECUTION_COMPLETION_FACT,
        PREFLIGHT_EXECUTION_PASS_FACT,
    )
    assert result.execution_artifact["registered_artifact_count"] == 8
    assert len(result.registrations) == 8
    assert result.execution_artifact["preflight_execution_status"] == (
        "ALL_BRANCHES_PASS"
    )
    assert result.execution_artifact["branch_preflight_statuses"] == {
        "MARGINAL_STATIC": "PASS",
        "TEMPORAL_MARGINAL_INCREMENT": "PASS",
        "JOINT_RESIDUAL_INCREMENT": "PASS",
    }
    assert result.execution_artifact["historical_outcomes_read"] is False
    assert result.execution_artifact["evidence_created"] is False


def test_preflight_execution_additive_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    live = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_CONTRACT_FREEZE_TASK_KEY
    ]
    live_preflight = next(
        item
        for item in live["tasks"]
        if item["task_key"] == PREFLIGHT_EXECUTION_TASK_KEY
    )
    live_preflight.pop("requested_capability")
    live_preflight.pop("input_artifact_digests")
    live_preflight["dependencies"] = live_preflight["dependencies"][:2]
    live_preflight["metric_contract"] = {
        key: value
        for key, value in live_preflight["metric_contract"].items()
        if key not in {"mainline_integration", "formal_branch_runs", "monte_carlo_replicates", "historical_outcomes_read", "statistical_results_read", "production_action"}
    }
    source_fact = next(
        item
        for item in source["facts"]["artifacts"]
        if item.startswith("m4-v2-branch-preflight-execution-source-contract:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(MARGINAL_CONTRACT_FREEZE_TASK_KEY,),
        allowlisted_revised_task_keys=(PREFLIGHT_EXECUTION_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )

    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [MARGINAL_CONTRACT_FREEZE_TASK_KEY]
    assert dry_run["revised_task_keys"] == [PREFLIGHT_EXECUTION_TASK_KEY]
    assert dry_run["existing_task_deletions"] == 0
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_preflight_pass_projects_marginal_contract_freeze_as_next_consumer() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task_by_key = {item.task_key: item for item in manifest.tasks}
    execution_ids = {
        supervisor_module.M4_V2_DESIGN_TASK_KEY: "1" * 64,
        supervisor_module.M4_V2_DESIGN_REPLAY_TASK_KEY: "2" * 64,
        PREFLIGHT_DESIGN_TASK_KEY: "3" * 64,
        FIXTURE_FREEZE_TASK_KEY: "4" * 64,
        PREFLIGHT_EXECUTION_TASK_KEY: "5" * 64,
    }
    for task in payload["tasks"]:
        if task["task_key"] in execution_ids:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        mainline_completion_fact(task=task_by_key[key], execution_id=execution_id)
        for key, execution_id in execution_ids.items()
    )
    payload["facts"]["artifacts"].extend(
        (
            DESIGN_COMPLETION_FACT,
            DESIGN_REPLAY_COMPLETION_FACT,
            PREFLIGHT_DESIGN_COMPLETION_FACT,
            FIXTURE_FREEZE_COMPLETION_FACT,
            PREFLIGHT_EXECUTION_COMPLETION_FACT,
            PREFLIGHT_EXECUTION_PASS_FACT,
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": PREFLIGHT_EXECUTION_TASK_KEY,
            "preflight_execution_status": "ALL_BRANCHES_PASS",
            "branch_preflight_statuses": {
                "MARGINAL_STATIC": "PASS",
                "TEMPORAL_MARGINAL_INCREMENT": "PASS",
                "JOINT_RESIDUAL_INCREMENT": "PASS",
            },
            "solver_preflight_status": "PASS",
            "orthogonal_endpoint_status": "PASS",
            "legacy_role_resolution_status": "PASS",
            "preflight_result_count": 3,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "MARGINAL_STATIC_CONTRACT_FREEZE"
    assert projection["live_mainline_status"] == (
        "BRANCH_PREFLIGHT_VALIDATED_IN_MAINLINE"
    )
    assert projection["branch_preflight_execution"]["executed"] is True
    assert projection["branch_preflight_execution"]["all_branches_pass"] is True
    assert projection["next_consumer"] == MARGINAL_CONTRACT_FREEZE_TASK_KEY
    assert projection["evidence_progress_increment"] == 0


def test_supervisor_registers_preflight_execution_capability() -> None:
    assert PREFLIGHT_EXECUTION_TASK_KEY in {
        task.task_key for task in load_m4_manifest(MANIFEST_PATH).tasks
    }
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert PREFLIGHT_EXECUTION_CAPABILITY in supervisor.capabilities
