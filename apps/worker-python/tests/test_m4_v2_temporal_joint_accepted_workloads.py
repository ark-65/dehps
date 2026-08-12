from __future__ import annotations

import copy
import hashlib
import math
import sys
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2 import (
    joint_residual_increment as joint,
)
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
    EVALUATED_RESUME_CHECKPOINT_COUNTS_V2,
    EVENT_TYPES,
    INPUT_BUNDLE_FIELDS,
    REGISTERED_HISTORICAL_SCHEME_IDS,
    RESOLVED_INPUT_FIELDS,
    AcceptedWorkloadContractError,
    advance_resume_index,
    build_event,
    build_full_transcript,
    build_resume_index,
    build_resume_journal_transition,
    evaluated_coordinate_sequence,
    event_payload_digest,
    event_payload_schema,
    historical_settled_outcome_digest,
    is_resume_checkpoint_count,
    preterminal_transcript_digest,
    validate_event,
    validate_full_transcript,
    validate_input_bundle,
    validate_registered_computation_inputs,
    validate_resume_index,
    validate_resume_snapshot_relative_path_v1,
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


def test_request516_settled_outcome_digest_is_branch_neutral_and_closed() -> None:
    owner = {
        "evaluation_ordinal": 901,
        "issue": "issue-0901",
        "red_numbers": [1, 4, 9, 17, 24, 33],
    }
    expected = m4_v2_domain_digest(
        owner, domain="dehps.m4.v2.historical-settled-outcome.v1"
    )
    assert historical_settled_outcome_digest(**owner) == expected
    assert historical_settled_outcome_digest(**owner) == expected
    for mutation in (
        {**owner, "evaluation_ordinal": 902},
        {**owner, "issue": "issue-0902"},
        {**owner, "red_numbers": [1, 4, 9, 17, 25, 33]},
    ):
        assert historical_settled_outcome_digest(**mutation) != expected
    for invalid in (
        {**owner, "red_numbers": list(reversed(owner["red_numbers"]))},
        {**owner, "red_numbers": [1, 1, 9, 17, 24, 33]},
        {**owner, "red_numbers": [0, 4, 9, 17, 24, 33]},
    ):
        with pytest.raises(
            AcceptedWorkloadContractError,
            match="settled_outcome_owner_invalid",
        ):
            historical_settled_outcome_digest(**invalid)


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
            "numerical_contract_digest": capsule.NUMERIC_RUNTIME_CONTRACT_DIGEST,
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


