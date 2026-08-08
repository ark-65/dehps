from __future__ import annotations

import json
import shutil
from copy import deepcopy
from dataclasses import asdict
from math import comb
from pathlib import Path

import numpy as np
import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_decision import (
    EXPECTED_FAILED_GATE_MAP,
    MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_design import (
    HEALTH_DECISION_ARTIFACT_DIGEST,
    HEALTH_DECISION_EXECUTION_ARTIFACT_DIGEST,
    HEALTH_DECISION_EXECUTION_ID,
    HEALTH_DECISION_TASK_KEY,
    HEALTH_RESULT_DIGEST,
    MARGINAL_STATIC_REPAIR_DESIGN_CAPABILITY,
    MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_DESIGN_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
    MarginalStaticRepairDesignError,
    build_marginal_static_repair_design_artifacts,
    load_marginal_static_repair_design_source_contract,
    verify_marginal_static_repair_design_source_bytes,
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
    M4MarginalStaticRepairDesignCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
SOURCE_PATH = ROOT / MARGINAL_STATIC_REPAIR_DESIGN_SOURCE_CONTRACT_PATH


def _copy_source_tree(target_root: Path) -> dict:
    contract = load_marginal_static_repair_design_source_contract(SOURCE_PATH)
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = target_root / MARGINAL_STATIC_REPAIR_DESIGN_SOURCE_CONTRACT_PATH
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PATH, target_contract)
    return contract


def _task():
    manifest = load_m4_manifest(MANIFEST_PATH)
    return next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY
    )


def _parents() -> tuple[dict, dict]:
    decision_execution = {
        "execution_id": HEALTH_DECISION_EXECUTION_ID,
        "artifact_digest": HEALTH_DECISION_EXECUTION_ARTIFACT_DIGEST,
        "task_key": HEALTH_DECISION_TASK_KEY,
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "decision": "REPAIR_MEASUREMENT_SYSTEM",
        "decision_fact": MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT,
        "duplicate_validation": False,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "promotion_gate_opened": False,
    }
    decision = {
        "artifact_type": "m4_v2_marginal_static_measurement_health_decision",
        "artifact_digest": HEALTH_DECISION_ARTIFACT_DIGEST,
        "health_result_digest": HEALTH_RESULT_DIGEST,
        "measurement_health": "REPAIR",
        "decision": "REPAIR_MEASUREMENT_SYSTEM",
        "decision_fact": MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT,
        "failed_cell_ids": list(EXPECTED_FAILED_GATE_MAP),
        "failed_cell_count": 4,
        "failed_gate_map": {
            key: list(value) for key, value in EXPECTED_FAILED_GATE_MAP.items()
        },
        "threshold_changed": False,
        "manual_override": False,
        "duplicate_validation": False,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
    }
    return decision_execution, decision


def _masses(odds: float) -> np.ndarray:
    values = np.asarray(
        [comb(16, k) * comb(17, 6 - k) * odds**k for k in range(7)],
        dtype=np.float64,
    )
    return values / np.sum(values)


def _sum_distribution(values: np.ndarray, count: int) -> np.ndarray:
    result = np.asarray([1.0])
    base = values
    exponent = count
    while exponent:
        if exponent & 1:
            result = np.convolve(result, base)
        exponent //= 2
        if exponent:
            base = np.convolve(base, base)
    result = np.maximum(result, 0.0)
    return result / np.sum(result)


def _exact_randomized_np_power(odds: float, count: int) -> float:
    null = _sum_distribution(_masses(1.0), count)
    alternative = _sum_distribution(_masses(odds), count)
    null_tail = np.cumsum(null[::-1])[::-1]
    alternative_tail = np.cumsum(alternative[::-1])[::-1]
    threshold = int(np.flatnonzero(null_tail <= 0.05)[0])
    randomization = (0.05 - null_tail[threshold]) / null[threshold - 1]
    return float(
        alternative_tail[threshold]
        + randomization * alternative[threshold - 1]
    )


def test_source_contract_and_exact_forward_feasibility_are_frozen(
    tmp_path: Path,
) -> None:
    contract = _copy_source_tree(tmp_path)
    verify_marginal_static_repair_design_source_bytes(
        root_dir=tmp_path,
        contract=contract,
    )
    frozen = contract["frozen_contract"]
    assert _exact_randomized_np_power(1.1085745296098741, 61) == pytest.approx(
        frozen["analytic_power_feasibility"]["forward_61"]["0.010"],
        abs=2e-15,
    )
    assert _exact_randomized_np_power(1.2594098354832832, 61) == pytest.approx(
        frozen["analytic_power_feasibility"]["forward_61"]["0.050"],
        abs=2e-15,
    )
    assert frozen["analytic_power_feasibility"]["forward_61"]["0.010"] < 0.8
    assert frozen["analytic_power_feasibility"]["forward_61"]["0.050"] < 0.95

    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(MarginalStaticRepairDesignError, match="source_modified"):
        verify_marginal_static_repair_design_source_bytes(
            root_dir=tmp_path,
            contract=contract,
        )


