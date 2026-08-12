from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from dehps.config import ROOT_DIR
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory import (
    predictive_route_reconciliation as governance_reference,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    branch_decision as marginal,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    joint_residual_increment as joint,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    routing,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    temporal_marginal_increment as temporal,
)
from dehps.research_os.information_theory.progress import (
    M4_P3_PREDICTIVE_PREREGISTRATION_FACT,
    M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY,
    M4_V2_SUCCESSOR_REPLAY_FACTS,
    M4_V2_SUCCESSOR_TASKS,
    P2R_TASK_KEY,
    PREDICTIVE_P3_PASS_TO_P4_FACT,
    PREDICTIVE_P3_TASK_KEY,
    PREDICTIVE_P4_TASK_KEY,
    PREDICTIVE_P5_TASK_KEY,
    validate_m4_v2_successor_structure,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import (
    M4_V2_ARTIFACT_TYPE_REGISTRY,
    M4_V2_BRANCH_IDS,
    M4_V2_ESTIMAND_DIGESTS,
    M4_V2_MEASUREMENT_CONTRACT_DIGEST,
    M4_V2_MEASUREMENT_CONTRACT_KEY,
    M4_V2_NESTED_SCHEMA_REGISTRY,
    ControlPlaneManifest,
    M4V2BranchDecisionArtifact,
    MainlineArtifactRegistration,
    ResearchOSValidationError,
    TaskStatus,
    governance_execution_metadata_digest,
    governance_request_identity_digest,
    governance_reviewer_decision_digest,
    jsonable,
    m4_v2_canonical_json,
    validate_m4_v2_artifact_envelope,
    validate_m4_v2_nested_schema,
)

from scripts import build_m4_v2_global_routing_manifest as global_builder
from scripts import build_m4_v2_joint_residual_increment_manifest as joint_builder
from scripts import build_m4_v2_temporal_marginal_increment_manifest as temporal_builder
from scripts import build_m4_v2_three_branch_decision_manifest as marginal_builder

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
BASE_SHA = "15760f143ad92d7dd6df34a89924af950669a513"
CONTROL_PLANE_KEY = "m4-information-theory-mainline"
GIT_COMMIT = "a" * 40

EXPECTED_ARTIFACT_TYPES = {
    "M4V2BranchDecisionArtifact",
    "M4V2BranchDecisionReplayArtifact",
    "M4V2TemporalMarginalIncrementDesignArtifact",
    "M4V2TemporalMarginalIncrementPreregistrationBundleArtifact",
    "M4V2TemporalMarginalIncrementHealthAggregateArtifact",
    "M4V2TemporalMarginalIncrementHistoricalAggregateArtifact",
    "M4V2TemporalMarginalIncrementCandidateModelArtifact",
    "M4V2TemporalMarginalIncrementProducerCompletionArtifact",
    "M4V2TemporalMarginalIncrementScientificFailureArtifact",
    "M4V2JointResidualIncrementDesignArtifact",
    "M4V2JointResidualIncrementPreregistrationArtifact",
    "M4V2JointResidualMaximumEntropyBaselineArtifact",
    "M4V2JointResidualMeasurementHealthArtifact",
    "M4V2JointResidualHistoricalExecutionArtifact",
    "M4V2JointResidualCandidateModelArtifact",
    "M4V2JointResidualProducerCompletionArtifact",
    "M4V2JointResidualScientificFailureArtifact",
}

# Every numbered obligation in Request487 is intentionally mapped to at least one
# executable test below.  The matrix is itself checked so a future edit cannot
# silently drop one of the 45 frozen acceptance obligations.
ACCEPTANCE_MATRIX = {
    1: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    2: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    3: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    4: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    5: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    6: "test_marginal_identity_adoption_is_categorical_result_blind_and_singular",
    7: "test_governance_digest_equivalence_and_lifecycle_fail_closed",
    8: "test_marginal_identity_adoption_is_categorical_result_blind_and_singular",
    9: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    10: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    11: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    12: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    13: "test_resolver_global_route_and_four_and_p3_barrier",
    14: "test_resolver_global_route_and_four_and_p3_barrier",
    15: "test_global_router_is_finite_categorical_and_replay_is_pure",
    16: "test_global_router_is_finite_categorical_and_replay_is_pure",
    17: "test_global_router_is_finite_categorical_and_replay_is_pure",
    18: "test_global_router_repair_and_partial_positive_never_adaptive",
    19: "test_global_router_repair_and_partial_positive_never_adaptive",
    20: "test_resolver_global_route_and_four_and_p3_barrier",
    21: "test_resolver_global_route_and_four_and_p3_barrier",
    22: "test_resolver_global_route_and_four_and_p3_barrier",
    23: "test_resolver_global_route_and_four_and_p3_barrier",
    24: "test_p4_requires_completed_p3_and_explicit_pass",
    25: "test_p4_requires_completed_p3_and_explicit_pass",
    26: "test_source_contracts_exact_closure_and_digest_drift_fail_closed",
    27: "test_synthetic_cartesian_grid_seed_and_count_invariance",
    28: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    29: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    30: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    31: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    32: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    33: "test_acceptance_matrix_covers_all_45_required_goal_tests",
    34: "test_governance_digest_equivalence_and_lifecycle_fail_closed",
    35: "test_governance_constants_and_all_source_contract_seals",
    36: "test_successor_v2_estimator_identity_rejects_predecessor_v1",
    37: "test_fixed_null_warmup_exact_alias_and_falsifiers",
    38: "test_temporal_composite_and_joint_chronology_contracts",
    39: "test_synthetic_cartesian_grid_seed_and_count_invariance",
    40: "test_all_17_artifact_types_nested_lineage_paths_and_cardinalities",
    41: "test_holm_lineage_and_formal_one_rules_fail_before_workload",
    42: "test_global_router_is_finite_categorical_and_replay_is_pure",
    43: "test_atomic_publication_crash_reconciliation_and_conflicts",
    44: "test_engineering_boundary_has_zero_runtime_or_operator_actions",
    45: "test_resolver_global_route_and_four_and_p3_barrier",
}


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _manifest_payload() -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "show", f"{BASE_SHA}:{MANIFEST_PATH.relative_to(ROOT_DIR)}"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _successor_payload() -> dict[str, Any]:
    payload = _manifest_payload()
    for builder, digest in (
        (marginal_builder.build_manifest, _digest("marginal-source")),
        (temporal_builder.build_manifest, _digest("temporal-source")),
        (joint_builder.build_manifest, _digest("joint-source")),
        (global_builder.build_manifest, _digest("global-source")),
    ):
        payload, dry_run = builder(payload, digest)
        assert dry_run["status"] == "VERIFIED"
        assert dry_run["existing_goal_deletions"] == 0
        assert dry_run["existing_task_deletions"] == 0
        assert dry_run["existing_fact_deletions"] == 0
        assert dry_run["existing_state_regressions"] == 0
        assert dry_run["import_performed"] is False
    return payload


def _without_manifest_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(payload))
    result.pop("artifact_digest", None)
    result.pop("manifest_digest", None)
    return result


def _task(payload: Mapping[str, Any], task_key: str) -> dict[str, Any]:
    matches = [
        copy.deepcopy(item) for item in payload["tasks"] if item["task_key"] == task_key
    ]
    assert len(matches) == 1
    return matches[0]


def _dependency_tuples(task: Mapping[str, Any]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (
            item["dependency_type"],
            item["target_key"],
            item["required_status"],
        )
        for item in task["dependencies"]
    )


def _set_task_completed(payload: dict[str, Any], task_key: str) -> None:
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    typed_task = next(task for task in manifest.tasks if task.task_key == task_key)
    task = next(item for item in payload["tasks"] if item["task_key"] == task_key)
    task["status"] = "completed"
    task["completion_classification"] = "COMPLETE"
    if typed_task.requested_capability is not None:
        _add_facts(
            payload,
            mainline_completion_fact(
                task=typed_task,
                execution_id=_digest(f"completed-execution:{task_key}"),
            ),
        )


def _add_facts(payload: dict[str, Any], *facts: str) -> None:
    payload["facts"]["artifacts"] = sorted(
        set(payload["facts"]["artifacts"]).union(facts)
    )
    payload.pop("artifact_digest", None)
    payload.pop("manifest_digest", None)


def _resolution(manifest: ControlPlaneManifest, task_key: str):
    snapshot = ResearchOSControlPlane().resolve(manifest)
    return next(item for item in snapshot.resolutions if item.task_key == task_key)


def _registration(
    artifact: Mapping[str, Any],
    *,
    task_key: str,
    execution_id: str,
    slug: str,
    filename: str,
) -> dict[str, Any]:
    record = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key=CONTROL_PLANE_KEY,
        task_key=task_key,
        task_digest=_digest(f"task:{task_key}"),
        artifact_digest=str(artifact["artifact_digest"]),
        artifact_type=str(artifact["artifact_type"]),
        schema_version=str(artifact["schema_version"]),
        artifact_path=(
            f"runtime/research-os/mainline/tasks/{task_key}/{execution_id}/"
            f"artifacts/{slug}/{artifact['artifact_digest']}/{filename}"
        ),
        parent_digests=tuple(artifact["parent_digests"]),
        git_commit=GIT_COMMIT,
    )
    return {"registration_digest": record.registration_digest, **jsonable(record)}


class _TrackingIdentity(dict[str, Any]):
    def __init__(self, value: Mapping[str, Any]) -> None:
        super().__init__(value)
        self.reads: list[str] = []

    def get(self, key: str, default: Any = None) -> Any:
        self.reads.append(key)
        return super().get(key, default)

    def __getitem__(self, key: str) -> Any:
        self.reads.append(key)
        return super().__getitem__(key)