def _joint_preregistration(
    *, source_digest: str, seed_digest: str, warmup_digest: str
) -> dict[str, Any]:
    artifact_type = "M4V2JointResidualIncrementPreregistrationArtifact"
    fields = M4_V2_ARTIFACT_TYPE_REGISTRY[artifact_type].body_fields
    body = {field: _digest(f"joint-preregistration:{field}") for field in fields}
    body.update(
        {
            "status": "FROZEN",
            "measurement_contract_key": M4_V2_MEASUREMENT_CONTRACT_KEY,
            "measurement_contract_digest": M4_V2_MEASUREMENT_CONTRACT_DIGEST,
            "branch_id": JOINT,
            "estimand_digest": joint.JOINT_ESTIMAND_DIGEST,
            "source_contract_digest": source_digest,
            "seed_contract_digest": seed_digest,
            "warmup_request_payload_digest": warmup_digest,
            "planned_counts": dict(joint.PLANNED_COUNTS),
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


def _small_early_event_stream(
    bundle: Mapping[str, Any], *, branch_id: str,
) -> list[dict[str, Any]]:
    runner = temporal_runner if branch_id == TEMPORAL else joint_runner
    started_payload = runner._started_payload(bundle)
    started = build_event(
        branch_id=branch_id,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=bundle["producer_execution_id"],
        event_index=0,
        event_type="WORKLOAD_STARTED",
        coordinate_key={"phase": "HEALTH_PRE_DRAW_VALIDATION"},
        payload_schema=event_payload_schema(
            branch_id=branch_id, event_type="WORKLOAD_STARTED"
        ),
        payload=started_payload,
        payload_digest=event_payload_digest(
            branch_id=branch_id,
            event_type="WORKLOAD_STARTED",
            payload=started_payload,
        ),
        previous_event_digest_or_null=None,
    )
    terminal_payload = _early_terminal(branch_id)
    terminal_payload["preterminal_transcript_digest"] = preterminal_transcript_digest(
        branch_id=branch_id,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=bundle["producer_execution_id"],
        execution_subpath=terminal_payload["execution_subpath"],
        decision_path=terminal_payload["decision_path"],
        ordered_preterminal_event_digests=[started["event_digest"]],
    )
    terminal = build_event(
        branch_id=branch_id,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=bundle["producer_execution_id"],
        event_index=1,
        event_type="TERMINAL_OUTCOME",
        coordinate_key={
            "phase": "TERMINAL_OUTCOME",
            "execution_subpath": "EARLY_IDENTITY_VALID_HEALTH_REPAIR",
            "decision_path": "IDENTITY_VALID_HEALTH_REPAIR",
        },
        payload_schema=event_payload_schema(
            branch_id=branch_id, event_type="TERMINAL_OUTCOME"
        ),
        payload=terminal_payload,
        payload_digest=event_payload_digest(
            branch_id=branch_id,
            event_type="TERMINAL_OUTCOME",
            payload=terminal_payload,
        ),
        previous_event_digest_or_null=started["event_digest"],
    )
    return [started, terminal]


def _registered_computation_inputs(
    *, branch_id: str, source_digest: str, identities: Mapping[str, str]
) -> dict[str, Any]:
    records = [
        {"issue": f"issue-{ordinal:04d}", "red_numbers": [1, 2, 3, 4, 5, 6]}
        for ordinal in range(1, 3482)
    ]
    # The envelope is structurally complete but deliberately trips the frozen
    # pre-draw identity gate, keeping this unit test result-blind and small.
    records[1]["issue"] = records[0]["issue"]
    folds = [
        {
            "fold_index": offset,
            "fold_digest": _digest(f"{branch_id}:fold:{ordinal}"),
            "training_start_ordinal": 1,
            "training_end_ordinal": ordinal - 1,
            "test_ordinal": ordinal,
            "test_issue": records[ordinal - 1]["issue"],
            "test_draw_date": "",
        }
        for offset, ordinal in enumerate(range(901, 3482))
    ]
    phase_order = [
        "COUNTS_FIT_THROUGH_T_MINUS_1",
        "VIRTUAL_CHECKPOINT_PERSISTED",
        "TARGET_T_EXPOSED",
        "TARGET_T_SCORED",
        "COUNTS_UPDATED_WITH_T",
        "FOLD_SETTLED",
    ]
    entries = [
        {
            "fold_index": fold["fold_index"],
            "fold_digest": fold["fold_digest"],
            "test_ordinal": fold["test_ordinal"],
            "phase_order": phase_order,
            "order_digest": _digest(
                f"{branch_id}:order:{fold['test_ordinal']}"
            ),
        }
        for fold in folds
    ]
    schemes = list(REGISTERED_HISTORICAL_SCHEME_IDS)
    roots = [
        {
            "replicate_index": index,
            "root_seed": index,
            "root_digest": _digest(f"{branch_id}:root:{index}"),
        }
        for index in range(2000)
    ]
    children = [
        {
            "replicate_index": index,
            "scheme_id": scheme,
            "root_seed": index,
            "child_digest": _digest(f"{branch_id}:child:{index}:{scheme}"),
        }
        for index in range(2000)
        for scheme in schemes
    ]
    common = {
        "formal_historical_folds_executed": 0,
        "bootstrap_children_executed": 0,
        "historical_scores_computed": 0,
        "statistical_results_read": False,
        "evidence_created": False,
        "accepted_model_artifact_digest": None,
        "promotion_gate_opened": False,
        "duplicate_validation": False,
        "production_action": "none",
    }
    return {
        "dataset": {
            "artifact_digest": identities["dataset"],
            "body": {
                "dataset_content_digest": identities["dataset-content"],
                "history_snapshot": {"records": records},
            },
        },
        "fold": {
            "artifact_digest": identities["fold-manifest"],
            "body": {"folds": folds},
        },
        "checkpoint": {
            "artifact_digest": identities["checkpoint-order-manifest"],
            "body": {"entries": entries},
        },
        "resampling": {
            "artifact_digest": identities["resampling-manifest"],
            "body": {"schemes": schemes, "roots": roots, "children": children},
        },
        "plan": {
            "artifact_digest": identities["historical-execution-plan"],
            "body": {
                "status": "FROZEN_PREREGISTRATION",
                "source_contract_digest": source_digest,
                "dataset_snapshot_digest": identities["dataset"],
                "dataset_content_digest": identities["dataset-content"],
                "fold_manifest_digest": identities["fold-manifest"],
                "checkpoint_order_manifest_digest": identities[
                    "checkpoint-order-manifest"
                ],
                "resampling_manifest_digest": identities["resampling-manifest"],
                "inference_algorithms": {"registered": True},
                "time_stability": {"registered": True},
                "execution": {"registered": True},
                "formal_historical_execution_authorized": False,
                "automatic_evidence_from_preregistration": False,
                "next_consumer": "accepted-parent-runner",
                **common,
            },
        },
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
            "numeric_runtime_contract": dict(capsule.NUMERIC_RUNTIME_CONTRACT),
            "numeric_runtime_contract_digest": (
                capsule.NUMERIC_RUNTIME_CONTRACT_DIGEST
            ),
        },
    }
    registered = _registered_computation_inputs(
        branch_id=branch_id,
        source_digest=source_digest,
        identities=static_digests,
    )
    resolved_values = {
        "source_contract_envelope": source,
        "preregistration_envelope": preregistration,
        "ordered_parent_decision_envelopes": [decision],
        "ordered_parent_replay_envelopes": [replay],
        "accepted_support_model_envelope": support,
        "accepted_support_model_registration_record": registration,
        "ordered_holm_lineage_envelopes": [{"artifact_digest": static_digests["holm"]}],
        "dataset_snapshot_envelope": registered["dataset"],
        "fold_manifest_envelope": registered["fold"],
        "checkpoint_order_manifest_envelope": registered["checkpoint"],
        "resampling_manifest_envelope": registered["resampling"],
        "historical_execution_plan_envelope": registered["plan"],
        "fixture_source_envelope": {
            "artifact_digest": capsule.Q_M_SOLVER_SOURCE_CONTRACT_DIGEST
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
        "fixture_source_artifact_digest": capsule.Q_M_SOLVER_SOURCE_CONTRACT_DIGEST,
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
    weights = ["0x1.0000000000000p+0"] * 33
    evaluated = capsule.evaluate_registered_weights(weights)
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
        "numeric_runtime_contract_digest": capsule.NUMERIC_RUNTIME_CONTRACT_DIGEST,
        "evaluator_contract_digest": capsule.EVALUATOR_CONTRACT_DIGEST,
        "q_t_marginal_content_digest": evaluated["q_t_marginal_content_digest"],
        "q_t_full_distribution_content_digest": evaluated[
            "q_t_full_distribution_content_digest"
        ],
    }
    prefix_digest = _digest(f"prefix-chain-{ordinal}")
    q_m_marginal_digest = evaluated["q_t_marginal_content_digest"]
    q_m_full_digest = evaluated["q_t_full_distribution_content_digest"]
    if support_kind == "WARMUP_NULL_ALIAS":
        owner = {
            "dataset_content_digest": temporal.DATASET_CONTENT_DIGEST,
            "checkpoint_order_manifest_digest": (
                temporal.CHECKPOINT_ORDER_MANIFEST_DIGEST
            ),
            "transition_ordinal": ordinal,
            "issue": issue,
            "prefix_last_ordinal": ordinal - 1,
            "prefix_last_issue": f"issue-{ordinal - 1:04d}",
            "prefix_outcome_chain_digest": prefix_digest,
            "parent_estimator_id": capsule.PARENT_ESTIMATOR_ID,
            "q_m_marginal_content_digest": q_m_marginal_digest,
            "q_m_full_distribution_content_digest": q_m_full_digest,
        }
        owner["checkpoint_digest"] = m4_v2_domain_digest(
            owner, domain="dehps.m4.v2.strict-prior-marginal-checkpoint.v1"
        )
        owner_digest = owner["checkpoint_digest"]
        support_row = temporal.build_temporal_warmup_row(owner)
        shared["temporal_support_checkpoint_digest"] = owner_digest
        shared["temporal_support_row_digest"] = support_row["row_digest"]
    else:
        pretarget = temporal.build_accepted_temporal_pretarget_checkpoint(
            transition_ordinal=ordinal,
            issue=issue,
            training_prefix_outcome_chain_digest=prefix_digest,
            theta_float_hex="0x0.0p+0",
            q_t_marginal_content_digest=shared["q_t_marginal_content_digest"],
            q_t_full_distribution_content_digest=shared[
                "q_t_full_distribution_content_digest"
            ],
        )
        owner = {
            "schema_version": (
                "dehps-m4-v2-candidate-v3-q-m-solver-output-checkpoint.v1"
            ),
            "support_kind": support_kind,
            "dataset_content_digest": temporal.DATASET_CONTENT_DIGEST,
            "fold_manifest_digest": temporal.FOLD_MANIFEST_DIGEST,
            "checkpoint_order_manifest_digest": (
                temporal.CHECKPOINT_ORDER_MANIFEST_DIGEST
            ),
            "transition_ordinal": ordinal,
            "issue": issue,
            "training_prefix_last_ordinal": ordinal - 1,
            "training_prefix_outcome_chain_digest": prefix_digest,
            "parent_estimator_id": capsule.PARENT_ESTIMATOR_ID,
            "q_m_carrier_contract_digest": capsule.Q_M_CARRIER_CONTRACT_DIGEST,
            "q_m_solver_source_contract_digest": (
                capsule.Q_M_SOLVER_SOURCE_CONTRACT_DIGEST
            ),
            "numeric_runtime_contract_digest": (
                capsule.NUMERIC_RUNTIME_CONTRACT_DIGEST
            ),
            "q_m_output_evaluator_contract_digest": (
                capsule.EVALUATOR_CONTRACT_DIGEST
            ),
            "q_m_target_marginal_float_hex_in_ball_order_1_through_33": evaluated[
                "q_t_marginal_float_hex_in_ball_order_1_through_33"
            ],
            "q_m_target_marginal_content_digest": q_m_marginal_digest,
            "q_m_natural_parameter_float_hex_in_ball_order_1_through_33": [
                "0x0.0p+0"
            ] * 33,
            "q_m_solver_iteration_count": 1,
            "q_m_solver_termination_reason": "REGISTERED_CONVERGENCE",
            "q_m_maximum_marginal_residual_float_hex": "0x0.0p+0",
            "q_m_full_distribution_content_digest": q_m_full_digest,
            "pretarget_checkpoint_digest": pretarget[
                "pretarget_checkpoint_digest"
            ],
        }
        owner["q_m_solver_output_checkpoint_digest"] = m4_v2_domain_digest(
            owner,
            domain=(
                "dehps.m4.v2.candidate-v3.q-m-solver-output-checkpoint.v1"
            ),
        )
        owner_digest = owner["q_m_solver_output_checkpoint_digest"]
        support_row = temporal.build_accepted_temporal_evaluation_row(pretarget)
        shared["temporal_support_checkpoint_digest"] = pretarget[
            "pretarget_checkpoint_digest"
        ]
        shared["temporal_support_row_digest"] = support_row["q_t_row_digest"]
    certificate_values = {
        **shared,
        "prefix_outcome_chain_digest": prefix_digest,
        "q_m_target_marginal_float_hex_in_ball_order_1_through_33": evaluated[
            "q_t_marginal_float_hex_in_ball_order_1_through_33"
        ],
        "q_m_target_marginal_content_digest": evaluated[
            "q_t_marginal_content_digest"
        ],
        "q_m_full_distribution_content_digest": evaluated[
            "q_t_full_distribution_content_digest"
        ],
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
        "partition_float_hex": evaluated["partition_float_hex"],
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
        numeric_runtime_contract_digest=capsule.NUMERIC_RUNTIME_CONTRACT_DIGEST,
        rows=[_capsule_row(ordinal) for ordinal in range(2, 3482)],
    )


def test_probability_capsule_uniform_weights_use_legal_six_of_33_evaluator() -> None:
    evaluated = capsule.evaluate_registered_weights(
        ["0x1.0000000000000p+0"] * 33
    )
    assert float.fromhex(evaluated["partition_float_hex"]) == math.comb(33, 6)
    marginals = [
        float.fromhex(value)
        for value in evaluated[
            "q_t_marginal_float_hex_in_ball_order_1_through_33"
        ]
    ]
    assert max(abs(value - 2.0 / 11.0) for value in marginals) < 1e-14
    assert all(value != 0.5 for value in marginals)


def test_numeric_runtime_build_owner_and_temporal_propagation_are_exact() -> None:
    assert (
        capsule.validate_numeric_runtime_contract(capsule.NUMERIC_RUNTIME_CONTRACT)
        == capsule.NUMERIC_RUNTIME_CONTRACT
    )
    capsule.validate_registered_build_closures()
    for field, replacement in (
        ("worker_image_digest", _digest("different-worker-image")),
        ("blas_lapack_binary_closure_digest", _digest("different-blas-closure")),
        ("python_version", "3.14.5"),
    ):
        changed_runtime = dict(capsule.NUMERIC_RUNTIME_CONTRACT)
        changed_runtime[field] = replacement
        with pytest.raises(
            capsule.TemporalProbabilityCapsuleError,
            match="numeric_runtime_contract_identity_mismatch",
        ):
            capsule.validate_numeric_runtime_contract(changed_runtime)

    with pytest.raises(
        capsule.TemporalProbabilityCapsuleError,
        match="capsule_index_runtime_mismatch",
    ):
        capsule.build_probability_capsule_index(
            producer_source_contract_digest=_digest("temporal-source"),
            numeric_runtime_contract_digest=_digest("ambient-host-runtime"),
            rows=[],
        )

    bundle = _temporal_bundle()
    assert validate_input_bundle(bundle, branch_id=TEMPORAL) == bundle
    for owner_path in ("source", "preregistration"):
        changed = copy.deepcopy(bundle)
        if owner_path == "source":
            changed["resolved_inputs"]["source_contract_envelope"]["body"][
                "numeric_runtime_contract_digest"
            ] = _digest("different-runtime")
        else:
            changed["resolved_inputs"]["preregistration_envelope"]["body"][
                "numerical_contract_digest"
            ] = _digest("different-runtime")
        changed["input_bundle_digest"] = m4_v2_domain_digest(
            {field: changed[field] for field in INPUT_BUNDLE_FIELDS[:-1]},
            domain=_domain(TEMPORAL, "accepted-workload-input-bundle.v2"),
        )
        with pytest.raises(
            AcceptedWorkloadContractError,
            match=(
                "accepted_workload_numeric_runtime_propagation_mismatch"
                if owner_path == "source"
                else "accepted_workload_preregistration_invalid"
            ),
        ):
            validate_input_bundle(changed, branch_id=TEMPORAL)


def test_versioned_artifact_dispatch_requires_explicit_type_and_schema(
    probability_capsule: Mapping[str, Any],
) -> None:
    candidate = _registered_temporal_candidate_v3(probability_capsule)
    rebuilt = m4_v2_build_artifact_envelope(
        artifact_type=candidate["artifact_type"],
        schema_version=candidate["schema_version"],
        body=candidate["body"],
        parent_digests=candidate["parent_digests"],
    )
    assert rebuilt == candidate
    with pytest.raises(ValueError, match="body fields must be exactly"):
        m4_v2_build_artifact_envelope(
            artifact_type=candidate["artifact_type"],
            body=candidate["body"],
            parent_digests=candidate["parent_digests"],
        )
    with pytest.raises(ValueError, match="schema changed"):
        m4_v2_build_artifact_envelope(
            artifact_type=candidate["artifact_type"],
            schema_version="dehps-m4-v2-temporal-marginal-increment-candidate-model.v999",
            body=candidate["body"],
            parent_digests=candidate["parent_digests"],
        )


def _registered_temporal_candidate_v3(
    probability_capsule: Mapping[str, Any],
) -> dict[str, Any]:
    warmup_rows: list[dict[str, Any]] = []
    evaluation_rows: list[dict[str, Any]] = []
    for capsule_row in probability_capsule["rows"]:
        certificate = capsule_row["weight_derivation_certificate"]
        if capsule_row["support_kind"] == "WARMUP_NULL_ALIAS":
            warmup_rows.append(
                temporal.build_temporal_warmup_row(
                    certificate["q_m_owner_checkpoint"]
                )
            )
        else:
            pretarget = temporal.build_accepted_temporal_pretarget_checkpoint(
                transition_ordinal=capsule_row["transition_ordinal"],
                issue=capsule_row["issue"],
                training_prefix_outcome_chain_digest=certificate[
                    "prefix_outcome_chain_digest"
                ],
                theta_float_hex=capsule_row["theta_float_hex"],
                q_t_marginal_content_digest=capsule_row[
                    "q_t_marginal_content_digest"
                ],
                q_t_full_distribution_content_digest=capsule_row[
                    "q_t_full_distribution_content_digest"
                ],
            )
            evaluation_rows.append(
                temporal.build_accepted_temporal_evaluation_row(pretarget)
            )
    rule = temporal.build_transition_local_warmup_rule()
    warmup = temporal.build_temporal_warmup_index(
        warmup_rows, rule_digest=rule["rule_digest"]
    )
    evaluation = temporal.build_accepted_temporal_evaluation_index(evaluation_rows)
    composite = temporal.build_temporal_composite_view(
        warmup_index_digest=warmup["warmup_index_digest"],
        accepted_temporal_evaluation_index_digest=evaluation[
            "accepted_temporal_evaluation_index_digest"
        ],
    )
    source_digest = probability_capsule["producer_source_contract_digest"]
    body = {
        "status": "COMPLETE",
        "measurement_contract_key": M4_V2_MEASUREMENT_CONTRACT_KEY,
        "measurement_contract_digest": M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        "branch_id": TEMPORAL,
        "estimand_digest": temporal.TEMPORAL_ESTIMAND_DIGEST,
        "model_id": temporal.TEMPORAL_MODEL_ID,
        "source_contract_digest": source_digest,
        "dataset_content_digest": temporal.DATASET_CONTENT_DIGEST,
        "fold_manifest_digest": temporal.FOLD_MANIFEST_DIGEST,
        "marginal_parent_model_artifact_digest": MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        "marginal_parent_probability_chain_digest": _digest(
            "marginal-parent-probability-chain"
        ),
        "support_model_id": temporal.SUPPORT_MODEL_ID,
        "historical_warmup_index": warmup,
        "warmup_index_digest": warmup["warmup_index_digest"],
        "accepted_temporal_evaluation_index": evaluation,
        "accepted_temporal_evaluation_index_digest": evaluation[
            "accepted_temporal_evaluation_index_digest"
        ],
        "composite_temporal_view": composite,
        "composite_view_digest": composite["composite_view_digest"],
        "historical_fold_count": 2581,
        "production_action": "none",
        "probability_capsule_index": dict(probability_capsule),
        "probability_capsule_index_digest": probability_capsule["index_digest"],
        "probability_capsule_evaluator_contract_digest": probability_capsule[
            "evaluator_contract_digest"
        ],
    }
    return m4_v2_build_artifact_envelope(
        artifact_type="M4V2TemporalMarginalIncrementCandidateModelArtifact",
        schema_version=(
            "dehps-m4-v2-temporal-marginal-increment-candidate-model.v3"
        ),
        body=body,
        parent_digests=(source_digest, MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST),
    )


def _temporal_support_registration(
    candidate: Mapping[str, Any], decision: Mapping[str, Any]
) -> dict[str, Any]:
    body = decision["body"]
    record = MainlineArtifactRegistration(
        execution_id=body["producer_execution_id"],
        control_plane_key="m4-information-theory-mainline",
        task_key=body["producer_task_key"],
        task_digest=_digest("temporal-producer-task"),
        artifact_digest=candidate["artifact_digest"],
        artifact_type=candidate["artifact_type"],
        schema_version=candidate["schema_version"],
        artifact_path=(
            "runtime/research-os/mainline/tasks/"
            f"{body['producer_task_key']}/{body['producer_execution_id']}/"
            "artifacts/candidate/registered/model.json"
        ),
        parent_digests=tuple(candidate["parent_digests"]),
        git_commit="28d3706d5cb7681d49b529e792125a3a4e137535",
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


def _joint_bundle(probability_capsule: Mapping[str, Any]) -> dict[str, Any]:
    source_digest = probability_capsule["producer_source_contract_digest"]
    marginal_decision, marginal_replay = _accepted_marginal_parent(source_digest)
    candidate = _registered_temporal_candidate_v3(probability_capsule)
    candidate_digest = candidate["artifact_digest"]
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
    support_registration = _temporal_support_registration(
        candidate, temporal_decision
    )
    seed = _seed_contract(JOINT)
    joint_warmup_digest = _digest("joint-warmup-request")
    joint_preregistration = _joint_preregistration(
        source_digest=source_digest,
        seed_digest=seed["seed_contract_digest"],
        warmup_digest=joint_warmup_digest,
    )
    joint_identities = {
        "dataset": _digest("joint-dataset"),
        "dataset-content": _digest("joint-dataset-content"),
        "fold-manifest": _digest("joint-fold"),
        "checkpoint-order-manifest": _digest("joint-checkpoint"),
        "resampling-manifest": _digest("joint-resampling"),
        "historical-execution-plan": _digest("joint-plan"),
    }
    registered = _registered_computation_inputs(
        branch_id=JOINT,
        source_digest=source_digest,
        identities=joint_identities,
    )
    resolved_values = {
        "source_contract_envelope": {
            "artifact_digest": source_digest,
            "source_set_digest": _digest("joint-source-set-v4"),
            "body": {
                "seed_contract": seed,
                "seed_contract_digest": seed["seed_contract_digest"],
            },
        },
        "preregistration_envelope": joint_preregistration,
        "ordered_parent_decision_envelopes": [marginal_decision, temporal_decision],
        "ordered_parent_replay_envelopes": [marginal_replay, temporal_replay],
        "accepted_support_model_envelope": candidate,
        "accepted_support_model_registration_record": support_registration,
        "ordered_holm_lineage_envelopes": [
            {"artifact_digest": _digest("joint-holm-marginal")},
            {"artifact_digest": _digest("joint-holm-temporal")},
        ],
        "dataset_snapshot_envelope": registered["dataset"],
        "fold_manifest_envelope": registered["fold"],
        "checkpoint_order_manifest_envelope": registered["checkpoint"],
        "resampling_manifest_envelope": registered["resampling"],
        "historical_execution_plan_envelope": registered["plan"],
        "fixture_source_envelope": {
            "artifact_digest": capsule.Q_M_SOLVER_SOURCE_CONTRACT_DIGEST
        },
        "seed_contract": seed,
    }
    resolved = {field: resolved_values[field] for field in RESOLVED_INPUT_FIELDS}
    values = {
        "schema_version": "m4-v2-joint-accepted-parent-workload-input.v2",
        "branch_id": JOINT,
        "source_contract_artifact_digest": source_digest,
        "source_set_digest": _digest("joint-source-set-v4"),
        "preregistration_artifact_digest": joint_preregistration[
            "artifact_digest"
        ],
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
        "accepted_support_model_registration_digest": support_registration[
            "registration_digest"
        ],
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
        "fixture_source_artifact_digest": capsule.Q_M_SOLVER_SOURCE_CONTRACT_DIGEST,
        "synthetic_root_seed_full_sha256": seed[
            "upstream_seed_and_resampling_contract"
        ]["root_seeds"]["synthetic"]["known_material_full_sha256"],
        "historical_root_seed_full_sha256": seed[
            "upstream_seed_and_resampling_contract"
        ]["root_seeds"]["historical"]["known_material_full_sha256"],
        "warmup_request_payload_digest": joint_warmup_digest,
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
    assert "accepted_workload_computation" not in plan
    healthy = copy.deepcopy(bundle)
    records = healthy["resolved_inputs"]["dataset_snapshot_envelope"][
        "body"
    ]["history_snapshot"]["records"]
    for ordinal, record in enumerate(records, start=1):
        record["issue"] = f"issue-{ordinal:04d}"
    healthy["input_bundle_digest"] = m4_v2_domain_digest(
        {field: healthy[field] for field in INPUT_BUNDLE_FIELDS[:-1]},
        domain=_domain(TEMPORAL, "accepted-workload-input-bundle.v2"),
    )
    folds, schemes = validate_registered_computation_inputs(
        bundle, branch_id=TEMPORAL
    )
    assert folds[0] == (901, "issue-0901")
    assert folds[-1] == (3481, "issue-3481")
    assert schemes == list(REGISTERED_HISTORICAL_SCHEME_IDS)
    injected = copy.deepcopy(bundle)
    injected["resolved_inputs"]["historical_execution_plan_envelope"]["body"][
        "accepted_workload_computation"
    ] = {"forbidden": True}
    with pytest.raises(
        AcceptedWorkloadContractError,
        match="registered_execution_plan_fields_invalid",
    ):
        validate_registered_computation_inputs(injected, branch_id=TEMPORAL)
    healthy_stream = temporal_runner.iter_temporal_marginal_increment_accepted_parent_events(
        healthy
    )
    assert next(healthy_stream)["event_type"] == "WORKLOAD_STARTED"
    events = _small_early_event_stream(bundle, branch_id=TEMPORAL)
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
        events=events,
        next_coordinate=None,
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
    with pytest.raises(
        AcceptedWorkloadContractError,
        match="accepted_workload_failure_terminal_owner_mismatch",
    ):
        list(
            temporal_runner.iter_temporal_marginal_increment_accepted_parent_events(
                bundle, resume_index=resume
            )
        )
    changed = copy.deepcopy(resume)
    changed["events"][0]["payload"]["rng_draw_count"] = 1
    with pytest.raises(AcceptedWorkloadContractError):
        list(
            temporal_runner.iter_temporal_marginal_increment_accepted_parent_events(
                bundle, resume_index=changed
            )
        )


def test_joint_registered_candidate_binds_typed_parents_capsule_and_resume(
    probability_capsule: dict[str, Any]
) -> None:
    bundle = _joint_bundle(probability_capsule)
    assert validate_input_bundle(bundle, branch_id=JOINT) == bundle
    assert probability_capsule["row_count"] == 3480
    assert [row["transition_ordinal"] for row in probability_capsule["rows"]] == list(
        range(2, 3482)
    )
    parents = bundle["resolved_inputs"]["ordered_parent_decision_envelopes"]
    assert (
        parents[1]["body"]["accepted_model_artifact_digest"]
        == bundle["accepted_support_model_artifact_digest"]
    )
    healthy_stream = joint_runner.iter_joint_residual_increment_accepted_parent_events(
        bundle
    )
    assert next(healthy_stream)["event_type"] == "WORKLOAD_STARTED"
    events = _small_early_event_stream(bundle, branch_id=JOINT)
    assert [event["event_type"] for event in events] == [
        "WORKLOAD_STARTED",
        "TERMINAL_OUTCOME",
    ]
    resume = build_resume_index(
        branch_id=JOINT,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events,
        next_coordinate=None,
    )
    with pytest.raises(
        AcceptedWorkloadContractError,
        match="accepted_workload_failure_terminal_owner_mismatch",
    ):
        list(
            joint_runner.iter_joint_residual_increment_accepted_parent_events(
                bundle, resume_index=resume
            )
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
    with pytest.raises(AcceptedWorkloadContractError, match="parent.*cardinality"):
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
    with pytest.raises(
        (AcceptedWorkloadContractError, capsule.TemporalProbabilityCapsuleError),
        match="accepted_support_model_invalid|index_digest",
    ):
        list(
            joint_runner.iter_joint_residual_increment_accepted_parent_events(
                bad_capsule
            )
        )


def test_joint_consumes_sealed_capsule_without_numeric_rerun(
    probability_capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _joint_bundle(probability_capsule)

    def forbidden_numeric_rerun(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Joint must not re-run Temporal capsule numerics")

    monkeypatch.setattr(capsule, "evaluate_registered_weights", forbidden_numeric_rerun)
    joint_runner._validate_accepted_parents_and_capsule(bundle)
    changed = copy.deepcopy(bundle)
    changed["resolved_inputs"]["accepted_support_model_envelope"]["body"][
        "probability_capsule_index"
    ]["rows"][0]["numeric_runtime_contract_digest"] = _digest("wrong-runtime")
    with pytest.raises(
        capsule.TemporalProbabilityCapsuleError,
        match="sealed_capsule_row_identity_mismatch",
    ):
        joint_runner._validate_accepted_parents_and_capsule(changed)


def test_atomic_accepted_workload_equal_pending_recovery_and_exact_metadata(
    tmp_path: Any,
) -> None:
    bundle = _temporal_bundle()
    events = _small_early_event_stream(bundle, branch_id=TEMPORAL)
    resume = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events,
        next_coordinate=None,
    )
    transcript = build_full_transcript(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events,
    )
    task_key = "m4-v2-temporal-test-owner"
    relative_root = supervisor_module._accepted_workload_relative_root(
        task_key=task_key, execution_id=EXECUTION_ID
    )
    event_paths: list[tuple[str, Mapping[str, Any]]] = []
    for event in events:
        event_path, _ = supervisor_module._publish_accepted_workload_event_and_resume(
            root_dir=tmp_path,
            task_key=task_key,
            execution_id=EXECUTION_ID,
            event=event,
            resume_index=build_resume_index(
                branch_id=TEMPORAL,
                input_bundle_digest=bundle["input_bundle_digest"],
                producer_execution_id=EXECUTION_ID,
                events=events[: event["event_index"] + 1],
                next_coordinate=(
                    None
                    if event["event_type"] == "TERMINAL_OUTCOME"
                    else {"kind": "PRE_DRAW_VALIDATION"}
                ),
            ),
        )
        event_paths.append((event_path, event))
    pending = tmp_path / relative_root / ".pending"
    pending.mkdir(parents=True, exist_ok=True)
    staged_resume = pending / f"resume-index-{resume['resume_index_digest']}.json"
    supervisor_module._atomic_write_staged_file(
        staged_resume, supervisor_module._atomic_artifact_bytes(resume)
    )
    supervisor_module._recover_accepted_workload_pending(
        root_dir=tmp_path, task_key=task_key, execution_id=EXECUTION_ID
    )
    assert list(pending.iterdir()) == []

    owned = tuple(event_paths) + (
        (f"{relative_root}/transcript.json", transcript),
        (f"{relative_root}/resume-index.json", resume),
    )
    metadata = dict(
        supervisor_module.M4V2SuccessorCapability._accepted_workload_execution_metadata(
            bundle=bundle, owned_files=owned
        )
    )
    assert set(metadata) == {
        "accepted_workload_input_bundle_digest",
        "accepted_workload_resume_index_digest",
        "accepted_workload_resume_index_path",
        "accepted_workload_terminal_event_digest",
        "accepted_workload_transcript_digest",
        "accepted_workload_transcript_event_count",
        "accepted_workload_transcript_path",
        "accepted_workload_transcript_schema",
    }
    assert metadata["accepted_workload_terminal_event_digest"] == events[-1][
        "event_digest"
    ]
    supervisor_module._validate_accepted_workload_execution_metadata_keys(metadata)
    with pytest.raises(
        supervisor_module.MainlineSupervisorError,
        match="exact execution metadata is incomplete",
    ):
        supervisor_module._validate_accepted_workload_execution_metadata_keys(
            metadata | {"accepted_workload_unregistered_ninth_field": True}
        )
    extra_owned = owned[:-2] + (
        (f"{relative_root}/events/99999999-{'f' * 64}.json", events[-1]),
        *owned[-2:],
    )
    with pytest.raises(
        supervisor_module.MainlineSupervisorError,
        match="final ownership is not byte-equal",
    ):
        supervisor_module.M4V2SuccessorCapability._accepted_workload_execution_metadata(
            bundle=bundle, owned_files=extra_owned
        )


def test_atomic_pending_ambiguity_and_truncated_event_preserve_bytes(
    tmp_path: Any,
) -> None:
    relative_root = supervisor_module._accepted_workload_relative_root(
        task_key="m4-v2-temporal-test-owner", execution_id=EXECUTION_ID
    )
    pending = tmp_path / relative_root / ".pending"
    pending.mkdir(parents=True)
    first = pending / f"resume-index-{'a' * 64}.json"
    second = pending / f"resume-index-{'b' * 64}.json"
    first.write_bytes(b"{")
    second.write_bytes(b"{")
    with pytest.raises(
        supervisor_module.AtomicPublicationGovernanceIncident,
        match="pending set is ambiguous",
    ):
        supervisor_module._recover_accepted_workload_pending(
            root_dir=tmp_path,
            task_key="m4-v2-temporal-test-owner",
            execution_id=EXECUTION_ID,
        )
    assert first.read_bytes() == b"{" and second.read_bytes() == b"{"

    first.unlink()
    second.unlink()
    events = tmp_path / relative_root / "events"
    events.mkdir(parents=True)
    truncated = events / f"00000000-{'c' * 64}.json"
    truncated.write_bytes(b"{")
    with pytest.raises(
        supervisor_module.AtomicPublicationGovernanceIncident,
        match="event bytes are unreadable",
    ):
        supervisor_module._accepted_workload_event_entries(
            tmp_path / relative_root
        )
    assert truncated.read_bytes() == b"{"


def test_atomic_pending_filename_must_equal_payload_owner(tmp_path: Any) -> None:
    bundle = _temporal_bundle()
    events = _small_early_event_stream(bundle, branch_id=TEMPORAL)
    resume = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events,
        next_coordinate=None,
    )
    task_key = "m4-v2-temporal-pending-filename-owner"
    relative_root = supervisor_module._accepted_workload_relative_root(
        task_key=task_key, execution_id=EXECUTION_ID
    )
    pending = tmp_path / relative_root / ".pending"
    pending.mkdir(parents=True)
    wrong_name = pending / f"resume-index-{'f' * 64}.json"
    supervisor_module._atomic_write_staged_file(
        wrong_name, supervisor_module._atomic_artifact_bytes(resume)
    )
    with pytest.raises(
        supervisor_module.AtomicPublicationGovernanceIncident,
        match="resume filename owner changed",
    ):
        supervisor_module._recover_accepted_workload_pending(
            root_dir=tmp_path,
            task_key=task_key,
            execution_id=EXECUTION_ID,
        )
    assert wrong_name.is_file()


def test_atomic_orphan_adoption_reuses_one_resumed_generator(tmp_path: Any) -> None:
    bundle = _temporal_bundle()
    events = _small_early_event_stream(bundle, branch_id=TEMPORAL)
    assert [event["event_type"] for event in events] == [
        "WORKLOAD_STARTED",
        "TERMINAL_OUTCOME",
    ]
    task_key = "m4-v2-temporal-linear-resume-owner"
    started_resume = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events[:1],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
    )
    started_delta, started_head, started_reference = build_resume_journal_transition(
        None,
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        event=events[0],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
        checkpoint_resume_index_or_null=started_resume,
    )
    supervisor_module._publish_accepted_workload_journal_transition_v2(
        root_dir=tmp_path,
        task_key=task_key,
        execution_id=EXECUTION_ID,
        event=events[0],
        delta=started_delta,
        head=started_head,
        checkpoint_reference_or_null=started_reference,
        checkpoint_resume_index_or_null=started_resume,
    )
    relative_root = supervisor_module._accepted_workload_relative_root(
        task_key=task_key, execution_id=EXECUTION_ID
    )
    orphan = events[1]
    orphan_path = (
        tmp_path
        / relative_root
        / "events"
        / f"{orphan['event_index']:08d}-{orphan['event_digest']}.json"
    )
    supervisor_module._atomic_write_staged_file(
        orphan_path, supervisor_module._atomic_artifact_bytes(orphan)
    )
    terminal_resume = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events,
        next_coordinate=None,
    )
    orphan_delta, _, _ = build_resume_journal_transition(
        started_delta,
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        event=orphan,
        next_coordinate=None,
        checkpoint_resume_index_or_null=terminal_resume,
    )
    orphan_delta_path = (
        tmp_path
        / relative_root
        / "resume-deltas"
        / f"{orphan['event_index']:08d}-{orphan_delta['delta_digest']}.json"
    )
    supervisor_module._atomic_write_staged_file(
        orphan_delta_path, supervisor_module._atomic_artifact_bytes(orphan_delta)
    )

    invocation_count = 0

    def counting_iterator(*args: Any, **kwargs: Any) -> Any:
        nonlocal invocation_count
        invocation_count += 1
        resume_index = kwargs.get("resume_index")
        prefix_length = (
            len(resume_index["events"])
            if isinstance(resume_index, Mapping)
            else 0
        )
        return iter(events[prefix_length:])

    capability = supervisor_module.M4V2SuccessorCapability(
        repository=object(), root_dir=tmp_path
    )
    recovered, resume, transcript, owned = capability._run_accepted_workload_events(
        task=SimpleNamespace(task_key=task_key),
        execution_id=EXECUTION_ID,
        branch_id=TEMPORAL,
        bundle=bundle,
        iterator=counting_iterator,
    )
    assert invocation_count == 1
    assert recovered == events
    assert resume["terminal_seen"] is True
    assert transcript["events"] == events
    assert len(owned) == len(events) + 2


def test_incremental_resume_advance_matches_full_rebuild_without_prefix_revalidation() -> None:
    bundle = _temporal_bundle()
    events = _small_early_event_stream(bundle, branch_id=TEMPORAL)
    folds, schemes = validate_registered_computation_inputs(
        bundle, branch_id=TEMPORAL
    )
    started = advance_resume_index(
        None,
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        event=events[0],
        fold_coordinates=folds,
        sensitivity_scheme_ids=schemes,
    )
    assert started == build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events[:1],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
    )
    terminal = advance_resume_index(
        started,
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        event=events[1],
        fold_coordinates=folds,
        sensitivity_scheme_ids=schemes,
    )
    assert terminal == build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events,
        next_coordinate=None,
    )


def test_resume_v2_geometric_cadence_and_aggregate_prefix_cost_are_linear() -> None:
    assert EVALUATED_RESUME_CHECKPOINT_COUNTS_V2 == (
        1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 9761
    )
    observed = tuple(
        count
        for count in range(1, 9762)
        if is_resume_checkpoint_count(count, count == 9761)
    )
    assert observed == EVALUATED_RESUME_CHECKPOINT_COUNTS_V2
    assert sum(observed[:-1]) < 2 * 9761
    assert sum(observed) < 3 * 9761


def test_resume_v2_transition_is_bounded_between_checkpoints_and_tamper_fails() -> None:
    bundle = _temporal_bundle()
    events = _small_early_event_stream(bundle, branch_id=TEMPORAL)
    started_resume = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events[:1],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
    )
    delta, head, reference = build_resume_journal_transition(
        None,
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        event=events[0],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
        checkpoint_resume_index_or_null=started_resume,
    )
    assert "events" not in delta and "ordered_event_digests" not in delta
    assert "events" not in head and "ordered_event_digests" not in head
    assert reference is not None
    assert len(supervisor_module._atomic_artifact_bytes(delta)) < 4096
    assert len(supervisor_module._atomic_artifact_bytes(head)) < 4096
    tampered = copy.deepcopy(delta)
    tampered["prefix_root_digest"] = "f" * 64
    with pytest.raises(AcceptedWorkloadContractError):
        build_resume_journal_transition(
            tampered,
            branch_id=TEMPORAL,
            input_bundle_digest=bundle["input_bundle_digest"],
            producer_execution_id=EXECUTION_ID,
            event=events[1],
            next_coordinate=None,
            checkpoint_resume_index_or_null=build_resume_index(
                branch_id=TEMPORAL,
                input_bundle_digest=bundle["input_bundle_digest"],
                producer_execution_id=EXECUTION_ID,
                events=events,
                next_coordinate=None,
            ),
        )


