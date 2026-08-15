from __future__ import annotations

import json
import shutil
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_contract import (
    MARGINAL_STATIC_CONTRACT_FREEZE_CAPABILITY,
    MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT,
    MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY,
    MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
    MARGINAL_STATIC_SOURCE_CONTRACT_PATH,
    MarginalStaticContractError,
    build_marginal_static_contract_artifacts,
    estimate_legal_marginals,
    load_marginal_static_source_contract,
    verify_marginal_static_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.preflight_design import (
    PREFLIGHT_DESIGN_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.preflight_execution import (
    PREFLIGHT_EXECUTION_COMPLETION_FACT,
    PREFLIGHT_EXECUTION_PASS_FACT,
    PREFLIGHT_EXECUTION_TASK_KEY,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    M4MarginalStaticContractFreezeCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
SOURCE_CONTRACT_PATH = ROOT / MARGINAL_STATIC_SOURCE_CONTRACT_PATH


def _copy_source_contract_tree(target_root: Path) -> dict:
    contract = load_marginal_static_source_contract(SOURCE_CONTRACT_PATH)
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = target_root / MARGINAL_STATIC_SOURCE_CONTRACT_PATH
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_CONTRACT_PATH, target_contract)
    return contract


def _inputs() -> tuple[dict, dict, dict, dict, dict, dict]:
    source = load_marginal_static_source_contract(SOURCE_CONTRACT_PATH)
    design = {
        "artifact_type": "m4_v2_branch_identifiability_preflight_design",
        "artifact_digest": "1" * 64,
        "branch_id": "MARGINAL_STATIC",
        "status": "FROZEN_DESIGN",
        "estimand_digest": "2" * 64,
        "historical_outcomes_read": False,
        "evidence_created": False,
    }
    health = {
        "artifact_type": "m4_v2_branch_health_preflight_result",
        "artifact_digest": "3" * 64,
        "branch_id": "MARGINAL_STATIC",
        "branch_design_digest": design["artifact_digest"],
        "status": "PASS",
        "measurement_health": "PASS",
        "decision_credit": False,
        "historical_evidence_eligible": False,
    }
    completion = {
        "artifact_type": "m4_v2_branch_preflight_execution_completion",
        "artifact_digest": "4" * 64,
        "status": "COMPLETE",
        "all_branches_pass": True,
        "all_branches_pass_fact": PREFLIGHT_EXECUTION_PASS_FACT,
        "branch_result_digests": [health["artifact_digest"]],
    }
    legacy_decision = {
        "artifact_type": "marginal_measurement_acceptance_decision",
        "artifact_digest": "5" * 64,
        "branch_id": "MARGINAL_STATIC",
        "measurement_health": "REPAIR",
        "eligible_for_formal_branch_program": False,
        "historical_evidence": "NOT_RUN",
        "historical_run_status": "NOT_RUN",
    }
    legacy_replay = {
        "artifact_type": "branch_decision_replay_attestation",
        "artifact_digest": "6" * 64,
        "branch_id": "MARGINAL_STATIC",
        "status": "REPLAY_VERIFIED",
        "same_decision_content": True,
        "decision_artifact_digest": legacy_decision["artifact_digest"],
    }
    return source, design, health, completion, legacy_decision, legacy_replay


def _build_run() -> object:
    source, design, health, completion, legacy_decision, legacy_replay = _inputs()
    return build_marginal_static_contract_artifacts(
        source_contract=source,
        measurement_contract_v2_digest="7" * 64,
        marginal_branch_design=design,
        preflight_execution_artifact_digest="8" * 64,
        marginal_branch_health=health,
        preflight_completion=completion,
        legacy_marginal_decision=legacy_decision,
        legacy_decision_replay=legacy_replay,
        execution_id="9" * 64,
        git_commit="a" * 40,
    )


def test_legal_marginal_estimator_is_exact_and_deterministic() -> None:
    counts = [164] * 21 + [163] * 12
    first = estimate_legal_marginals(counts, training_issue_count=900)
    second = estimate_legal_marginals(counts, training_issue_count=900)

    assert first == second
    assert len(first) == 33
    assert sum(first) == Fraction(6)
    assert first[0] == (Fraction(164) + Fraction(2, 11)) / 901
    assert all(Fraction(0) < item < Fraction(1) for item in first)

    with pytest.raises(MarginalStaticContractError, match="input_invalid"):
        estimate_legal_marginals(counts[:-1], training_issue_count=900)
    with pytest.raises(MarginalStaticContractError, match="input_invalid"):
        estimate_legal_marginals([0] * 33, training_issue_count=900)


def test_contract_freeze_is_deterministic_and_does_not_override_repair() -> None:
    first = _build_run()
    second = _build_run()

    assert first == second
    assert len(first.artifacts) == 2
    contract = first.measurement_contract
    completion = first.completion
    assert contract["estimator"]["formula"] == "q_i=(c_i+2/11)/(n+1)"
    assert contract["score"]["unit"] == "bits_per_issue"
    assert contract["legacy_measurement_health"] == "REPAIR"
    assert contract["legacy_repair_overridden"] is False
    assert contract["accepted_model_artifact_digest"] is None
    assert contract["sampled_synthetic_execution_status"] == "NOT_AUTHORIZED"
    assert contract["historical_execution_status"] == "NOT_AUTHORIZED"
    assert contract["formal_branch_runs_executed"] == 0
    assert contract["actual_fold_count"] == 0
    assert contract["evidence_created"] is False
    assert completion["completion_fact"] == (
        MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT
    )
    assert completion["next_consumer"] == MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY


def test_contract_freeze_fails_closed_on_legacy_or_preflight_drift() -> None:
    source, design, health, completion, legacy_decision, legacy_replay = _inputs()
    legacy_decision["eligible_for_formal_branch_program"] = True
    with pytest.raises(MarginalStaticContractError, match="input_identity_changed"):
        build_marginal_static_contract_artifacts(
            source_contract=source,
            measurement_contract_v2_digest="7" * 64,
            marginal_branch_design=design,
            preflight_execution_artifact_digest="8" * 64,
            marginal_branch_health=health,
            preflight_completion=completion,
            legacy_marginal_decision=legacy_decision,
            legacy_decision_replay=legacy_replay,
            execution_id="9" * 64,
            git_commit="a" * 40,
        )

    legacy_decision["eligible_for_formal_branch_program"] = False
    health["status"] = "FAIL"
    with pytest.raises(MarginalStaticContractError, match="input_identity_changed"):
        build_marginal_static_contract_artifacts(
            source_contract=source,
            measurement_contract_v2_digest="7" * 64,
            marginal_branch_design=design,
            preflight_execution_artifact_digest="8" * 64,
            marginal_branch_health=health,
            preflight_completion=completion,
            legacy_marginal_decision=legacy_decision,
            legacy_decision_replay=legacy_replay,
            execution_id="9" * 64,
            git_commit="a" * 40,
        )


def test_source_contract_detects_byte_and_contract_tamper(tmp_path: Path) -> None:
    contract = _copy_source_contract_tree(tmp_path)
    verify_marginal_static_source_bytes(root_dir=tmp_path, contract=contract)

    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(MarginalStaticContractError, match="source_modified"):
        verify_marginal_static_source_bytes(root_dir=tmp_path, contract=contract)

    drifted = deepcopy(contract)
    drifted["frozen_contract"]["estimator"]["minimum_training_issues"] = 899
    drifted["artifact_digest"] = "0" * 64
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(MarginalStaticContractError, match="source_contract_invalid"):
        load_marginal_static_source_contract(drift_path)


def test_capability_materializes_three_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_contract_tree(tmp_path)
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY
    )
    _, design, health, completion, legacy_decision, legacy_replay = _inputs()
    expected = task.input_artifact_digests
    design["artifact_digest"] = expected[2]
    health["artifact_digest"] = expected[4]
    health["branch_design_digest"] = expected[2]
    completion["artifact_digest"] = expected[5]
    completion["branch_result_digests"] = [expected[4]]
    legacy_decision["artifact_digest"] = expected[6]
    legacy_replay["artifact_digest"] = expected[7]
    legacy_replay["decision_artifact_digest"] = expected[6]
    preflight_execution = {
        "execution_id": "b" * 64,
        "artifact_digest": expected[3],
        "completion_fact": PREFLIGHT_EXECUTION_COMPLETION_FACT,
        "all_branches_pass": True,
        "all_branches_pass_fact": PREFLIGHT_EXECUTION_PASS_FACT,
        "historical_outcomes_read": False,
        "evidence_created": False,
    }

    def fake_load_parent(**kwargs: object) -> tuple[dict, dict, object]:
        task_key = kwargs["task_key"]
        if task_key == PREFLIGHT_EXECUTION_TASK_KEY:
            return {}, preflight_execution, "preflight"
        if task_key == PREFLIGHT_DESIGN_TASK_KEY:
            return {}, {}, "design"
        if task_key == supervisor_module.M4_V2_MARGINAL_BINDING_TASK_KEY:
            return {}, {}, "binding"
        assert task_key == supervisor_module.M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY
        return {}, {}, "replay"

    def fake_registered_group(**kwargs: object) -> tuple[dict, ...]:
        return (health,) if kwargs["registrations"] == "preflight" else (design,)

    def fake_registered_type(**kwargs: object) -> dict:
        return {
            "m4_v2_branch_preflight_execution_completion": completion,
            "marginal_measurement_acceptance_decision": legacy_decision,
            "branch_decision_replay_attestation": legacy_replay,
        }[kwargs["artifact_type"]]

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        fake_load_parent,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type_group",
        fake_registered_group,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        fake_registered_type,
    )
    result = M4MarginalStaticContractFreezeCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )

    assert result.completion_facts == (
        MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT,
    )
    assert len(result.registrations) == 3
    assert result.execution_artifact["registered_artifact_count"] == 3
    assert result.execution_artifact["actual_fold_count"] == 0
    assert result.execution_artifact["synthetic_replicates"] == 0
    assert result.execution_artifact["historical_execution_status"] == (
        "NOT_AUTHORIZED"
    )
    assert result.execution_artifact["legacy_repair_overridden"] is False


