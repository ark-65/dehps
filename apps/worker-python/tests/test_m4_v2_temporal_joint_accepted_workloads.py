from __future__ import annotations

import copy
import hashlib
import sys
from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest
from dehps.research_os.information_theory.measurement_system_v2 import (
    m4_v2_joint_residual_increment_execution as joint_runner,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    m4_v2_temporal_marginal_increment_execution as temporal_runner,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    temporal_marginal_increment as temporal,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    temporal_probability_capsule as capsule,
)
from dehps.research_os.information_theory.measurement_system_v2.branch_decision import (
    MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST,
    MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
    build_marginal_static_branch_decision,
    build_marginal_static_branch_decision_replay,
)
from dehps.research_os.information_theory.measurement_system_v2.m4_v2_increment_execution_support import (
    EVENT_TYPES,
    INPUT_BUNDLE_FIELDS,
    RESOLVED_INPUT_FIELDS,
    AcceptedWorkloadContractError,
    build_event,
    build_full_transcript,
    build_resume_index,
    evaluated_coordinate_sequence,
    event_payload_digest,
    event_payload_schema,
    validate_event,
    validate_full_transcript,
    validate_input_bundle,
    validate_resume_index,
)
from dehps.research_os.models import (
    M4_V2_ARTIFACT_TYPE_REGISTRY,
    M4_V2_ESTIMAND_DIGESTS,
    M4_V2_MEASUREMENT_CONTRACT_DIGEST,
    M4_V2_MEASUREMENT_CONTRACT_KEY,
    M4_V2_NESTED_SCHEMA_REGISTRY,
    M4V2BranchDecisionArtifact,
    MainlineArtifactRegistration,
    m4_v2_build_artifact_envelope,
    m4_v2_domain_digest,
)

TEMPORAL = "TEMPORAL_MARGINAL_INCREMENT"
JOINT = "JOINT_RESIDUAL_INCREMENT"
EXECUTION_ID = hashlib.sha256(b"accepted-workload-execution").hexdigest()
RUNTIME_CONTRACT = {
    "python_implementation": "cpython",
    "python_version": "3.14.4",
    "numpy_version": "2.4.6",
    "byteorder": "little",
    "float_identity": (
        "IEEE-754 binary64 values serialized only by the already frozen "
        "float.hex and big-endian transport rules"
    ),
    "mismatch_rule": "fail before workload start; no compatibility fallback",
}


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _domain(branch_id: str, suffix: str) -> str:
    prefix = "dehps.m4.v2.temporal" if branch_id == TEMPORAL else "dehps.m4.v2.joint"
    return f"{prefix}.{suffix}"