def test_snapshot_reference_then_head_is_the_only_checkpoint_commit(
    tmp_path: Any,
) -> None:
    bundle = _temporal_bundle()
    events = _small_early_event_stream(bundle, branch_id=TEMPORAL)
    task_key = "m4-v2-temporal-snapshot-head-owner"
    started_resume = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events[:1],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
    )
    delta, head, reference = build_resume_journal_transition(
        None,
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        event=events[0],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
        checkpoint_resume_index_or_null=started_resume,
    )
    supervisor_module._publish_accepted_workload_journal_transition_v2(
        root_dir=tmp_path,
        task_key=task_key,
        execution_id=EXECUTION_ID,
        event=events[0],
        delta=delta,
        head=head,
        checkpoint_reference_or_null=reference,
        checkpoint_resume_index_or_null=started_resume,
    )
    base = tmp_path / supervisor_module._accepted_workload_relative_root(
        task_key=task_key, execution_id=EXECUTION_ID
    )
    assert not (base / "resume-index.json").exists()
    snapshot_path = base / reference["v1_resume_snapshot_path"]
    reference_path = base / head["latest_checkpoint_reference_path_or_null"]
    assert snapshot_path.is_file() and reference_path.is_file()
    assert snapshot_path.read_bytes() == supervisor_module._atomic_artifact_bytes(
        started_resume
    )
    assert head["latest_checkpoint_snapshot_path_or_null"] == (
        reference["v1_resume_snapshot_path"]
    )
    assert head["latest_checkpoint_reference_digest_or_null"] == (
        reference["checkpoint_reference_digest"]
    )


