from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.contracts import (
    BRANCH_IDS,
    json_compatible_copy,
    load_measurement_contract_v2,
)
from dehps.research_os.information_theory.measurement_system_v2.execution import (
    DESIGN_COMPLETION_FACT,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.preflight_design import (
    PREFLIGHT_DESIGN_COMPLETION_FACT,
    PREFLIGHT_DESIGN_TASK_KEY,
    PREFLIGHT_FIXTURE_FREEZE_TASK_KEY,
    PREFLIGHT_SOURCE_CONTRACT_PATH,
    BranchPreflightDesignError,
    build_branch_preflight_design_artifacts,
    load_preflight_source_contract,
    verify_preflight_source_bytes,
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
    M4BranchIdentifiabilityPreflightDesignCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
CONTRACT_PATH = ROOT / "configs/research-os/m4-measurement-contract-v2.json"
SOURCE_CONTRACT_PATH = ROOT / PREFLIGHT_SOURCE_CONTRACT_PATH


def _copy_source_contract_tree(target_root: Path) -> dict:
    contract = load_preflight_source_contract(SOURCE_CONTRACT_PATH)
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = target_root / PREFLIGHT_SOURCE_CONTRACT_PATH
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_CONTRACT_PATH, target_contract)
    return contract


def test_preflight_design_projection_is_deterministic_and_result_blind() -> None:
    contract = load_measurement_contract_v2(CONTRACT_PATH)
    kwargs = {
        "design_execution_artifact_digest": "1" * 64,
        "design_replay_execution_artifact_digest": "2" * 64,
        "gate_compiler_replay_digest": "3" * 64,
        "execution_id": "4" * 64,
        "git_commit": "5" * 40,
    }
    first = build_branch_preflight_design_artifacts(contract, **kwargs)
    second = build_branch_preflight_design_artifacts(contract, **kwargs)

    assert first == second
    assert tuple(item["branch_id"] for item in first.branch_contracts) == BRANCH_IDS
    assert len({item["artifact_digest"] for item in first.artifacts}) == 5
    for branch_id, artifact in zip(BRANCH_IDS, first.branch_contracts, strict=True):
        assert artifact["legal_domain"] == contract.payload["legal_domain"]
        assert artifact["estimand"] == json_compatible_copy(
            contract.branch(branch_id)
        )
        assert artifact["preflight_execution_status"] == "NOT_RUN"
        assert artifact["identifiability_preflight_status"] is None
        assert artifact["formal_execution_allowed"] is False
        assert artifact["historical_outcomes_read"] is False
        assert artifact["statistical_results_read"] is False
        assert artifact["evidence_created"] is False

    cross = first.cross_branch_contract
    assert cross["required_branch_order"] == list(BRANCH_IDS)
    assert cross["no_duplicate_credit_invariants"] == json_compatible_copy(
        contract.payload["estimand_contract"]["no_duplicate_credit_invariants"]
    )
    assert cross["preflight_result_count"] == 0
    assert any(
        marker["value"] == "IMPLEMENTED_REQUIRES_JOINT_PREFLIGHT"
        for marker in cross["unresolved_contract_markers_by_branch"][BRANCH_IDS[2]]
    )
    completion = first.completion
    assert completion["preflight_execution_count"] == 0
    assert completion["preflight_result_count"] == 0
    assert completion["actual_fold_count"] == 0
    assert completion["formal_branch_runs_executed"] == 0
    assert completion["evidence_progress_increment"] == 0
    assert completion["next_consumer"] == PREFLIGHT_FIXTURE_FREEZE_TASK_KEY


def test_preflight_source_contract_verifies_exact_bytes_and_detects_tamper(
    tmp_path: Path,
) -> None:
    contract = _copy_source_contract_tree(tmp_path)
    assert [entry["path"] for entry in contract["source_entries"]] == [
        (
            "apps/worker-python/dehps/research_os/information_theory/"
            "measurement_system_v2/contracts.py"
        ),
        (
            "apps/worker-python/dehps/research_os/information_theory/"
            "measurement_system_v2/preflight_design.py"
        ),
    ]
    verify_preflight_source_bytes(root_dir=tmp_path, contract=contract)

    first_path = tmp_path / contract["source_entries"][0]["path"]
    first_path.write_bytes(first_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(BranchPreflightDesignError, match="source_modified"):
        verify_preflight_source_bytes(root_dir=tmp_path, contract=contract)


def test_preflight_capability_materializes_only_frozen_design_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_contract_tree(tmp_path)
    for relative in (
        "configs/research-os/m4-measurement-contract-v2.json",
        "configs/research-os/m4-measurement-contract-v2-replay-fixture-v1.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)

    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(item for item in manifest.tasks if item.task_key == PREFLIGHT_DESIGN_TASK_KEY)
    design_execution = {
        "execution_id": "1" * 64,
        "artifact_digest": "2" * 64,
    }
    gate_replay = {
        "artifact_type": "GateCompilerReplayArtifact",
        "artifact_digest": "3" * 64,
        "status": "REPLAY_VERIFIED",
        "promotion_gate_opened": False,
    }
    replay_execution = {
        "execution_id": "4" * 64,
        "artifact_digest": "5" * 64,
        "measurement_contract_v2_digest": task.input_artifact_digests[0],
        "design_execution_id": design_execution["execution_id"],
        "design_execution_artifact_digest": design_execution["artifact_digest"],
        "gate_compiler_replay_digest": gate_replay["artifact_digest"],
    }

    def fake_load_parent(**kwargs):
        if kwargs["task_key"] == supervisor_module.M4_V2_DESIGN_TASK_KEY:
            return {}, design_execution, []
        assert kwargs["task_key"] == supervisor_module.M4_V2_DESIGN_REPLAY_TASK_KEY
        return {}, replay_execution, [{"artifact_type": "GateCompilerReplayArtifact"}]

    monkeypatch.setattr(supervisor_module, "_load_single_completed_execution", fake_load_parent)
    monkeypatch.setattr(supervisor_module, "_load_registered_type", lambda **_: gate_replay)
    result = M4BranchIdentifiabilityPreflightDesignCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="6" * 64,
        git_commit="7" * 40,
    )

    assert result.completion_facts == (PREFLIGHT_DESIGN_COMPLETION_FACT,)
    assert result.execution_artifact["registered_artifact_count"] == 6
    assert len(result.registrations) == 6
    assert result.execution_artifact["formal_branch_runs_executed"] == 0
    assert result.execution_artifact["preflight_result_count"] == 0
    assert result.execution_artifact["historical_outcomes_read"] is False
    assert result.execution_artifact["p2_6_3_statistical_results_read"] is False
    assert result.execution_artifact["evidence_created"] is False
    assert {item.artifact_type for item in result.registrations} == {
        "m4_v2_branch_identifiability_preflight_design",
        "m4_v2_cross_branch_preflight_design",
        "m4_v2_branch_preflight_design_completion",
        "research_os_mainline_execution",
    }


def test_preflight_additive_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    live = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != PREFLIGHT_FIXTURE_FREEZE_TASK_KEY
    ]
    live_preflight = next(
        item for item in live["tasks"] if item["task_key"] == PREFLIGHT_DESIGN_TASK_KEY
    )
    live_preflight.pop("requested_capability")
    live_preflight["input_artifact_digests"] = live_preflight[
        "input_artifact_digests"
    ][:2]
    live_preflight["dependencies"] = live_preflight["dependencies"][:2]
    live_preflight["metric_contract"] = {
        "engineering_complete": False,
        "engineering_increment_percent": 0,
        "evidence_complete": False,
        "evidence_increment_percent": 0,
        "phase": "M4-V2-PREFLIGHT-DESIGN",
    }
    source_fact = next(
        item
        for item in source["facts"]["artifacts"]
        if item.startswith("m4-v2-branch-preflight-source-contract:")
    )
    live["facts"]["artifacts"].remove(source_fact)
    live_by_key = {item["task_key"]: item for item in live["tasks"]}

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(PREFLIGHT_FIXTURE_FREEZE_TASK_KEY,),
        allowlisted_revised_task_keys=(PREFLIGHT_DESIGN_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )

    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [PREFLIGHT_FIXTURE_FREEZE_TASK_KEY]
    assert dry_run["revised_task_keys"] == [PREFLIGHT_DESIGN_TASK_KEY]
    assert dry_run["existing_task_deletions"] == 0
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]
    migrated_by_key = {item["task_key"]: item for item in migrated["tasks"]}
    normalized_live_by_key = {
        item["task_key"]: item
        for item in ControlPlaneManifest.from_dict(live).to_dict()["tasks"]
    }
    for key in live_by_key:
        if key != PREFLIGHT_DESIGN_TASK_KEY:
            assert migrated_by_key[key] == normalized_live_by_key[key]


