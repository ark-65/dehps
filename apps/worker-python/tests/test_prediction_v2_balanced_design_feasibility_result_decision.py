from __future__ import annotations

import copy
import json
from functools import lru_cache

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_feasibility_execution import (
    MulticoverSearchResult,
    build_positive_certificate,
    build_search_result_artifact,
    compile_translation_orbit_inventory,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_feasibility_result_decision import (
    EXECUTION_ID,
    POSITIVE_DECISION,
    POSITIVE_OUTCOME,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_CAPABILITY,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_COMPLETION_FACT,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY,
    PREDICTION_V2_BALANCED_DESIGN_RESULT_DECISION_APPROVED_EVENT,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY,
    REPETITION_SCAN,
    TERMINAL_CHECKPOINT_DIGEST,
    PredictionV2BalancedDesignResultDecisionError,
    build_prediction_v2_balanced_design_result_decision_artifacts,
    load_prediction_v2_balanced_design_result_decision_source_contract,
    replay_prediction_v2_balanced_design_result_decision,
    verify_prediction_v2_balanced_design_result_decision_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import ResearchEvidenceSupervisor

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)
EXECUTION_TASK_KEY = "prediction-v2-balanced-design-feasibility-execution"
EXECUTION_COMPLETION_FACT = (
    "prediction-v2-balanced-design-feasibility-execution:COMPLETE"
)
SOURCE_FACT_PREFIX = "prediction-v2-balanced-design-feasibility-result-decision-source:"


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _source() -> dict:
    source = load_prediction_v2_balanced_design_result_decision_source_contract(
        ROOT_DIR
        / PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_balanced_design_result_decision_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    return source


@lru_cache(maxsize=1)
def _parents() -> dict[str, dict]:
    inventory = compile_translation_orbit_inventory()
    search = MulticoverSearchResult(
        outcome=POSITIVE_OUTCOME,
        profile=(5, 1),
        short_subset_indices=(0,),
        selected_full_representative_ids=(4633, 9898, 15056, 19950, 36400),
        selected_short_representative_ids=(24285,),
        node_expansions=1_193_047,
        completed_branch_count=0,
        total_branch_count=10,
        search_exhausted=False,
        transcript_digest=(
            "c4d4e0bc2310eaee7239b64789a8af3277b8b940a1228cc6036d49f206a283eb"
        ),
        checkpoint_count=2,
        terminal_checkpoint_digest=TERMINAL_CHECKPOINT_DIGEST,
    )
    certificate = build_positive_certificate(inventory=inventory, result=search)
    inventory_artifact = inventory.to_artifact()
    result = build_search_result_artifact(
        inventory_artifact_digest=inventory_artifact["artifact_digest"],
        result=search,
        certificate=certificate,
        peak_resident_bytes=348_434_432,
    )
    completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-balanced-design-execution-completion.v1"
            ),
            "artifact_type": (
                "prediction_v2_balanced_design_feasibility_execution_completion"
            ),
            "status": "COMPLETE",
            "completion_fact": EXECUTION_COMPLETION_FACT,
            "outcome": POSITIVE_OUTCOME,
            "inventory_artifact_digest": inventory_artifact["artifact_digest"],
            "result_artifact_digest": result["artifact_digest"],
            "terminal_checkpoint_digest": TERMINAL_CHECKPOINT_DIGEST,
            "repetition_scan": REPETITION_SCAN,
            "separate_duplicate_membership_or_uniqueness_scan": False,
            "evidence_created": False,
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "parent_digests": [
                inventory_artifact["artifact_digest"],
                result["artifact_digest"],
            ],
        },
        domain="dehps.prediction-v2.balanced-design.execution-completion.v1",
    )
    execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "task_key": EXECUTION_TASK_KEY,
            "execution_id": EXECUTION_ID,
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "outcome": POSITIVE_OUTCOME,
            "existence_established_in_cyclic_scope": True,
            "global_nonexistence_established": False,
            "orbit_inventory_digest": inventory_artifact["artifact_digest"],
            "search_result_digest": result["artifact_digest"],
            "execution_completion_digest": completion["artifact_digest"],
            "checkpoint_count": 2,
            "repetition_scan": REPETITION_SCAN,
            "evidence_created": False,
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "parent_digests": [
                inventory_artifact["artifact_digest"],
                result["artifact_digest"],
                completion["artifact_digest"],
            ],
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return {
        "execution": execution,
        "inventory": inventory_artifact,
        "result": result,
        "completion": completion,
        "execution_replay": {
            "status": "REPLAY_VERIFIED",
            "outcome": POSITIVE_OUTCOME,
            "certificate_verified": True,
            "terminal_checkpoint_verified": True,
            "workload_rerun": False,
            "repetition_scan": REPETITION_SCAN,
        },
    }


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(
            *(_recursive_keys(item) for item in value.values()), set()
        )
    if isinstance(value, (list, tuple)):
        return set().union(*(_recursive_keys(item) for item in value), set())
    return set()