def test_head_pending_commits_only_after_exact_immutable_prerequisites(
    tmp_path: Any,
) -> None:
    bundle = _temporal_bundle()
    events = _small_early_event_stream(bundle, branch_id=TEMPORAL)
    task_key = "m4-v2-temporal-pending-head-owner"
    resume = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events[:1],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
    )
    delta, head, reference = build_resume_journal_transition(
        None,
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        event=events[0],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
        checkpoint_resume_index_or_null=resume,
    )
    supervisor_module._publish_accepted_workload_journal_transition_v2(
        root_dir=tmp_path,
        task_key=task_key,
        execution_id=EXECUTION_ID,
        event=events[0],
        delta=delta,
        head=head,
        checkpoint_reference_or_null=reference,
        checkpoint_resume_index_or_null=resume,
        commit_head=False,
    )
    base = tmp_path / supervisor_module._accepted_workload_relative_root(
        task_key=task_key, execution_id=EXECUTION_ID
    )
    pending = base / (
        ".pending-resume-journal-head-v2-none-"
        f"{head['head_digest']}.json"
    )
    supervisor_module._atomic_write_staged_file(
        pending, supervisor_module._atomic_artifact_bytes(head)
    )
    supervisor_module._recover_accepted_workload_pending_v2(
        root_dir=tmp_path,
        task_key=task_key,
        execution_id=EXECUTION_ID,
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        fold_coordinates=validate_registered_computation_inputs(
            bundle, branch_id=TEMPORAL
        )[0],
        sensitivity_scheme_ids=REGISTERED_HISTORICAL_SCHEME_IDS,
    )
    assert not pending.exists()
    assert (base / "resume-journal-head-v2.json").read_bytes() == (
        supervisor_module._atomic_artifact_bytes(head)
    )