def test_repair_design_preserves_old_repair_and_performs_zero_validation() -> None:
    contract = load_marginal_static_repair_design_source_contract(SOURCE_PATH)
    decision_execution, decision = _parents()
    run = build_marginal_static_repair_design_artifacts(
        source_contract=contract,
        health_decision_execution=decision_execution,
        health_decision=decision,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )
    assert run.feasibility["forward_61_gate_admissible"] == {
        "0.010": False,
        "0.050": False,
    }
    assert run.repair_design["old_decision_preserved"] == (
        "REPAIR_MEASUREMENT_SYSTEM"
    )
    assert run.repair_design["automatic_pass_from_reanalysis"] is False
    assert run.repair_design["seed_contract"]["round_42_seed_reuse"] is False
    for artifact in run.artifacts:
        assert artifact["generated_issues"] == 0
        assert artifact["synthetic_replicates"] == 0
        assert artifact["checkpoint_reads"] == 0
        assert artifact["duplicate_validation"] is False
        assert artifact["historical_outcomes_read"] is False
        assert artifact["evidence_created"] is False
        assert artifact["production_action"] == "none"


def test_capability_and_replay_reconstruct_design_without_old_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_tree(tmp_path)
    task = _task()
    decision_execution, decision = _parents()
    parent_by_type = {
        "m4_v2_marginal_static_measurement_health_decision": decision,
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, decision_execution, "decision-registrations"),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **kwargs: parent_by_type[kwargs["artifact_type"]],
    )
    result = M4MarginalStaticRepairDesignCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )
    assert result.completion_facts == (
        MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_FACT,
    )
    assert len(result.registrations) == 4
    execution = result.execution_artifact
    assert execution["registered_artifact_count"] == 4
    assert execution["generated_issues"] == 0
    assert execution["synthetic_replicates"] == 0
    assert execution["checkpoint_reads"] == 0
    assert execution["duplicate_validation"] is False
    assert execution["round_42_seed_reuse"] is False
    assert execution["automatic_pass_from_reanalysis"] is False
    assert execution["downstream_consumer"] == (
        MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
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
                    "execution_id": "c" * 64,
                    "payload": [
                        [
                            "execution_artifact_path",
                            result.execution_artifact_path.relative_to(
                                tmp_path
                            ).as_posix(),
                        ],
                        ["registered_artifact_count", 4],
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
        task_key=MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,
        execution_id="c" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["design_only"] is True
    assert capability_replay["generated_issues_during_replay"] == 0
    assert capability_replay["synthetic_replicates_during_replay"] == 0
    assert capability_replay["checkpoint_reads"] == 0
    assert capability_replay["duplicate_validation"] is False


def test_additive_repair_design_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    normalized = ControlPlaneManifest.from_dict(source).to_dict(
        include_digest=False
    )
    live = deepcopy(normalized)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
    ]
    live_repair = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY
    )
    live_repair.pop("requested_capability")
    live_repair.pop("input_artifact_digests")
    live_repair["dependencies"] = live_repair["dependencies"][:2]
    source_fact = next(
        fact
        for fact in live["facts"]["artifacts"]
        if fact.startswith("m4-v2-marginal-static-repair-design-source:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=normalized,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_completed_repair_design_projects_only_preregistration_ready() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    repair_task = next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY
    )
    decision_task = next(
        task for task in manifest.tasks if task.task_key == HEALTH_DECISION_TASK_KEY
    )
    for task in payload["tasks"]:
        if task["task_key"] in {
            HEALTH_DECISION_TASK_KEY,
            MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,
        }:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT,
            MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_FACT,
            mainline_completion_fact(task=decision_task, execution_id="d" * 64),
            mainline_completion_fact(task=repair_task, execution_id="e" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,
            "execution_artifact_digest": "f" * 64,
            "registered_artifact_count": 4,
            "actual_fold_count": 0,
            "forward_61_classification": "ANALYTICALLY_INFEASIBLE",
            "marginal_static_repair_analytic_feasibility_digest": "1" * 64,
            "marginal_static_repair_design_artifact_digest": "2" * 64,
            "marginal_static_repair_design_completion_digest": "3" * 64,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "MARGINAL_STATIC_REPAIR_PREREGISTRATION"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_REPAIR_DESIGN_VALIDATED_IN_MAINLINE"
    )
    repair = projection["marginal_static_repair_design"]
    assert repair["completed"] is True
    assert repair["forward_61_classification"] == "ANALYTICALLY_INFEASIBLE"
    assert repair["generated_issues"] == 0
    assert repair["duplicate_validation"] is False
    prereg = projection["marginal_static_repair_preregistration"]
    assert prereg["resolver_status"] == "ready"


def test_supervisor_registers_repair_design_capability() -> None:
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert MARGINAL_STATIC_REPAIR_DESIGN_CAPABILITY in supervisor.capabilities