def _accepted_marginal_parent(
    source_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    decision = build_marginal_static_branch_decision(
        categorical_identity={
            "measurement_health": "PASS",
            "historical_run_status": "COMPLETE",
            "historical_evidence": "POSITIVE",
            "accepted_for_downstream_baseline": True,
            "accepted_model_artifact_digest": MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
            "baseline_artifact_digest": MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST,
            "baseline_source_model_artifact_digest": None,
            "endpoint_digest": _digest("marginal-endpoint"),
        },
        producer_execution_id=_digest("marginal-decision-execution"),
        parent_digests=(source_digest, _digest("marginal-parent")),
    ).to_dict()
    replay = build_marginal_static_branch_decision_replay(
        decision=decision,
        source_contract_digest=source_digest,
        decision_registration_digest=_digest("marginal-decision-registration"),
        decision_producer_execution_artifact_digest=_digest(
            "marginal-decision-execution-artifact"
        ),
        replay_execution_id=_digest("marginal-replay-execution"),
    ).to_dict()
    return decision, replay


def _seed_contract(branch_id: str) -> dict[str, Any]:
    seed = {
        "upstream_seed_and_resampling_contract": {
            "root_seeds": {
                "synthetic": {
                    "known_material_full_sha256": _digest(f"{branch_id}-synthetic")
                },
                "historical": {
                    "known_material_full_sha256": _digest(f"{branch_id}-historical")
                },
            }
        }
    }
    seed["seed_contract_digest"] = m4_v2_domain_digest(
        seed, domain=_domain(branch_id, "seed-contract.v3")
    )
    return seed


def _temporal_preregistration(
    *, source_digest: str, seed_digest: str, warmup_digest: str
) -> dict[str, Any]:
    artifact_type = "M4V2TemporalMarginalIncrementPreregistrationBundleArtifact"
    fields = M4_V2_ARTIFACT_TYPE_REGISTRY[artifact_type].body_fields
    body = {field: _digest(f"preregistration:{field}") for field in fields}
    rule = temporal.build_transition_local_warmup_rule()
    body.update(
        {
            "status": "FROZEN",
            "measurement_contract_key": M4_V2_MEASUREMENT_CONTRACT_KEY,
            "measurement_contract_digest": M4_V2_MEASUREMENT_CONTRACT_DIGEST,
            "branch_id": TEMPORAL,
            "estimand_digest": M4_V2_ESTIMAND_DIGESTS[TEMPORAL],
            "source_contract_digest": source_digest,
            "seed_contract_digest": seed_digest,
            "warmup_request_payload_digest": warmup_digest,
            "transition_local_warmup_rule": rule,
            "transition_local_warmup_rule_digest": rule["rule_digest"],
            "planned_counts": dict(temporal.PLANNED_COUNTS),
            "execution_authorized": False,
            "result_payload_reads": 0,
            "historical_outcomes_read": 0,
            "scientific_computation": 0,
            "evidence_created": False,
            "production_action": "none",
        }
    )
    return m4_v2_build_artifact_envelope(
        artifact_type=artifact_type,
        body=body,
        parent_digests=(source_digest,),
    )


def _marginal_support_registration() -> dict[str, Any]:
    record = MainlineArtifactRegistration(
        execution_id="f55ded4805b328738b85e1143dafde436c7925ee1c76dafbb049cd600c7e7da6",
        control_plane_key="m4-information-theory-mainline",
        task_key="m4-v2-marginal-static-historical-measurement-gate-compiler",
        task_digest="a109c223111b622d8b6e7c468ca878de6eda3c2e472e7632520571c5dba3eafd",
        artifact_digest=MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        artifact_type="m4_v2_marginal_static_evaluated_model_identity",
        schema_version="dehps-m4-v2-marginal-static-evaluated-model-identity.v1",
        artifact_path=(
            "runtime/research-os/mainline/tasks/"
            "m4-v2-marginal-static-historical-measurement-gate-compiler/"
            "f55ded4805b328738b85e1143dafde436c7925ee1c76dafbb049cd600c7e7da6/"
            "artifacts/marginal-static-evaluated-model/"
            f"{MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST}/model.json"
        ),
        parent_digests=(
            "dcab7f9d512c40cfafdc7eae0800cd1aac90c18674760d9d20cb46850bb5d60c",
            "cb6e184beb00bdb22af28a4ee6770240327f59f0fd171f443315841866b421a3",
            "36056c0168bf71a995ec2a0bb9bf4663b0222b8fce621899a1e861282597e841",
            "5044252bd63afb00bd7719a4c20febf29a5ce41ab2f6679def643d450f9eb2d0",
            MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST,
        ),
        git_commit="720617d3d7745dd56498eab1f344dfb140ca99ee",
    )
    assert record.registration_digest == (
        "e3fc6ac295d69c4771a6f00c4f42a95902b5f5c64811d5a2fb85b12ec6234eae"
    )
    return {
        "registration_digest": record.registration_digest,
        "execution_id": record.execution_id,
        "control_plane_key": record.control_plane_key,
        "task_key": record.task_key,
        "task_digest": record.task_digest,
        "artifact_digest": record.artifact_digest,
        "artifact_type": record.artifact_type,
        "schema_version": record.schema_version,
        "artifact_path": record.artifact_path,
        "parent_digests": list(record.parent_digests),
        "git_commit": record.git_commit,
    }


def _early_terminal(branch_id: str) -> dict[str, Any]:
    return {
        "execution_subpath": "EARLY_IDENTITY_VALID_HEALTH_REPAIR",
        "decision_path": "IDENTITY_VALID_HEALTH_REPAIR",
        "failure_stage": "HEALTH",
        "terminal_decision": "MEASUREMENT_REPAIR_REQUIRED",
        "scientific_decision": "MEASUREMENT_REPAIR_REQUIRED",
        "evaluation_status": "REPAIR_REQUIRED",
        "measurement_health": "REPAIR",
        "historical_evidence": "NOT_RUN",
        "baseline_artifact_body_or_null": None,
        "health_artifact_body_or_null": None,
        "historical_artifact_body_or_null": None,
        "candidate_artifact_body_or_null": None,
        "failure_artifact_body_or_null": {
            "branch_id": branch_id,
            "failure_code": "REGISTERED_PRE_DRAW_REPAIR",
        },
        "expected_baseline_artifact_digest_or_null": None,
        "expected_health_artifact_digest_or_null": None,
        "expected_historical_artifact_digest_or_null": None,
        "expected_candidate_artifact_digest_or_null": None,
        "expected_failure_artifact_digest_or_null": _digest(
            f"{branch_id}-pre-draw-failure"
        ),
        "completed_fold_count": 0,
        "completed_resample_count": 0,
        "reason_codes": ["REGISTERED_PRE_DRAW_REPAIR"],
        "planned_counts": dict(temporal.PLANNED_COUNTS),
    }


def _computation(branch_id: str) -> dict[str, Any]:
    return {
        "pre_draw_terminal_outcome_or_null": _early_terminal(branch_id),
        "health_replicate_evidence_in_order": [],
        "health_aggregate_body_or_null": None,
        "historical_fold_commits_in_order": [],
        "historical_sensitivity_summaries_in_order": [],
        "historical_aggregate_body_or_null": None,
        "terminal_outcome_without_preterminal": _early_terminal(branch_id),
    }


def _temporal_bundle() -> dict[str, Any]:
    branch_id = TEMPORAL
    source_digest = _digest("temporal-registered-source-v3")
    source_set_digest = _digest("temporal-registered-source-set-v4")
    seed = _seed_contract(branch_id)
    warmup_digest = _digest("temporal-warmup-request")
    preregistration = _temporal_preregistration(
        source_digest=source_digest,
        seed_digest=seed["seed_contract_digest"],
        warmup_digest=warmup_digest,
    )
    decision, replay = _accepted_marginal_parent(source_digest)
    registration = _marginal_support_registration()
    support = {
        "artifact_digest": MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        "body": {
            "model_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "accepted_for_downstream_baseline": True,
            "production_action": "none",
        },
    }
    static_digests = {
        name: _digest(f"temporal-{name}")
        for name in (
            "holm",
            "dataset",
            "dataset-content",
            "fold-manifest",
            "checkpoint-order-manifest",
            "resampling-manifest",
            "historical-execution-plan",
            "fixture-source",
        )
    }
    source = {
        "artifact_digest": source_digest,
        "source_set_digest": source_set_digest,
        "body": {
            "seed_contract": seed,
            "seed_contract_digest": seed["seed_contract_digest"],
        },
    }
    resolved_values = {
        "source_contract_envelope": source,
        "preregistration_envelope": preregistration,
        "ordered_parent_decision_envelopes": [decision],
        "ordered_parent_replay_envelopes": [replay],
        "accepted_support_model_envelope": support,
        "accepted_support_model_registration_record": registration,
        "ordered_holm_lineage_envelopes": [{"artifact_digest": static_digests["holm"]}],
        "dataset_snapshot_envelope": {
            "artifact_digest": static_digests["dataset"],
            "body": {"dataset_content_digest": static_digests["dataset-content"]},
        },
        "fold_manifest_envelope": {"artifact_digest": static_digests["fold-manifest"]},
        "checkpoint_order_manifest_envelope": {
            "artifact_digest": static_digests["checkpoint-order-manifest"]
        },
        "resampling_manifest_envelope": {
            "artifact_digest": static_digests["resampling-manifest"]
        },
        "historical_execution_plan_envelope": {
            "artifact_digest": static_digests["historical-execution-plan"],
            "body": {"accepted_workload_computation": _computation(branch_id)},
        },
        "fixture_source_envelope": {
            "artifact_digest": static_digests["fixture-source"]
        },
        "seed_contract": seed,
    }
    resolved = {field: resolved_values[field] for field in RESOLVED_INPUT_FIELDS}
    values = {
        "schema_version": "m4-v2-temporal-accepted-parent-workload-input.v2",
        "branch_id": branch_id,
        "source_contract_artifact_digest": source_digest,
        "source_set_digest": source_set_digest,
        "preregistration_artifact_digest": preregistration["artifact_digest"],
        "producer_execution_id": EXECUTION_ID,
        "ordered_parent_decision_artifact_digests": [decision["artifact_digest"]],
        "ordered_parent_replay_artifact_digests": [replay["artifact_digest"]],
        "accepted_support_model_artifact_digest": MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        "accepted_support_model_registration_digest": registration[
            "registration_digest"
        ],
        "ordered_holm_lineage_artifact_digests": [static_digests["holm"]],
        "dataset_snapshot_artifact_digest": static_digests["dataset"],
        "dataset_content_digest": static_digests["dataset-content"],
        "fold_manifest_artifact_digest": static_digests["fold-manifest"],
        "checkpoint_order_manifest_artifact_digest": static_digests[
            "checkpoint-order-manifest"
        ],
        "resampling_manifest_artifact_digest": static_digests["resampling-manifest"],
        "historical_execution_plan_artifact_digest": static_digests[
            "historical-execution-plan"
        ],
        "fixture_source_artifact_digest": static_digests["fixture-source"],
        "synthetic_root_seed_full_sha256": seed[
            "upstream_seed_and_resampling_contract"
        ]["root_seeds"]["synthetic"]["known_material_full_sha256"],
        "historical_root_seed_full_sha256": seed[
            "upstream_seed_and_resampling_contract"
        ]["root_seeds"]["historical"]["known_material_full_sha256"],
        "warmup_request_payload_digest": warmup_digest,
        "runtime_contract": RUNTIME_CONTRACT,
        "resolved_inputs": resolved,
    }
    bundle = {field: values[field] for field in INPUT_BUNDLE_FIELDS[:-1]}
    bundle["input_bundle_digest"] = m4_v2_domain_digest(
        bundle, domain=_domain(branch_id, "accepted-workload-input-bundle.v2")
    )
    return validate_input_bundle(bundle, branch_id=branch_id)


def _capsule_row(ordinal: int) -> dict[str, Any]:
    support_kind = (
        "WARMUP_NULL_ALIAS" if ordinal <= 900 else "ACCEPTED_TEMPORAL_EVALUATION"
    )
    issue = f"issue-{ordinal:04d}"
    owner_digest = _digest(f"q-m-owner-{ordinal}")
    owner = {
        "parent_estimator_id": capsule.PARENT_ESTIMATOR_ID,
        (
            "checkpoint_digest"
            if support_kind == "WARMUP_NULL_ALIAS"
            else "q_m_solver_output_checkpoint_digest"
        ): owner_digest,
    }
    if support_kind == "ACCEPTED_TEMPORAL_EVALUATION":
        owner["q_m_solver_source_contract_digest"] = (
            capsule.Q_M_SOLVER_SOURCE_CONTRACT_DIGEST
        )
    weights = ["0x1.0000000000000p+0"] * 33
    weight_digest = m4_v2_domain_digest(
        {"candidate_weight_float_hex_in_ball_order_1_through_33": weights},
        domain="dehps.m4.v2.temporal.candidate-weight-content.v1",
    )
    shared = {
        "transition_ordinal": ordinal,
        "issue": issue,
        "support_kind": support_kind,
        "temporal_support_row_digest": _digest(f"temporal-support-row-{ordinal}"),
        "temporal_support_checkpoint_digest": _digest(
            f"temporal-support-checkpoint-{ordinal}"
        ),
        "theta_float_hex": "0x0.0p+0",
        "candidate_weight_float_hex_in_ball_order_1_through_33": weights,
        "candidate_weight_content_digest": weight_digest,
        "numeric_runtime_contract_digest": _digest("numeric-runtime-contract"),
        "evaluator_contract_digest": capsule.EVALUATOR_CONTRACT_DIGEST,
        "q_t_marginal_content_digest": _digest(f"q-t-marginal-{ordinal}"),
        "q_t_full_distribution_content_digest": _digest(f"q-t-full-{ordinal}"),
    }
    certificate_values = {
        **shared,
        "prefix_outcome_chain_digest": _digest(f"prefix-chain-{ordinal}"),
        "q_m_target_marginal_float_hex_in_ball_order_1_through_33": [
            "0x1.0000000000000p-1"
        ]
        * 33,
        "q_m_target_marginal_content_digest": _digest(f"q-m-marginal-{ordinal}"),
        "q_m_full_distribution_content_digest": _digest(f"q-m-full-{ordinal}"),
        "q_m_solver_source_contract_digest": capsule.Q_M_SOLVER_SOURCE_CONTRACT_DIGEST,
        "q_m_solver_iteration_count": 1,
        "q_m_solver_termination_reason": "REGISTERED_CONVERGENCE",
        "q_m_natural_parameter_float_hex_in_ball_order_1_through_33": ["0x0.0p+0"] * 33,
        "q_m_maximum_marginal_residual_float_hex": "0x0.0p+0",
        "previous_draw_issue": f"issue-{ordinal - 1:04d}",
        "previous_draw_labels_in_ascending_order": [1, 2, 3, 4, 5, 6],
        "previous_draw_content_digest": _digest(f"previous-draw-{ordinal}"),
        "combined_log_weight_float_hex_in_ball_order_1_through_33": ["0x0.0p+0"] * 33,
        "maximum_combined_log_weight_float_hex": "0x0.0p+0",
        "centered_log_weight_float_hex_in_ball_order_1_through_33": ["0x0.0p+0"] * 33,
        "q_m_owner_checkpoint": owner,
        "q_m_owner_checkpoint_digest": owner_digest,
    }
    certificate = {
        field: certificate_values[field] for field in capsule.CERTIFICATE_FIELDS[:-1]
    }
    certificate["certificate_digest"] = m4_v2_domain_digest(
        certificate,
        domain="dehps.m4.v2.temporal.probability-weight-derivation-certificate.v1",
    )
    row_values = {
        **shared,
        "weight_derivation_certificate": certificate,
        "weight_derivation_certificate_digest": certificate["certificate_digest"],
        "partition_float_hex": "0x1.0000000000000p+0",
    }
    row = {field: row_values[field] for field in capsule.CAPSULE_ROW_FIELDS[:-1]}
    row["capsule_digest"] = m4_v2_domain_digest(
        row, domain="dehps.m4.v2.temporal.probability-capsule-row.v2"
    )
    return row


@pytest.fixture(scope="module")
def probability_capsule() -> dict[str, Any]:
    return capsule.build_probability_capsule_index(
        producer_source_contract_digest=_digest("joint-registered-source-v3"),
        numeric_runtime_contract_digest=_digest("numeric-runtime-contract"),
        rows=[_capsule_row(ordinal) for ordinal in range(2, 3482)],
    )


def _joint_bundle(probability_capsule: Mapping[str, Any]) -> dict[str, Any]:
    source_digest = probability_capsule["producer_source_contract_digest"]
    marginal_decision, marginal_replay = _accepted_marginal_parent(source_digest)
    candidate_digest = _digest("registered-temporal-candidate-v3")
    temporal_decision = M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id=TEMPORAL,
        estimand_digest=temporal.TEMPORAL_ESTIMAND_DIGEST,
        decision_path="EVALUATED_COMPLETE",
        terminal_decision="BRANCH_INFORMATION_ACCEPTED",
        scientific_decision="BRANCH_INFORMATION_ACCEPTED",
        evaluation_status="COMPLETE",
        measurement_health="PASS",
        historical_evidence="POSITIVE",
        accepted_for_downstream_baseline=True,
        accepted_model_artifact_digest=candidate_digest,
        baseline_artifact_digest=MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        baseline_source_model_artifact_digest=MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        producer_task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        producer_execution_id=_digest("temporal-decision-execution"),
        parent_digests=(source_digest, _digest("temporal-parent")),
    ).to_dict()
    temporal_replay = temporal.build_temporal_branch_replay(
        source_contract_digest=source_digest,
        decision_artifact=temporal_decision,
        decision_registration_digest=_digest("temporal-decision-registration"),
        decision_producer_execution_artifact_digest=_digest(
            "temporal-decision-execution-artifact"
        ),
        replay_execution_id=_digest("temporal-replay-execution"),
    )
    seed = _seed_contract(JOINT)
    resolved_values = {
        "source_contract_envelope": {
            "artifact_digest": source_digest,
            "source_set_digest": _digest("joint-source-set-v4"),
            "body": {
                "seed_contract": seed,
                "seed_contract_digest": seed["seed_contract_digest"],
            },
        },
        "preregistration_envelope": {"artifact_digest": _digest("joint-prereg")},
        "ordered_parent_decision_envelopes": [marginal_decision, temporal_decision],
        "ordered_parent_replay_envelopes": [marginal_replay, temporal_replay],
        "accepted_support_model_envelope": {
            "schema_version": "dehps-m4-v2-temporal-marginal-increment-candidate-model.v3",
            "artifact_type": "M4V2TemporalMarginalIncrementCandidateModelArtifact",
            "artifact_digest": candidate_digest,
            "body": {
                "source_contract_digest": source_digest,
                "probability_capsule_index": dict(probability_capsule),
                "probability_capsule_index_digest": probability_capsule["index_digest"],
                "probability_capsule_evaluator_contract_digest": probability_capsule[
                    "evaluator_contract_digest"
                ],
            },
            "parent_digests": [source_digest],
        },
        "accepted_support_model_registration_record": _marginal_support_registration(),
        "ordered_holm_lineage_envelopes": [
            {"artifact_digest": _digest("joint-holm-marginal")},
            {"artifact_digest": _digest("joint-holm-temporal")},
        ],
        "dataset_snapshot_envelope": {"artifact_digest": _digest("joint-dataset")},
        "fold_manifest_envelope": {"artifact_digest": _digest("joint-fold")},
        "checkpoint_order_manifest_envelope": {
            "artifact_digest": _digest("joint-checkpoint")
        },
        "resampling_manifest_envelope": {
            "artifact_digest": _digest("joint-resampling")
        },
        "historical_execution_plan_envelope": {
            "artifact_digest": _digest("joint-plan"),
            "body": {"accepted_workload_computation": _computation(JOINT)},
        },
        "fixture_source_envelope": {"artifact_digest": _digest("joint-fixture")},
        "seed_contract": seed,
    }
    resolved = {field: resolved_values[field] for field in RESOLVED_INPUT_FIELDS}
    values = {
        "schema_version": "m4-v2-joint-accepted-parent-workload-input.v2",
        "branch_id": JOINT,
        "source_contract_artifact_digest": source_digest,
        "source_set_digest": _digest("joint-source-set-v4"),
        "preregistration_artifact_digest": _digest("joint-prereg"),
        "producer_execution_id": EXECUTION_ID,
        "ordered_parent_decision_artifact_digests": [
            marginal_decision["artifact_digest"],
            temporal_decision["artifact_digest"],
        ],
        "ordered_parent_replay_artifact_digests": [
            marginal_replay["artifact_digest"],
            temporal_replay["artifact_digest"],
        ],
        "accepted_support_model_artifact_digest": candidate_digest,
        "accepted_support_model_registration_digest": _digest(
            "joint-support-registration"
        ),
        "ordered_holm_lineage_artifact_digests": [
            _digest("joint-holm-marginal"),
            _digest("joint-holm-temporal"),
        ],
        "dataset_snapshot_artifact_digest": _digest("joint-dataset"),
        "dataset_content_digest": _digest("joint-dataset-content"),
        "fold_manifest_artifact_digest": _digest("joint-fold"),
        "checkpoint_order_manifest_artifact_digest": _digest("joint-checkpoint"),
        "resampling_manifest_artifact_digest": _digest("joint-resampling"),
        "historical_execution_plan_artifact_digest": _digest("joint-plan"),
        "fixture_source_artifact_digest": _digest("joint-fixture"),
        "synthetic_root_seed_full_sha256": seed[
            "upstream_seed_and_resampling_contract"
        ]["root_seeds"]["synthetic"]["known_material_full_sha256"],
        "historical_root_seed_full_sha256": seed[
            "upstream_seed_and_resampling_contract"
        ]["root_seeds"]["historical"]["known_material_full_sha256"],
        "warmup_request_payload_digest": _digest("joint-warmup-request"),
        "runtime_contract": RUNTIME_CONTRACT,
        "resolved_inputs": resolved,
    }
    bundle = {field: values[field] for field in INPUT_BUNDLE_FIELDS[:-1]}
    bundle["input_bundle_digest"] = m4_v2_domain_digest(
        bundle, domain=_domain(JOINT, "accepted-workload-input-bundle.v2")
    )
    return bundle