def test_event_only_crash_rebuilds_exact_delta_snapshot_reference_and_head(
    tmp_path: Any,
) -> None:
    bundle = _temporal_bundle()
    started = _small_early_event_stream(bundle, branch_id=TEMPORAL)[0]
    task_key = "m4-v2-temporal-event-only-crash-owner"
    base = tmp_path / supervisor_module._accepted_workload_relative_root(
        task_key=task_key, execution_id=EXECUTION_ID
    )
    event_path = (
        base / "events"
        / f"{started['event_index']:08d}-{started['event_digest']}.json"
    )
    supervisor_module._atomic_write_staged_file(
        event_path, supervisor_module._atomic_artifact_bytes(started)
    )
    folds, schemes = validate_registered_computation_inputs(
        bundle, branch_id=TEMPORAL
    )
    supervisor_module._recover_accepted_workload_pending_v2(
        root_dir=tmp_path, task_key=task_key, execution_id=EXECUTION_ID,
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        fold_coordinates=folds, sensitivity_scheme_ids=schemes,
    )
    head = supervisor_module._load_object(
        base / "resume-journal-head-v2.json"
    )
    assert head["next_event_index"] == 1
    assert len(supervisor_module._accepted_workload_delta_entries(base)) == 1
    assert len(supervisor_module._accepted_workload_snapshot_entries(base)) == 1
    assert len(supervisor_module._accepted_workload_checkpoint_entries(base)) == 1


