from __future__ import annotations

import json
import shutil
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2 import (
    marginal_static_repair_v2_health_decision as decision_module,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_decision import (
    EXPECTED_SENSITIVITY_LIMIT_TOPOLOGY,
    MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_PASS_FACT,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
    REQUIRED_GATE_CELL_IDS,
    MarginalStaticRepairV2HealthDecisionError,
    build_marginal_static_repair_v2_health_decision,
    load_marginal_static_repair_v2_health_decision_source_contract,
    repair_v2_health_decision_mapping,
    verify_marginal_static_repair_v2_health_decision_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_execution import (
    MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT,
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
    M4MarginalStaticRepairV2HealthDecisionCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
SOURCE_PATH = ROOT / MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_SOURCE_CONTRACT_PATH


def _copy_source_tree(target_root: Path) -> dict:
    contract = load_marginal_static_repair_v2_health_decision_source_contract(
        SOURCE_PATH
    )
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = (
        target_root / MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_SOURCE_CONTRACT_PATH
    )
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PATH, target_contract)
    return contract


def _task():
    manifest = load_m4_manifest(MANIFEST_PATH)
    return next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY
    )


def _parent_artifacts() -> tuple[dict, dict, dict]:
    execution = {
        "artifact_type": "research_os_mainline_execution",
        "artifact_digest": decision_module.REPAIR_V2_HEALTH_EXECUTION_ARTIFACT_DIGEST,
        "execution_id": decision_module.REPAIR_V2_HEALTH_EXECUTION_ID,
        "task_key": decision_module.REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
        "task_digest": decision_module.REPAIR_V2_HEALTH_EXECUTION_TASK_DIGEST,
        "status": "COMPLETE",
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "completion_fact": decision_module.REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT,
        "repair_v2_health_result_digest": decision_module.REPAIR_V2_HEALTH_RESULT_DIGEST,
        "repair_v2_health_execution_completion_digest": (
            decision_module.REPAIR_V2_HEALTH_COMPLETION_DIGEST
        ),
        "repair_v2_preliminary_measurement_health": "PASS",
        "repair_v2_authoritative_decision": None,
        "duplicate_validation": False,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "production_action": "none",
    }
    cells = []
    for cell_id in REQUIRED_GATE_CELL_IDS:
        role = (
            "LOCAL_POWER"
            if cell_id.startswith("LOCAL_")
            else "POSITIVE_CONTROL"
            if "V2_M1_GROUP" in cell_id
            else "NEGATIVE_CONTROL"
        )
        cells.append(
            {
                "cell": {"cell_id": cell_id, "role": role},
                "required_gate": True,
                "classification": "DETECTABLE" if role == "LOCAL_POWER" else "PASS",
                "detection_rate": 1.0,
                "wilson_lower_95": 0.9,
                "wilson_upper_95": 1.0,
                "gates": {"frozen_required_gate": True},
            }
        )
    for cell_id, topology in EXPECTED_SENSITIVITY_LIMIT_TOPOLOGY.items():
        cells.append(
            {
                "cell": {"cell_id": cell_id, "role": "LOCAL_POWER"},
                "required_gate": False,
                **topology,
                "gates": {"local_admissible": False},
            }
        )
    health = {
        "artifact_type": ("m4_v2_marginal_static_repair_v2_measurement_health_result"),
        "artifact_digest": decision_module.REPAIR_V2_HEALTH_RESULT_DIGEST,
        "status": "COMPLETE_PENDING_DECISION_REPLAY",
        "preliminary_measurement_health": "PASS",
        "authoritative_decision": None,
        "branch_id": "MARGINAL_STATIC",
        "cell_count": 14,
        "negative_control_count": 6,
        "positive_control_count": 2,
        "admissible_local_cell_count": 2,
        "failed_required_gate_cell_ids": [],
        "failed_required_gate_cell_count": 0,
        "all_children_complete": True,
        "all_legal_finite_and_identity_valid": True,
        "familywise_claim_basis": "union_bound_only",
        "cross_cell_independence_claimed": False,
        "manual_override": False,
        "workload_digest": decision_module.REPAIR_V2_WORKLOAD_SEED_DIGEST,
        "inference_digest": decision_module.REPAIR_V2_INFERENCE_GATE_DIGEST,
        "preregistration_digest": decision_module.REPAIR_V2_PREREGISTRATION_DIGEST,
        "completion_index_digest": (
            decision_module.REPAIR_V2_HEALTH_COMPLETION_INDEX_DIGEST
        ),
        "historical_execution_status": "NOT_AUTHORIZED",
        "historical_outcomes_read": False,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
        "cell_results": cells,
    }
    completion = {
        "artifact_type": (
            "m4_v2_marginal_static_repair_v2_health_execution_completion"
        ),
        "artifact_digest": decision_module.REPAIR_V2_HEALTH_COMPLETION_DIGEST,
        "status": "COMPLETE",
        "execution_id": decision_module.REPAIR_V2_HEALTH_EXECUTION_ID,
        "preliminary_measurement_health": "PASS",
        "authoritative_decision": None,
        "health_result_digest": decision_module.REPAIR_V2_HEALTH_RESULT_DIGEST,
        "completion_index_digest": (
            decision_module.REPAIR_V2_HEALTH_COMPLETION_INDEX_DIGEST
        ),
        "completion_fact": decision_module.REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT,
        "duplicate_validation": False,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
    }
    return execution, health, completion


def test_frozen_repair_v2_health_mapping_routes_pass_to_design() -> None:
    assert repair_v2_health_decision_mapping("PASS") == (
        "PASS_TO_HISTORICAL_MEASUREMENT",
        MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_PASS_FACT,
        True,
        MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY,
    )
    assert repair_v2_health_decision_mapping("REPAIR")[2] is False
    assert repair_v2_health_decision_mapping("INCONCLUSIVE")[2] is False
    with pytest.raises(MarginalStaticRepairV2HealthDecisionError, match="unrecognized"):
        repair_v2_health_decision_mapping("TUNE_AND_PASS")


def test_repair_v2_health_decision_source_detects_byte_and_contract_tamper(
    tmp_path: Path,
) -> None:
    contract = _copy_source_tree(tmp_path)
    verify_marginal_static_repair_v2_health_decision_source_bytes(
        root_dir=tmp_path,
        contract=contract,
    )
    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(
        MarginalStaticRepairV2HealthDecisionError,
        match="source_modified",
    ):
        verify_marginal_static_repair_v2_health_decision_source_bytes(
            root_dir=tmp_path,
            contract=contract,
        )

    drifted = deepcopy(contract)
    drifted["frozen_contract"]["duplicate_validation"] = "allowed"
    drifted["artifact_digest"] = "0" * 64
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(
        MarginalStaticRepairV2HealthDecisionError,
        match="source_invalid",
    ):
        load_marginal_static_repair_v2_health_decision_source_contract(drift_path)


def test_exact_repair_v2_result_builds_pass_without_duplicate_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = load_marginal_static_repair_v2_health_decision_source_contract(SOURCE_PATH)
    execution, health, completion = _parent_artifacts()
    monkeypatch.setattr(decision_module, "_verify_artifact", lambda *_, **__: None)
    decision = build_marginal_static_repair_v2_health_decision(
        source_contract=source,
        health_execution=execution,
        health_result=health,
        health_completion=completion,
    )
    assert decision["authoritative_decision"] == "PASS_TO_HISTORICAL_MEASUREMENT"
    assert decision["decision_fact"] == (
        MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_PASS_FACT
    )
    assert decision["required_gate_cell_count"] == 10
    assert decision["sensitivity_limit_cell_count"] == 4
    assert decision["duplicate_validation"] is False
    assert decision["historical_outcomes_read"] is False
    assert decision["evidence_created"] is False
    assert decision["next_consumer"] == (
        MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY
    )


def test_repair_v2_health_decision_capability_and_replay_are_zero_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_tree(tmp_path)
    task = _task()
    expected = task.input_artifact_digests
    health_execution = {"execution_id": "a" * 64, "artifact_digest": expected[1]}
    health_result = {
        "artifact_type": ("m4_v2_marginal_static_repair_v2_measurement_health_result"),
        "artifact_digest": expected[2],
    }
    health_completion = {
        "artifact_type": (
            "m4_v2_marginal_static_repair_v2_health_execution_completion"
        ),
        "artifact_digest": expected[3],
    }
    decision = {
        "schema_version": ("dehps-m4-v2-marginal-static-repair-v2-health-decision.v1"),
        "artifact_type": (
            "m4_v2_marginal_static_measurement_repair_v2_health_decision"
        ),
        "artifact_digest": "b" * 64,
        "measurement_health": "PASS",
        "authoritative_decision": "PASS_TO_HISTORICAL_MEASUREMENT",
        "decision": "PASS_TO_HISTORICAL_MEASUREMENT",
        "decision_fact": MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_PASS_FACT,
        "failed_required_gate_cell_ids": [],
        "failed_required_gate_cell_count": 0,
        "required_gate_cell_ids": list(REQUIRED_GATE_CELL_IDS),
        "required_gate_cell_count": 10,
        "admissible_local_cell_ids": list(decision_module.ADMISSIBLE_LOCAL_CELL_IDS),
        "admissible_local_cell_count": 2,
        "sensitivity_limit_cell_ids": list(EXPECTED_SENSITIVITY_LIMIT_TOPOLOGY),
        "sensitivity_limit_topology": EXPECTED_SENSITIVITY_LIMIT_TOPOLOGY,
        "sensitivity_limit_cell_count": 4,
        "eligible_for_historical_measurement": True,
        "eligible_for_historical_measurement_design": True,
        "next_consumer": MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY,
    }
    parents = {
        "m4_v2_marginal_static_repair_v2_measurement_health_result": health_result,
        "m4_v2_marginal_static_repair_v2_health_execution_completion": (
            health_completion
        ),
        "m4_v2_marginal_static_measurement_repair_v2_health_decision": decision,
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, health_execution, "health-registrations"),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **kwargs: parents[kwargs["artifact_type"]],
    )
    monkeypatch.setattr(
        supervisor_module,
        "build_marginal_static_repair_v2_health_decision",
        lambda **_: decision,
    )
    result = M4MarginalStaticRepairV2HealthDecisionCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )
    assert result.completion_facts == (
        MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_PASS_FACT,
    )
    assert len(result.registrations) == 2
    execution = result.execution_artifact
    assert execution["generated_issues"] == 0
    assert execution["compact_index_reads"] == 0
    assert execution["duplicate_validation"] is False
    assert execution["historical_outcomes_read"] is False
    assert execution["evidence_created"] is False

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "c" * 64,
                    "payload": [
                        [
                            "execution_artifact_path",
                            result.execution_artifact_path.relative_to(
                                tmp_path
                            ).as_posix(),
                        ],
                        ["registered_artifact_count", 2],
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
        task_key=MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
        execution_id="c" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["decision_only"] is True
    assert capability_replay["generated_issues_during_replay"] == 0
    assert capability_replay["duplicate_validation"] is False


def test_additive_repair_v2_health_decision_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    normalized = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live = deepcopy(normalized)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY
    ]
    live_decision = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY
    )
    live_decision.pop("requested_capability")
    live_decision.pop("input_artifact_digests")
    live_decision["dependencies"] = live_decision["dependencies"][:2]
    source_fact = next(
        fact
        for fact in live["facts"]["artifacts"]
        if fact.startswith("m4-v2-marginal-static-repair-v2-health-decision-source:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=normalized,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_repair_v2_health_decision_projects_historical_design_as_next() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    decision_task = next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY
    )
    for task in payload["tasks"]:
        if task["task_key"] == MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT,
            MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_PASS_FACT,
            mainline_completion_fact(task=decision_task, execution_id="e" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
            "execution_artifact_digest": "f" * 64,
            "registered_artifact_count": 2,
            "actual_fold_count": 0,
            "measurement_health": "PASS",
            "authoritative_decision": "PASS_TO_HISTORICAL_MEASUREMENT",
            "decision_fact": MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_PASS_FACT,
            "failed_required_gate_cell_count": 0,
            "required_gate_cell_count": 10,
            "admissible_local_cell_count": 2,
            "sensitivity_limit_cell_ids": list(EXPECTED_SENSITIVITY_LIMIT_TOPOLOGY),
            "sensitivity_limit_cell_count": 4,
            "eligible_for_historical_measurement": True,
            "eligible_for_historical_measurement_design": True,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_VALIDATED_IN_MAINLINE"
    )
    decision = projection["marginal_static_repair_v2_health_decision"]
    assert decision["completed"] is True
    assert decision["measurement_health"] == "PASS"
    assert decision["required_gate_cell_count"] == 10
    assert decision["sensitivity_limit_cell_count"] == 4
    assert decision["eligible_for_historical_measurement_design"] is True
    assert decision["duplicate_validation"] is False
    assert decision["evidence_created"] is False
    assert decision["next_consumer"] == (
        MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY
    )


def test_supervisor_registers_repair_v2_health_decision_capability() -> None:
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert (
        MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_CAPABILITY in supervisor.capabilities
    )
