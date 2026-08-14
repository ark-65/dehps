from __future__ import annotations

import copy
import json

import pytest
from dehps.config import ROOT_DIR
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.models import ControlPlaneManifest, ObjectiveClass
from dehps.research_os.structural_utility.m4_p3_result_blind_design import (
    M4_P3_STRUCTURAL_UTILITY_DESIGN_APPROVED_EVENT,
    M4_P3_STRUCTURAL_UTILITY_DESIGN_CAPABILITY,
    M4_P3_STRUCTURAL_UTILITY_DESIGN_SOURCE_CONTRACT_PATH,
    M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY,
    M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
    PARENT_CAPABILITY,
    PARENT_COMPLETED_EVENT_DIGEST,
    PARENT_COMPLETION_DIGEST,
    PARENT_COMPLETION_REGISTRATION_DIGEST,
    PARENT_EXECUTION_DIGEST,
    PARENT_EXECUTION_ID,
    PARENT_EXECUTION_REGISTRATION_DIGEST,
    PARENT_INTAKE_HANDOFF_DIGEST,
    PARENT_INTAKE_HANDOFF_REGISTRATION_DIGEST,
    PARENT_MANIFEST_DIGEST,
    PARENT_TASK_DIGEST,
    PARENT_TASK_KEY,
    M4P3ResultBlindStructuralUtilityDesignError,
    build_m4_p3_result_blind_structural_utility_design_artifacts,
    load_m4_p3_result_blind_structural_utility_design_source_contract,
    replay_m4_p3_result_blind_structural_utility_design,
    verify_m4_p3_result_blind_structural_utility_design_source_bytes,
)
from dehps.research_os.structural_utility.m4_p3_result_blind_execution import (
    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
)
from dehps.research_os.structural_utility.m4_p3_result_blind_preregistration import (
    M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_CAPABILITY,
)
from dehps.research_os.supervisor import ResearchEvidenceSupervisor
from scripts.build_m4_p3_result_blind_structural_utility_design_manifest import (
    MIGRATED_SOURCE_MANIFEST_DIGEST,
    _source_payload,
)

MANIFEST_PATH = ROOT_DIR / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)
SOURCE_FACT_PREFIX = "m4-p3-result-blind-structural-utility-design-source:"


def _source() -> dict:
    source = load_m4_p3_result_blind_structural_utility_design_source_contract(
        ROOT_DIR / M4_P3_STRUCTURAL_UTILITY_DESIGN_SOURCE_CONTRACT_PATH
    )
    verify_m4_p3_result_blind_structural_utility_design_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    return source


def _completed_event() -> dict:
    return {
        "event_digest": PARENT_COMPLETED_EVENT_DIGEST,
        "execution_id": PARENT_EXECUTION_ID,
        "control_plane_key": "m4-information-theory-mainline",
        "manifest_digest": PARENT_MANIFEST_DIGEST,
        "task_digest": PARENT_TASK_DIGEST,
        "task_key": PARENT_TASK_KEY,
        "capability": PARENT_CAPABILITY,
        "event_type": "completed",
        "sequence": 1,
    }


def _registration(
    *, registration_digest: str, artifact_digest: str, artifact_type: str, schema: str
) -> dict:
    return {
        "registration_digest": registration_digest,
        "execution_id": PARENT_EXECUTION_ID,
        "control_plane_key": "m4-information-theory-mainline",
        "task_digest": PARENT_TASK_DIGEST,
        "task_key": PARENT_TASK_KEY,
        "artifact_digest": artifact_digest,
        "artifact_type": artifact_type,
        "schema_version": schema,
        "artifact_path": f"runtime/registered/{artifact_digest}.json",
        "parent_digests": [],
        "git_commit": "612f2427b3ab1c96fa215902e43e86436bb7b875",
    }


def _parent_registrations() -> tuple[dict, ...]:
    return (
        _registration(
            registration_digest=PARENT_EXECUTION_REGISTRATION_DIGEST,
            artifact_digest=PARENT_EXECUTION_DIGEST,
            artifact_type="research_os_mainline_execution",
            schema="dehps-research-os-mainline-execution.v1",
        ),
        _registration(
            registration_digest=PARENT_INTAKE_HANDOFF_REGISTRATION_DIGEST,
            artifact_digest=PARENT_INTAKE_HANDOFF_DIGEST,
            artifact_type=(
                "prediction_v2_balanced_design_structural_utility_"
                "research_intake_handoff"
            ),
            schema=(
                "dehps-prediction-v2-balanced-design-structural-utility-"
                "research-intake-handoff.v1"
            ),
        ),
        _registration(
            registration_digest=PARENT_COMPLETION_REGISTRATION_DIGEST,
            artifact_digest=PARENT_COMPLETION_DIGEST,
            artifact_type=(
                "prediction_v2_balanced_design_structural_evaluation_"
                "result_decision_completion"
            ),
            schema=(
                "dehps-prediction-v2-balanced-design-structural-evaluation-"
                "result-decision-completion.v1"
            ),
        ),
    )