def test_wrong_pending_event_filename_fails_before_head_commit(
    tmp_path: Any,
) -> None:
    bundle = _temporal_bundle()
    started = _small_early_event_stream(bundle, branch_id=TEMPORAL)[0]
    task_key = "m4-v2-temporal-wrong-pending-owner"
    base = tmp_path / supervisor_module._accepted_workload_relative_root(
        task_key=task_key, execution_id=EXECUTION_ID
    )
    pending = base / ".pending"
    pending.mkdir(parents=True)
    wrong = pending / f"event-00000000-{'f' * 64}.json"
    supervisor_module._atomic_write_staged_file(
        wrong, supervisor_module._atomic_artifact_bytes(started)
    )
    folds, schemes = validate_registered_computation_inputs(
        bundle, branch_id=TEMPORAL
    )
    with pytest.raises(
        supervisor_module.AtomicPublicationGovernanceIncident,
        match="pending event filename owner changed",
    ):
        supervisor_module._recover_accepted_workload_pending_v2(
            root_dir=tmp_path, task_key=task_key,
            execution_id=EXECUTION_ID, branch_id=TEMPORAL,
            input_bundle_digest=bundle["input_bundle_digest"],
            fold_coordinates=folds, sensitivity_scheme_ids=schemes,
        )
    assert wrong.is_file()
    assert not (base / "resume-journal-head-v2.json").exists()