def _registered_payload(branch_id: str, event_type: str) -> tuple[dict, dict]:
    coordinate = {
        "WORKLOAD_STARTED": {"phase": "HEALTH_PRE_DRAW_VALIDATION"},
        "HEALTH_REPLICATE_COMMIT": {"cell_index": 0, "replicate_index": 0},
        "HEALTH_AGGREGATE_COMPLETE": {"phase": "HEALTH_AGGREGATE"},
        "HISTORICAL_FOLD_COMMIT": {"evaluation_ordinal": 901, "issue": "issue-901"},
        "HISTORICAL_SENSITIVITY_SCHEME_COMMIT": {
            "scheme_index": 0,
            "scheme_id": "BASELINE_BLOCK_LENGTH",
        },
        "HISTORICAL_AGGREGATE_COMPLETE": {"phase": "HISTORICAL_AGGREGATE"},
        "TERMINAL_OUTCOME": {
            "phase": "TERMINAL_OUTCOME",
            "execution_subpath": "EARLY_IDENTITY_VALID_HEALTH_REPAIR",
            "decision_path": "IDENTITY_VALID_HEALTH_REPAIR",
        },
    }[event_type]
    if event_type == "WORKLOAD_STARTED":
        payload = {
            "input_bundle_digest": _digest("event-input"),
            "producer_task_key": (
                temporal_runner.producer_task_key(branch_id)
                if hasattr(temporal_runner, "producer_task_key")
                else joint_runner.producer_task_key(branch_id)
            ),
            "producer_execution_id": EXECUTION_ID,
            "branch_id": branch_id,
            "source_contract_digest": _digest("event-source"),
            "preregistration_artifact_digest": _digest("event-prereg"),
            "parent_decision_artifact_digests_in_order": [_digest("event-decision")],
            "parent_replay_artifact_digests_in_order": [_digest("event-replay")],
            "scientific_execution_started": True,
            "start_phase": "HEALTH_PRE_DRAW_VALIDATION",
            "rng_draw_count": 0,
            "synthetic_replicate_count": 0,
            "historical_fold_count": 0,
            "bootstrap_resample_count": 0,
        }
    elif event_type == "HEALTH_REPLICATE_COMMIT":
        fields = M4_V2_NESTED_SCHEMA_REGISTRY[
            "synthetic_health_replicate_evidence_commitment"
        ].field_variants[0]
        payload = {field: _digest(f"replicate:{field}") for field in fields}
        payload.update(
            {
                "branch_id": branch_id,
                "evaluation_range": [901, 3481],
                "evaluation_count": 2581,
                "observed_mean_float_hex": "0x0.0p+0",
                "analytic_truth_float_hex": "0x0.0p+0",
                "bias_float_hex": "0x0.0p+0",
                "bootstrap_block_lengths": [1, 2, 4, 8],
                "ordered_bootstrap_child_mean_chain_digests": [_digest("child")],
                "primary_detection": False,
                "primary_interval": ["0x0.0p+0", "0x0.0p+0"],
                "primary_standard_error_float_hex": "0x0.0p+0",
                "primary_mde_float_hex": "0x0.0p+0",
            }
        )
        without_digest = {
            field: payload[field]
            for field in fields
            if field != "replicate_evidence_digest"
        }
        payload["replicate_evidence_digest"] = m4_v2_domain_digest(
            without_digest,
            domain=_domain(branch_id, "synthetic-health.replicate-evidence.v2"),
        )
    elif event_type in {
        "HEALTH_AGGREGATE_COMPLETE",
        "HISTORICAL_AGGREGATE_COMPLETE",
    }:
        artifact_type = {
            (
                TEMPORAL,
                "HEALTH_AGGREGATE_COMPLETE",
            ): "M4V2TemporalMarginalIncrementHealthAggregateArtifact",
            (
                TEMPORAL,
                "HISTORICAL_AGGREGATE_COMPLETE",
            ): "M4V2TemporalMarginalIncrementHistoricalAggregateArtifact",
            (
                JOINT,
                "HEALTH_AGGREGATE_COMPLETE",
            ): "M4V2JointResidualMeasurementHealthArtifact",
            (
                JOINT,
                "HISTORICAL_AGGREGATE_COMPLETE",
            ): "M4V2JointResidualHistoricalExecutionArtifact",
        }[(branch_id, event_type)]
        payload = {
            field: _digest(f"aggregate:{field}")
            for field in M4_V2_ARTIFACT_TYPE_REGISTRY[artifact_type].body_fields
        }
        payload["branch_id"] = branch_id
    elif event_type == "HISTORICAL_FOLD_COMMIT":
        payload = {
            "evaluation_ordinal": 901,
            "issue": "issue-901",
            "fold_digest": _digest("fold"),
            "prediction_checkpoint_body": {"registered": True},
            "prediction_checkpoint_digest": _digest("checkpoint"),
            "score_row_body": {"registered": True},
            "score_row_digest": _digest("score-row"),
        }
        payload["fold_commit_digest"] = m4_v2_domain_digest(
            payload,
            domain=_domain(branch_id, "accepted-workload-historical-fold-commit.v1"),
        )
    elif event_type == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT":
        fields = M4_V2_NESTED_SCHEMA_REGISTRY["sensitivity_summary"].field_variants[0]
        payload = {field: _digest(f"scheme:{field}") for field in fields}
        payload.update(
            {
                "scheme_id": "BASELINE_BLOCK_LENGTH",
                "block_length": 1,
                "resample_count": 2000,
                "effect_interval_bits_per_issue": ["0x0.0p+0", "0x0.0p+0"],
                "equivalence_upper_bound_bits_per_issue": "0x0.0p+0",
                "bootstrap_standard_error": "0x0.0p+0",
                "decision_credit": "REGISTERED_ONLY",
            }
        )
    else:
        payload = _early_terminal(branch_id) | {
            "preterminal_transcript_digest": _digest("preterminal")
        }
    return payload, coordinate


