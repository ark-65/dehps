from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.execution import (
    DESIGN_COMPLETION_FACT,
)
from dehps.research_os.information_theory.measurement_system_v2.fixture_freeze import (
    FIXTURE_FREEZE_CAPABILITY,
    FIXTURE_FREEZE_COMPLETION_FACT,
    FIXTURE_FREEZE_SOURCE_CONTRACT_PATH,
    FIXTURE_FREEZE_TASK_KEY,
    PREFLIGHT_EXECUTION_TASK_KEY,
    FixtureFreezeError,
    build_fixture_freeze_artifacts,
    computed_fixture_contract,
    load_fixture_freeze_source_contract,
    verify_fixture_freeze_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.preflight_design import (
    PREFLIGHT_DESIGN_COMPLETION_FACT,
    PREFLIGHT_DESIGN_TASK_KEY,
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
    M4BranchIdentifiabilityFixtureFreezeCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
SOURCE_CONTRACT_PATH = ROOT / FIXTURE_FREEZE_SOURCE_CONTRACT_PATH


def _copy_source_contract_tree(target_root: Path) -> dict:
    contract = load_fixture_freeze_source_contract(SOURCE_CONTRACT_PATH)
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = target_root / FIXTURE_FREEZE_SOURCE_CONTRACT_PATH
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_CONTRACT_PATH, target_contract)
    return contract


def test_fixture_contract_regenerates_exact_orthogonal_truth() -> None:
    source = load_fixture_freeze_source_contract(SOURCE_CONTRACT_PATH)
    computed = computed_fixture_contract()
    frozen = source["frozen_contract"]

    assert frozen["exact_solver_fixtures"] == computed["exact_solver_fixtures"]
    assert frozen["orthogonal_control_fixtures"] == computed[
        "orthogonal_control_fixtures"
    ]
    assert frozen["legacy_role_resolution_fixtures"] == computed[
        "legacy_role_resolution_fixtures"
    ]
    roles = {
        item["fixture_id"]: item["expected_roles"]
        for item in computed["orthogonal_control_fixtures"]
    }
    assert roles["V2_M1_GROUP_ODDS_2_STATIONARY"] == {
        "MARGINAL_STATIC": "POSITIVE_CONTROL",
        "TEMPORAL_MARGINAL_INCREMENT": "NEGATIVE_CONTROL",
        "JOINT_RESIDUAL_INCREMENT": "NEGATIVE_CONTROL",
    }
    assert roles["V2_T1_OVERLAP_ODDS_2_MARKOV"][
        "TEMPORAL_MARGINAL_INCREMENT"
    ] == "POSITIVE_CONTROL"
    assert roles["V2_J1_HISTORY_IS4_LAMBDA_HALF"][
        "JOINT_RESIDUAL_INCREMENT"
    ] == "POSITIVE_CONTROL"


def test_fixture_freeze_build_is_deterministic_and_has_zero_results() -> None:
    source = load_fixture_freeze_source_contract(SOURCE_CONTRACT_PATH)
    kwargs = {
        "source_contract": source,
        "preflight_design_execution_artifact_digest": "1" * 64,
        "preflight_design_completion_digest": "2" * 64,
        "cross_branch_preflight_design_digest": "3" * 64,
        "execution_id": "4" * 64,
        "git_commit": "5" * 40,
    }
    first = build_fixture_freeze_artifacts(**kwargs)
    second = build_fixture_freeze_artifacts(**kwargs)

    assert first == second
    assert len(first.artifacts) == 4
    assert len({item["artifact_digest"] for item in first.artifacts}) == 4
    for artifact in first.artifacts:
        assert artifact["historical_outcomes_read"] is False
        assert artifact["evidence_created"] is False
    assert first.solver_contract["formal_execution_allowed"] is False
    assert first.solver_contract["preflight_result_count"] == 0
    assert first.legacy_role_resolution_contract["role_resolution_status"] == (
        "NOT_RUN"
    )
    assert first.completion["fixture_contract_count"] == 3
    assert first.completion["formal_branch_runs_executed"] == 0
    assert first.completion["preflight_result_count"] == 0
    assert first.completion["next_consumer"] == PREFLIGHT_EXECUTION_TASK_KEY


def test_fixture_source_contract_detects_byte_and_truth_tamper(
    tmp_path: Path,
) -> None:
    contract = _copy_source_contract_tree(tmp_path)
    verify_fixture_freeze_source_bytes(root_dir=tmp_path, contract=contract)

    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(FixtureFreezeError, match="source_modified"):
        verify_fixture_freeze_source_bytes(root_dir=tmp_path, contract=contract)

    drifted = deepcopy(contract)
    drifted["frozen_contract"]["acceptance"]["positive_floor_bits"] = 0.002
    drifted["artifact_digest"] = "0" * 64
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(FixtureFreezeError, match="source_contract_invalid"):
        load_fixture_freeze_source_contract(drift_path)


def test_fixture_capability_materializes_only_frozen_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_contract_tree(tmp_path)
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(item for item in manifest.tasks if item.task_key == FIXTURE_FREEZE_TASK_KEY)
    preflight_execution = {
        "execution_id": "1" * 64,
        "artifact_digest": "2" * 64,
        "completion_fact": PREFLIGHT_DESIGN_COMPLETION_FACT,
        "formal_branch_runs_executed": 0,
        "preflight_result_count": 0,
        "historical_outcomes_read": False,
        "evidence_created": False,
    }
    preflight_completion = {
        "artifact_type": "m4_v2_branch_preflight_design_completion",
        "artifact_digest": task.input_artifact_digests[1],
        "status": "COMPLETE",
        "next_consumer": FIXTURE_FREEZE_TASK_KEY,
    }
    cross_branch = {
        "artifact_type": "m4_v2_cross_branch_preflight_design",
        "artifact_digest": task.input_artifact_digests[2],
        "formal_execution_allowed": False,
        "preflight_result_count": 0,
    }

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, preflight_execution, []),
    )

    def fake_registered_type(**kwargs):
        return (
            preflight_completion
            if kwargs["artifact_type"]
            == "m4_v2_branch_preflight_design_completion"
            else cross_branch
        )

    monkeypatch.setattr(supervisor_module, "_load_registered_type", fake_registered_type)
    result = M4BranchIdentifiabilityFixtureFreezeCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="3" * 64,
        git_commit="4" * 40,
    )

    assert result.completion_facts == (FIXTURE_FREEZE_COMPLETION_FACT,)
    assert result.execution_artifact["registered_artifact_count"] == 5
    assert len(result.registrations) == 5
    assert result.execution_artifact["fixture_contract_count"] == 3
    assert result.execution_artifact["formal_branch_runs_executed"] == 0
    assert result.execution_artifact["preflight_result_count"] == 0
    assert result.execution_artifact["evidence_created"] is False
    assert {item.artifact_type for item in result.registrations} == {
        "m4_v2_joint_maxent_fixture_contract",
        "m4_v2_orthogonal_control_fixture_contract",
        "m4_v2_legacy_role_resolution_fixture_contract",
        "m4_v2_branch_fixture_freeze_completion",
        "research_os_mainline_execution",
    }