@pytest.mark.parametrize("crash_stage", ["delta", "snapshot", "reference"])
def test_exact_staged_prerequisite_crash_is_recovered_once(
    tmp_path: Any, crash_stage: str,
) -> None:
    bundle = _temporal_bundle()
    started = _small_early_event_stream(bundle, branch_id=TEMPORAL)[0]
    task_key = f"m4-v2-temporal-{crash_stage}-staged-owner"
    base = tmp_path / supervisor_module._accepted_workload_relative_root(
        task_key=task_key, execution_id=EXECUTION_ID
    )
    resume = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID, events=[started],
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
    )
    delta, _, reference = build_resume_journal_transition(
        None, branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID, event=started,
        next_coordinate={"kind": "PRE_DRAW_VALIDATION"},
        checkpoint_resume_index_or_null=resume,
    )
    event_path = (
        base / "events" / f"00000000-{started['event_digest']}.json"
    )
    supervisor_module._atomic_write_staged_file(
        event_path, supervisor_module._atomic_artifact_bytes(started)
    )
    if crash_stage == "delta":
        pending = base / ".pending"
        pending.mkdir()
        staged = pending / f"resume-delta-00000000-{delta['delta_digest']}.json"
        supervisor_module._atomic_write_staged_file(
            staged, supervisor_module._atomic_artifact_bytes(delta)
        )
    else:
        delta_path = (
            base / "resume-deltas" / f"00000000-{delta['delta_digest']}.json"
        )
        supervisor_module._atomic_write_staged_file(
            delta_path, supervisor_module._atomic_artifact_bytes(delta)
        )
        token = reference["checkpoint_reference_digest"][:32]
        snapshots = base / "resume-snapshots"
        checkpoints = base / "resume-checkpoints"
        snapshots.mkdir()
        checkpoints.mkdir()
        snapshot_pending = snapshots / (
            f".pending-00000001-{resume['resume_index_digest']}-{token}.json"
        )
        supervisor_module._atomic_write_staged_file(
            snapshot_pending, supervisor_module._atomic_artifact_bytes(resume)
        )
        if crash_stage == "reference":
            supervisor_module._atomic_publish_noreplace_same_directory(
                snapshot_pending,
                snapshots / f"00000001-{resume['resume_index_digest']}.json",
            )
            reference_pending = checkpoints / (
                f".pending-00000001-{reference['checkpoint_reference_digest']}-"
                f"{token}.json"
            )
            supervisor_module._atomic_write_staged_file(
                reference_pending,
                supervisor_module._atomic_artifact_bytes(reference),
            )
    folds, schemes = validate_registered_computation_inputs(
        bundle, branch_id=TEMPORAL
    )
    supervisor_module._recover_accepted_workload_pending_v2(
        root_dir=tmp_path, task_key=task_key, execution_id=EXECUTION_ID,
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        fold_coordinates=folds, sensitivity_scheme_ids=schemes,
    )
    assert (base / "resume-journal-head-v2.json").is_file()
    assert not list((base / ".pending").iterdir())
    assert not [
        path for directory in (base / "resume-snapshots", base / "resume-checkpoints")
        for path in directory.iterdir() if path.name.startswith(".pending-")
    ]


