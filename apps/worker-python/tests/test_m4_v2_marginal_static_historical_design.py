from __future__ import annotations

import json
import shutil
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2 import (
    marginal_static_historical_design as design_module,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_design import (
    EVALUATION_FOLD_COUNT,
    HISTORICAL_ISSUE_COUNT,
    INITIAL_TRAINING_ISSUES,
    MARGINAL_STATIC_HISTORICAL_DESIGN_CAPABILITY,
    MARGINAL_STATIC_HISTORICAL_DESIGN_COMPLETION_FACT,
    MARGINAL_STATIC_HISTORICAL_DESIGN_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY,
    MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY,
    MarginalStaticHistoricalDesignError,
    build_marginal_static_historical_design_artifacts,
    load_marginal_static_historical_design_source_contract,
    validate_fold_boundary,
    verify_marginal_static_historical_design_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest, TaskStatus
from dehps.research_os.supervisor import (
    M4MarginalStaticHistoricalDesignCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = ROOT / "configs/research-os/m4-information-theory-artifact-index-v1.json"
SOURCE_PATH = ROOT / MARGINAL_STATIC_HISTORICAL_DESIGN_SOURCE_CONTRACT_PATH


def _copy_source_tree(target_root: Path) -> dict:
    contract = load_marginal_static_historical_design_source_contract(SOURCE_PATH)
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = (
        target_root / MARGINAL_STATIC_HISTORICAL_DESIGN_SOURCE_CONTRACT_PATH
    )
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PATH, target_contract)
    preregistration = target_root / design_module.FROZEN_PREREGISTRATION_PATH
    preregistration.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / design_module.FROZEN_PREREGISTRATION_PATH, preregistration)
    return contract


def _task():
    manifest = load_m4_manifest(MANIFEST_PATH)
    return next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY
    )


def _parents() -> dict[str, dict]:
    health_execution = {
        "artifact_type": "research_os_mainline_execution",
        "artifact_digest": design_module.REPAIR_V2_HEALTH_DECISION_EXECUTION_DIGEST,
        "execution_id": design_module.REPAIR_V2_HEALTH_DECISION_EXECUTION_ID,
        "task_key": design_module.REPAIR_V2_HEALTH_DECISION_TASK_KEY,
        "status": "COMPLETE",
        "completion_classification": "VALIDATED_IN_MAINLINE",
    }
    health_decision = {
        "artifact_type": (
            "m4_v2_marginal_static_measurement_repair_v2_health_decision"
        ),
        "artifact_digest": design_module.REPAIR_V2_HEALTH_DECISION_DIGEST,
        "authoritative_decision": "PASS_TO_HISTORICAL_MEASUREMENT",
        "measurement_health": "PASS",
        "eligible_for_historical_measurement_design": True,
        "historical_outcomes_read": False,
        "evidence_created": False,
    }
    marginal_execution = {
        "artifact_type": "research_os_mainline_execution",
        "artifact_digest": design_module.MARGINAL_STATIC_CONTRACT_EXECUTION_DIGEST,
        "execution_id": design_module.MARGINAL_STATIC_CONTRACT_EXECUTION_ID,
        "task_key": design_module.MARGINAL_STATIC_CONTRACT_TASK_KEY,
    }
    marginal_contract = {
        "artifact_type": "m4_v2_marginal_static_measurement_contract",
        "artifact_digest": design_module.MARGINAL_STATIC_MEASUREMENT_CONTRACT_DIGEST,
        "estimator": {
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "minimum_training_issues": INITIAL_TRAINING_ISSUES,
            "formula": "q_i=(c_i+2/11)/(n+1)",
            "exact_sum_identity": "sum_i q_i=(6*n+6)/(n+1)=6",
        },
        "score": {"baseline_q_i": "2/11", "unit": "bits_per_issue"},
    }
    measurement_execution = {
        "artifact_type": "research_os_mainline_execution",
        "artifact_digest": design_module.MEASUREMENT_CONTRACT_DESIGN_EXECUTION_DIGEST,
        "execution_id": design_module.MEASUREMENT_CONTRACT_DESIGN_EXECUTION_ID,
        "task_key": design_module.MEASUREMENT_CONTRACT_DESIGN_TASK_KEY,
    }
    gate_compiler = {
        "artifact_type": "measurement_v2_gate_compiler_contract",
        "artifact_digest": design_module.GATE_COMPILER_CONTRACT_DIGEST,
        "gate_compiler_contract": {
            "practical_threshold_bits_per_issue": 0.01,
            "multiplicity": {
                "family": "fixed_three_primary_branch_endpoints",
                "method": "HOLM",
            },
        },
    }
    preregistration = json.loads(
        (ROOT / design_module.FROZEN_PREREGISTRATION_PATH).read_text(encoding="utf-8")
    )
    return {
        "health-execution": health_execution,
        health_decision["artifact_type"]: health_decision,
        "marginal-execution": marginal_execution,
        marginal_contract["artifact_type"]: marginal_contract,
        "measurement-execution": measurement_execution,
        gate_compiler["artifact_type"]: gate_compiler,
        "preregistration": preregistration,
    }