def test_preflight_completion_projects_next_canonical_consumer() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task_by_key = {item.task_key: item for item in manifest.tasks}
    execution_ids = {
        supervisor_module.M4_V2_DESIGN_TASK_KEY: "1" * 64,
        supervisor_module.M4_V2_DESIGN_REPLAY_TASK_KEY: "2" * 64,
        PREFLIGHT_DESIGN_TASK_KEY: "3" * 64,
    }
    for task in payload["tasks"]:
        if task["task_key"] in execution_ids:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        mainline_completion_fact(
            task=task_by_key[key],
            execution_id=execution_id,
        )
        for key, execution_id in execution_ids.items()
    )
    payload["facts"]["artifacts"].extend(
        (
            DESIGN_COMPLETION_FACT,
            DESIGN_REPLAY_COMPLETION_FACT,
            PREFLIGHT_DESIGN_COMPLETION_FACT,
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "measurement_contract_v2_digest": task_by_key[
                PREFLIGHT_DESIGN_TASK_KEY
            ].input_artifact_digests[0],
            "execution_task_key": PREFLIGHT_DESIGN_TASK_KEY,
            "branch_preflight_design_digests": ["4" * 64] * 3,
            "formal_branch_runs_executed": 0,
            "preflight_result_count": 0,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "PREFLIGHT_FIXTURE_FREEZE"
    assert projection["live_mainline_status"] == (
        "PREFLIGHT_DESIGN_VALIDATED_IN_MAINLINE"
    )
    assert projection["branch_preflight_design"]["design_frozen"] is True
    assert projection["branch_preflight_design"]["branch_design_count"] == 3
    assert projection["next_consumer"] == PREFLIGHT_FIXTURE_FREEZE_TASK_KEY
    assert projection["evidence_progress_increment"] == 0


def test_supervisor_registers_preflight_design_capability() -> None:
    assert PREFLIGHT_DESIGN_TASK_KEY in {
        task.task_key for task in load_m4_manifest(MANIFEST_PATH).tasks
    }
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert supervisor_module.PREFLIGHT_DESIGN_CAPABILITY in supervisor.capabilities
