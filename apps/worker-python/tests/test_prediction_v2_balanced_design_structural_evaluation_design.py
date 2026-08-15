from __future__ import annotations

import copy
import json

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_structural_evaluation_design import (
    CONFIRMATORY_ENDPOINT,
    FIXED_CERTIFICATE_DIGEST,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_APPROVED_EVENT,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_CAPABILITY,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_COMPLETION_FACT,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY,
    PRIMARY_NULL,
    REPETITION_SCAN,
    RESULT_DECISION,
    RESULT_DECISION_EXECUTION_ID,
    SECONDARY_NULL,
    PredictionV2BalancedDesignStructuralEvaluationDesignError,
    build_prediction_v2_balanced_design_structural_evaluation_design_artifacts,
    load_prediction_v2_balanced_design_structural_evaluation_design_source_contract,
    replay_prediction_v2_balanced_design_structural_evaluation_design,
    verify_prediction_v2_balanced_design_structural_evaluation_design_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import ResearchEvidenceSupervisor

MANIFEST_PATH = ROOT_DIR / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
INDEX_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
RESULT_DECISION_TASK_KEY = (
    "prediction-v2-balanced-design-feasibility-result-decision"
)
RESULT_DECISION_COMPLETION_FACT = (
    "prediction-v2-balanced-design-feasibility-result-decision:COMPLETE"
)
SOURCE_FACT_PREFIX = (
    "prediction-v2-balanced-design-structural-evaluation-design-source:"
)
STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY = (
    "prediction-v2-balanced-design-structural-evaluation-execution"
)
STRUCTURAL_EVALUATION_PREREGISTRATION_CAPABILITY = (
    "prediction_v2_balanced_design_structural_evaluation_preregistration"
)


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _source() -> dict:
    source = load_prediction_v2_balanced_design_structural_evaluation_design_source_contract(
        ROOT_DIR
        / PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_balanced_design_structural_evaluation_design_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    return source


def _claim_boundary() -> dict:
    return {
        "historical_evidence": "INCONCLUSIVE",
        "prediction_v2_mode": "SHADOW_ONLY",
        "prediction_v2_route": "BASELINE_ONLY",
        "new_model_created": False,
        "promotion_gate_opened": False,
        "p3_authorized": False,
        "production_action": "none",
    }


def _parents() -> dict[str, dict]:
    decision = _artifact(
        {
            "schema_version": "dehps-prediction-v2-balanced-design-result-decision.v1",
            "artifact_type": (
                "prediction_v2_balanced_design_feasibility_result_decision"
            ),
            "decision": RESULT_DECISION,
            "certificate_artifact_digest": FIXED_CERTIFICATE_DIGEST,
            "certificate_verified": True,
            "decision_usefulness_established": False,
            **_claim_boundary(),
            "parent_digests": [],
        },
        domain="dehps.prediction-v2.balanced-design-result-decision.v1",
    )
    handoff = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-balanced-design-structural-evaluation-"
                "design-handoff.v1"
            ),
            "artifact_type": (
                "prediction_v2_balanced_design_structural_evaluation_design_handoff"
            ),
            "fixed_certificate_artifact_digest": FIXED_CERTIFICATE_DIGEST,
            "fixed_before_evaluation": True,
            "evaluation_execution_authorized": False,
            **_claim_boundary(),
            "parent_digests": [decision["artifact_digest"]],
        },
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-design-"
            "handoff.v1"
        ),
    )
    completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-balanced-design-result-decision-completion.v1"
            ),
            "artifact_type": (
                "prediction_v2_balanced_design_feasibility_result_decision_completion"
            ),
            "completion_fact": RESULT_DECISION_COMPLETION_FACT,
            "decision_artifact_digest": decision["artifact_digest"],
            "structural_evaluation_handoff_digest": handoff["artifact_digest"],
            **_claim_boundary(),
            "parent_digests": [
                decision["artifact_digest"],
                handoff["artifact_digest"],
            ],
        },
        domain="dehps.prediction-v2.balanced-design-result-decision-completion.v1",
    )
    execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "execution_id": RESULT_DECISION_EXECUTION_ID,
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "decision": RESULT_DECISION,
            "certificate_artifact_digest": FIXED_CERTIFICATE_DIGEST,
            "certificate_verified": True,
            "decision_usefulness_established": False,
            "result_decision_digest": decision["artifact_digest"],
            "structural_evaluation_handoff_digest": handoff["artifact_digest"],
            "result_decision_completion_digest": completion["artifact_digest"],
            **_claim_boundary(),
            "parent_digests": [
                decision["artifact_digest"],
                handoff["artifact_digest"],
                completion["artifact_digest"],
            ],
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return {
        "result_decision_execution": execution,
        "result_decision": decision,
        "structural_evaluation_handoff": handoff,
        "result_decision_completion": completion,
        "result_decision_replay": {
            "status": "REPLAY_VERIFIED",
            "same_registered_content": True,
            "workload_rerun": False,
        },
    }


