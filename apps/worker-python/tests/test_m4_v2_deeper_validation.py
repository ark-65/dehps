from __future__ import annotations

import importlib.util
from copy import deepcopy

import pytest
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2 import (
    deeper_validation as subject,
)
from dehps.research_os.supervisor import (
    M4V2DeeperValidationCapability,
    ResearchEvidenceSupervisor,
)

SOURCE_DIGEST = "a" * 64
DECISION_REGISTRATION_DIGEST = "b" * 64
REPLAY_REGISTRATION_DIGEST = "c" * 64
ROUTE_REGISTRATION_DIGEST = "d" * 64
CLOSURE_REGISTRATION_DIGEST = "e" * 64


def _old_route() -> dict[str, object]:
    return {
        "artifact_digest": subject.OLD_GLOBAL_ROUTE_DIGEST,
        "route": subject.OLD_GLOBAL_ROUTE,
        "decision_projection_rows": [{"branch_id": "MARGINAL_STATIC"}],
    }


def _branch_decisions() -> list[dict[str, object]]:
    return [
        {
            "artifact_digest": subject.MARGINAL_DECISION_DIGEST,
            "body": {
                "branch_id": "MARGINAL_STATIC",
                "terminal_decision": "INCONCLUSIVE_DUE_TO_POWER",
                "measurement_health": "PASS",
                "historical_evidence": "INCONCLUSIVE",
                "accepted_for_downstream_baseline": False,
            },
        },
        {
            "artifact_digest": subject.TEMPORAL_DECISION_DIGEST,
            "body": {
                "branch_id": "TEMPORAL_MARGINAL_INCREMENT",
                "terminal_decision": "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
            },
        },
        {
            "artifact_digest": subject.JOINT_DECISION_DIGEST,
            "body": {
                "branch_id": "JOINT_RESIDUAL_INCREMENT",
                "terminal_decision": "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
            },
        },
    ]


def _branch_replays() -> list[dict[str, object]]:
    return [
        {
            "artifact_digest": digest,
            "body": {
                "replay_status": "REGISTERED_REPLAY_VERIFIED",
                "workload_rerun": False,
            },
        }
        for digest in subject.BRANCH_REPLAY_DIGESTS
    ]


def _intake() -> dict[str, object]:
    return subject.build_intake_artifact(
        old_route=_old_route(),
        branch_decisions=_branch_decisions(),
        branch_replays=_branch_replays(),
        historical_inference={
            "artifact_digest": subject.HISTORICAL_INFERENCE_DIGEST,
            "formal_historical_folds_executed": subject.FROZEN_FOLD_COUNT,
            "mde_bits_per_issue": subject.FROZEN_MDE,
            "primary_threshold_bits_per_issue": subject.FROZEN_PRACTICAL_THRESHOLD,
            "equivalence_power_at_zero": subject.FROZEN_EQUIVALENCE_POWER,
        },
        historical_design={"artifact_digest": subject.HISTORICAL_DESIGN_DIGEST},
        dataset_boundary={"artifact_digest": subject.DATASET_BOUNDARY_DIGEST},
        source_contract_digest=SOURCE_DIGEST,
    )


def test_intake_is_zero_compute_and_identifies_the_exact_parent_branch() -> None:
    intake = _intake()

    assert intake["artifact_type"] == subject.INTAKE_ARTIFACT_TYPE
    assert intake["body"]["priority_parent_branch"] == "MARGINAL_STATIC"
    assert intake["body"]["recommended_single_validation_program"] == (
        "POWER_RESOLUTION_REQUIRED"
    )
    assert intake["body"]["positive_branches"] == []
    assert intake["body"]["repair_branches"] == []
    assert intake["body"]["scientific_computation"] == 0
    assert intake["body"]["new_historical_folds"] == 0
    assert intake["body"]["predictive_p3_folds"] == 0


def test_power_feasibility_requires_forward_evidence_without_a_holdout() -> None:
    decision = subject.build_deeper_validation_decision(
        intake_artifact=_intake(),
        reviewer_decision="POWER_RESOLUTION_REQUIRED",
        reviewer_approval_decision_id=subject.REVIEW_APPROVAL_DECISION_ID,
    )

    assert decision["body"]["required_independent_fold_count"] == 4676
    assert decision["body"]["additional_independent_folds_required"] == 2095
    assert decision["body"]["registered_unused_independent_holdout_available"] is False
    assert decision["body"]["repeated_resampling_is_independent_information"] is False
    assert decision["body"]["deeper_validation_decision"] == (
        "FORWARD_EVIDENCE_REQUIRED"
    )
    assert decision["body"]["formal_execution_count"] == 0
    assert decision["body"]["new_historical_folds"] == 0


