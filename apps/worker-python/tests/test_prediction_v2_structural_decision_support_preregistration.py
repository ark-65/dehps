from __future__ import annotations

import copy
import json
import shutil
from dataclasses import asdict, replace

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_gate import (
    MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
    MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_forward_evidence_or_pivot_planner import (
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT,
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_promotion_planner import (
    PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
    PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_decision_support_design import (
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
    build_prediction_v2_structural_design_artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_decision_support_preregistration import (
    MINIMUM_STRICTLY_DOMINATED_NULLS,
    NULL_REPLICATE_COUNT,
    OPTIMIZER_ISLAND_COUNT,
    OPTIMIZER_NAME,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_CAPABILITY,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
    PRIMARY_CANDIDATE_BUDGET,
    PredictionV2StructuralPreregistrationError,
    build_prediction_v2_structural_preregistration_artifacts,
    load_prediction_v2_structural_preregistration_source_contract,
    verify_prediction_v2_structural_preregistration_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    PredictionV2StructuralDecisionSupportPreregistrationCapability,
    ResearchEvidenceSupervisor,
)
from test_prediction_v2_structural_decision_support_design import (
    _inputs as _design_inputs,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)


def _seal(payload: dict, *, domain: str) -> dict:
    value = dict(payload)
    value["artifact_digest"] = ""
    identity = dict(value)
    identity.pop("artifact_digest")
    value["artifact_digest"] = canonical_digest(identity, domain=domain)
    return value


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list | tuple):
        return any(_contains_key(item, key) for item in value)
    return False


def _design_summaries() -> tuple[dict, object]:
    design = build_prediction_v2_structural_design_artifacts(
        **_design_inputs(),
        require_registered_identities=False,
    )
    execution = _seal(
        {
            "artifact_type": "research_os_mainline_execution",
            "task_key": PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "registered_artifact_count": 4,
            "completion_fact": (
                PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT
            ),
            "structural_design_contract_digest": design.design_contract[
                "artifact_digest"
            ],
            "structural_preregistration_handoff_digest": (
                design.preregistration_handoff["artifact_digest"]
            ),
            "structural_design_completion_digest": design.completion["artifact_digest"],
            "downstream_consumer": (
                PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
            ),
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "candidate_portfolios_generated": 0,
            "optimizers_executed": 0,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "formal_historical_folds_executed": 0,
            "bootstrap_children_executed": 0,
            "evidence_created": False,
            "new_model_created": False,
            "structural_algorithm_implemented": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return execution, design


def _inputs() -> dict:
    execution, design = _design_summaries()
    return {
        "source_contract": (
            load_prediction_v2_structural_preregistration_source_contract(
                ROOT_DIR
                / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE_CONTRACT_PATH
            )
        ),
        "design_execution": execution,
        "design_contract": design.design_contract,
        "design_handoff": design.preregistration_handoff,
        "design_completion": design.completion,
    }


def test_source_contract_freezes_all_choices_without_validation_path() -> None:
    source = load_prediction_v2_structural_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_structural_preregistration_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    assert not _contains_key(source, "duplicate_validation")
    frozen = source["frozen_contract"]
    execution = frozen["execution_contract"]
    assert execution["primary_candidate_budget"]["B"] == PRIMARY_CANDIDATE_BUDGET
    assert execution["optimizer"]["name"] == OPTIMIZER_NAME
    assert execution["optimizer"]["island_count"] == OPTIMIZER_ISLAND_COUNT
    assert execution["null_baseline"]["replicate_count"] == NULL_REPLICATE_COUNT
    assert execution["exactness"]["comparison_tolerance"] == 0
    assert frozen["arithmetic_proof"]["simultaneous_minimum_budget"] == 176
    assert frozen["arithmetic_proof"]["target_singleton_count"] == 32
    assert frozen["arithmetic_proof"]["target_pair_count"] == 5


def test_builder_emits_frozen_exact_contract_without_executing_it() -> None:
    run = build_prediction_v2_structural_preregistration_artifacts(
        **_inputs(),
        require_registered_identities=False,
    )
    assert len(run.artifacts) == 3
    assert not _contains_key(run.artifacts, "duplicate_validation")
    preregistration = run.preregistration
    frozen = preregistration["execution_contract"]
    acceptance = frozen["structural_only_acceptance"]
    assert preregistration["contract_status"] == "FROZEN"
    assert frozen["optimizer"]["total_proposals"] == 5_767_168
    assert acceptance["minimum_strictly_dominated_null_replicates"] == (
        MINIMUM_STRICTLY_DOMINATED_NULLS
    )
    assert acceptance["maximum_null_replicates_strictly_dominating_candidate"] == 0
    assert all(item["candidate_portfolios_generated"] == 0 for item in run.artifacts)
    assert all(item["optimizer_proposals_executed"] == 0 for item in run.artifacts)
    assert all(item["null_replicates_executed"] == 0 for item in run.artifacts)
    assert run.execution_handoff["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
    )


def test_builder_fails_closed_on_design_execution_tamper() -> None:
    inputs = _inputs()
    execution = copy.deepcopy(inputs["design_execution"])
    execution["candidate_portfolios_generated"] = 1
    inputs["design_execution"] = _seal(
        {key: value for key, value in execution.items() if key != "artifact_digest"},
        domain="dehps.research-os.mainline-execution.v1",
    )
    with pytest.raises(
        PredictionV2StructuralPreregistrationError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_structural_preregistration_artifacts(
            **inputs,
            require_registered_identities=False,
        )


def test_additive_migration_revises_preregistration_and_adds_only_execution() -> None:
    source_payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_payload.pop("manifest_digest")
    source = ControlPlaneManifest.from_dict(source_payload).to_dict(
        include_digest=False
    )
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
    ]
    preregistration = next(
        item
        for item in live["tasks"]
        if item["task_key"]
        == PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
    )
    preregistration["requested_capability"] = None
    preregistration["input_artifact_digests"] = []
    preregistration["metric_contract"]["engineering_complete"] = False
    preregistration["metric_contract"]["engineering_increment_percent"] = 0
    source_contract = load_prediction_v2_structural_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    source_fact = (
        "prediction-v2-structural-preregistration-source:"
        f"{source_contract['artifact_digest']}"
    )
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert len(migrated["tasks"]) == len(live["tasks"]) + 1
    assert source_fact in migrated["facts"]["artifacts"]


def test_status_routes_completed_preregistration_to_structural_execution() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task_keys = (
        MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
        PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY,
    )
    tasks = {item.task_key: item for item in manifest.tasks}
    for item in payload["tasks"]:
        if item["task_key"] in task_keys:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
            "m4-v2-marginal-static-historical-evidence:INCONCLUSIVE",
            PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
            PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT,
            PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT,
            PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_COMPLETION_FACT,
            *(
                mainline_completion_fact(task=tasks[key], execution_id=char * 64)
                for key, char in zip(task_keys, "efdc9", strict=True)
            ),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": (
                PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
            ),
            "historical_evidence": "INCONCLUSIVE",
            "selected_program": "STRUCTURAL_DECISION_SUPPORT_PIVOT",
            "prediction_research_disposition": (
                "FROZEN_PENDING_STRUCTURAL_PORTFOLIO_EXECUTION"
            ),
            "primary_candidate_budget": 176,
            "optimizer": OPTIMIZER_NAME,
            "optimizer_island_count": 22,
            "total_optimizer_proposals_frozen": 5_767_168,
            "null_replicate_count_frozen": 4_096,
            "comparison_tolerance": 0,
            "minimum_strictly_dominated_nulls": 3_893,
            "maximum_nulls_dominating_candidate": 0,
            "minimum_replacement_distance_required": 2,
            "optimizer_wall_clock_limit_seconds": 7_200,
            "null_wall_clock_limit_seconds": 7_200,
            "resident_memory_limit_bytes": 2_147_483_648,
            "registered_artifact_count": 4,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION"
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_STRUCTURAL_PREREGISTRATION_VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
    )
    preregistration = projection[
        "prediction_v2_structural_decision_support_preregistration"
    ]
    assert preregistration["resolver_status"] == "completed"
    assert preregistration["preregistration_contract_frozen"] is True
    assert preregistration["primary_candidate_budget"] == 176
    assert preregistration["next_consumer_resolver_status"] == "ready"
    assert not _contains_key(preregistration, "duplicate_validation")


def test_supervisor_executes_and_replays_without_uniqueness_validation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = load_prediction_v2_structural_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    for entry in source["source_entries"]:
        destination = tmp_path / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / entry["path"], destination)
    destination = (
        tmp_path
        / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE_CONTRACT_PATH,
        destination,
    )

    design_execution, design = _design_summaries()
    artifact_by_type = {item["artifact_type"]: item for item in design.artifacts}
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, design_execution, []),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda *, artifact_type, **_: artifact_by_type[artifact_type],
    )
    original_build = build_prediction_v2_structural_preregistration_artifacts
    monkeypatch.setattr(
        supervisor_module,
        "build_prediction_v2_structural_preregistration_artifacts",
        lambda **kwargs: original_build(
            **kwargs,
            require_registered_identities=False,
        ),
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key
        == PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
    )
    task = replace(
        task,
        input_artifact_digests=(
            source["artifact_digest"],
            design_execution["artifact_digest"],
            *(str(item["artifact_digest"]) for item in design.artifacts),
        ),
    )
    result = PredictionV2StructuralDecisionSupportPreregistrationCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )
    assert len(result.registrations) == 4
    assert not _contains_key(result.execution_artifact, "duplicate_validation")
    assert result.execution_artifact["candidate_portfolios_generated"] == 0
    assert result.execution_artifact["optimizer_proposals_executed"] == 0
    assert result.execution_artifact["null_replicates_executed"] == 0
    assert result.completion_facts == (
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_COMPLETION_FACT,
    )

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "a" * 64,
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
        task_key=(PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY),
        execution_id="a" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["same_registered_content"] is True
    assert capability_replay["optimizer_proposals_replayed"] == 0
    assert capability_replay["null_replicates_replayed"] == 0
    assert not _contains_key(capability_replay, "duplicate_validation")
    assert capability_replay["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
    )


def test_artifact_index_and_supervisor_register_preregistration() -> None:
    source = load_prediction_v2_structural_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    entry = index[source["artifact_digest"]]
    assert entry["path"] == str(
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    assert entry["identity_field"] == "artifact_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_CAPABILITY in (
        supervisor.capabilities
    )