@pytest.mark.parametrize("branch_id", [TEMPORAL, JOINT])
@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_all_seven_registered_event_schemas_domains_and_chain_are_fail_closed(
    branch_id: str, event_type: str
) -> None:
    payload, coordinate = _registered_payload(branch_id, event_type)
    input_digest = (
        payload["input_bundle_digest"]
        if event_type == "WORKLOAD_STARTED"
        else _digest("event-input")
    )
    schema = event_payload_schema(branch_id=branch_id, event_type=event_type)
    payload_digest = event_payload_digest(
        branch_id=branch_id, event_type=event_type, payload=payload
    )
    event = build_event(
        branch_id=branch_id,
        input_bundle_digest=input_digest,
        producer_execution_id=EXECUTION_ID,
        event_index=0,
        event_type=event_type,
        coordinate_key=coordinate,
        payload_schema=schema,
        payload=payload,
        payload_digest=payload_digest,
        previous_event_digest_or_null=None,
    )
    assert (
        validate_event(
            event,
            branch_id=branch_id,
            input_bundle_digest=input_digest,
            producer_execution_id=EXECUTION_ID,
        )
        == event
    )

    with pytest.raises(
        AcceptedWorkloadContractError,
        match="accepted_workload_event_payload_schema_invalid",
    ):
        build_event(
            branch_id=branch_id,
            input_bundle_digest=input_digest,
            producer_execution_id=EXECUTION_ID,
            event_index=0,
            event_type=event_type,
            coordinate_key=coordinate,
            payload_schema=f"{schema}.tampered",
            payload=payload,
            payload_digest=payload_digest,
            previous_event_digest_or_null=None,
        )
    with pytest.raises(AcceptedWorkloadContractError, match="digest_mismatch"):
        build_event(
            branch_id=branch_id,
            input_bundle_digest=input_digest,
            producer_execution_id=EXECUTION_ID,
            event_index=0,
            event_type=event_type,
            coordinate_key=coordinate,
            payload_schema=schema,
            payload=payload,
            payload_digest=_digest("wrong-domain"),
            previous_event_digest_or_null=None,
        )
    with pytest.raises(AcceptedWorkloadContractError, match="event_chain_invalid"):
        build_event(
            branch_id=branch_id,
            input_bundle_digest=input_digest,
            producer_execution_id=EXECUTION_ID,
            event_index=1,
            event_type=event_type,
            coordinate_key=coordinate,
            payload_schema=schema,
            payload=payload,
            payload_digest=payload_digest,
            previous_event_digest_or_null=None,
        )