def test_design_freezes_discriminating_estimands_and_executes_zero_work() -> None:
    run = build_m4_p3_result_blind_structural_utility_design_artifacts(
        source_contract=_source(),
        completed_event=_completed_event(),
        parent_registrations=_parent_registrations(),
    )
    assert run.design["portfolio_budget"] == 100
    assert run.design["fold_count_range"] == {"minimum": 60, "maximum": 120}
    assert [item["metric"] for item in run.design["confirmatory_coordinates"]] == [
        "pair_coverage_ratio",
        "triple_coverage_ratio",
        "high_overlap_ticket_pair_rate",
        "normalized_pair_usage_entropy",
        "largest_similarity_cluster_fraction",
        "family_concentration_hhi",
    ]
    assert run.design["constructive_invariant"]["unique_ticket_fraction"] == "1/1"
    assert (
        run.design["constructive_invariant"]["confirmatory_advantage_metric"] is False
    )
    for artifact in run.artifacts:
        assert artifact["result_blind"] is True
        assert artifact["parent_payloads_read"] == 0
        assert artifact["portfolios_generated"] == 0
        assert artifact["folds_executed"] == 0
        assert artifact["metric_results_read"] == 0
        assert artifact["raw_outcome_rows_read"] == 0
        assert artifact["previous_structural_result_values_read"] == 0
        assert artifact["prediction_v2_mode"] == "SHADOW_ONLY"
        assert artifact["old_training_lines"] == "FROZEN"
        assert artifact["production_action"] == "none"
    rebuilt, replay = replay_m4_p3_result_blind_structural_utility_design(
        source_contract=_source(),
        completed_event=_completed_event(),
        parent_registrations=_parent_registrations(),
    )
    assert rebuilt.artifacts == run.artifacts
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["parent_payloads_read"] == 0
    assert replay["previous_structural_result_values_read"] == 0


def test_design_rejects_result_values_in_parent_projection() -> None:
    event = _completed_event()
    event["candidate_triple_collision_mass"] = 605
    with pytest.raises(
        M4P3ResultBlindStructuralUtilityDesignError,
        match="parent_event_not_result_blind",
    ):
        build_m4_p3_result_blind_structural_utility_design_artifacts(
            source_contract=_source(),
            completed_event=event,
            parent_registrations=_parent_registrations(),
        )