def _marginal_pair(*, evidence: str = "NEGATIVE", health: str = "PASS"):
    evaluated = health == "PASS"
    accepted = evaluated and evidence == "POSITIVE"
    categorical = {
        "measurement_health": health,
        "historical_run_status": "COMPLETE",
        "historical_evidence": evidence,
        "accepted_for_downstream_baseline": accepted,
        "accepted_model_artifact_digest": (
            marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST if evaluated else None
        ),
        "baseline_artifact_digest": (
            marginal.MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST if evaluated else None
        ),
        "baseline_source_model_artifact_digest": None,
        "endpoint_digest": _digest("marginal-endpoint"),
    }
    decision_execution = _digest("marginal-decision-execution")
    decision = marginal.build_marginal_static_branch_decision(
        categorical_identity=categorical,
        producer_execution_id=decision_execution,
        parent_digests=(
            _digest("marginal-source"),
            marginal.MARGINAL_STATIC_GATE_ARTIFACT_DIGEST,
        ),
    ).to_dict()
    decision_registration = _registration(
        decision,
        task_key=marginal.MARGINAL_STATIC_DECISION_TASK_KEY,
        execution_id=decision_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    replay_execution = _digest("marginal-replay-execution")
    replay = marginal.build_marginal_static_branch_decision_replay(
        decision=decision,
        source_contract_digest=_digest("marginal-source"),
        decision_registration_digest=decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "marginal-producer-execution-artifact"
        ),
        replay_execution_id=replay_execution,
    ).to_dict()
    replay_registration = _registration(
        replay,
        task_key=marginal.MARGINAL_STATIC_REPLAY_TASK_KEY,
        execution_id=replay_execution,
        slug="branch-decision-replay",
        filename="replay.json",
    )
    return {
        "decision": decision,
        "decision_registration": decision_registration,
        "replay": replay,
        "replay_registration": replay_registration,
    }