def test_registered_temporal_input_v2_resume_and_full_transcript() -> None:
    assert sys.implementation.name == RUNTIME_CONTRACT["python_implementation"]
    assert np.__version__ == RUNTIME_CONTRACT["numpy_version"]
    bundle = _temporal_bundle()
    assert validate_input_bundle(bundle, branch_id=TEMPORAL) == bundle
    extra = dict(bundle)
    extra["unexpected"] = True
    with pytest.raises(
        AcceptedWorkloadContractError, match="input_bundle_fields_invalid"
    ):
        validate_input_bundle(extra, branch_id=TEMPORAL)
    wrong_owner = copy.deepcopy(bundle)
    wrong_owner["resolved_inputs"]["accepted_support_model_envelope"]["body"][
        "model_id"
    ] = "UNREGISTERED_SUPPORT_MODEL"
    wrong_owner["input_bundle_digest"] = m4_v2_domain_digest(
        {field: wrong_owner[field] for field in INPUT_BUNDLE_FIELDS[:-1]},
        domain=_domain(TEMPORAL, "accepted-workload-input-bundle.v2"),
    )
    with pytest.raises(
        AcceptedWorkloadContractError, match="accepted_support_model_body_mismatch"
    ):
        validate_input_bundle(wrong_owner, branch_id=TEMPORAL)
    plan = bundle["resolved_inputs"]["historical_execution_plan_envelope"]["body"]
    assert "deterministic_event_payloads" not in plan
    events = list(
        temporal_runner.iter_temporal_marginal_increment_accepted_parent_events(bundle)
    )
    assert [event["event_type"] for event in events] == [
        "WORKLOAD_STARTED",
        "TERMINAL_OUTCOME",
    ]
    transcript = build_full_transcript(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events,
    )
    assert (
        validate_full_transcript(
            transcript,
            branch_id=TEMPORAL,
            input_bundle_digest=bundle["input_bundle_digest"],
            producer_execution_id=EXECUTION_ID,
        )
        == transcript
    )
    resume = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events[:1],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
    )
    assert (
        validate_resume_index(
            resume,
            branch_id=TEMPORAL,
            input_bundle_digest=bundle["input_bundle_digest"],
            producer_execution_id=EXECUTION_ID,
        )
        == resume
    )
    assert (
        list(
            temporal_runner.iter_temporal_marginal_increment_accepted_parent_events(
                bundle, resume_index=resume
            )
        )
        == events[1:]
    )
    changed = copy.deepcopy(resume)
    changed["events"][0]["payload"]["rng_draw_count"] = 1
    with pytest.raises(AcceptedWorkloadContractError):
        list(
            temporal_runner.iter_temporal_marginal_increment_accepted_parent_events(
                bundle, resume_index=changed
            )
        )