def test_additive_migration_adds_one_goal_staged_tasks_and_revises_only_intake() -> None:
    source = load_m4_manifest(MANIFEST_PATH).to_dict(include_digest=False)
    live = copy.deepcopy(source)
    live["goals"] = [
        item
        for item in live["goals"]
        if item["goal_key"] != M4_P3_STRUCTURAL_UTILITY_GOAL_KEY
    ]
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
            not in {
                M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
                M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
                M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
            }
    ]
    intake = next(
        item
        for item in live["tasks"]
        if item["task_key"] == M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY
    )
    intake["goal_key"] = "M4_INFORMATION_THEORY_EVIDENCE"
    intake["goal_digest"] = ""
    intake["task_type"] = (
        "prediction_v2_balanced_design_structural_utility_research_intake"
    )
    intake["requested_capability"] = None
    intake["input_artifact_digests"] = []
    intake["metric_contract"] = {
        "engineering_complete": False,
        "engineering_increment_percent": 0,
        "evidence_complete": False,
        "evidence_increment_percent": 0,
        "phase": "PREDICTION-V2-BALANCED-DESIGN-STRUCTURAL-UTILITY-RESEARCH-INTAKE",
        "mainline_integration": {
            "goal": "M4_INFORMATION_THEORY_EVIDENCE",
            "ready_condition": "wait_for_approved_result_blind_research",
            "runner": "pending",
            "upstream_artifacts": ["registered structural intake"],
            "downstream_artifacts": ["future design"],
            "status_projection": "unified_m4_status.measurement_system_v2",
            "evidence_progress_rule": "zero",
            "decision_consumer": "future research",
            "downstream_consumer": "future research",
        },
    }
    source_digest = _source()["artifact_digest"]
    source_fact = SOURCE_FACT_PREFIX + source_digest
    live["facts"]["artifacts"] = [
        item for item in live["facts"]["artifacts"] if item != source_fact
    ]
    live["facts"]["external_events"] = [
        item
        for item in live["facts"]["external_events"]
        if item != M4_P3_STRUCTURAL_UTILITY_DESIGN_APPROVED_EVENT
    ]
    design_source_task = next(
        item
        for item in source["tasks"]
        if item["task_key"] == M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY
    )
    completion_fact = next(
        dependency["target_key"]
        for dependency in design_source_task["dependencies"]
        if dependency["dependency_type"] == "artifact"
    )
    if completion_fact not in live["facts"]["artifacts"]:
        live["facts"]["artifacts"].append(completion_fact)
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,),
        allowlisted_new_task_keys=(
            M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
            M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
            M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(M4_P3_STRUCTURAL_UTILITY_DESIGN_APPROVED_EVENT,),
    )
    assert dry_run["new_goal_keys"] == [M4_P3_STRUCTURAL_UTILITY_GOAL_KEY]
    assert set(dry_run["new_task_keys"]) == {
        M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
        M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
        M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
    }
    assert dry_run["revised_task_keys"] == [M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    migrated_manifest = ControlPlaneManifest.from_dict(migrated)
    migrated_resolutions = {
        item.task_key: item.status.value
        for item in ResearchOSControlPlane().resolve(migrated_manifest).resolutions
    }
    assert migrated_resolutions[M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY] == "ready"


def test_manifest_status_index_and_supervisor_bind_the_independent_goal() -> None:
    assert ObjectiveClass.STRUCTURAL_DECISION_UTILITY.value == (
        "structural_decision_utility"
    )
    source = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    goals = {item.goal_key: item for item in manifest.goals}
    tasks = {item.task_key: item for item in manifest.tasks}
    assert goals[M4_P3_STRUCTURAL_UTILITY_GOAL_KEY].objective_class is (
        ObjectiveClass.STRUCTURAL_DECISION_UTILITY
    )
    design = tasks[M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY]
    assert design.goal_key == M4_P3_STRUCTURAL_UTILITY_GOAL_KEY
    assert design.requested_capability == M4_P3_STRUCTURAL_UTILITY_DESIGN_CAPABILITY
    assert design.input_artifact_digests == (
        source["artifact_digest"],
        PARENT_EXECUTION_DIGEST,
        PARENT_INTAKE_HANDOFF_DIGEST,
        PARENT_COMPLETION_DIGEST,
    )
    preregistration = tasks[M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY]
    assert (
        preregistration.requested_capability
        == M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_CAPABILITY
    )
    resolutions = {
        item.task_key: item.status.value
        for item in ResearchOSControlPlane().resolve(manifest).resolutions
    }
    assert (
        resolutions[M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY]
        == "dependency_wait"
    )
    assert (
        resolutions[M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY]
        == "dependency_wait"
    )
    status = build_m4_status(manifest)
    projection = status["structural_utility"]
    assert projection["goal_status"] == "ACTIVE"
    assert projection["m4_p3_result_blind_design"]["result_blind"] is True
    assert (
        projection["m4_p3_result_blind_design"]["resolver_status"]
        == "dependency_wait"
    )
    assert projection["m4_p3_result_blind_design"]["portfolios_generated"] == 0
    assert projection["integration_answer"] == "NO — INTEGRATION_PENDING"
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == (
        M4_P3_STRUCTURAL_UTILITY_DESIGN_SOURCE_CONTRACT_PATH.as_posix()
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert M4_P3_STRUCTURAL_UTILITY_DESIGN_CAPABILITY in supervisor.capabilities


def test_design_migration_builder_rejects_a_later_source_manifest() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    contract_digest = _source()["artifact_digest"]
    assert source["manifest_digest"] != MIGRATED_SOURCE_MANIFEST_DIGEST
    with pytest.raises(SystemExit, match="source-base manifest identity changed"):
        _source_payload(source, contract_digest)

    changed = copy.deepcopy(source)
    changed["manifest_digest"] = "0" * 64
    with pytest.raises(SystemExit, match="source-base manifest identity changed"):
        _source_payload(changed, contract_digest)