def test_result_decision_verifies_certificate_and_replays_without_workload() -> None:
    run = build_prediction_v2_balanced_design_result_decision_artifacts(
        source_contract=_source(),
        require_registered_identities=False,
        **_parents(),
    )
    assert run.decision["decision"] == POSITIVE_DECISION
    assert run.decision["certificate_verified"] is True
    assert run.decision["prediction_probability_claim"] is False
    assert run.structural_evaluation_handoff["fixed_before_evaluation"] is True
    assert run.completion["repetition_scan"] == REPETITION_SCAN
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
        "duplicate_scan",
        "membership_scan",
        "membership_validation",
    }.intersection(_recursive_keys(run.artifacts))
    rebuilt, replay = replay_prediction_v2_balanced_design_result_decision(
        source_contract=_source(),
        require_registered_identities=False,
        **_parents(),
    )
    assert rebuilt.artifacts == run.artifacts
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False


def test_result_decision_fails_closed_on_parent_outcome_drift() -> None:
    parents = copy.deepcopy(_parents())
    changed = parents["execution"]
    changed["outcome"] = "NOT_FOUND_WITHIN_FROZEN_BUDGET"
    identity = {
        key: value for key, value in changed.items() if key != "artifact_digest"
    }
    changed["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.research-os.mainline-execution.v1",
    )
    with pytest.raises(
        PredictionV2BalancedDesignResultDecisionError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_balanced_design_result_decision_artifacts(
            source_contract=_source(),
            require_registered_identities=False,
            **parents,
        )


def test_additive_migration_revises_decision_and_adds_only_design_task() -> None:
    source = load_m4_manifest(MANIFEST_PATH).to_dict(include_digest=False)
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
    ]
    decision = next(
        item
        for item in live["tasks"]
        if item["task_key"]
        == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
    )
    decision["requested_capability"] = None
    decision["input_artifact_digests"] = []
    decision["metric_contract"]["engineering_complete"] = False
    decision["metric_contract"]["engineering_increment_percent"] = 0
    source_fact = SOURCE_FACT_PREFIX + _source()["artifact_digest"]
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    live["facts"]["external_events"] = [
        event
        for event in live["facts"]["external_events"]
        if event != PREDICTION_V2_BALANCED_DESIGN_RESULT_DECISION_APPROVED_EVENT
    ]
    _, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(
            PREDICTION_V2_BALANCED_DESIGN_RESULT_DECISION_APPROVED_EVENT,
        ),
    )
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0


def test_manifest_index_supervisor_and_status_bind_singular_decision() -> None:
    source_contract = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    decision_task = tasks[
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
    ]
    assert decision_task.requested_capability == (
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_CAPABILITY
    )
    assert decision_task.input_artifact_digests[0] == source_contract["artifact_digest"]
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source_contract["artifact_digest"]]["path"] == str(
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_SOURCE_CONTRACT_PATH
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_CAPABILITY in (
        supervisor.capabilities
    )

    payload = manifest.to_dict(include_digest=False)
    for item in payload["tasks"]:
        if item["task_key"] in {
            EXECUTION_TASK_KEY,
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY,
        }:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"] = list(
        dict.fromkeys(
            (
                *payload["facts"]["artifacts"],
                EXECUTION_COMPLETION_FACT,
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_COMPLETION_FACT,
                mainline_completion_fact(
                    task=tasks[EXECUTION_TASK_KEY], execution_id="a" * 64
                ),
                mainline_completion_fact(
                    task=decision_task,
                    execution_id="b" * 64,
                ),
            )
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
            ),
            "execution_outcome": POSITIVE_OUTCOME,
            "decision": POSITIVE_DECISION,
            "certificate_artifact_digest": (
                "b7a0069edef9f6a2aeec3f2205a50a63ba39594ed555c3c89b108830cd3c28db"
            ),
            "certificate_verified": True,
            "existence_established_in_cyclic_scope": True,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == (
        "PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN"
    )
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_BALANCED_DESIGN_RESULT_DECISION_VALIDATED_IN_MAINLINE"
    )
    assert (
        projection["prediction_v2_balanced_design_feasibility_result_decision"][
            "decision"
        ]
        == POSITIVE_DECISION
    )
    assert (
        projection["prediction_v2_balanced_design_structural_evaluation_design"][
            "resolver_status"
        ]
        == "ready"
    )