def test_joint_fixture_size_isolation_still_binds_typed_parents_capsule_and_resume(
    monkeypatch: pytest.MonkeyPatch, probability_capsule: dict[str, Any]
) -> None:
    bundle = _joint_bundle(probability_capsule)

    def validate_closed_joint_input(
        value: Mapping[str, Any], *, branch_id: str
    ) -> dict[str, Any]:
        assert branch_id == JOINT
        assert tuple(value) == INPUT_BUNDLE_FIELDS
        assert value["schema_version"] == (
            "m4-v2-joint-accepted-parent-workload-input.v2"
        )
        assert value["input_bundle_digest"] == m4_v2_domain_digest(
            {field: value[field] for field in INPUT_BUNDLE_FIELDS[:-1]},
            domain=_domain(JOINT, "accepted-workload-input-bundle.v2"),
        )
        assert (
            "deterministic_event_payloads"
            not in value["resolved_inputs"]["historical_execution_plan_envelope"][
                "body"
            ]
        )
        return dict(value)

    # The generic validator requires the complete registered Temporal candidate
    # (899 warmup + 2581 evaluation rows).  This focused test isolates that
    # already-covered envelope layer while retaining the exact input-v2 seal,
    # both typed accepted parents/replays, and every one of the 3480 capsule rows.
    monkeypatch.setattr(
        joint_runner, "validate_input_bundle", validate_closed_joint_input
    )
    assert probability_capsule["row_count"] == 3480
    assert [row["transition_ordinal"] for row in probability_capsule["rows"]] == list(
        range(2, 3482)
    )
    parents = bundle["resolved_inputs"]["ordered_parent_decision_envelopes"]
    assert (
        parents[1]["body"]["accepted_model_artifact_digest"]
        == bundle["accepted_support_model_artifact_digest"]
    )
    events = list(
        joint_runner.iter_joint_residual_increment_accepted_parent_events(bundle)
    )
    assert [event["event_type"] for event in events] == [
        "WORKLOAD_STARTED",
        "TERMINAL_OUTCOME",
    ]
    resume = build_resume_index(
        branch_id=JOINT,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events[:1],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
    )
    assert (
        list(
            joint_runner.iter_joint_residual_increment_accepted_parent_events(
                bundle, resume_index=resume
            )
        )
        == events[1:]
    )
    transcript = build_full_transcript(
        branch_id=JOINT,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events,
    )
    assert (
        validate_full_transcript(
            transcript,
            branch_id=JOINT,
            input_bundle_digest=bundle["input_bundle_digest"],
            producer_execution_id=EXECUTION_ID,
        )
        == transcript
    )

    bad_parent = copy.deepcopy(bundle)
    bad_parent["resolved_inputs"]["ordered_parent_decision_envelopes"] = [
        bad_parent["resolved_inputs"]["ordered_parent_decision_envelopes"][0]
    ]
    bad_parent["input_bundle_digest"] = m4_v2_domain_digest(
        {field: bad_parent[field] for field in INPUT_BUNDLE_FIELDS[:-1]},
        domain=_domain(JOINT, "accepted-workload-input-bundle.v2"),
    )
    with pytest.raises(AcceptedWorkloadContractError, match="parent_cardinality"):
        list(
            joint_runner.iter_joint_residual_increment_accepted_parent_events(
                bad_parent
            )
        )
    bad_capsule = copy.deepcopy(bundle)
    bad_capsule["resolved_inputs"]["accepted_support_model_envelope"]["body"][
        "probability_capsule_index"
    ]["index_digest"] = _digest("tampered-capsule-index")
    bad_capsule["input_bundle_digest"] = m4_v2_domain_digest(
        {field: bad_capsule[field] for field in INPUT_BUNDLE_FIELDS[:-1]},
        domain=_domain(JOINT, "accepted-workload-input-bundle.v2"),
    )
    with pytest.raises(capsule.TemporalProbabilityCapsuleError, match="index_digest"):
        list(
            joint_runner.iter_joint_residual_increment_accepted_parent_events(
                bad_capsule
            )
        )