def test_legacy_migration_restarts_after_multi_pair_prehead_crash(
    tmp_path: Any, monkeypatch: Any,
) -> None:
    bundle = _temporal_bundle()
    events = _small_early_event_stream(bundle, branch_id=TEMPORAL)
    task_key = "m4-v2-temporal-legacy-interrupted-owner"
    legacy = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events, next_coordinate=None,
    )
    base = tmp_path / supervisor_module._accepted_workload_relative_root(
        task_key=task_key, execution_id=EXECUTION_ID
    )
    base.mkdir(parents=True)
    fixed = base / "resume-index.json"
    fixed_bytes = supervisor_module._atomic_artifact_bytes(legacy)
    fixed.write_bytes(fixed_bytes)
    folds, schemes = validate_registered_computation_inputs(
        bundle, branch_id=TEMPORAL
    )
    original_publish = supervisor_module._publish_accepted_workload_journal_transition_v2
    prehead_calls = 0

    def crash_after_second_prehead(**kwargs: Any) -> Any:
        nonlocal prehead_calls
        result = original_publish(**kwargs)
        if kwargs.get("commit_head") is False:
            prehead_calls += 1
            if prehead_calls == 2:
                raise OSError("simulated migration crash")
        return result

    monkeypatch.setattr(
        supervisor_module,
        "_publish_accepted_workload_journal_transition_v2",
        crash_after_second_prehead,
    )
    with pytest.raises(OSError, match="simulated migration crash"):
        supervisor_module._migrate_accepted_workload_legacy_v1(
            root_dir=tmp_path, task_key=task_key, execution_id=EXECUTION_ID,
            branch_id=TEMPORAL,
            input_bundle_digest=bundle["input_bundle_digest"],
            legacy_resume=legacy, fold_coordinates=folds,
            sensitivity_scheme_ids=schemes,
        )
    monkeypatch.setattr(
        supervisor_module,
        "_publish_accepted_workload_journal_transition_v2",
        original_publish,
    )
    migrated_events, migrated_deltas, head = (
        supervisor_module._migrate_accepted_workload_legacy_v1(
            root_dir=tmp_path, task_key=task_key, execution_id=EXECUTION_ID,
            branch_id=TEMPORAL,
            input_bundle_digest=bundle["input_bundle_digest"],
            legacy_resume=legacy, fold_coordinates=folds,
            sensitivity_scheme_ids=schemes,
        )
    )
    assert migrated_events == events and len(migrated_deltas) == 2
    assert head["next_event_index"] == 2
    assert fixed.read_bytes() == fixed_bytes


def test_legacy_v1_migration_never_rewrites_fixed_seed(tmp_path: Any) -> None:
    bundle = _temporal_bundle()
    events = _small_early_event_stream(bundle, branch_id=TEMPORAL)
    task_key = "m4-v2-temporal-legacy-seed-owner"
    legacy = build_resume_index(
        branch_id=TEMPORAL,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=EXECUTION_ID,
        events=events,
        next_coordinate=None,
    )
    base = tmp_path / supervisor_module._accepted_workload_relative_root(
        task_key=task_key, execution_id=EXECUTION_ID
    )
    base.mkdir(parents=True)
    fixed = base / "resume-index.json"
    fixed_bytes = supervisor_module._atomic_artifact_bytes(legacy)
    fixed.write_bytes(fixed_bytes)
    folds, schemes = validate_registered_computation_inputs(
        bundle, branch_id=TEMPORAL
    )
    migrated_events, migrated_deltas, head = (
        supervisor_module._migrate_accepted_workload_legacy_v1(
            root_dir=tmp_path,
            task_key=task_key,
            execution_id=EXECUTION_ID,
            branch_id=TEMPORAL,
            input_bundle_digest=bundle["input_bundle_digest"],
            legacy_resume=legacy,
            fold_coordinates=folds,
            sensitivity_scheme_ids=schemes,
        )
    )
    assert fixed.read_bytes() == fixed_bytes
    assert migrated_events == events and len(migrated_deltas) == 2
    assert head["next_event_index"] == 2
    assert sorted(path.name[:8] for path in (base / "resume-snapshots").iterdir()) == [
        "00000001",
        "00000002",
    ]


@pytest.mark.parametrize(
    "malicious",
    [
        "/resume-snapshots/00000001-" + "a" * 64 + ".json",
        "resume-snapshots/../00000001-" + "a" * 64 + ".json",
        "resume-snapshots\\00000001-" + "a" * 64 + ".json",
        "resume-snapshots//00000001-" + "a" * 64 + ".json",
        "resume-snapshots/000000001-" + "a" * 64 + ".json",
        "resume-snapshots/00000001-" + "A" * 64 + ".json",
    ],
)
def test_snapshot_serialized_path_rejects_traversal_and_noncanonical_identity(
    malicious: str,
) -> None:
    with pytest.raises(AcceptedWorkloadContractError):
        validate_resume_snapshot_relative_path_v1(
            malicious,
            checkpoint_event_count=1,
            resume_index_digest="a" * 64,
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