def _build(*, execution_id: str = "a" * 64, git_commit: str = "b" * 40):
    parents = _parents()
    return build_marginal_static_historical_design_artifacts(
        source_contract=load_marginal_static_historical_design_source_contract(
            SOURCE_PATH
        ),
        repair_v2_health_decision_execution=parents["health-execution"],
        repair_v2_health_decision=parents[
            "m4_v2_marginal_static_measurement_repair_v2_health_decision"
        ],
        marginal_static_contract_execution=parents["marginal-execution"],
        marginal_static_measurement_contract=parents[
            "m4_v2_marginal_static_measurement_contract"
        ],
        measurement_contract_design_execution=parents["measurement-execution"],
        gate_compiler_contract=parents["measurement_v2_gate_compiler_contract"],
        frozen_preregistration=parents["preregistration"],
        execution_id=execution_id,
        git_commit=git_commit,
    )


def test_source_contract_detects_byte_and_contract_tamper(tmp_path: Path) -> None:
    contract = _copy_source_tree(tmp_path)
    verify_marginal_static_historical_design_source_bytes(
        root_dir=tmp_path,
        contract=contract,
    )
    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(MarginalStaticHistoricalDesignError, match="source_modified"):
        verify_marginal_static_historical_design_source_bytes(
            root_dir=tmp_path,
            contract=contract,
        )

    drifted = deepcopy(contract)
    drifted["frozen_contract"]["historical_execution_authorized"] = True
    drifted["artifact_digest"] = "0" * 64
    path = tmp_path / "drifted.json"
    path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(MarginalStaticHistoricalDesignError, match="source_invalid"):
        load_marginal_static_historical_design_source_contract(path)


def test_design_freezes_strict_prior_boundary_and_issue_cluster_inference() -> None:
    run = _build()
    boundary = run.dataset_boundary["historical_boundary"]
    walk = run.walk_forward_design["walk_forward"]
    inference = run.inference_design["inference"]
    stability = run.inference_design["time_stability"]
    controls = run.inference_design["controls_and_invariants"]

    assert boundary["issue_count"] == HISTORICAL_ISSUE_COUNT
    assert boundary["post_cutoff_rows_excluded_at_design"] == 6
    assert boundary["design_red_numbers_read"] is False
    assert walk["initial_training_ordinals"] == [1, 900]
    assert walk["evaluation_ordinals"] == [901, 3481]
    assert walk["evaluation_fold_count"] == EVALUATION_FOLD_COUNT
    assert inference["resampling_unit"] == "issue-level settled score difference"
    assert inference["bootstrap_replicates"] == 2000
    assert [item["issue_count"] for item in stability["primary_halves"]] == [
        1291,
        1290,
    ]
    assert [item["issue_count"] for item in stability["thirds_sensitivity"]] == [
        861,
        860,
        860,
    ]
    assert controls["global_number_relabeling"].endswith("no decision credit")
    assert run.completion["formal_historical_folds_executed"] == 0
    assert run.completion["database_queries_during_capability"] == 0
    assert run.completion["historical_red_outcomes_read"] is False
    assert run.completion["statistical_results_read"] is False
    assert run.completion["evidence_created"] is False
    assert run.completion["next_consumer"] == (
        MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
    )
    assert _build().artifacts == run.artifacts