def _zero_compute_records(*, marginal_evidence: str = "NEGATIVE", health: str = "PASS"):
    marginal_record = _marginal_pair(evidence=marginal_evidence, health=health)
    temporal_execution = _digest("temporal-decision-execution")
    temporal_decision, temporal_completion = (
        temporal.build_temporal_parent_not_accepted_path(
            source_contract_digest=_digest("temporal-source"),
            preregistration_artifact_digest=_digest("temporal-preregistration"),
            marginal_decision_artifact=marginal_record["decision"],
            marginal_replay_artifact=marginal_record["replay"],
            producer_execution_id=temporal_execution,
        )
    )
    temporal_decision_registration = _registration(
        temporal_decision,
        task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        execution_id=temporal_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    temporal_replay_execution = _digest("temporal-replay-execution")
    temporal_replay = temporal.build_temporal_branch_replay(
        source_contract_digest=_digest("temporal-source"),
        decision_artifact=temporal_decision,
        decision_registration_digest=temporal_decision_registration[
            "registration_digest"
        ],
        decision_producer_execution_artifact_digest=_digest(
            "temporal-producer-execution-artifact"
        ),
        replay_execution_id=temporal_replay_execution,
    )
    temporal_replay_registration = _registration(
        temporal_replay,
        task_key=temporal.TEMPORAL_REPLAY_TASK_KEY,
        execution_id=temporal_replay_execution,
        slug="branch-decision-replay",
        filename="replay.json",
    )
    temporal_record = {
        "decision": temporal_decision,
        "decision_registration": temporal_decision_registration,
        "replay": temporal_replay,
        "replay_registration": temporal_replay_registration,
    }

    joint_execution = _digest("joint-decision-execution")
    joint_decision, joint_completion = joint.build_joint_parent_not_accepted_path(
        source_contract_digest=_digest("joint-source"),
        preregistration_artifact_digest=_digest("joint-preregistration"),
        marginal_decision_artifact=marginal_record["decision"],
        marginal_replay_artifact=marginal_record["replay"],
        temporal_decision_artifact=temporal_decision,
        temporal_replay_artifact=temporal_replay,
        producer_execution_id=joint_execution,
    )
    joint_decision_registration = _registration(
        joint_decision,
        task_key=joint.JOINT_PRODUCER_TASK_KEY,
        execution_id=joint_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    joint_replay_execution = _digest("joint-replay-execution")
    joint_replay = joint.build_joint_branch_replay(
        source_contract_digest=_digest("joint-source"),
        decision_artifact=joint_decision,
        decision_registration_digest=joint_decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "joint-producer-execution-artifact"
        ),
        replay_execution_id=joint_replay_execution,
    )
    joint_replay_registration = _registration(
        joint_replay,
        task_key=joint.JOINT_REPLAY_TASK_KEY,
        execution_id=joint_replay_execution,
        slug="branch-decision-replay",
        filename="replay.json",
    )
    joint_record = {
        "decision": joint_decision,
        "decision_registration": joint_decision_registration,
        "replay": joint_replay,
        "replay_registration": joint_replay_registration,
    }
    return (
        (marginal_record, temporal_record, joint_record),
        (temporal_completion, joint_completion),
    )


def _accepted_records():
    marginal_record = _marginal_pair(evidence="POSITIVE")

    temporal_execution = _digest("accepted-temporal-decision-execution")
    temporal_model = _digest("accepted-temporal-model")
    temporal_decision = M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        estimand_digest=M4_V2_ESTIMAND_DIGESTS["TEMPORAL_MARGINAL_INCREMENT"],
        decision_path="EVALUATED_COMPLETE",
        terminal_decision="BRANCH_INFORMATION_ACCEPTED",
        scientific_decision="BRANCH_INFORMATION_ACCEPTED",
        evaluation_status="COMPLETE",
        measurement_health="PASS",
        historical_evidence="POSITIVE",
        accepted_for_downstream_baseline=True,
        accepted_model_artifact_digest=temporal_model,
        baseline_artifact_digest=marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        baseline_source_model_artifact_digest=(
            marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST
        ),
        producer_task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        producer_execution_id=temporal_execution,
        parent_digests=(
            _digest("temporal-source"),
            _digest("temporal-preregistration"),
            marginal_record["decision"]["artifact_digest"],
            marginal_record["replay"]["artifact_digest"],
        ),
    ).to_dict()
    temporal_decision_registration = _registration(
        temporal_decision,
        task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        execution_id=temporal_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    temporal_replay_execution = _digest("accepted-temporal-replay-execution")
    temporal_replay = temporal.build_temporal_branch_replay(
        source_contract_digest=_digest("temporal-source"),
        decision_artifact=temporal_decision,
        decision_registration_digest=temporal_decision_registration[
            "registration_digest"
        ],
        decision_producer_execution_artifact_digest=_digest(
            "accepted-temporal-producer-execution-artifact"
        ),
        replay_execution_id=temporal_replay_execution,
    )
    temporal_record = {
        "decision": temporal_decision,
        "decision_registration": temporal_decision_registration,
        "replay": temporal_replay,
        "replay_registration": _registration(
            temporal_replay,
            task_key=temporal.TEMPORAL_REPLAY_TASK_KEY,
            execution_id=temporal_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }

    joint_execution = _digest("accepted-joint-decision-execution")
    joint_decision = M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id="JOINT_RESIDUAL_INCREMENT",
        estimand_digest=M4_V2_ESTIMAND_DIGESTS["JOINT_RESIDUAL_INCREMENT"],
        decision_path="EVALUATED_COMPLETE",
        terminal_decision="BRANCH_INFORMATION_ACCEPTED",
        scientific_decision="BRANCH_INFORMATION_ACCEPTED",
        evaluation_status="COMPLETE",
        measurement_health="PASS",
        historical_evidence="POSITIVE",
        accepted_for_downstream_baseline=True,
        accepted_model_artifact_digest=_digest("accepted-joint-model"),
        baseline_artifact_digest=_digest("accepted-joint-baseline"),
        baseline_source_model_artifact_digest=temporal_model,
        producer_task_key=joint.JOINT_PRODUCER_TASK_KEY,
        producer_execution_id=joint_execution,
        parent_digests=(
            _digest("joint-source"),
            _digest("joint-preregistration"),
            temporal_decision["artifact_digest"],
            temporal_replay["artifact_digest"],
        ),
    ).to_dict()
    joint_decision_registration = _registration(
        joint_decision,
        task_key=joint.JOINT_PRODUCER_TASK_KEY,
        execution_id=joint_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    joint_replay_execution = _digest("accepted-joint-replay-execution")
    joint_replay = joint.build_joint_branch_replay(
        source_contract_digest=_digest("joint-source"),
        decision_artifact=joint_decision,
        decision_registration_digest=joint_decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "accepted-joint-producer-execution-artifact"
        ),
        replay_execution_id=joint_replay_execution,
    )
    joint_record = {
        "decision": joint_decision,
        "decision_registration": joint_decision_registration,
        "replay": joint_replay,
        "replay_registration": _registration(
            joint_replay,
            task_key=joint.JOINT_REPLAY_TASK_KEY,
            execution_id=joint_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }
    return marginal_record, temporal_record, joint_record


def _partial_positive_records():
    """One valid positive ancestor plus an inconclusive Temporal and stopped Joint."""

    marginal_record = _marginal_pair(evidence="POSITIVE")
    temporal_execution = _digest("partial-temporal-decision-execution")
    temporal_decision = M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        estimand_digest=M4_V2_ESTIMAND_DIGESTS["TEMPORAL_MARGINAL_INCREMENT"],
        decision_path="EVALUATED_COMPLETE",
        terminal_decision="INCONCLUSIVE_DUE_TO_POWER",
        scientific_decision="INCONCLUSIVE_DUE_TO_POWER",
        evaluation_status="COMPLETE",
        measurement_health="PASS",
        historical_evidence="INCONCLUSIVE",
        accepted_for_downstream_baseline=False,
        accepted_model_artifact_digest=_digest("partial-temporal-model"),
        baseline_artifact_digest=marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        baseline_source_model_artifact_digest=(
            marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST
        ),
        producer_task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        producer_execution_id=temporal_execution,
        parent_digests=(
            _digest("temporal-source"),
            _digest("temporal-preregistration"),
            marginal_record["decision"]["artifact_digest"],
            marginal_record["replay"]["artifact_digest"],
        ),
    ).to_dict()
    temporal_decision_registration = _registration(
        temporal_decision,
        task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        execution_id=temporal_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    temporal_replay_execution = _digest("partial-temporal-replay-execution")
    temporal_replay = temporal.build_temporal_branch_replay(
        source_contract_digest=_digest("temporal-source"),
        decision_artifact=temporal_decision,
        decision_registration_digest=temporal_decision_registration[
            "registration_digest"
        ],
        decision_producer_execution_artifact_digest=_digest(
            "partial-temporal-producer-execution-artifact"
        ),
        replay_execution_id=temporal_replay_execution,
    )
    temporal_record = {
        "decision": temporal_decision,
        "decision_registration": temporal_decision_registration,
        "replay": temporal_replay,
        "replay_registration": _registration(
            temporal_replay,
            task_key=temporal.TEMPORAL_REPLAY_TASK_KEY,
            execution_id=temporal_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }

    joint_execution = _digest("partial-joint-decision-execution")
    joint_decision, _ = joint.build_joint_parent_not_accepted_path(
        source_contract_digest=_digest("joint-source"),
        preregistration_artifact_digest=_digest("joint-preregistration"),
        marginal_decision_artifact=marginal_record["decision"],
        marginal_replay_artifact=marginal_record["replay"],
        temporal_decision_artifact=temporal_decision,
        temporal_replay_artifact=temporal_replay,
        producer_execution_id=joint_execution,
    )
    joint_decision_registration = _registration(
        joint_decision,
        task_key=joint.JOINT_PRODUCER_TASK_KEY,
        execution_id=joint_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    joint_replay_execution = _digest("partial-joint-replay-execution")
    joint_replay = joint.build_joint_branch_replay(
        source_contract_digest=_digest("joint-source"),
        decision_artifact=joint_decision,
        decision_registration_digest=joint_decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "partial-joint-producer-execution-artifact"
        ),
        replay_execution_id=joint_replay_execution,
    )
    joint_record = {
        "decision": joint_decision,
        "decision_registration": joint_decision_registration,
        "replay": joint_replay,
        "replay_registration": _registration(
            joint_replay,
            task_key=joint.JOINT_REPLAY_TASK_KEY,
            execution_id=joint_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }
    return marginal_record, temporal_record, joint_record


def test_acceptance_matrix_covers_all_45_required_goal_tests() -> None:
    assert tuple(ACCEPTANCE_MATRIX) == tuple(range(1, 46))
    test_names = {
        name
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    }
    assert set(ACCEPTANCE_MATRIX.values()).issubset(test_names)


def test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history() -> None:
    before = ControlPlaneManifest.from_dict(_manifest_payload()).to_dict(
        include_digest=False
    )
    after = ControlPlaneManifest.from_dict(_successor_payload()).to_dict(
        include_digest=False
    )
    before_tasks = {item["task_key"]: item for item in before["tasks"]}
    after_tasks = {item["task_key"]: item for item in after["tasks"]}
    assert set(before_tasks).issubset(after_tasks)
    assert len(after_tasks) == len(before_tasks) + 11

    revised = {global_builder.GLOBAL_TASK, global_builder.PREDICTIVE_P3_TASK}
    for task_key, task in before_tasks.items():
        if task_key not in revised:
            assert after_tasks[task_key] == task
        else:
            for state_field in (
                "status",
                "completion_classification",
                "superseded_by_task_digest",
            ):
                assert after_tasks[task_key].get(state_field) == task.get(state_field)
    for fact_type, facts in before["facts"].items():
        assert set(facts).issubset(after["facts"][fact_type])

    p2 = after_tasks["m4-p2-synthetic-measurement-validation"]
    assert p2 == before_tasks["m4-p2-synthetic-measurement-validation"]
    p2r = after_tasks[P2R_TASK_KEY]
    assert p2r["status"] == "draft"
    assert p2r["completion_classification"] == "INTEGRATION_PENDING"
    assert all(
        dependency["target_key"] != P2R_TASK_KEY
        for key in (
            PREDICTIVE_P3_TASK_KEY,
            PREDICTIVE_P4_TASK_KEY,
            PREDICTIVE_P5_TASK_KEY,
        )
        for dependency in after_tasks[key]["dependencies"]
    )
    assert not any(
        "promotion:allowed" in fact.lower() for fact in after["facts"]["artifacts"]
    )

    structural_goal = next(
        item
        for item in after["goals"]
        if item["goal_key"] == "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY"
    )
    assert (
        "NO_STABLE_STRUCTURAL_UTILITY"
        in structural_goal["target_metric_manifest"]["allowed_decisions"]
    )
    assert structural_goal["target_metric_manifest"]["prediction_promotion"] == "closed"


def test_marginal_identity_adoption_is_categorical_result_blind_and_singular() -> None:
    tracked = _TrackingIdentity(
        {
            "measurement_health": "PASS",
            "historical_run_status": "COMPLETE",
            "historical_evidence": "NEGATIVE",
            "accepted_for_downstream_baseline": False,
            "accepted_model_artifact_digest": marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
            "baseline_artifact_digest": marginal.MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST,
            "baseline_source_model_artifact_digest": None,
            "endpoint_digest": _digest("endpoint"),
        }
    )
    first = marginal.build_marginal_static_branch_decision(
        categorical_identity=tracked,
        producer_execution_id=_digest("categorical-producer"),
        parent_digests=(_digest("source"), _digest("registered-gate")),
    )
    second = marginal.build_marginal_static_branch_decision(
        categorical_identity=dict(tracked),
        producer_execution_id=_digest("categorical-producer"),
        parent_digests=(_digest("source"), _digest("registered-gate")),
    )
    assert first.artifact_digest == second.artifact_digest
    assert first.branch_id == "MARGINAL_STATIC"
    assert first.terminal_decision == "NO_DETECTABLE_INFORMATION"
    assert first.producer_task_key == marginal.MARGINAL_STATIC_DECISION_TASK_KEY
    assert not {
        "raw_p_value",
        "fold_scores",
        "historical_fold_scores",
        "prediction_results",
    }.intersection(tracked.reads)

    polluted = dict(tracked)
    polluted["raw_primary_p_value"] = 0.001
    with pytest.raises(
        marginal.MarginalStaticBranchDecisionError, match="result_payload"
    ):
        marginal.build_marginal_static_branch_decision(
            categorical_identity=polluted,
            producer_execution_id=_digest("categorical-producer"),
            parent_digests=(_digest("source"), _digest("registered-gate")),
        )
    wrong_identity = dict(tracked)
    wrong_identity["accepted_model_artifact_digest"] = _digest("not-marginal")
    with pytest.raises(
        marginal.MarginalStaticBranchDecisionError, match="identity_mismatch"
    ):
        marginal.build_marginal_static_branch_decision(
            categorical_identity=wrong_identity,
            producer_execution_id=_digest("categorical-producer"),
            parent_digests=(_digest("source"), _digest("registered-gate")),
        )


def _governance_fixture(identifier: int, *, failed: bool = False):
    request = {
        "id": identifier,
        "request_key": f"request-{identifier}",
        "request_type": "engineering_implementation"
        if failed
        else "research_scheduler_request",
        "requested_by_role": "research",
        "requested_by": "research:fixture",
        "hypothesis_id": None,
        "experiment_id": None,
        "parent_request_id": None,
        "title": "result-blind fixture",
        "summary": "metadata only",
        "payload": {"result_payload_reads": 0, "computation": 0},
        "status": "failed" if failed else "completed",
        "risk_level": "critical",
        "requires_review": True,
        "metadata": {"scientific_result_read": False},
    }
    execution_id = identifier + 1000
    execution = {
        "id": execution_id,
        "request_id": identifier,
        "executor_role": "engineering" if failed else "research",
        "executor_id": "fixture:executor",
        "execution_type": "isolated",
        "status": "failed" if failed else "completed",
        "environment": "isolated",
        "run_id": f"run-{execution_id}",
        "started_at": "2026-08-11T00:00:00+00:00",
        "completed_at": "2026-08-11T00:00:01+00:00",
        "artifact_paths": [],
        "created_at": "2026-08-11T00:00:00+00:00",
    }
    decision_count = 3 if failed else 2
    decisions = []
    for offset in range(decision_count):
        decision_id = identifier * 10 + offset
        final = offset == decision_count - 1
        decisions.append(
            {
                "id": decision_id,
                "request_id": identifier,
                "previous_status": "running" if final else "under_review",
                "new_status": (
                    "failed"
                    if failed and final
                    else "completed"
                    if final
                    else "approved"
                ),
                "decision_code": (
                    "execution_failed"
                    if failed and final
                    else "execution_completed"
                    if final
                    else "request_approved"
                ),
                "summary": f"decision-{offset}",
                "reason": {"result_blind": True, "result_payload_reads": 0},
                "decided_by_role": "reviewer",
                "decided_by": "reviewer:fixture",
                "decided_at": f"2026-08-11T00:00:0{offset}+00:00",
                "created_at": f"2026-08-11T00:00:0{offset}+00:00",
            }
        )
    return request, execution, decisions


class _Rows:
    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self.rows = [copy.deepcopy(dict(row)) for row in rows]

    def fetchall(self):
        return copy.deepcopy(self.rows)


class _GovernanceCursor:
    def __init__(self, fixture: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        self.fixture = fixture
        self.sql: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql: str, _params: Any):
        normalized = " ".join(sql.split())
        self.sql.append(normalized)
        if "FROM agent_requests" in normalized:
            return _Rows(self.fixture["requests"])
        if (
            "FROM agent_request_executions" in normalized
            and "count(*)" not in normalized
        ):
            return _Rows(self.fixture["executions"])
        if "decision_code = 'request_approved'" in normalized:
            return _Rows(self.fixture["counts"])
        if "FROM agent_request_decisions" in normalized and "max(id)" not in normalized:
            return _Rows(self.fixture["decisions"])
        if "count(*) AS count" in normalized:
            return _Rows(self.fixture["counts"])
        if "max(id) AS last_decision_id" in normalized:
            return _Rows(self.fixture["last"])
        raise AssertionError(normalized)


class _GovernanceConnection:
    def __init__(self, cursor: _GovernanceCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self, **_kwargs):
        return self._cursor


class _GovernanceRepository:
    def __init__(self, fixture: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        self.cursor = _GovernanceCursor(fixture)

    def _connection_factory(self):
        return _GovernanceConnection(self.cursor)


def _synthetic_governance_contract():
    completed_request, completed_execution, completed_decisions = _governance_fixture(1)
    failed_request, failed_execution, failed_decisions = _governance_fixture(
        2, failed=True
    )
    completed_binding = {
        "request_id": 1,
        "execution_id": completed_execution["id"],
        "reviewer_approval_decision_id": completed_decisions[0]["id"],
        "completion_decision_id": completed_decisions[-1]["id"],
        "request_identity_digest": governance_request_identity_digest(
            completed_request
        ),
        "execution_metadata_digest": governance_execution_metadata_digest(
            completed_execution
        ),
        "reviewer_approval_decision_digest": governance_reviewer_decision_digest(
            completed_decisions[0]
        ),
        "completion_decision_digest": governance_reviewer_decision_digest(
            completed_decisions[-1]
        ),
    }
    failed_binding = {
        "request_id": 2,
        "execution_id": failed_execution["id"],
        "approval_decision_id": failed_decisions[0]["id"],
        "start_decision_id": failed_decisions[1]["id"],
        "failure_decision_id": failed_decisions[-1]["id"],
        "request_identity_digest": governance_request_identity_digest(failed_request),
        "execution_metadata_digest": governance_execution_metadata_digest(
            failed_execution
        ),
        "approval_decision_digest": governance_reviewer_decision_digest(
            failed_decisions[0]
        ),
        "start_decision_digest": governance_reviewer_decision_digest(
            failed_decisions[1]
        ),
        "failure_decision_digest": governance_reviewer_decision_digest(
            failed_decisions[-1]
        ),
        "artifact_paths": [],
        "repository_files_changed": 0,
    }
    fixture = {
        "requests": [completed_request, failed_request],
        "executions": [completed_execution, failed_execution],
        "decisions": [*completed_decisions, *failed_decisions],
        "counts": [{"request_id": 1, "count": 1}, {"request_id": 2, "count": 1}],
        "last": [
            {"request_id": 1, "last_decision_id": completed_decisions[-1]["id"]},
            {"request_id": 2, "last_decision_id": failed_decisions[-1]["id"]},
        ],
    }
    return completed_binding, failed_binding, fixture


def test_governance_digest_equivalence_and_lifecycle_fail_closed(monkeypatch) -> None:
    request, execution, decisions = _governance_fixture(77)
    assert governance_request_identity_digest(
        request
    ) == governance_reference.governance_request_identity_digest(request)
    sanitized_execution = {
        key: value
        for key, value in execution.items()
        if key not in {"status", "completed_at", "artifact_paths"}
    }
    assert governance_execution_metadata_digest(
        sanitized_execution
    ) == governance_reference.governance_execution_metadata_digest(sanitized_execution)
    assert governance_reviewer_decision_digest(
        decisions[0]
    ) == governance_reference.governance_reviewer_decision_digest(decisions[0])
    for forbidden in (
        "result",
        "result_json",
        "execution_result",
        "error",
        "error_json",
    ):
        polluted = dict(sanitized_execution)
        polluted[forbidden] = {"must_not_be_read": True}
        with pytest.raises(ResearchOSValidationError, match="not_sanitized"):
            governance_execution_metadata_digest(polluted)

    completed_binding, failed_binding, fixture = _synthetic_governance_contract()
    monkeypatch.setattr(
        supervisor_module,
        "M4_V2_SUCCESSOR_GOVERNANCE_BINDINGS",
        (completed_binding,),
    )
    monkeypatch.setattr(
        supervisor_module,
        "M4_V2_FAILED_ENGINEERING_PREDECESSOR_BINDING",
        failed_binding,
    )
    repository = _GovernanceRepository(fixture)
    supervisor_module._verify_m4_v2_successor_governance(agent_repository=repository)
    combined_sql = " ".join(repository.cursor.sql).lower()
    assert "result_json" not in combined_sql
    assert "error_json" not in combined_sql
    assert "artifact_paths_json as artifact_paths" in combined_sql

    for mutation in ("duplicate_execution", "later_decision", "artifact_path"):
        broken = copy.deepcopy(fixture)
        if mutation == "duplicate_execution":
            broken["counts"][0]["count"] = 2
        elif mutation == "later_decision":
            broken["last"][0]["last_decision_id"] += 100
        else:
            broken["executions"][0]["artifact_paths"] = ["forbidden.json"]
        with pytest.raises(
            supervisor_module.MainlineSupervisorError, match="lifecycle changed"
        ):
            supervisor_module._verify_m4_v2_successor_governance(
                agent_repository=_GovernanceRepository(broken)
            )

    reused_failed = copy.deepcopy(fixture)
    reused_failed["requests"][1]["status"] = "completed"
    reused_failed["executions"][1]["status"] = "completed"
    with pytest.raises(
        supervisor_module.MainlineSupervisorError,
        match="failed Engineering predecessor",
    ):
        supervisor_module._verify_m4_v2_successor_governance(
            agent_repository=_GovernanceRepository(reused_failed)
        )


def test_governance_constants_and_all_source_contract_seals() -> None:
    bindings = supervisor_module.M4_V2_SUCCESSOR_GOVERNANCE_BINDINGS
    failed = supervisor_module.M4_V2_FAILED_ENGINEERING_PREDECESSOR_BINDING
    assert [item["request_id"] for item in bindings] == [
        478,
        479,
        480,
        481,
        482,
        484,
        485,
        486,
    ]
    assert [item["execution_id"] for item in bindings] == [
        399,
        400,
        402,
        401,
        403,
        405,
        406,
        407,
    ]
    assert len(bindings) == 8
    assert sum(key.endswith("_digest") for item in bindings for key in item) == 32
    assert failed["request_id"] == 483
    assert failed["execution_id"] == 404
    assert failed["artifact_paths"] == []
    assert failed["repository_files_changed"] == 0
    assert sum(key.endswith("_digest") for key in failed) == 5

    assert supervisor_module.M4_V2_HISTORICAL_SOURCE_PIN == (
        "4e787ebc1b13e1a16fe42b80054cb2a01f4c0b6b"
    )
    assert set(supervisor_module.M4_V2_HISTORICAL_SOURCE_IDENTITIES) == {
        "marginal",
        "temporal",
        "joint",
        "global",
    }
    for family, spec in supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS.items():
        legacy = supervisor_module.verify_m4_v2_historical_successor_source_contract(
            root_dir=ROOT_DIR, family=family
        )
        assert (
            legacy["artifact_digest"],
            legacy["source_set_digest"],
        ) == supervisor_module.M4_V2_HISTORICAL_SOURCE_IDENTITIES[family]
        assert len(legacy["source_entries"]) == 7
        if family in {"temporal", "joint"}:
            assert spec["selector"] == f"{family}_v3"
            assert spec["path"].endswith("source-v3.json")
            assert spec["historical_path"].endswith("source-v2.json")
        else:
            # Marginal and Global have no live selector after Request512.  Their
            # checked-out files are irrelevant to this audit-only verifier.
            assert "selector" not in spec


def test_zero_compute_parent_stop_chain_replays_and_global_route() -> None:
    records, completions = _zero_compute_records()
    temporal_completion, joint_completion = completions
    for record, branch_id in zip(records, M4_V2_BRANCH_IDS, strict=True):
        decision = validate_m4_v2_artifact_envelope(record["decision"])
        replay = validate_m4_v2_artifact_envelope(record["replay"])
        assert decision["body"]["branch_id"] == branch_id
        assert replay["body"]["branch_id"] == branch_id
        assert replay["body"]["replay_status"] == "REGISTERED_REPLAY_VERIFIED"
        assert replay["body"]["workload_rerun"] is False
        assert (
            replay["body"]["decision_registration_digest"]
            == replay["parent_digests"][2]
        )
    for decision in (records[1]["decision"], records[2]["decision"]):
        assert (
            decision["body"]["terminal_decision"] == "NOT_EVALUABLE_PARENT_NOT_ACCEPTED"
        )
        assert decision["body"]["scientific_decision"] is None
        assert decision["body"]["evaluation_status"] == "NOT_RUN_PARENT_NOT_ACCEPTED"
    for completion in completions:
        body = completion["body"]
        assert body["historical_outcomes_read"] == 0
        assert body["synthetic_replicate_count"] == 0
        assert body["warmup_alias_position_count"] == 0
        assert body["historical_fold_count"] == 0
        assert body["bootstrap_resample_count"] == 0
        assert body["evidence_created"] is False
        assert body["promotion_gate_opened"] is False
    assert (
        temporal_completion["body"]["registration_count_including_mainline_execution"]
        == 3
    )
    assert (
        joint_completion["body"]["registration_count_including_mainline_execution"] == 3
    )

    route = routing.compile_m4_v2_global_route_decision(
        records,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert route["route"] == "DEEPER_VALIDATION_REQUIRED"
    replay = routing.replay_m4_v2_global_route_decision(
        records,
        route,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["capability_status"] == "REGISTERED_REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert replay["durable_write_count"] == 0


def test_global_router_is_finite_categorical_and_replay_is_pure(monkeypatch) -> None:
    records = _accepted_records()
    route = routing.compile_m4_v2_global_route_decision(
        records,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert route["route"] == "ADAPTIVE_RESEARCH_ELIGIBLE"
    assert route["next_lane"] == "P3_PREDICTIVE_PREREGISTRATION_FREEZE"
    assert route["route"] in routing.GLOBAL_ROUTES
    assert route["decision_replay_coverage"] == "COMPLETE"
    assert route["measurement_global_coverage"] == "FULL"
    assert route["router_conclusive_coverage"] == "FULL"
    assert set(route["decision_projection_rows"][0]) == {
        "branch_id",
        "estimand_digest",
        "decision_path",
        "terminal_decision",
        "scientific_decision",
        "evaluation_status",
        "measurement_health",
        "historical_evidence",
        "accepted_for_downstream_baseline",
        "accepted_model_artifact_digest",
        "baseline_artifact_digest",
        "baseline_source_model_artifact_digest",
        "decision_artifact_digest",
        "decision_producer_execution_id",
        "replay_artifact_digest",
        "replay_registration_digest",
    }

    forbidden_workload_calls = []
    for module, name in (
        (temporal, "build_temporal_warmup_index"),
        (temporal, "build_temporal_composite_view"),
        (joint, "build_q_base_checkpoint_index"),
        (joint, "build_joint_z_checkpoint_index"),
        (joint, "build_joint_target_prediction_index"),
    ):
        monkeypatch.setattr(
            module,
            name,
            lambda *_args, _name=name, **_kwargs: forbidden_workload_calls.append(
                _name
            ),
        )
    replay = routing.replay_m4_v2_global_route_decision(
        records,
        route,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert forbidden_workload_calls == []
    assert replay == {
        "status": "REPLAY_VERIFIED",
        "outer_status": "REPLAY_VERIFIED",
        "capability_status": "REGISTERED_REPLAY_VERIFIED",
        "same_route_decision_identity": True,
        "same_registered_content": True,
        "route_artifact_digest": route["artifact_digest"],
        "source_integrity_verified": True,
        "workload_rerun": False,
        "raw_history_read": False,
        "numerical_result_payload_read": False,
        "durable_write_count": 0,
        "new_fact_count": 0,
        "durable_state_changed": False,
    }
    source = inspect.getsource(routing.compile_m4_v2_global_route_decision)
    assert "repository" not in source.lower()
    assert "fold" not in source.lower()


def test_global_router_repair_and_partial_positive_never_adaptive() -> None:
    repair_records, _ = _zero_compute_records(
        marginal_evidence="INCONCLUSIVE", health="REPAIR"
    )
    repair = routing.compile_m4_v2_global_route_decision(
        repair_records,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert repair["route"] == "MEASUREMENT_REPAIR_REQUIRED"
    assert repair["route"] != "ADAPTIVE_RESEARCH_ELIGIBLE"

    partial = routing.compile_m4_v2_global_route_decision(
        _partial_positive_records(),
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert partial["positive_branches"] == ["MARGINAL_STATIC"]
    assert partial["measurement_global_coverage"] == "PARTIAL"
    assert partial["router_conclusive_coverage"] == "PARTIAL"
    assert partial["route"] == "DEEPER_VALIDATION_REQUIRED"
    assert partial["route"] != "ADAPTIVE_RESEARCH_ELIGIBLE"


def test_resolver_global_route_and_four_and_p3_barrier() -> None:
    payload = _successor_payload()
    manifest = ControlPlaneManifest.from_dict(payload)
    structure = validate_m4_v2_successor_structure(manifest)
    assert structure == {
        "status": "VERIFIED",
        "branch_order": list(M4_V2_BRANCH_IDS),
        "global_replay_facts": list(M4_V2_SUCCESSOR_REPLAY_FACTS),
        "predictive_p3_dependency_count": 4,
        "predictive_preregistration_capability": None,
        "predictive_preregistration_fact_available": False,
        "p3_fold_execution_authorized": False,
    }
    global_task = _task(payload, global_builder.GLOBAL_TASK)
    placeholder = _task(payload, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY)
    predictive_p3 = _task(payload, PREDICTIVE_P3_TASK_KEY)
    assert global_task["requested_capability"] == routing.GLOBAL_ROUTE_CAPABILITY
    assert _dependency_tuples(global_task) == (
        ("artifact", global_builder.SOURCE_FACT, "available"),
        *(("artifact", fact, "available") for fact in M4_V2_SUCCESSOR_REPLAY_FACTS),
    )
    assert placeholder["requested_capability"] is None
    assert placeholder["metric_contract"]["runner"] is None
    assert placeholder["metric_contract"]["execution_authorized"] is False
    assert placeholder["completion_classification"] == "INTEGRATION_PENDING"
    assert _dependency_tuples(placeholder) == (
        ("task", global_builder.GLOBAL_TASK, "completed"),
        ("artifact", routing.ADAPTIVE_RESEARCH_ELIGIBILITY_FACT, "available"),
    )
    assert _dependency_tuples(predictive_p3) == (
        *_dependency_tuples(placeholder),
        ("task", M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY, "completed"),
        ("artifact", M4_P3_PREDICTIVE_PREREGISTRATION_FACT, "available"),
    )

    for fact in M4_V2_SUCCESSOR_REPLAY_FACTS[:-1]:
        _add_facts(payload, fact)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, global_builder.GLOBAL_TASK).status
        is TaskStatus.DEPENDENCY_WAIT
    )

    _add_facts(payload, M4_V2_SUCCESSOR_REPLAY_FACTS[-1])
    for task_key in set(M4_V2_SUCCESSOR_TASKS.values()) - {global_builder.GLOBAL_TASK}:
        _set_task_completed(payload, task_key)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    successor_ready = [
        item.task_key
        for item in ResearchOSControlPlane().resolve(manifest).ready_queue
        if item.task_key in M4_V2_SUCCESSOR_TASKS.values()
    ]
    assert successor_ready == [global_builder.GLOBAL_TASK]

    _set_task_completed(payload, global_builder.GLOBAL_TASK)
    _add_facts(payload, routing.ADAPTIVE_RESEARCH_ELIGIBILITY_FACT)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY).status
        is TaskStatus.READY
    )
    assert (
        _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )

    _set_task_completed(payload, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )
    assert M4_P3_PREDICTIVE_PREREGISTRATION_FACT not in manifest.facts.artifacts

    _add_facts(payload, M4_P3_PREDICTIVE_PREREGISTRATION_FACT)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status is TaskStatus.READY
    successor_capabilities = {
        task["requested_capability"]
        for task in payload["tasks"]
        if task["task_key"] in M4_V2_SUCCESSOR_TASKS.values()
    }
    assert (
        _task(payload, PREDICTIVE_P3_TASK_KEY)["requested_capability"]
        not in successor_capabilities
    )


def test_p4_requires_completed_p3_and_explicit_pass() -> None:
    payload = _successor_payload()
    p4 = _task(payload, PREDICTIVE_P4_TASK_KEY)
    assert _dependency_tuples(p4) == (
        ("task", PREDICTIVE_P3_TASK_KEY, "completed"),
        ("artifact", PREDICTIVE_P3_PASS_TO_P4_FACT, "available"),
    )
    _set_task_completed(payload, global_builder.GLOBAL_TASK)
    _set_task_completed(payload, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY)
    _add_facts(
        payload,
        routing.ADAPTIVE_RESEARCH_ELIGIBILITY_FACT,
        M4_P3_PREDICTIVE_PREREGISTRATION_FACT,
    )
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status is TaskStatus.READY
    assert (
        _resolution(manifest, PREDICTIVE_P4_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )
    _set_task_completed(payload, PREDICTIVE_P3_TASK_KEY)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, PREDICTIVE_P4_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )
    _add_facts(payload, PREDICTIVE_P3_PASS_TO_P4_FACT)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert _resolution(manifest, PREDICTIVE_P4_TASK_KEY).status is TaskStatus.READY


def test_source_contracts_exact_closure_and_digest_drift_fail_closed(
    tmp_path: Path,
) -> None:
    specs = supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS
    legacy_source_sets: dict[str, tuple[str, ...]] = {}
    for family in ("marginal", "temporal", "joint", "global"):
        contract = supervisor_module.verify_m4_v2_historical_successor_source_contract(
            root_dir=ROOT_DIR, family=family
        )
        entries = tuple(item["path"] for item in contract["source_entries"])
        assert len(entries) == len(set(entries)) == 7
        legacy_source_sets[family] = entries
        for item in contract["source_entries"]:
            historical_bytes = supervisor_module._m4_v2_raw_git_blob(
                root_dir=ROOT_DIR,
                commit=supervisor_module.M4_V2_HISTORICAL_SOURCE_PIN,
                path=item["path"],
            )
            assert item["sha256"] == hashlib.sha256(historical_bytes).hexdigest()

    active_source_sets: dict[str, tuple[str, ...]] = {}
    expected_arrays = {
        "temporal": "c3aa7e4fbb5a60393e68582ebf9b47d572892b8c2a8494db8065b8a604ab1898",
        "joint": "b9d51e1feb75e656708e410c9f719d839fedc3ed5c6dc2eae9929be8bfdcb60d",
    }
    for family in ("temporal", "joint"):
        selector = specs[family]["selector"]
        contract = supervisor_module.load_m4_v2_active_successor_source_contract(
            root_dir=ROOT_DIR, selector=selector
        )
        entries = tuple(item["path"] for item in contract["source_entries"])
        assert entries == tuple(specs[family]["entries"])
        assert len(entries) == len(set(entries)) == 12
        assert contract["schema_version"].endswith("source-contract.v3")
        assert contract["source_path_array_contract_version"] == 4
        assert contract["source_path_array_digest"] == expected_arrays[family]
        assert contract["accepted_support_input_schema"] == (
            "dehps-m4-v2-accepted-support-input.v3"
        )
        assert all(
            item["sha256"]
            == hashlib.sha256((ROOT_DIR / item["path"]).read_bytes()).hexdigest()
            for item in contract["source_entries"]
        )
        active_source_sets[family] = entries

    for rejected_selector in (
        "marginal",
        "global",
        "temporal",
        "joint",
        "temporal_v2",
        "joint_v2",
    ):
        with pytest.raises(
            supervisor_module.MainlineSupervisorError,
            match="selector is not authorized",
        ):
            supervisor_module.load_m4_v2_active_successor_source_contract(
                root_dir=ROOT_DIR, selector=rejected_selector
            )

    assert "branch_decision" not in {
        node.module
        for module in (temporal, joint, routing)
        for node in ast.walk(ast.parse(inspect.getsource(module)))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert M4V2BranchDecisionArtifact.__module__ == "dehps.research_os.models"

    family = "temporal"
    spec = specs[family]
    for entry in supervisor_module.load_m4_v2_active_successor_source_contract(
        root_dir=ROOT_DIR, selector=spec["selector"]
    )["source_entries"]:
        target = tmp_path / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / entry["path"], target)
    contract_target = tmp_path / spec["path"]
    contract_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT_DIR / spec["path"], contract_target)
    first_source = tmp_path / spec["entries"][0]
    first_source.write_bytes(first_source.read_bytes() + b"\n# digest drift\n")
    with pytest.raises(
        supervisor_module.MainlineSupervisorError, match="source bytes changed"
    ):
        supervisor_module.load_m4_v2_active_successor_source_contract(
            root_dir=tmp_path, selector=spec["selector"]
        )

    original_raw_git_blob = supervisor_module._m4_v2_raw_git_blob

    def tampered_historical_blob(*, root_dir: Path, commit: str, path: str) -> bytes:
        content = original_raw_git_blob(root_dir=root_dir, commit=commit, path=path)
        if path == legacy_source_sets["joint"][0]:
            return content + b"\n# historical tamper\n"
        return content

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            supervisor_module, "_m4_v2_raw_git_blob", tampered_historical_blob
        )
        with pytest.raises(
            supervisor_module.MainlineSupervisorError,
            match="historical source bytes changed",
        ):
            supervisor_module.verify_m4_v2_historical_successor_source_contract(
                root_dir=ROOT_DIR, family="joint"
            )


def test_successor_v2_estimator_identity_rejects_predecessor_v1() -> None:
    payload = _successor_payload()
    temporal_tasks = [
        item
        for item in payload["tasks"]
        if item["task_key"].startswith("m4-v2-temporal-marginal-increment")
    ]
    joint_tasks = [
        item
        for item in payload["tasks"]
        if item["task_key"].startswith("m4-v2-joint-residual-increment")
    ]
    assert temporal_tasks and joint_tasks
    assert all(
        item["input_artifact_digests"] == [_digest("temporal-source")]
        for item in temporal_tasks
    )
    assert all(
        item["input_artifact_digests"] == [_digest("joint-source")]
        for item in joint_tasks
    )
    assert all(
        item["metric_contract"]["estimator_id"] == temporal.TEMPORAL_MODEL_ID
        for item in temporal_tasks
    )
    assert all(
        item["metric_contract"]["estimator_id"] == joint.JOINT_ESTIMATOR_ID
        for item in joint_tasks
    )
    assert joint.REQUEST481_PREDECESSOR_ESTIMATOR_ID != joint.JOINT_ESTIMATOR_ID
    assert (
        temporal.REQUEST481_PREDECESSOR_JOINT_ESTIMATOR_ID
        != temporal.SUCCESSOR_JOINT_ESTIMATOR_ID
    )
    assert (
        supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["temporal"]["selector"]
        == "temporal_v3"
    )
    assert (
        supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["joint"]["selector"]
        == "joint_v3"
    )
    assert supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["temporal"]["path"].endswith(
        "source-v3.json"
    )
    assert supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["joint"]["path"].endswith(
        "source-v3.json"
    )


def _warmup_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rule = temporal.build_transition_local_warmup_rule()
    rows = []
    for ordinal in range(temporal.WARMUP_START, temporal.WARMUP_END + 1):
        checkpoint = temporal.build_strict_prior_marginal_checkpoint(
            transition_ordinal=ordinal,
            issue=f"issue-{ordinal}",
            prefix_last_issue=f"issue-{ordinal - 1}",
            prefix_outcome_chain_digest=_digest(f"prefix-{ordinal}"),
            q_m_marginal_content_digest=_digest(f"qm-marginal-{ordinal}"),
            q_m_full_distribution_content_digest=_digest(f"qm-full-{ordinal}"),
        )
        rows.append(temporal.build_temporal_warmup_row(checkpoint))
    return rule, rows


def test_fixed_null_warmup_exact_alias_and_falsifiers() -> None:
    rule, rows = _warmup_rows()
    index = temporal.build_temporal_warmup_index(rows, rule_digest=rule["rule_digest"])
    assert rule["transition_range"] == [2, 900]
    assert rule["transition_count"] == 899
    assert rule["theta_float_hex"] == "0x0.0p+0"
    assert rule["theta_ieee754_binary64_be_hex"] == "0000000000000000"
    assert rule["negative_zero_allowed"] is False
    assert rule["temporal_theta_fit_invoked"] is False
    assert rule["temporal_theta_root_existence_test_invoked"] is False
    assert rule["regularization"] is None
    assert rule["fallback"] is None
    assert index["row_count"] == 899
    assert [item["transition_ordinal"] for item in rows] == list(range(2, 901))
    assert all(
        item["q_t_marginal_content_digest"] == item["q_m_marginal_content_digest"]
        for item in rows
    )
    assert all(
        item["q_t_full_distribution_content_digest"]
        == item["q_m_full_distribution_content_digest"]
        for item in rows
    )
    assert all(item["temporal_theta_fit_invoked"] is False for item in rows)

    for field, changed in (
        ("theta_float_hex", "-0x0.0p+0"),
        ("theta_float_hex", "0x1.0000000000000p-1"),
        ("temporal_theta_fit_invoked", True),
        ("q_t_full_distribution_content_digest", _digest("reconstructed-q-t")),
    ):
        tampered = copy.deepcopy(rows[0])
        tampered[field] = changed
        with pytest.raises(temporal.TemporalMarginalIncrementContractError):
            temporal.validate_temporal_warmup_row(tampered)
    with pytest.raises(
        temporal.TemporalMarginalIncrementContractError, match="coverage_or_order"
    ):
        temporal.build_temporal_warmup_index(rows[:-1], rule_digest=rule["rule_digest"])
    duplicated = [*rows[:-1], rows[-2]]
    with pytest.raises(
        temporal.TemporalMarginalIncrementContractError, match="coverage_or_order"
    ):
        temporal.build_temporal_warmup_index(
            duplicated, rule_digest=rule["rule_digest"]
        )

    same_prefix = dict(rows[10])
    same_prefix["non_identity_suffix_provenance"] = "changed"
    temporal.assert_temporal_suffix_noninterference(rows[10], same_prefix)
    changed_prefix = dict(rows[10])
    changed_prefix["q_m_full_distribution_content_digest"] = _digest("suffix-leak")
    with pytest.raises(temporal.TemporalMarginalIncrementContractError, match="suffix"):
        temporal.assert_temporal_suffix_noninterference(rows[10], changed_prefix)
    assert (
        temporal.temporal_synthetic_warmup_position(
            cell_index=0, replicate_index=0, transition_ordinal=2
        )
        == 0
    )
    assert (
        temporal.temporal_synthetic_warmup_position(
            cell_index=13, replicate_index=511, transition_ordinal=900
        )
        == 6_444_031
    )


def test_temporal_composite_and_joint_chronology_contracts() -> None:
    view = temporal.build_temporal_composite_view(
        warmup_index_digest=_digest("warmup-index"),
        accepted_temporal_evaluation_index_digest=_digest("accepted-index"),
    )
    assert view["transition_range"] == [2, 3481]
    assert view["row_count"] == 3480
    assert temporal.temporal_checkpoint_plan(900).theta_fit_invoked is False
    assert temporal.temporal_checkpoint_plan(901).prefix_last_ordinal == 900
    assert temporal.temporal_checkpoint_plan(901).theta_fit_invoked is True
    assert temporal.temporal_checkpoint_plan(902).prefix_last_ordinal == 901
    assert joint.joint_checkpoint_plan(901).eta_training_range == (2, 900)
    assert joint.joint_checkpoint_plan(901).eta_training_count == 899
    assert joint.joint_checkpoint_plan(902).eta_training_range == (2, 901)
    assert joint.joint_checkpoint_plan(902).eta_training_count == 900
    assert joint.joint_checkpoint_plan(902).target_z_may_be_reconstructed is False


def test_synthetic_cartesian_grid_seed_and_count_invariance() -> None:
    expected_counts = {
        "cell_count": 14,
        "replicates_per_cell": 512,
        "synthetic_replicate_count": 7168,
        "synthetic_generated_issue_count": 15_920_128,
        "outer_evaluation_issue_count": 9_468_928,
        "bootstrap_resample_count": 14_651_392,
        "historical_fold_count": 2581,
        "historical_child_count": 16_000,
        "warmup_transition_count_per_replicate": 899,
        "warmup_alias_position_count": 6_444_032,
    }
    assert dict(temporal.PLANNED_COUNTS) == expected_counts
    assert dict(joint.PLANNED_COUNTS) == expected_counts
    assert temporal.SYNTHETIC_WARMUP_RNG_CALL_COUNT == 0
    assert joint.SYNTHETIC_WARMUP_RNG_CALL_COUNT == 0
    assert temporal.SYNTHETIC_BOOTSTRAP_SEED_MATERIAL_CHANGED_BY_WARMUP is False
    assert joint.SYNTHETIC_BOOTSTRAP_SEED_MATERIAL_CHANGED_BY_WARMUP is False
    assert temporal.SYNTHETIC_WARMUP_COMPUTED_PER_BOOTSTRAP_CHILD is False
    assert joint.SYNTHETIC_WARMUP_COMPUTED_PER_BOOTSTRAP_CHILD is False

    health = _digest("health-contract")
    seed = _digest("seed-contract")
    temporal_coordinates = [
        temporal.build_temporal_synthetic_sequence_coordinate(
            health_contract_digest=health,
            seed_contract_digest=seed,
            cell_index=cell,
            replicate_index=replicate,
        )
        for cell in range(14)
        for replicate in range(512)
    ]
    joint_coordinates = [
        joint.build_joint_synthetic_sequence_coordinate(
            health_contract_digest=health,
            seed_contract_digest=seed,
            cell_index=cell,
            replicate_index=replicate,
        )
        for cell in range(14)
        for replicate in range(512)
    ]
    assert len(temporal_coordinates) == len(joint_coordinates) == 7168
    assert len({item["coordinate_digest"] for item in temporal_coordinates}) == 7168
    assert len({item["coordinate_digest"] for item in joint_coordinates}) == 7168
    assert {item["coordinate_digest"] for item in temporal_coordinates}.isdisjoint(
        item["coordinate_digest"] for item in joint_coordinates
    )
    assert all(
        item["seed_contract_digest"] == seed
        for item in temporal_coordinates + joint_coordinates
    )
    assert all(
        item["sequence_seed_full_sha256"] != seed
        for item in temporal_coordinates + joint_coordinates
    )
    tampered = copy.deepcopy(temporal_coordinates[0])
    tampered["sequence_seed_full_sha256"] = _digest("seed-drift")
    with pytest.raises(
        temporal.TemporalMarginalIncrementContractError, match="seed_or_cell"
    ):
        temporal.validate_temporal_synthetic_sequence_coordinate(tampered)


def test_all_17_artifact_types_nested_lineage_paths_and_cardinalities() -> None:
    assert len(M4_V2_ARTIFACT_TYPE_REGISTRY) == 17
    assert set(M4_V2_ARTIFACT_TYPE_REGISTRY) == EXPECTED_ARTIFACT_TYPES
    assert len(M4_V2_NESTED_SCHEMA_REGISTRY) == 46
    assert all(spec.body_fields for spec in M4_V2_ARTIFACT_TYPE_REGISTRY.values())
    assert all(
        len(spec.body_fields) == len(set(spec.body_fields))
        for spec in M4_V2_ARTIFACT_TYPE_REGISTRY.values()
    )

    records, completions = _zero_compute_records()
    for record in records:
        for artifact_name in ("decision", "replay"):
            envelope = record[artifact_name]
            validate_m4_v2_artifact_envelope(envelope)
            missing = copy.deepcopy(envelope)
            missing.pop("parent_digests")
            with pytest.raises(ResearchOSValidationError):
                validate_m4_v2_artifact_envelope(missing)
            extra = copy.deepcopy(envelope)
            extra["sidecar"] = {}
            with pytest.raises(ResearchOSValidationError):
                validate_m4_v2_artifact_envelope(extra)
    eighteenth = copy.deepcopy(records[0]["decision"])
    eighteenth["artifact_type"] = "M4V2ForbiddenEighteenthArtifact"
    with pytest.raises(ResearchOSValidationError, match="unknown"):
        validate_m4_v2_artifact_envelope(eighteenth)

    assert temporal.temporal_registration_plan(
        "PARENT_NOT_ACCEPTED"
    ).artifact_types_in_registration_order == (
        "M4V2BranchDecisionArtifact",
        "M4V2TemporalMarginalIncrementProducerCompletionArtifact",
        "research_os_mainline_execution",
    )
    assert joint.joint_registration_plan(
        "PARENT_NOT_ACCEPTED"
    ).artifact_types_in_registration_order == (
        "M4V2BranchDecisionArtifact",
        "M4V2JointResidualProducerCompletionArtifact",
        "research_os_mainline_execution",
    )
    assert (
        temporal.temporal_registration_plan(
            "EVALUATED_COMPLETE"
        ).registration_count_including_mainline_execution
        == 6
    )
    assert (
        joint.joint_registration_plan(
            "EVALUATED_COMPLETE"
        ).registration_count_including_mainline_execution
        == 7
    )
    for completion in completions:
        assert (
            completion["artifact_digest"]
            not in completion["body"]["registered_artifact_digests_in_order"]
        )

    q_digest = _digest("q")
    certificate = joint.build_q_base_reconstruction_certificate(
        transition_ordinal=2,
        temporal_support_row_digest=_digest("temporal-row"),
        q_t_full_distribution_content_digest=q_digest,
        q_base_full_distribution_content_digest=q_digest,
        max_probability_difference_float_hex="0x0.0p+0",
        max_marginal_difference_float_hex="0x0.0p+0",
        normalization_residual_float_hex="0x0.0p+0",
    )
    checkpoint = joint.build_q_base_checkpoint(
        transition_ordinal=2,
        issue="issue-2",
        temporal_support_row_digest=_digest("temporal-row"),
        temporal_composite_view_digest=_digest("temporal-view"),
        q_t_marginal_content_digest=_digest("q-marginal"),
        q_t_full_distribution_content_digest=q_digest,
        baseline_contract_digest=_digest("baseline-contract"),
        reconstruction_certificate=certificate,
    )
    assert checkpoint["q_base_full_distribution_content_digest"] == q_digest
    drift = copy.deepcopy(checkpoint)
    drift["q_base_full_distribution_content_digest"] = _digest("qbase-drift")
    with pytest.raises(joint.JointResidualIncrementContractError, match="alias"):
        joint.validate_q_base_checkpoint(drift)
    coordinate = joint.build_certificate_coordinate_identity(
        scope="HISTORICAL_Z",
        source_contract_digest=_digest("joint-source"),
        preregistration_artifact_digest=_digest("joint-prereg"),
        producer_execution_id=_digest("joint-producer"),
        transition_ordinal=2,
        issue_or_sequence_coordinate_digest="issue-2",
        support_kind="WARMUP_NULL_ALIAS",
    )
    validate_m4_v2_nested_schema("certificate_coordinate_identity", coordinate)
    coordinate_drift = copy.deepcopy(coordinate)
    coordinate_drift["transition_ordinal"] = 3
    with pytest.raises(joint.JointResidualIncrementContractError):
        joint.validate_certificate_coordinate_identity(coordinate_drift)

    execution_id = _digest("global-execution")
    artifact_digest = _digest("global-route-artifact")
    expected_path = (
        f"runtime/research-os/mainline/tasks/{routing.GLOBAL_ROUTE_TASK_KEY}/"
        f"{execution_id}/artifacts/global-routing-decision/{artifact_digest}/decision.json"
    )
    assert (
        routing.m4_v2_global_route_artifact_path(
            execution_id=execution_id, artifact_digest=artifact_digest
        )
        == expected_path
    )


def test_holm_lineage_and_formal_one_rules_fail_before_workload() -> None:
    exact = temporal.validate_accepted_parent_raw_p_lineage(
        parent_branch_id="MARGINAL_STATIC",
        terminal_decision="BRANCH_INFORMATION_ACCEPTED",
        accepted_for_downstream_baseline=True,
        historical_artifact_digest=temporal.MARGINAL_RAW_P_ARTIFACT_DIGEST,
        historical_registration_digest=temporal.MARGINAL_RAW_P_REGISTRATION_DIGEST,
        producer_execution_id=_digest("marginal-producer"),
        replay_status="REGISTERED_REPLAY_VERIFIED",
        raw_primary_p_value=0.125,
    )
    assert exact == 0.125
    for changed in (
        {"historical_artifact_digest": _digest("missing-historical")},
        {"historical_registration_digest": _digest("missing-registration")},
        {"replay_status": "REPLAY_VERIFIED"},
        {"accepted_for_downstream_baseline": False},
    ):
        arguments = {
            "parent_branch_id": "MARGINAL_STATIC",
            "terminal_decision": "BRANCH_INFORMATION_ACCEPTED",
            "accepted_for_downstream_baseline": True,
            "historical_artifact_digest": temporal.MARGINAL_RAW_P_ARTIFACT_DIGEST,
            "historical_registration_digest": temporal.MARGINAL_RAW_P_REGISTRATION_DIGEST,
            "producer_execution_id": _digest("marginal-producer"),
            "replay_status": "REGISTERED_REPLAY_VERIFIED",
            "raw_primary_p_value": 0.125,
            **changed,
        }
        with pytest.raises(
            temporal.TemporalMarginalIncrementContractError, match="lineage"
        ):
            temporal.validate_accepted_parent_raw_p_lineage(**arguments)
    assert (
        temporal.validate_temporal_holm_family(
            {
                "MARGINAL_STATIC": 0.125,
                "TEMPORAL_MARGINAL_INCREMENT": 0.25,
                "JOINT_RESIDUAL_INCREMENT": 1.0,
            },
            marginal_raw_p_value=0.125,
            temporal_raw_p_value=0.25,
        )["JOINT_RESIDUAL_INCREMENT"]
        == 1.0
    )
    assert joint.formal_holm_one_allowed(
        branch_id="JOINT_RESIDUAL_INCREMENT",
        terminal_decision=None,
        replay_status=None,
        temporal_is_current_evaluated_branch=True,
        joint_has_formally_not_run=True,
    )
    for terminal in (
        "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
        "MEASUREMENT_REPAIR_REQUIRED",
        "INVALID_EXECUTION",
    ):
        assert joint.formal_holm_one_allowed(
            branch_id="TEMPORAL_MARGINAL_INCREMENT",
            terminal_decision=terminal,
            replay_status="REGISTERED_REPLAY_VERIFIED",
        )
    assert not joint.formal_holm_one_allowed(
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        terminal_decision="NO_DETECTABLE_INFORMATION",
        replay_status="REGISTERED_REPLAY_VERIFIED",
    )
    assert not joint.formal_holm_one_allowed(
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        terminal_decision="INVALID_EXECUTION",
        replay_status=None,
    )


def test_supervisor_global_replay_is_zero_write_and_preserves_all_identities(
    monkeypatch,
) -> None:
    payload = _successor_payload()
    manifest = ControlPlaneManifest.from_dict(payload)
    before_manifest = m4_v2_canonical_json(manifest.to_dict(include_digest=True))
    before_snapshot = ResearchOSControlPlane().resolve(manifest)
    before_ready = m4_v2_canonical_json(jsonable(before_snapshot.ready_queue))
    records = _accepted_records()
    route = routing.compile_m4_v2_global_route_decision(
        records,
        source_contract_digest=_digest("global-source"),
        task_digest=next(
            task
            for task in manifest.tasks
            if task.task_key == routing.GLOBAL_ROUTE_TASK_KEY
        ).artifact_digest,
    )

    class ReadOnlyRepository:
        def __init__(self):
            self.loads = 0
            self.writes: list[str] = []
            self.control_plane = ResearchOSControlPlane()

        def load_manifest(self, *, control_plane_key: str):
            assert control_plane_key == CONTROL_PLANE_KEY
            self.loads += 1
            return manifest

        def __getattr__(self, name: str):
            if any(
                token in name
                for token in (
                    "record",
                    "import",
                    "write",
                    "register",
                    "update",
                    "append",
                )
            ):

                def forbidden(*_args, **_kwargs):
                    self.writes.append(name)
                    raise AssertionError(f"durable write attempted: {name}")

                return forbidden
            raise AttributeError(name)

    repository = ReadOnlyRepository()
    execution_id = _digest("global-execution")
    execution_artifact = {
        "execution_id": execution_id,
        "artifact_digest": _digest("global-execution-artifact"),
    }
    registrations = [
        {"artifact_type": routing.GLOBAL_ROUTE_ARTIFACT_TYPE},
        {"artifact_type": "research_os_mainline_execution"},
    ]
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_kwargs: ({}, execution_artifact, registrations),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_m4_v2_successor_source_contract",
        lambda **_kwargs: {"artifact_digest": _digest("global-source")},
    )
    monkeypatch.setattr(
        supervisor_module.M4V2SuccessorCapability,
        "_source",
        lambda _self, _family, _task: {"artifact_digest": _digest("global-source")},
    )
    by_decision_task = {
        marginal.MARGINAL_STATIC_DECISION_TASK_KEY: records[0],
        temporal.TEMPORAL_PRODUCER_TASK_KEY: records[1],
        joint.JOINT_PRODUCER_TASK_KEY: records[2],
    }
    monkeypatch.setattr(
        supervisor_module.M4V2SuccessorCapability,
        "_branch_record",
        lambda _self, **kwargs: by_decision_task[kwargs["decision_task_key"]],
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **_kwargs: route,
    )
    supervisor = object.__new__(supervisor_module.ResearchEvidenceSupervisor)
    supervisor.repository = repository
    supervisor.root_dir = ROOT_DIR
    supervisor.control_plane_key = CONTROL_PLANE_KEY
    status_projection_calls: list[str] = []
    monkeypatch.setattr(
        supervisor,
        "_build_lane_status",
        lambda current_manifest, **kwargs: (
            status_projection_calls.append(current_manifest.artifact_digest)
            or {
                "manifest_digest": current_manifest.artifact_digest,
                "snapshot_digest": kwargs["snapshot"].snapshot_digest,
                "ready_queue": jsonable(kwargs["snapshot"].ready_queue),
            }
        ),
    )
    monkeypatch.setattr(
        supervisor,
        "_write_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("state write")),
    )
    monkeypatch.setattr(
        supervisor,
        "_write_lane_status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("lane write")),
    )
    replay = supervisor.replay(task_key=routing.GLOBAL_ROUTE_TASK_KEY)
    assert replay["status"] == "REPLAY_VERIFIED"
    assert (
        replay["capability_replay"]["capability_status"] == "REGISTERED_REPLAY_VERIFIED"
    )
    assert replay["capability_replay"]["workload_rerun"] is False
    assert replay["durable_state_changed"] is False
    assert repository.writes == []
    assert status_projection_calls == [manifest.artifact_digest]
    assert (
        m4_v2_canonical_json(manifest.to_dict(include_digest=True)) == before_manifest
    )
    after_snapshot = ResearchOSControlPlane().resolve(manifest)
    assert after_snapshot.snapshot_digest == before_snapshot.snapshot_digest
    assert m4_v2_canonical_json(jsonable(after_snapshot.ready_queue)) == before_ready


class _RegistrationCursor:
    def __init__(self, stored: Mapping[str, Any] | None) -> None:
        self.stored = None if stored is None else copy.deepcopy(dict(stored))
        self._last = ""

    def execute(self, sql: str, _params: Any):
        self._last = " ".join(sql.split())
        return self

    def fetchone(self):
        if "SELECT registration_json" in self._last:
            return None if self.stored is None else {"registration_json": self.stored}
        raise AssertionError(self._last)


def test_atomic_publication_crash_reconciliation_and_conflicts(
    tmp_path: Path, monkeypatch
) -> None:
    staged = tmp_path / ".staging" / "00.json"
    content = b'{"frozen":true}\n'
    fsync_calls: list[int] = []
    real_fsync = os.fsync

    def observed_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(supervisor_module.os, "fsync", observed_fsync)
    supervisor_module._atomic_write_staged_file(staged, content)
    assert staged.read_bytes() == content
    assert len(fsync_calls) >= 2
    with pytest.raises(FileExistsError):
        supervisor_module._atomic_write_staged_file(staged, content)

    destination = tmp_path / "canonical" / "artifact.json"
    ownership = supervisor_module._atomic_publish_noreplace(staged, destination)
    assert ownership[2] is True
    assert not staged.exists()
    assert destination.read_bytes() == content

    identical_stage = tmp_path / ".staging" / "01.json"
    supervisor_module._atomic_write_staged_file(identical_stage, content)
    preexisting = supervisor_module._atomic_publish_noreplace(
        identical_stage, destination
    )
    assert preexisting[2] is False
    assert identical_stage.exists()
    mismatch_stage = tmp_path / ".staging" / "02.json"
    supervisor_module._atomic_write_staged_file(mismatch_stage, b"different\n")
    with pytest.raises(supervisor_module.MainlineSupervisorError, match="collision"):
        supervisor_module._atomic_publish_noreplace(mismatch_stage, destination)
    assert destination.read_bytes() == content

    supervisor_module.ResearchEvidenceSupervisor._cleanup_owned_atomic_paths(
        {destination: ownership}
    )
    assert not destination.exists()
    preserved = tmp_path / "canonical" / "preexisting.json"
    preserved.parent.mkdir(parents=True, exist_ok=True)
    preserved.write_bytes(content)
    stat = preserved.stat()
    supervisor_module.ResearchEvidenceSupervisor._cleanup_owned_atomic_paths(
        {preserved: (stat.st_dev, stat.st_ino, False)}
    )
    assert preserved.exists()

    registration = MainlineArtifactRegistration(
        execution_id=_digest("execution"),
        control_plane_key=CONTROL_PLANE_KEY,
        task_key="task",
        task_digest=_digest("task"),
        artifact_digest=_digest("artifact"),
        artifact_type="artifact",
        schema_version="v1",
        artifact_path="runtime/research-os/mainline/tasks/task/artifact.json",
        parent_digests=(_digest("parent"),),
        git_commit=GIT_COMMIT,
    )
    exact = jsonable(registration)
    supervisor_module._atomic_insert_registration(
        _RegistrationCursor(exact), registration
    )
    mismatch = dict(exact)
    mismatch["artifact_path"] = "mismatch"
    with pytest.raises(
        supervisor_module.MainlineSupervisorError, match="not idempotent"
    ):
        supervisor_module._atomic_insert_registration(
            _RegistrationCursor(mismatch), registration
        )

    class ReconciliationRepository:
        def __init__(
            self,
            *,
            head_digest: str,
            registrations: Sequence[Mapping[str, Any]],
            completed_event_count: int,
        ) -> None:
            self.head_digest = head_digest
            self.registrations = list(registrations)
            self.completed_event_count = completed_event_count

        def load_manifest(self, *, control_plane_key: str):
            assert control_plane_key == CONTROL_PLANE_KEY
            return SimpleNamespace(artifact_digest=self.head_digest)

        def list_mainline_execution_events(self, **_kwargs):
            return [
                {"event_type": "completed"} for _ in range(self.completed_event_count)
            ]

        def list_mainline_artifacts(self, **_kwargs):
            return copy.deepcopy(self.registrations)

    expected_row = {
        "registration_digest": registration.registration_digest,
        **jsonable(registration),
    }
    head = _digest("head")
    complete = _digest("complete")
    task = SimpleNamespace(task_key="task")

    def reconcile(repository: Any) -> str:
        instance = object.__new__(supervisor_module.ResearchEvidenceSupervisor)
        instance.repository = repository
        instance.root_dir = ROOT_DIR
        instance.control_plane_key = CONTROL_PLANE_KEY
        return instance._reconcile_atomic_completion(
            task=task,
            execution_id=registration.execution_id,
            expected_head_manifest_digest=head,
            completed_manifest_digest=complete,
            expected_registrations=(registration,),
        )

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_kwargs: ({}, {}, []),
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[expected_row],
                completed_event_count=1,
            )
        )
        == "COMMITTED"
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=head,
                registrations=[],
                completed_event_count=0,
            )
        )
        == "ABSENT"
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[expected_row],
                completed_event_count=0,
            )
        )
        == "INCIDENT"
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[],
                completed_event_count=1,
            )
        )
        == "INCIDENT"
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_kwargs: (_ for _ in ()).throw(
            supervisor_module.MainlineSupervisorError("registered file missing")
        ),
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[expected_row],
                completed_event_count=1,
            )
        )
        == "INCIDENT"
    )

    source = inspect.getsource(
        supervisor_module.ResearchEvidenceSupervisor._complete_atomic_capability
    )
    assert source.count("connection.commit()") == 1
    assert source.index("_atomic_publish_noreplace") < source.index(
        "connection.commit()"
    )
    assert "self.repository.connection_factory()" in source
    repository_diff = subprocess.run(
        ["git", "diff", "--", "apps/worker-python/dehps/research_os/repository.py"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert repository_diff == ""


def test_engineering_boundary_has_zero_runtime_or_operator_actions() -> None:
    changed = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert not any(" runtime/" in line or line.endswith(" runtime") for line in changed)
    assert not any("data/output" in line for line in changed)
    for builder in (
        marginal_builder.build_manifest,
        temporal_builder.build_manifest,
        joint_builder.build_manifest,
        global_builder.build_manifest,
    ):
        source = inspect.getsource(builder)
        assert "import_manifest" not in source
        assert "run_once" not in source
        assert "promotion" not in source.lower() or "promotion_gate_opened" in source
    successor = supervisor_module.M4V2SuccessorCapability
    assert not hasattr(successor, "promote")
    assert (
        M4_P3_PREDICTIVE_PREREGISTRATION_FACT
        not in _successor_payload()["facts"]["artifacts"]
    )
