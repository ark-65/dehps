from __future__ import annotations

import copy
import inspect
import json

import pytest

from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_structural_evaluation_result_decision import (
    DECISION,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_CAPABILITY,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY,
    PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_UTILITY_RESEARCH_INTAKE_TASK_KEY,
    REGISTERED_OUTCOME,
    PredictionV2BalancedDesignStructuralEvaluationResultDecisionError,
    build_prediction_v2_balanced_design_structural_evaluation_result_decision_artifacts,
    load_prediction_v2_balanced_design_structural_evaluation_result_decision_source_contract,
    replay_prediction_v2_balanced_design_structural_evaluation_result_decision,
    verify_prediction_v2_balanced_design_structural_evaluation_result_decision_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.supervisor import (
    PredictionV2BalancedDesignStructuralEvaluationResultDecisionCapability,
    ResearchEvidenceSupervisor,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _claim_boundary() -> dict:
    return {
        "historical_evidence": "INCONCLUSIVE",
        "prediction_v2_mode": "SHADOW_ONLY",
        "prediction_v2_route": "BASELINE_ONLY",
        "evidence_created": False,
        "new_model_created": False,
        "promotion_gate_opened": False,
        "p3_authorized": False,
        "production_action": "none",
    }


def _source() -> dict:
    contract = load_prediction_v2_balanced_design_structural_evaluation_result_decision_source_contract(
        ROOT_DIR
        / PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_balanced_design_structural_evaluation_result_decision_source_bytes(
        root_dir=ROOT_DIR,
        contract=contract,
    )
    return contract


def _parents() -> dict[str, dict]:
    result = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-balanced-design-structural-evaluation-result.v1"
            ),
            "artifact_type": (
                "prediction_v2_balanced_design_structural_evaluation_result"
            ),
            "status": "COMPLETE",
            "outcome": REGISTERED_OUTCOME,
            "candidate_triple_collision_mass": 605,
            "inference": {
                "outcome": REGISTERED_OUTCOME,
                "primary_lower_tail_numerator": 55,
                "primary_upper_tail_numerator": 9_972,
                "primary_denominator": 10_000,
                "secondary_lower_tail_numerator": 1,
                "secondary_upper_tail_numerator": 2_000,
                "secondary_denominator": 2_000,
                "secondary_null_can_change_outcome": False,
            },
            **_claim_boundary(),
        },
        domain=("dehps.prediction-v2.balanced-design-structural-evaluation-result.v1"),
    )
    diagnostics = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-balanced-design-structural-evaluation-"
                "diagnostics.v1"
            ),
            "artifact_type": (
                "prediction_v2_balanced_design_structural_evaluation_diagnostics"
            ),
            "status": "COMPLETE",
            "candidate": {"triple_collision_mass": 605},
            **_claim_boundary(),
        },
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-diagnostics.v1"
        ),
    )
    completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-balanced-design-structural-evaluation-"
                "execution-completion.v1"
            ),
            "artifact_type": (
                "prediction_v2_balanced_design_structural_evaluation_"
                "execution_completion"
            ),
            "status": "COMPLETE",
            "outcome": REGISTERED_OUTCOME,
            "result_artifact_digest": result["artifact_digest"],
            "diagnostics_artifact_digest": diagnostics["artifact_digest"],
            **_claim_boundary(),
        },
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-"
            "execution-completion.v1"
        ),
    )
    execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "execution_id": "a" * 64,
            "task_key": (
                "prediction-v2-balanced-design-structural-evaluation-execution"
            ),
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "outcome": REGISTERED_OUTCOME,
            "evaluation_result_digest": result["artifact_digest"],
            "evaluation_diagnostics_digest": diagnostics["artifact_digest"],
            "evaluation_completion_digest": completion["artifact_digest"],
            "registered_artifact_count": 4,
            **_claim_boundary(),
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return {
        "execution": execution,
        "result": result,
        "diagnostics": diagnostics,
        "completion": completion,
        "execution_replay": {
            "status": "REPLAY_VERIFIED",
            "same_registered_content": True,
            "workload_rerun": False,
            "outcome": REGISTERED_OUTCOME,
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


def test_result_decision_is_exact_bounded_and_replayable() -> None:
    run = build_prediction_v2_balanced_design_structural_evaluation_result_decision_artifacts(
        source_contract=_source(),
        require_registered_identities=False,
        **_parents(),
    )
    assert run.decision["decision"] == DECISION
    assert run.decision["primary_lower_tail_numerator"] == 55
    assert run.decision["structural_advantage_established_within_matched_null"]
    assert run.decision["global_structural_optimum_established"] is False
    assert run.decision["operational_utility_established"] is False
    assert run.structural_utility_intake_handoff[
        "future_utility_definition_must_be_result_blind"
    ]
    assert (
        run.structural_utility_intake_handoff["this_result_may_tune_future_utility"]
        is False
    )
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
        "membership_validation",
        "duplicate_scan",
        "membership_scan",
    }.intersection(_recursive_keys(run.artifacts))

    rebuilt, replay = (
        replay_prediction_v2_balanced_design_structural_evaluation_result_decision(
            source_contract=_source(),
            require_registered_identities=False,
            **_parents(),
        )
    )
    assert rebuilt.artifacts == run.artifacts
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert not {
        "duplicate_membership_uniqueness_or_repetition_scans",
        "repetition_scan",
    }.intersection(_recursive_keys(replay))


def test_result_decision_fails_closed_on_tail_drift() -> None:
    parents = copy.deepcopy(_parents())
    parents["result"]["inference"]["primary_lower_tail_numerator"] = 101
    identity = dict(parents["result"])
    identity.pop("artifact_digest")
    parents["result"]["artifact_digest"] = canonical_digest(
        identity,
        domain=("dehps.prediction-v2.balanced-design-structural-evaluation-result.v1"),
    )
    with pytest.raises(
        PredictionV2BalancedDesignStructuralEvaluationResultDecisionError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_balanced_design_structural_evaluation_result_decision_artifacts(
            source_contract=_source(),
            require_registered_identities=False,
            **parents,
        )


def test_manifest_index_supervisor_and_status_bind_singular_decision() -> None:
    source = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    decision = tasks[
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY
    ]
    intake = tasks[
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_UTILITY_RESEARCH_INTAKE_TASK_KEY
    ]
    assert decision.requested_capability == (
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_CAPABILITY
    )
    assert decision.input_artifact_digests[0] == source["artifact_digest"]
    assert intake.requested_capability is None
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == str(
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_SOURCE_CONTRACT_PATH
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert (
        PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_CAPABILITY
        in supervisor.capabilities
    )

    status = build_m4_status(
        manifest,
        measurement_v2_execution={
            "execution_task_key": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY
            ),
            "registered_outcome": REGISTERED_OUTCOME,
            "decision": DECISION,
            "structural_advantage_established_within_matched_null": True,
        },
    )
    projection = status["measurement_system_v2"]
    assert (
        projection[
            "prediction_v2_balanced_design_structural_evaluation_result_decision"
        ]["decision"]
        == DECISION
    )
    assert (
        projection["prediction_v2_balanced_design_structural_utility_research_intake"][
            "requested_capability"
        ]
        is None
    )


def test_supervisor_projection_and_replay_do_not_use_duplicate_metadata() -> None:
    execution_source = inspect.getsource(
        PredictionV2BalancedDesignStructuralEvaluationResultDecisionCapability
    )
    replay_source = inspect.getsource(ResearchEvidenceSupervisor.replay)
    branch_marker = (
        "elif (\n"
        "            task_key\n"
        "            == PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_"
        "RESULT_DECISION_TASK_KEY"
    )
    replay_branch = replay_source.split(branch_marker, 1)[1].split(
        "PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY",
        1,
    )[0]
    forbidden = {
        "duplicate_membership_uniqueness_or_repetition_scans",
        "repetition_scan",
    }
    assert not any(token in execution_source for token in forbidden)
    assert not any(token in replay_branch for token in forbidden)