def test_fold_boundary_rejects_current_future_and_post_cutoff_access() -> None:
    validate_fold_boundary(training_end_ordinal=900, test_ordinal=901)
    validate_fold_boundary(training_end_ordinal=3480, test_ordinal=3481)
    for training_end, test in ((900, 900), (900, 902), (3481, 3482), (899, 900)):
        with pytest.raises(MarginalStaticHistoricalDesignError, match="boundary"):
            validate_fold_boundary(
                training_end_ordinal=training_end,
                test_ordinal=test,
            )


def test_capability_and_replay_are_result_blind_design_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_tree(tmp_path)
    task = _task()
    parents = _parents()
    parent_executions = {
        design_module.REPAIR_V2_HEALTH_DECISION_TASK_KEY: parents["health-execution"],
        design_module.MARGINAL_STATIC_CONTRACT_TASK_KEY: parents["marginal-execution"],
        design_module.MEASUREMENT_CONTRACT_DESIGN_TASK_KEY: parents[
            "measurement-execution"
        ],
    }
    parent_registration_keys = {
        design_module.REPAIR_V2_HEALTH_DECISION_TASK_KEY: "health-registrations",
        design_module.MARGINAL_STATIC_CONTRACT_TASK_KEY: "marginal-registrations",
        design_module.MEASUREMENT_CONTRACT_DESIGN_TASK_KEY: (
            "measurement-registrations"
        ),
    }
    original_load_registered_type = supervisor_module._load_registered_type

    def load_execution(**kwargs):
        key = kwargs["task_key"]
        return {}, parent_executions[key], parent_registration_keys[key]

    typed_parents = {
        "m4_v2_marginal_static_measurement_repair_v2_health_decision": parents[
            "m4_v2_marginal_static_measurement_repair_v2_health_decision"
        ],
        "m4_v2_marginal_static_measurement_contract": parents[
            "m4_v2_marginal_static_measurement_contract"
        ],
        "measurement_v2_gate_compiler_contract": parents[
            "measurement_v2_gate_compiler_contract"
        ],
    }

    def load_registered_type(**kwargs):
        if isinstance(kwargs["registrations"], str):
            return typed_parents[kwargs["artifact_type"]]
        return original_load_registered_type(**kwargs)

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        load_execution,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        load_registered_type,
    )
    result = M4MarginalStaticHistoricalDesignCapability(
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
        MARGINAL_STATIC_HISTORICAL_DESIGN_COMPLETION_FACT,
    )
    assert len(result.registrations) == 5
    assert execution["historical_issue_count"] == 3481
    assert execution["planned_evaluation_fold_count"] == 2581
    assert execution["formal_historical_folds_executed"] == 0
    assert execution["database_queries_during_capability"] == 0
    assert execution["historical_red_outcomes_read"] is False
    assert execution["statistical_results_read"] is False
    assert execution["evidence_created"] is False
    assert execution["promotion_gate_opened"] is False

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
        task_key=MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY,
        execution_id="c" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["design_only"] is True
    assert capability_replay["formal_historical_folds_executed"] == 0
    assert capability_replay["database_queries_during_replay"] == 0
    assert capability_replay["historical_red_outcomes_read"] is False
    assert capability_replay["evidence_created"] is False


