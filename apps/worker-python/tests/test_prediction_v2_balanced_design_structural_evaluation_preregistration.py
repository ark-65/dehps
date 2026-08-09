from __future__ import annotations

import copy
import json

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_structural_evaluation_design import (
    build_prediction_v2_balanced_design_structural_evaluation_design_artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_structural_evaluation_execution import (
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_CAPABILITY,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_structural_evaluation_preregistration import (
    ALPHA_DENOMINATOR,
    DESIGN_EXECUTION_ID,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_APPROVED_EVENT,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_CAPABILITY,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY,
    PRIMARY_REPLICATES,
    REPETITION_SCAN,
    SECONDARY_REPLICATES,
    PredictionV2BalancedDesignStructuralEvaluationPreregistrationError,
    build_prediction_v2_balanced_design_structural_evaluation_preregistration_artifacts,
    load_prediction_v2_balanced_design_structural_evaluation_preregistration_source_contract,
    replay_prediction_v2_balanced_design_structural_evaluation_preregistration,
    verify_prediction_v2_balanced_design_structural_evaluation_preregistration_source_bytes,
)
from dehps.research_os.information_theory.progress import load_m4_manifest
from dehps.research_os.supervisor import ResearchEvidenceSupervisor
from test_prediction_v2_balanced_design_structural_evaluation_design import (
    _parents as _design_parents,
)
from test_prediction_v2_balanced_design_structural_evaluation_design import (
    _source as _design_source,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
SOURCE_FACT_PREFIX = (
    "prediction-v2-balanced-design-structural-evaluation-preregistration-source:"
)


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _source() -> dict:
    source = load_prediction_v2_balanced_design_structural_evaluation_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_balanced_design_structural_evaluation_preregistration_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    return source


def _parents() -> dict[str, dict]:
    design_run = build_prediction_v2_balanced_design_structural_evaluation_design_artifacts(
        source_contract=_design_source(),
        require_registered_identities=False,
        **_design_parents(),
    )
    execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "execution_id": DESIGN_EXECUTION_ID,
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "design_artifact_digest": design_run.design["artifact_digest"],
            "preregistration_handoff_digest": design_run.preregistration_handoff[
                "artifact_digest"
            ],
            "design_completion_digest": design_run.completion["artifact_digest"],
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "parent_digests": [
                artifact["artifact_digest"] for artifact in design_run.artifacts
            ],
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return {
        "design_execution": execution,
        "design": design_run.design,
        "preregistration_handoff": design_run.preregistration_handoff,
        "design_completion": design_run.completion,
        "design_replay": {
            "status": "REPLAY_VERIFIED",
            "same_registered_content": True,
            "workload_rerun": False,
        },
    }


def test_preregistration_freezes_counts_and_removes_duplicate_validation() -> None:
    run = build_prediction_v2_balanced_design_structural_evaluation_preregistration_artifacts(
        source_contract=_source(),
        require_registered_identities=False,
        **_parents(),
    )
    frozen = run.preregistration
    assert frozen["primary_null"]["replicate_count"] == PRIMARY_REPLICATES
    assert frozen["secondary_null"]["replicate_count"] == SECONDARY_REPLICATES
    assert frozen["inference"]["alpha_denominator"] == ALPHA_DENOMINATOR
    assert frozen["random_stream"]["worker_count_affects_stream"] is False
    for null_key in ("primary_null", "secondary_null"):
        null = frozen[null_key]
        assert null["duplicate_validation_pass"] is False
        assert null["membership_validation_pass"] is False
        assert null["uniqueness_validation_pass"] is False
        assert null["repetition_scan"] == REPETITION_SCAN
    for artifact in run.artifacts:
        assert artifact["candidate_evaluation_statistics_read"] is False
        assert artifact["null_replicates_executed"] == 0
        assert artifact["duplicate_membership_uniqueness_or_repetition_scans"] == 0
        assert artifact["repetition_scan"] == REPETITION_SCAN

    rebuilt, replay = replay_prediction_v2_balanced_design_structural_evaluation_preregistration(
        source_contract=_source(),
        require_registered_identities=False,
        **_parents(),
    )
    assert rebuilt.artifacts == run.artifacts
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert replay["duplicate_membership_uniqueness_or_repetition_scans"] == 0


def test_preregistration_fails_closed_on_design_identity_drift() -> None:
    parents = copy.deepcopy(_parents())
    parents["preregistration_handoff"]["evaluation_execution_authorized"] = True
    identity = {
        key: value
        for key, value in parents["preregistration_handoff"].items()
        if key != "artifact_digest"
    }
    parents["preregistration_handoff"]["artifact_digest"] = canonical_digest(
        identity,
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-"
            "preregistration-handoff.v1"
        ),
    )
    with pytest.raises(
        PredictionV2BalancedDesignStructuralEvaluationPreregistrationError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_balanced_design_structural_evaluation_preregistration_artifacts(
            source_contract=_source(),
            require_registered_identities=False,
            **parents,
        )


def test_additive_migration_revises_preregistration_and_adds_only_execution() -> None:
    source = load_m4_manifest(MANIFEST_PATH).to_dict(include_digest=False)
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY
    ]
    current = next(
        item
        for item in live["tasks"]
        if item["task_key"]
        == PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
    )
    current["requested_capability"] = None
    current["input_artifact_digests"] = []
    source_fact = SOURCE_FACT_PREFIX + _source()["artifact_digest"]
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    live["facts"]["external_events"] = [
        event
        for event in live["facts"]["external_events"]
        if event
        != PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_APPROVED_EVENT
    ]
    _, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_APPROVED_EVENT,
        ),
    )
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0


def test_manifest_index_and_supervisor_bind_singular_preregistration() -> None:
    source_contract = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    current = tasks[
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
    ]
    assert current.requested_capability == (
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_CAPABILITY
    )
    assert current.input_artifact_digests[0] == source_contract["artifact_digest"]
    next_task = tasks[
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY
    ]
    assert next_task.requested_capability == (
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_CAPABILITY
    )
    assert tasks[
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY
    ].requested_capability is None
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source_contract["artifact_digest"]]["path"] == str(
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert (
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_CAPABILITY
        in supervisor.capabilities
    )
    assert (
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_CAPABILITY
        in supervisor.capabilities
    )