def test_additive_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    live = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY
    ]
    live_contract = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY
    )
    live_contract.pop("requested_capability")
    live_contract.pop("input_artifact_digests")
    live_contract["dependencies"] = live_contract["dependencies"][:2]
    live_contract["metric_contract"] = {
        key: value
        for key, value in live_contract["metric_contract"].items()
        if key not in {"mainline_integration", "synthetic_replicates"}
    }
    source_fact = next(
        item
        for item in source["facts"]["artifacts"]
        if item.startswith("m4-v2-marginal-static-contract-freeze-source:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,),
        allowlisted_revised_task_keys=(MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )

    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY]
    assert dry_run["revised_task_keys"] == [
        MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY
    ]
    assert dry_run["existing_task_deletions"] == 0
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_completion_projects_fixture_freeze_as_only_next_consumer() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    marginal_task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY
    )
    for task in payload["tasks"]:
        if task["task_key"] == MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].append(
        MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT
    )
    payload["facts"]["artifacts"].append(
        mainline_completion_fact(task=marginal_task, execution_id="e" * 64)
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY,
            "execution_artifact_digest": "e" * 64,
            "registered_artifact_count": 3,
            "actual_fold_count": 0,
            "marginal_static_measurement_contract_digest": "f" * 64,
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "identifiability_preflight_status": "PASS",
        },
    )
    projection = status["measurement_system_v2"]

    assert projection["phase"] == "MARGINAL_STATIC_FIXTURE_FREEZE"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_CONTRACT_VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY
    contract = projection["marginal_static_contract_freeze"]
    assert contract["completed"] is True
    assert contract["legacy_measurement_health"] == "REPAIR"
    assert contract["legacy_repair_overridden"] is False
    assert contract["historical_execution_status"] == "NOT_AUTHORIZED"
    assert contract["evidence_progress_increment"] == 0


def test_supervisor_registers_marginal_static_contract_capability() -> None:
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert MARGINAL_STATIC_CONTRACT_FREEZE_CAPABILITY in supervisor.capabilities