def test_design_is_zero_work_and_uses_uniqueness_by_construction() -> None:
    run = build_prediction_v2_balanced_design_structural_evaluation_design_artifacts(
        source_contract=_source(),
        require_registered_identities=False,
        **_parents(),
    )
    assert run.design["confirmatory_endpoint"] == CONFIRMATORY_ENDPOINT
    assert run.design["null_baselines"]["primary"]["type"] == PRIMARY_NULL
    assert run.design["null_baselines"]["secondary"]["type"] == SECONDARY_NULL
    assert run.design["null_baselines"]["primary"]["uniqueness_guarantee"] == (
        "disjoint_orbits_by_partition_construction"
    )
    assert run.design["null_baselines"]["secondary"]["uniqueness_guarantee"] == (
        "without_replacement_construction"
    )
    for artifact in run.artifacts:
        assert artifact["duplicate_or_repetition_scans"] == 0
        assert artifact["repetition_scan"] == REPETITION_SCAN
    rebuilt, replay = (
        replay_prediction_v2_balanced_design_structural_evaluation_design(
            source_contract=_source(),
            require_registered_identities=False,
            **_parents(),
        )
    )
    assert rebuilt.artifacts == run.artifacts
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert replay["duplicate_or_repetition_scans"] == 0


def test_design_fails_closed_on_fixed_certificate_drift() -> None:
    parents = copy.deepcopy(_parents())
    changed = parents["structural_evaluation_handoff"]
    changed["fixed_certificate_artifact_digest"] = "0" * 64
    identity = {key: value for key, value in changed.items() if key != "artifact_digest"}
    changed["artifact_digest"] = canonical_digest(
        identity,
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-design-"
            "handoff.v1"
        ),
    )
    with pytest.raises(
        PredictionV2BalancedDesignStructuralEvaluationDesignError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_balanced_design_structural_evaluation_design_artifacts(
            source_contract=_source(),
            require_registered_identities=False,
            **parents,
        )


def test_additive_migration_revises_design_and_adds_only_preregistration() -> None:
    source = load_m4_manifest(MANIFEST_PATH).to_dict(include_digest=False)
    source["tasks"] = [
        item
        for item in source["tasks"]
        if item["task_key"] != STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY
    ]
    source_preregistration = next(
        item
        for item in source["tasks"]
        if item["task_key"]
        == PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
    )
    source_preregistration["requested_capability"] = None
    source_preregistration["input_artifact_digests"] = []
    source_preregistration["dependencies"] = [
        dependency
        for dependency in source_preregistration["dependencies"]
        if dependency["dependency_type"] != "external_event"
    ]
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
    ]
    design = next(
        item
        for item in live["tasks"]
        if item["task_key"]
        == PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
    )
    design["requested_capability"] = None
    design["input_artifact_digests"] = []
    design["metric_contract"]["engineering_complete"] = False
    design["metric_contract"]["engineering_increment_percent"] = 0
    source_fact = SOURCE_FACT_PREFIX + _source()["artifact_digest"]
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    live["facts"]["external_events"] = [
        event
        for event in live["facts"]["external_events"]
        if event
        != PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_APPROVED_EVENT
    ]
    _, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_APPROVED_EVENT,
        ),
    )
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0


def test_manifest_index_supervisor_and_status_bind_singular_design() -> None:
    source_contract = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    design_task = tasks[
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
    ]
    assert design_task.requested_capability == (
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_CAPABILITY
    )
    assert design_task.input_artifact_digests[0] == source_contract["artifact_digest"]
    preregistration_task = tasks[
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
    ]
    assert preregistration_task.requested_capability == (
        STRUCTURAL_EVALUATION_PREREGISTRATION_CAPABILITY
    )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source_contract["artifact_digest"]]["path"] == str(
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_SOURCE_CONTRACT_PATH
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_CAPABILITY in (
        supervisor.capabilities
    )

    payload = manifest.to_dict(include_digest=False)
    for item in payload["tasks"]:
        if item["task_key"] in {
            RESULT_DECISION_TASK_KEY,
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY,
        }:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"] = list(
        dict.fromkeys(
            (
                *payload["facts"]["artifacts"],
                RESULT_DECISION_COMPLETION_FACT,
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_COMPLETION_FACT,
                mainline_completion_fact(
                    task=tasks[RESULT_DECISION_TASK_KEY], execution_id="a" * 64
                ),
                mainline_completion_fact(
                    task=design_task,
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
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
            ),
            "fixed_certificate_artifact_digest": FIXED_CERTIFICATE_DIGEST,
            "confirmatory_endpoint": CONFIRMATORY_ENDPOINT,
            "primary_null": PRIMARY_NULL,
            "secondary_null": SECONDARY_NULL,
            "duplicate_or_repetition_scans": 0,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == (
        "PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION"
    )
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_"
        "VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == (
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
    )
    design_projection = projection[
        "prediction_v2_balanced_design_structural_evaluation_design"
    ]
    assert design_projection["confirmatory_endpoint"] == CONFIRMATORY_ENDPOINT
    assert design_projection["duplicate_or_repetition_scans"] == 0
    assert design_projection["repetition_scan"] == REPETITION_SCAN
    assert design_projection["resolver_status"] == "completed"
    preregistration_resolution = {
        item.task_key: item.status.value
        for item in ResearchOSControlPlane().resolve(completed).resolutions
    }
    assert preregistration_resolution[
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
    ] == "ready"
    assert preregistration_task.requested_capability == (
        STRUCTURAL_EVALUATION_PREREGISTRATION_CAPABILITY
    )