def test_additive_migration_revises_one_task_and_adds_one_task() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    normalized = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live = deepcopy(normalized)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
    ]
    live_design = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY
    )
    live_design.pop("requested_capability")
    live_design.pop("input_artifact_digests")
    live_design["metric_contract"]["engineering_complete"] = False
    live_design["metric_contract"]["engineering_increment_percent"] = 0
    source_fact = next(
        fact
        for fact in live["facts"]["artifacts"]
        if fact.startswith("m4-v2-marginal-static-historical-design-source:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=normalized,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_status_projects_design_completion_to_separate_preregistration() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    design_task = next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY
    )
    for task in payload["tasks"]:
        if task["task_key"] == MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_HISTORICAL_DESIGN_COMPLETION_FACT,
            mainline_completion_fact(task=design_task, execution_id="e" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY,
            "execution_artifact_digest": "f" * 64,
            "registered_artifact_count": 5,
            "actual_fold_count": 0,
            "historical_dataset_boundary_digest": "1" * 64,
            "historical_walk_forward_design_digest": "2" * 64,
            "historical_inference_design_digest": "3" * 64,
            "historical_evidence": "NOT_RUN",
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == (
        "MARGINAL_STATIC_HISTORICAL_MEASUREMENT_PREREGISTRATION"
    )
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_HISTORICAL_DESIGN_VALIDATED_IN_MAINLINE"
    )
    design = projection["marginal_static_historical_measurement_design"]
    assert design["completed"] is True
    assert design["planned_evaluation_fold_count"] == 2581
    assert design["formal_historical_folds_executed"] == 0
    assert design["historical_red_outcomes_read"] is False
    assert design["evidence_created"] is False
    assert projection["next_consumer"] == (
        MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
    )


def test_artifact_index_and_supervisor_register_historical_design() -> None:
    source = load_marginal_static_historical_design_source_contract(SOURCE_PATH)
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    entry = index[source["artifact_digest"]]
    assert entry["path"] == str(SOURCE_PATH.relative_to(ROOT))
    assert entry["identity_field"] == "artifact_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert MARGINAL_STATIC_HISTORICAL_DESIGN_CAPABILITY in supervisor.capabilities


def test_latest_v2_summary_loads_registered_historical_design_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Resolution:
        task_key = MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY
        status = TaskStatus.COMPLETED

    execution = {
        "artifact_digest": "1" * 64,
        "historical_dataset_boundary_digest": "2" * 64,
        "historical_walk_forward_design_digest": "3" * 64,
        "historical_inference_design_digest": "4" * 64,
        "historical_design_completion_digest": "5" * 64,
        "formal_historical_folds_executed": 0,
        "historical_red_outcomes_read": False,
        "statistical_results_read": False,
        "evidence_created": False,
    }
    event = {
        "payload": [
            ["execution_artifact_digest", "1" * 64],
            ["registered_artifact_count", 5],
            ["actual_fold_count", 0],
        ]
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: (event, execution, ()),
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    summary = supervisor._latest_completed_v2_summary(
        type("Snapshot", (), {"resolutions": [Resolution()]})()
    )
    assert summary is not None
    assert summary["execution_task_key"] == (MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY)
    assert summary["execution_artifact_digest"] == "1" * 64
    assert summary["historical_dataset_boundary_digest"] == "2" * 64
    assert summary["historical_walk_forward_design_digest"] == "3" * 64
    assert summary["historical_inference_design_digest"] == "4" * 64
    assert summary["registered_artifact_count"] == 5


def test_latest_v2_summary_orders_repair_v2_decision_before_execution() -> None:
    decision_key = design_module.REPAIR_V2_HEALTH_DECISION_TASK_KEY
    execution_key = "m4-v2-marginal-static-measurement-repair-v2-health-execution"

    class Repository:
        def __init__(self) -> None:
            self.requested: list[str] = []

        def list_mainline_execution_events(self, **kwargs) -> list[dict]:
            key = kwargs["task_key"]
            self.requested.append(key)
            return [
                {
                    "event_type": "completed",
                    "payload": [["execution_artifact_digest", "6" * 64]],
                }
            ]

    resolutions = [
        type(
            "Resolution",
            (),
            {"task_key": decision_key, "status": TaskStatus.COMPLETED},
        )(),
        type(
            "Resolution",
            (),
            {"task_key": execution_key, "status": TaskStatus.COMPLETED},
        )(),
    ]
    repository = Repository()
    summary = ResearchEvidenceSupervisor(
        repository=repository,
        require_clean_tree=False,
    )._latest_completed_v2_summary(type("Snapshot", (), {"resolutions": resolutions})())
    assert summary is not None
    assert summary["execution_task_key"] == decision_key
    assert repository.requested == [decision_key]