def test_fixture_additive_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    live = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != PREFLIGHT_EXECUTION_TASK_KEY
    ]
    live_fixture = next(
        item for item in live["tasks"] if item["task_key"] == FIXTURE_FREEZE_TASK_KEY
    )
    live_fixture.pop("requested_capability")
    live_fixture.pop("input_artifact_digests")
    live_fixture["dependencies"] = live_fixture["dependencies"][:2]
    live_fixture["metric_contract"] = {
        "engineering_complete": False,
        "engineering_increment_percent": 0,
        "evidence_complete": False,
        "evidence_increment_percent": 0,
        "formal_execution_allowed": False,
        "phase": "M4-V2-PREFLIGHT-FIXTURE-FREEZE",
        "scope": "freeze_exact_branch_controls_joint_baseline_solver_and_numerical_boundaries_without_results",
        "reason": "preflight design exposes unresolved implementation and solver obligations before any synthetic or historical branch run",
    }
    source_fact = next(
        item
        for item in source["facts"]["artifacts"]
        if item.startswith("m4-v2-branch-fixture-freeze-source-contract:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(PREFLIGHT_EXECUTION_TASK_KEY,),
        allowlisted_revised_task_keys=(FIXTURE_FREEZE_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )

    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [PREFLIGHT_EXECUTION_TASK_KEY]
    assert dry_run["revised_task_keys"] == [FIXTURE_FREEZE_TASK_KEY]
    assert dry_run["existing_task_deletions"] == 0
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_fixture_completion_projects_preflight_execution_as_next_consumer() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task_by_key = {item.task_key: item for item in manifest.tasks}
    execution_ids = {
        supervisor_module.M4_V2_DESIGN_TASK_KEY: "1" * 64,
        supervisor_module.M4_V2_DESIGN_REPLAY_TASK_KEY: "2" * 64,
        PREFLIGHT_DESIGN_TASK_KEY: "3" * 64,
        FIXTURE_FREEZE_TASK_KEY: "4" * 64,
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
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "measurement_contract_v2_digest": task_by_key[
                PREFLIGHT_DESIGN_TASK_KEY
            ].input_artifact_digests[0],
            "execution_task_key": FIXTURE_FREEZE_TASK_KEY,
            "fixture_contract_count": 3,
            "formal_branch_runs_executed": 0,
            "preflight_result_count": 0,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "PREFLIGHT_EXECUTION"
    assert projection["live_mainline_status"] == (
        "PREFLIGHT_FIXTURES_VALIDATED_IN_MAINLINE"
    )
    assert projection["branch_preflight_fixture_freeze"]["fixtures_frozen"] is True
    assert projection["branch_preflight_fixture_freeze"][
        "fixture_contract_count"
    ] == 3
    assert projection["next_consumer"] == PREFLIGHT_EXECUTION_TASK_KEY
    assert projection["evidence_progress_increment"] == 0


def test_supervisor_registers_fixture_freeze_capability() -> None:
    assert FIXTURE_FREEZE_TASK_KEY in {
        task.task_key for task in load_m4_manifest(MANIFEST_PATH).tasks
    }
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert FIXTURE_FREEZE_CAPABILITY in supervisor.capabilities