def test_event_coordinate_accounting_includes_started_and_eight_schemes() -> None:
    coordinates = list(
        evaluated_coordinate_sequence(
            fold_coordinates=[
                (ordinal, f"issue-{ordinal}") for ordinal in range(901, 3482)
            ],
            sensitivity_scheme_ids=[f"scheme-{index}" for index in range(8)],
        )
    )
    assert coordinates[0][0] == "WORKLOAD_STARTED"
    assert sum(kind == "HEALTH_REPLICATE_COMMIT" for kind, _ in coordinates) == 14 * 512
    assert sum(kind == "HISTORICAL_FOLD_COMMIT" for kind, _ in coordinates) == 2581
    assert (
        sum(kind == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT" for kind, _ in coordinates)
        == 8
    )
    assert coordinates[-1][0] == "TERMINAL_OUTCOME"


def test_corrected_probability_authority_rejects_every_legacy_digest() -> None:
    capsule.require_corrected_probability_authority(
        [
            capsule.CORRECTED_AMENDMENT_CONTRACT_DIGEST,
            capsule.CORRECTED_RESOLVED_CONTRACT_DIGEST,
            capsule.CORRECTED_REBASED_ADDENDUM_DIGEST,
        ]
    )
    for legacy in capsule.INVALID_LEGACY_SUCCESSOR_DIGESTS:
        with pytest.raises(
            ValueError, match="legacy_probability_authority_digest_rejected"
        ):
            capsule.require_corrected_probability_authority(
                [
                    legacy,
                    capsule.CORRECTED_AMENDMENT_CONTRACT_DIGEST,
                    capsule.CORRECTED_RESOLVED_CONTRACT_DIGEST,
                    capsule.CORRECTED_REBASED_ADDENDUM_DIGEST,
                ]
            )