def test_reviewer_choice_and_artifact_identity_fail_closed() -> None:
    with pytest.raises(subject.M4V2DeeperValidationError):
        subject.build_deeper_validation_decision(
            intake_artifact=_intake(),
            reviewer_decision="FORWARD_EVIDENCE_REQUIRED",
            reviewer_approval_decision_id=subject.REVIEW_APPROVAL_DECISION_ID,
        )

    tampered = deepcopy(_intake())
    tampered["body"]["priority_parent_branch"] = "JOINT_RESIDUAL_INCREMENT"
    with pytest.raises(subject.M4V2DeeperValidationError):
        subject.build_deeper_validation_decision(
            intake_artifact=tampered,
            reviewer_decision="POWER_RESOLUTION_REQUIRED",
            reviewer_approval_decision_id=subject.REVIEW_APPROVAL_DECISION_ID,
        )


def test_registered_replays_and_superseding_route_close_predictive_p3() -> None:
    decision = subject.build_deeper_validation_decision(
        intake_artifact=_intake(),
        reviewer_decision="POWER_RESOLUTION_REQUIRED",
        reviewer_approval_decision_id=subject.REVIEW_APPROVAL_DECISION_ID,
    )
    decision_replay = subject.build_decision_replay(
        decision_artifact=decision,
        decision_registration_digest=DECISION_REGISTRATION_DIGEST,
    )
    route, closure = subject.build_superseding_global_route(
        old_route=_old_route(),
        branch_decisions=_branch_decisions(),
        branch_replays=_branch_replays(),
        deeper_decision=decision,
        deeper_replay=decision_replay,
        deeper_decision_registration_digest=DECISION_REGISTRATION_DIGEST,
        deeper_replay_registration_digest=REPLAY_REGISTRATION_DIGEST,
    )
    route_replay = subject.build_route_replay(
        route_artifact=route,
        route_registration_digest=ROUTE_REGISTRATION_DIGEST,
        p3_closure_artifact=closure,
        p3_closure_registration_digest=CLOSURE_REGISTRATION_DIGEST,
    )

    assert decision_replay["body"]["replay_status"] == "REGISTERED_REPLAY_VERIFIED"
    assert route["body"]["superseding_global_route"] == "FORWARD_EVIDENCE_REQUIRED"
    assert closure["body"]["predictive_p3_status"] == (
        "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION"
    )
    assert route_replay["body"]["replay_status"] == "REGISTERED_REPLAY_VERIFIED"
    assert route_replay["body"]["workload_rerun"] is False
    assert route_replay["body"]["predictive_p3_folds"] == 0
    assert route_replay["body"]["p4_started"] is False
    assert route_replay["body"]["promotion_triggered"] is False


def test_manifest_chain_is_exact_and_never_depends_on_blocked_compatibility() -> None:
    path = ROOT_DIR / "apps/worker-python/scripts/build_m4_v2_deeper_validation_manifest.py"
    spec = importlib.util.spec_from_file_location("deeper_validation_builder_test", path)
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)

    tasks = builder._new_tasks(SOURCE_DIGEST)
    assert tuple(item["task_key"] for item in tasks) == builder.NEW_TASK_KEYS
    assert len(tasks) == 5
    assert all(item["metric_contract"]["predictive_p3_folds"] == 0 for item in tasks)
    assert all(item["metric_contract"]["p4_started"] is False for item in tasks)
    assert all(item["metric_contract"]["promotion_triggered"] is False for item in tasks)
    assert all(
        item["metric_contract"]["old_replay_compatibility_dependency"] is False
        for item in tasks
    )
    dependencies = {
        dependency["target_key"]
        for item in tasks
        for dependency in item["dependencies"]
    }
    assert (
        "m4-v2-global-routing-recovery-v3-registered-replay-compatibility-v1"
        not in dependencies
    )


def test_supervisor_registers_the_singular_deeper_validation_dispatcher() -> None:
    supervisor = ResearchEvidenceSupervisor(require_clean_tree=False)
    capabilities = (
        subject.INTAKE_CAPABILITY,
        subject.DECISION_CAPABILITY,
        subject.DECISION_REPLAY_CAPABILITY,
        subject.ROUTE_CAPABILITY,
        subject.ROUTE_REPLAY_CAPABILITY,
    )
    dispatchers = [supervisor.capabilities[item] for item in capabilities]

    assert all(isinstance(item, M4V2DeeperValidationCapability) for item in dispatchers)
    assert len({id(item) for item in dispatchers}) == 1
