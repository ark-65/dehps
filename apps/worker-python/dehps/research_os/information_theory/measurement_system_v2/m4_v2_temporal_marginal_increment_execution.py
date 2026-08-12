from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Any

import numpy as np

from dehps.research_os.models import (
    m4_v2_build_artifact_envelope,
    m4_v2_domain_digest,
)

from .branch_decision import (
    validate_marginal_static_branch_decision,
    validate_marginal_static_branch_decision_replay,
)
from .m4_v2_increment_execution_support import (
    REGISTERED_HISTORICAL_SCHEME_IDS,
    AcceptedWorkloadContractError,
    build_event,
    event_payload_digest,
    event_payload_schema,
    historical_settled_outcome_digest,
    preterminal_transcript_digest,
    producer_task_key,
    resume_events,
    validate_event_owner_equalities,
    validate_input_bundle,
    validate_registered_computation_inputs,
)
from .m4_v2_increment_fixture_generators import (
    build_historical_sensitivity_summary,
    build_synthetic_health_cell_summary,
    build_synthetic_health_replicate_evidence,
    build_temporal_registered_sequence_coordinate,
    generate_registered_synthetic_sequence,
    neumaier_mean,
    score_temporal_increment_sequence,
    synthetic_cells,
)
from .m4_v2_legal_fixed_cardinality import (
    evaluate_overlap_tilt,
    legal_state_log_probability,
    overlap_coefficient_masses,
    solve_fixed_cardinality_maximum_entropy,
    solve_overlap_theta,
)
from .temporal_marginal_increment import (
    CHECKPOINT_ORDER_MANIFEST_DIGEST,
    DATASET_CONTENT_DIGEST,
    FOLD_MANIFEST_DIGEST,
    PARENT_ESTIMATOR_ID,
    SUPPORT_MODEL_ID,
    TEMPORAL_MODEL_ID,
    build_accepted_temporal_evaluation_index,
    build_accepted_temporal_evaluation_row,
    build_accepted_temporal_pretarget_checkpoint,
    build_strict_prior_marginal_checkpoint,
    build_temporal_composite_view,
    build_temporal_warmup_index,
    build_temporal_warmup_row,
    build_transition_local_warmup_rule,
)
from .temporal_probability_capsule import (
    CAPSULE_ROW_FIELDS,
    CERTIFICATE_FIELDS,
    EVALUATOR_CONTRACT_DIGEST,
    NUMERIC_RUNTIME_CONTRACT_DIGEST,
    Q_M_CARRIER_CONTRACT_DIGEST,
    Q_M_SOLVER_SOURCE_CONTRACT_DIGEST,
    build_probability_capsule_index,
    evaluate_registered_weights,
    validate_probability_capsule_row,
)

TEMPORAL_BRANCH_ID = "TEMPORAL_MARGINAL_INCREMENT"


def _validate_accepted_parent(bundle: Mapping[str, Any]) -> None:
    decisions = bundle["resolved_inputs"]["ordered_parent_decision_envelopes"]
    replays = bundle["resolved_inputs"]["ordered_parent_replay_envelopes"]
    if len(decisions) != 1 or len(replays) != 1:
        raise AcceptedWorkloadContractError("temporal_parent_cardinality_invalid")
    try:
        decision = validate_marginal_static_branch_decision(decisions[0]).to_dict()
        replay = validate_marginal_static_branch_decision_replay(
            replays[0], decision=decision
        ).to_dict()
    except ValueError as exc:
        raise AcceptedWorkloadContractError("temporal_parent_identity_invalid") from exc
    if (
        decision["artifact_digest"]
        != bundle["ordered_parent_decision_artifact_digests"][0]
        or replay["artifact_digest"]
        != bundle["ordered_parent_replay_artifact_digests"][0]
        or decision["body"]["accepted_for_downstream_baseline"] is not True
        or replay["body"]["workload_rerun"] is not False
        or replay["body"]["replay_status"] != "REGISTERED_REPLAY_VERIFIED"
        or replay["body"]["decision_artifact_digest"] != decision["artifact_digest"]
    ):
        raise AcceptedWorkloadContractError("temporal_parent_acceptance_invalid")


def _started_payload(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "input_bundle_digest": bundle["input_bundle_digest"],
        "producer_task_key": producer_task_key(TEMPORAL_BRANCH_ID),
        "producer_execution_id": bundle["producer_execution_id"],
        "branch_id": TEMPORAL_BRANCH_ID,
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "preregistration_artifact_digest": bundle["preregistration_artifact_digest"],
        "parent_decision_artifact_digests_in_order": list(
            bundle["ordered_parent_decision_artifact_digests"]
        ),
        "parent_replay_artifact_digests_in_order": list(
            bundle["ordered_parent_replay_artifact_digests"]
        ),
        "scientific_execution_started": True,
        "start_phase": "HEALTH_PRE_DRAW_VALIDATION",
        "rng_draw_count": 0,
        "synthetic_replicate_count": 0,
        "historical_fold_count": 0,
        "bootstrap_resample_count": 0,
    }


def _prefix_digest(records: Sequence[Mapping[str, Any]], ordinal: int) -> str:
    return m4_v2_domain_digest(
        {
            "dataset_content_digest": DATASET_CONTENT_DIGEST,
            "last_included_ordinal": ordinal - 1,
            "ordered_issue_and_six_red_number_rows_1_through_last_included_ordinal": [
                {
                    "issue": record["issue"],
                    "red_numbers": list(record["red_numbers"]),
                }
                for record in records[: ordinal - 1]
            ],
        },
        domain="dehps.m4.v2.dataset-prefix-outcome-chain.v1",
    )


@dataclass
class _TemporalStrictPriorState:
    """Single-invocation expanding-prefix state; each ordinal advances once."""

    bundle: Mapping[str, Any]
    counts: list[int] = field(default_factory=lambda: [0] * 33)
    coefficient_rows: list[tuple[float, ...]] = field(default_factory=list)
    observed_overlaps: list[int] = field(default_factory=list)
    next_ordinal: int = 2

    @property
    def records(self) -> Sequence[Mapping[str, Any]]:
        return self.bundle["resolved_inputs"]["dataset_snapshot_envelope"]["body"][
            "history_snapshot"
        ]["records"]

    def advance(self) -> dict[str, Any]:
        ordinal = self.next_ordinal
        if not 2 <= ordinal <= len(self.records):
            raise AcceptedWorkloadContractError("temporal_target_ordinal_invalid")
        previous = self.records[ordinal - 2]["red_numbers"]
        if ordinal == 2:
            for label in previous:
                self.counts[label - 1] += 1
        target_marginals = [(count + 2.0 / 11.0) / ordinal for count in self.counts]
        solution = solve_fixed_cardinality_maximum_entropy(target_marginals)
        theta = 0.0
        if ordinal >= 901:
            try:
                theta = solve_overlap_theta(
                    self.coefficient_rows, self.observed_overlaps
                ).theta
            except ValueError as exc:
                raise AcceptedWorkloadContractError(
                    "temporal_theta_fit_failed"
                ) from exc
        previous_state = [label - 1 for label in previous]
        actual = self.records[ordinal - 1]["red_numbers"]
        actual_state = [label - 1 for label in actual]
        evaluated = evaluate_overlap_tilt(
            solution.weights, previous_state, theta, actual_state
        )
        combined = [
            value + (theta if index in previous_state else 0.0)
            for index, value in enumerate(solution.lambdas)
        ]
        maximum = max(combined)
        centered = [value - maximum for value in combined]
        weights_hex = [math.exp(value).hex() for value in centered]
        registered = evaluate_registered_weights(weights_hex)
        q_m_maximum = max(solution.lambdas)
        q_m_registered = evaluate_registered_weights(
            [math.exp(value - q_m_maximum).hex() for value in solution.lambdas]
        )
        result = {
            "target_ordinal": ordinal,
            "issue": self.records[ordinal - 1]["issue"],
            "previous_issue": self.records[ordinal - 2]["issue"],
            "previous_red_numbers": list(previous),
            "prefix_outcome_chain_digest": _prefix_digest(self.records, ordinal),
            "q_m_natural_parameters_float_hex": [
                value.hex() for value in solution.lambdas
            ],
            "q_m_weights": list(solution.weights),
            "q_m_marginals_float_hex": [value.hex() for value in solution.marginals],
            "q_m_partition_float_hex": solution.partition.hex(),
            "q_m_maximum_marginal_residual_float_hex": (
                solution.maximum_marginal_residual.hex()
            ),
            "q_m_solver_iteration_count": solution.iterations,
            "theta_float_hex": theta.hex(),
            "combined_log_weight_float_hex": [value.hex() for value in combined],
            "maximum_combined_log_weight_float_hex": maximum.hex(),
            "centered_log_weight_float_hex": [value.hex() for value in centered],
            "candidate_weight_float_hex": weights_hex,
            "registered_evaluation": registered,
            "q_m_registered_evaluation": q_m_registered,
            "actual_log_probability_float_hex": evaluated.actual_log_probability.hex(),
        }
        self.coefficient_rows.append(
            overlap_coefficient_masses(solution.weights, previous_state)
        )
        self.observed_overlaps.append(len(set(previous).intersection(actual)))
        for label in actual:
            self.counts[label - 1] += 1
        self.next_ordinal += 1
        return result


def _capsule_support(
    numeric: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    ordinal = numeric["target_ordinal"]
    registered = numeric["registered_evaluation"]
    q_m_registered = numeric["q_m_registered_evaluation"]
    if ordinal <= 900:
        owner = build_strict_prior_marginal_checkpoint(
            transition_ordinal=ordinal,
            issue=numeric["issue"],
            prefix_last_issue=numeric["previous_issue"],
            prefix_outcome_chain_digest=numeric["prefix_outcome_chain_digest"],
            q_m_marginal_content_digest=q_m_registered["q_t_marginal_content_digest"],
            q_m_full_distribution_content_digest=q_m_registered[
                "q_t_full_distribution_content_digest"
            ],
        )
        support = build_temporal_warmup_row(owner)
        return owner, support
    pretarget = build_accepted_temporal_pretarget_checkpoint(
        transition_ordinal=ordinal,
        issue=numeric["issue"],
        training_prefix_outcome_chain_digest=numeric["prefix_outcome_chain_digest"],
        theta_float_hex=numeric["theta_float_hex"],
        q_t_marginal_content_digest=registered["q_t_marginal_content_digest"],
        q_t_full_distribution_content_digest=registered[
            "q_t_full_distribution_content_digest"
        ],
    )
    owner = {
        "schema_version": "dehps-m4-v2-candidate-v3-q-m-solver-output-checkpoint.v1",
        "support_kind": "ACCEPTED_TEMPORAL_EVALUATION",
        "dataset_content_digest": DATASET_CONTENT_DIGEST,
        "fold_manifest_digest": FOLD_MANIFEST_DIGEST,
        "checkpoint_order_manifest_digest": CHECKPOINT_ORDER_MANIFEST_DIGEST,
        "transition_ordinal": ordinal,
        "issue": numeric["issue"],
        "training_prefix_last_ordinal": ordinal - 1,
        "training_prefix_outcome_chain_digest": numeric["prefix_outcome_chain_digest"],
        "parent_estimator_id": PARENT_ESTIMATOR_ID,
        "q_m_carrier_contract_digest": Q_M_CARRIER_CONTRACT_DIGEST,
        "q_m_solver_source_contract_digest": Q_M_SOLVER_SOURCE_CONTRACT_DIGEST,
        "numeric_runtime_contract_digest": NUMERIC_RUNTIME_CONTRACT_DIGEST,
        "q_m_output_evaluator_contract_digest": EVALUATOR_CONTRACT_DIGEST,
        "q_m_target_marginal_float_hex_in_ball_order_1_through_33": q_m_registered[
            "q_t_marginal_float_hex_in_ball_order_1_through_33"
        ],
        "q_m_target_marginal_content_digest": q_m_registered[
            "q_t_marginal_content_digest"
        ],
        "q_m_natural_parameter_float_hex_in_ball_order_1_through_33": numeric[
            "q_m_natural_parameters_float_hex"
        ],
        "q_m_solver_iteration_count": numeric["q_m_solver_iteration_count"],
        "q_m_solver_termination_reason": "REGISTERED_CONVERGENCE",
        "q_m_maximum_marginal_residual_float_hex": numeric[
            "q_m_maximum_marginal_residual_float_hex"
        ],
        "q_m_full_distribution_content_digest": q_m_registered[
            "q_t_full_distribution_content_digest"
        ],
        "pretarget_checkpoint_digest": pretarget["pretarget_checkpoint_digest"],
    }
    owner["q_m_solver_output_checkpoint_digest"] = m4_v2_domain_digest(
        owner,
        domain="dehps.m4.v2.candidate-v3.q-m-solver-output-checkpoint.v1",
    )
    return owner, build_accepted_temporal_evaluation_row(pretarget)


def _probability_capsule_row(
    numeric: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    owner, support = _capsule_support(numeric)
    ordinal = numeric["target_ordinal"]
    warmup = ordinal <= 900
    registered = numeric["registered_evaluation"]
    q_m_registered = numeric["q_m_registered_evaluation"]
    support_row_digest = support["row_digest" if warmup else "q_t_row_digest"]
    support_checkpoint_digest = owner[
        "checkpoint_digest" if warmup else "pretarget_checkpoint_digest"
    ]
    weights = list(numeric["candidate_weight_float_hex"])
    weight_digest = m4_v2_domain_digest(
        {"candidate_weight_float_hex_in_ball_order_1_through_33": weights},
        domain="dehps.m4.v2.temporal.candidate-weight-content.v1",
    )
    previous_digest = m4_v2_domain_digest(
        {
            "transition_ordinal": ordinal,
            "previous_draw_issue": numeric["previous_issue"],
            "previous_draw_labels_in_ascending_order": numeric["previous_red_numbers"],
        },
        domain="dehps.m4.v2.temporal.strict-prior-previous-draw.v1",
    )
    values = {
        "transition_ordinal": ordinal,
        "issue": numeric["issue"],
        "support_kind": (
            "WARMUP_NULL_ALIAS" if warmup else "ACCEPTED_TEMPORAL_EVALUATION"
        ),
        "temporal_support_row_digest": support_row_digest,
        "temporal_support_checkpoint_digest": support_checkpoint_digest,
        "prefix_outcome_chain_digest": numeric["prefix_outcome_chain_digest"],
        "q_m_target_marginal_float_hex_in_ball_order_1_through_33": q_m_registered[
            "q_t_marginal_float_hex_in_ball_order_1_through_33"
        ],
        "q_m_target_marginal_content_digest": q_m_registered[
            "q_t_marginal_content_digest"
        ],
        "q_m_full_distribution_content_digest": q_m_registered[
            "q_t_full_distribution_content_digest"
        ],
        "q_m_solver_source_contract_digest": Q_M_SOLVER_SOURCE_CONTRACT_DIGEST,
        "q_m_solver_iteration_count": numeric["q_m_solver_iteration_count"],
        "q_m_solver_termination_reason": "REGISTERED_CONVERGENCE",
        "q_m_natural_parameter_float_hex_in_ball_order_1_through_33": numeric[
            "q_m_natural_parameters_float_hex"
        ],
        "q_m_maximum_marginal_residual_float_hex": numeric[
            "q_m_maximum_marginal_residual_float_hex"
        ],
        "theta_float_hex": numeric["theta_float_hex"],
        "previous_draw_issue": numeric["previous_issue"],
        "previous_draw_labels_in_ascending_order": numeric["previous_red_numbers"],
        "previous_draw_content_digest": previous_digest,
        "combined_log_weight_float_hex_in_ball_order_1_through_33": numeric[
            "combined_log_weight_float_hex"
        ],
        "maximum_combined_log_weight_float_hex": numeric[
            "maximum_combined_log_weight_float_hex"
        ],
        "centered_log_weight_float_hex_in_ball_order_1_through_33": numeric[
            "centered_log_weight_float_hex"
        ],
        "candidate_weight_float_hex_in_ball_order_1_through_33": weights,
        "candidate_weight_content_digest": weight_digest,
        "numeric_runtime_contract_digest": NUMERIC_RUNTIME_CONTRACT_DIGEST,
        "evaluator_contract_digest": EVALUATOR_CONTRACT_DIGEST,
        "q_t_marginal_content_digest": registered["q_t_marginal_content_digest"],
        "q_t_full_distribution_content_digest": registered[
            "q_t_full_distribution_content_digest"
        ],
        "q_m_owner_checkpoint": owner,
        "q_m_owner_checkpoint_digest": owner[
            "checkpoint_digest" if warmup else "q_m_solver_output_checkpoint_digest"
        ],
    }
    certificate = {field: values[field] for field in CERTIFICATE_FIELDS[:-1]}
    certificate["certificate_digest"] = m4_v2_domain_digest(
        certificate,
        domain="dehps.m4.v2.temporal.probability-weight-derivation-certificate.v1",
    )
    values.update(
        {
            "weight_derivation_certificate": certificate,
            "weight_derivation_certificate_digest": certificate["certificate_digest"],
            "partition_float_hex": registered["partition_float_hex"],
        }
    )
    row = {field: values[field] for field in CAPSULE_ROW_FIELDS[:-1]}
    row["capsule_digest"] = m4_v2_domain_digest(
        row, domain="dehps.m4.v2.temporal.probability-capsule-row.v2"
    )
    return validate_probability_capsule_row(row), support


def _coordinate(
    event_type: str, payload: Mapping[str, Any], index: int
) -> dict[str, Any]:
    if event_type == "WORKLOAD_STARTED":
        return {"phase": "HEALTH_PRE_DRAW_VALIDATION"}
    if event_type == "HEALTH_REPLICATE_COMMIT":
        return {"cell_index": index // 512, "replicate_index": index % 512}
    if event_type == "HEALTH_AGGREGATE_COMPLETE":
        return {"phase": "HEALTH_AGGREGATE"}
    if event_type == "HISTORICAL_FOLD_COMMIT":
        return {
            "evaluation_ordinal": payload["evaluation_ordinal"],
            "issue": payload["issue"],
        }
    if event_type == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT":
        return {"scheme_index": index, "scheme_id": payload["scheme_id"]}
    if event_type == "HISTORICAL_AGGREGATE_COMPLETE":
        return {"phase": "HISTORICAL_AGGREGATE"}
    return {
        "phase": "TERMINAL_OUTCOME",
        "execution_subpath": payload["execution_subpath"],
        "decision_path": payload["decision_path"],
    }


def _health_replicate_payload(
    bundle: Mapping[str, Any], *, cell_index: int, replicate_index: int
) -> dict[str, Any]:
    preregistration = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
    generated = generate_registered_synthetic_sequence(
        branch_id=TEMPORAL_BRANCH_ID,
        root_seed_full_sha256=bundle["synthetic_root_seed_full_sha256"],
        cell_index=cell_index,
        replicate_index=replicate_index,
    )
    coordinate = build_temporal_registered_sequence_coordinate(
        sequence=generated,
        fixture_source_digest=bundle["fixture_source_artifact_digest"],
        health_contract_digest=preregistration["health_contract_digest"],
        seed_contract_digest=preregistration["seed_contract_digest"],
        synthetic_root_seed_full_sha256=bundle[
            "synthetic_root_seed_full_sha256"
        ],
        replicate_index=replicate_index,
    )
    scored = score_temporal_increment_sequence(
        generated.draws,
        evaluation_issue_count=generated.cell.evaluation_issue_count,
    )
    payload, _ = build_synthetic_health_replicate_evidence(
        scored.score_values,
        branch_id=TEMPORAL_BRANCH_ID,
        root_seed_full_sha256=bundle["synthetic_root_seed_full_sha256"],
        cell_index=cell_index,
        cell_id=generated.cell.cell_id,
        fixture_id=generated.cell.fixture_id,
        horizon_id=generated.cell.horizon_id,
        replicate_index=replicate_index,
        sequence_coordinate_digest=coordinate["coordinate_digest"],
        prediction_checkpoint_chain_digest=(scored.prediction_checkpoint_chain_digest),
        score_row_chain_digest=scored.score_row_chain_digest,
        analytic_truth_bits_per_issue=(generated.cell.analytic_target_bits_per_issue),
    )
    return payload


def _health_aggregate_payload(
    bundle: Mapping[str, Any], events: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    replicate_payloads = [
        event["payload"]
        for event in events
        if event["event_type"] == "HEALTH_REPLICATE_COMMIT"
    ]
    if len(replicate_payloads) != 7168:
        raise AcceptedWorkloadContractError("temporal_health_grid_incomplete")
    summaries = [
        build_synthetic_health_cell_summary(
            replicate_payloads[index * 512 : (index + 1) * 512],
            branch_id=TEMPORAL_BRANCH_ID,
            cell=synthetic_cells(TEMPORAL_BRANCH_ID)[index],
        )
        for index in range(14)
    ]
    summary_chain = m4_v2_domain_digest(
        {
            "ordered_cell_summary_digests": [
                summary["cell_summary_digest"] for summary in summaries
            ]
        },
        domain="dehps.m4.v2.temporal.health-cell-summary-chain.v2",
    )
    failed = [
        summary["cell_id"]
        for summary in summaries
        if summary["threshold_pass"] is False
    ]
    preregistration = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
    return {
        "status": "COMPLETE",
        "measurement_contract_key": preregistration["measurement_contract_key"],
        "measurement_contract_digest": preregistration["measurement_contract_digest"],
        "branch_id": TEMPORAL_BRANCH_ID,
        "estimand_digest": preregistration["estimand_digest"],
        "decision_path": (
            "IDENTITY_VALID_HEALTH_REPAIR" if failed else "EVALUATED_COMPLETE"
        ),
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "preregistration_artifact_digest": bundle["preregistration_artifact_digest"],
        "marginal_decision_digest": bundle["ordered_parent_decision_artifact_digests"][
            0
        ],
        "marginal_replay_digest": bundle["ordered_parent_replay_artifact_digests"][0],
        "transition_local_warmup_rule_digest": preregistration[
            "transition_local_warmup_rule_digest"
        ],
        "synthetic_warmup_application_or_null": None,
        "synthetic_warmup_application_digest_or_null": None,
        "warmup_alias_position_count": 0,
        "cell_summaries": summaries,
        "cell_summary_chain_digest": summary_chain,
        "measurement_health": "REPAIR" if failed else "PASS",
        "failed_cell_ids": failed,
        "synthetic_replicate_count": 7168,
        "synthetic_generated_issue_count": 15_920_128,
        "outer_evaluation_issue_count": 9_468_928,
        "bootstrap_resample_count": 14_651_392,
        "historical_started": False,
        "repair_required": bool(failed),
        "production_action": "none",
    }


def _complete_grid_health_terminal(
    bundle: Mapping[str, Any], health_body: Mapping[str, Any]
) -> dict[str, Any]:
    health = m4_v2_build_artifact_envelope(
        artifact_type="M4V2TemporalMarginalIncrementHealthAggregateArtifact",
        schema_version=("dehps-m4-v2-temporal-marginal-increment-health-aggregate.v2"),
        body=health_body,
        parent_digests=(
            bundle["source_contract_artifact_digest"],
            bundle["preregistration_artifact_digest"],
            bundle["ordered_parent_decision_artifact_digests"][0],
            bundle["ordered_parent_replay_artifact_digests"][0],
        ),
    )
    preregistration = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
    return {
        "execution_subpath": "COMPLETE_GRID_HEALTH_REPAIR",
        "decision_path": "IDENTITY_VALID_HEALTH_REPAIR",
        "failure_stage": "HEALTH",
        "terminal_decision": "MEASUREMENT_REPAIR_REQUIRED",
        "scientific_decision": "MEASUREMENT_REPAIR_REQUIRED",
        "evaluation_status": "REPAIR_REQUIRED",
        "measurement_health": "REPAIR",
        "historical_evidence": "NOT_RUN",
        "baseline_artifact_body_or_null": None,
        "health_artifact_body_or_null": dict(health_body),
        "historical_artifact_body_or_null": None,
        "candidate_artifact_body_or_null": None,
        "failure_artifact_body_or_null": None,
        "expected_baseline_artifact_digest_or_null": None,
        "expected_health_artifact_digest_or_null": health["artifact_digest"],
        "expected_historical_artifact_digest_or_null": None,
        "expected_candidate_artifact_digest_or_null": None,
        "expected_failure_artifact_digest_or_null": None,
        "completed_fold_count": 0,
        "completed_resample_count": 0,
        "reason_codes": list(health_body["failed_cell_ids"]),
        "planned_counts": dict(preregistration["planned_counts"]),
    }


def _historical_fold_payload(
    bundle: Mapping[str, Any], *, numeric: Mapping[str, Any]
) -> tuple[dict[str, Any], float]:
    evaluation_ordinal = numeric["target_ordinal"]
    registered = numeric["registered_evaluation"]
    checkpoint = build_accepted_temporal_pretarget_checkpoint(
        transition_ordinal=evaluation_ordinal,
        issue=numeric["issue"],
        training_prefix_outcome_chain_digest=numeric["prefix_outcome_chain_digest"],
        theta_float_hex=numeric["theta_float_hex"],
        q_t_marginal_content_digest=registered["q_t_marginal_content_digest"],
        q_t_full_distribution_content_digest=registered[
            "q_t_full_distribution_content_digest"
        ],
    )
    evaluation = build_accepted_temporal_evaluation_row(checkpoint)
    row = bundle["resolved_inputs"]["dataset_snapshot_envelope"]["body"][
        "history_snapshot"
    ]["records"][evaluation_ordinal - 1]
    actual_state = [value - 1 for value in row["red_numbers"]]
    base_log_probability = legal_state_log_probability(
        numeric["q_m_weights"],
        actual_state,
        partition=float.fromhex(numeric["q_m_partition_float_hex"]),
    )
    paired_score = (
        float.fromhex(numeric["actual_log_probability_float_hex"])
        - base_log_probability
    ) / math.log(2.0)
    settled = historical_settled_outcome_digest(
        evaluation_ordinal=evaluation_ordinal,
        issue=row["issue"],
        red_numbers=row["red_numbers"],
    )
    score_row = {
        "evaluation_ordinal": evaluation_ordinal,
        "issue": row["issue"],
        "prediction_checkpoint_digest": evaluation["q_t_row_digest"],
        "settled_outcome_digest": settled,
        "paired_score_float_hex": paired_score.hex(),
    }
    score_row["score_row_digest"] = m4_v2_domain_digest(
        score_row,
        domain="dehps.m4.v2.temporal.historical-score-row.v2",
    )
    fold = bundle["resolved_inputs"]["fold_manifest_envelope"]["body"]["folds"][
        evaluation_ordinal - 901
    ]
    payload = {
        "evaluation_ordinal": evaluation_ordinal,
        "issue": row["issue"],
        "fold_digest": fold["fold_digest"],
        "prediction_checkpoint_body": evaluation,
        "prediction_checkpoint_digest": evaluation["q_t_row_digest"],
        "score_row_body": score_row,
        "score_row_digest": score_row["score_row_digest"],
    }
    payload["fold_commit_digest"] = m4_v2_domain_digest(
        payload,
        domain=("dehps.m4.v2.temporal.accepted-workload-historical-fold-commit.v1"),
    )
    return payload, paired_score


def _marginal_raw_p_value(bundle: Mapping[str, Any]) -> tuple[str, float]:
    envelope = bundle["resolved_inputs"]["ordered_holm_lineage_envelopes"][0]
    body = envelope.get("body")
    raw = body.get("raw_primary_p_value") if isinstance(body, Mapping) else None
    if (
        isinstance(raw, bool)
        or not isinstance(raw, (int, float))
        or not math.isfinite(float(raw))
        or not 0.0 <= float(raw) <= 1.0
    ):
        raise AcceptedWorkloadContractError(
            "temporal_registered_marginal_raw_p_missing"
        )
    return envelope["artifact_digest"], float(raw)


def _holm_adjusted_for_temporal(marginal: float, temporal: float) -> float:
    ordered = sorted(
        ((marginal, "MARGINAL_STATIC"), (temporal, TEMPORAL_BRANCH_ID), (1.0, "JOINT"))
    )
    adjusted: dict[str, float] = {}
    running = 0.0
    for index, (raw, branch) in enumerate(ordered):
        running = max(running, min(1.0, (3 - index) * raw))
        adjusted[branch] = running
    return adjusted[TEMPORAL_BRANCH_ID]


def _historical_aggregate_payload(
    bundle: Mapping[str, Any],
    *,
    health_artifact_digest: str,
    fold_payloads: Sequence[Mapping[str, Any]],
    sensitivity_summaries: Sequence[Mapping[str, Any]],
    sensitivity_owners: Sequence[Mapping[str, Any]],
    warmup_index_digest: str,
    evaluation_index_digest: str,
    composite_view_digest: str,
) -> dict[str, Any]:
    scores = [
        float.fromhex(item["score_row_body"]["paired_score_float_hex"])
        for item in fold_payloads
    ]
    if len(scores) != 2581 or len(sensitivity_summaries) != 8:
        raise AcceptedWorkloadContractError("temporal_historical_grid_incomplete")
    primary_index = list(REGISTERED_HISTORICAL_SCHEME_IDS).index(
        "MOVING_BLOCK_NONCIRCULAR_LENGTH_5_PRIMARY"
    )
    primary_owner = sensitivity_owners[primary_index]
    primary_means = [
        float.fromhex(value) for value in primary_owner["ordered_child_mean_float_hex"]
    ]
    observed = neumaier_mean(scores)
    threshold = 0.0
    centered = [value - observed + threshold for value in primary_means]
    raw_p = (1 + sum(value >= observed for value in centered)) / 2001.0
    alpha = 0.05 / 3.0
    lower, upper, equivalence_upper = np.quantile(
        np.asarray(primary_means, dtype=np.float64),
        [alpha / 2.0, 1.0 - alpha / 2.0, 1.0 - alpha],
        method="linear",
    )
    standard_error = float(np.std(primary_means, ddof=1))
    normal = NormalDist()
    mde = (normal.inv_cdf(1.0 - alpha) + normal.inv_cdf(0.8)) * standard_error
    power = normal.cdf(threshold / standard_error - normal.inv_cdf(1.0 - alpha))
    marginal_artifact_digest, marginal_p = _marginal_raw_p_value(bundle)
    prereg = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
    return {
        "status": "COMPLETE",
        "measurement_contract_key": prereg["measurement_contract_key"],
        "measurement_contract_digest": prereg["measurement_contract_digest"],
        "branch_id": TEMPORAL_BRANCH_ID,
        "estimand_digest": prereg["estimand_digest"],
        "decision_path": "EVALUATED_COMPLETE",
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "preregistration_artifact_digest": bundle["preregistration_artifact_digest"],
        "health_artifact_digest": health_artifact_digest,
        "marginal_raw_p_artifact_digest": marginal_artifact_digest,
        "dataset_content_digest": bundle["dataset_content_digest"],
        "fold_manifest_digest": bundle["fold_manifest_artifact_digest"],
        "checkpoint_chain_digest": m4_v2_domain_digest(
            {
                "ordered_checkpoint_digests": [
                    item["prediction_checkpoint_digest"] for item in fold_payloads
                ]
            },
            domain="dehps.m4.v2.temporal.historical-checkpoint-chain.v2",
        ),
        "score_sequence_digest": m4_v2_domain_digest(
            {
                "ordered_score_row_digests": [
                    item["score_row_digest"] for item in fold_payloads
                ]
            },
            domain="dehps.m4.v2.temporal.historical-score-sequence.v2",
        ),
        "score_count": 2581,
        "observed_mean_bits_per_issue": observed,
        "raw_primary_p_value": raw_p,
        "holm_family_raw_p_values": {
            "MARGINAL_STATIC": marginal_p,
            "TEMPORAL_MARGINAL_INCREMENT": raw_p,
            "JOINT_RESIDUAL_INCREMENT": 1.0,
        },
        "holm_adjusted_p_value": _holm_adjusted_for_temporal(marginal_p, raw_p),
        "simultaneous_effect_interval_bits_per_issue": {
            "lower_float_hex": float(lower).hex(),
            "upper_float_hex": float(upper).hex(),
        },
        "equivalence_upper_bound_bits_per_issue": float(equivalence_upper),
        "bootstrap_standard_error": standard_error,
        "mde_bits_per_issue": max(0.0, mde),
        "equivalence_power_at_zero": power,
        "equivalence_power_sufficient": power >= 0.8,
        "half_means_bits_per_issue": {
            "first_half_float_hex": neumaier_mean(scores[:1291]).hex(),
            "second_half_float_hex": neumaier_mean(scores[1291:]).hex(),
        },
        "positive_stability_pass": (
            neumaier_mean(scores[:1291]) > 0.0 and neumaier_mean(scores[1291:]) > 0.0
        ),
        "sensitivity_summaries": [dict(value) for value in sensitivity_summaries],
        "historical_child_count": 16000,
        "warmup_index_digest": warmup_index_digest,
        "accepted_temporal_evaluation_index_digest": evaluation_index_digest,
        "composite_view_digest": composite_view_digest,
        "production_action": "none",
    }


def _evaluated_terminal(
    bundle: Mapping[str, Any],
    *,
    health_body: Mapping[str, Any],
    historical_body: Mapping[str, Any],
    warmup_index: Mapping[str, Any],
    evaluation_index: Mapping[str, Any],
    composite_view: Mapping[str, Any],
    capsule_index: Mapping[str, Any],
) -> dict[str, Any]:
    parent_pairs = (
        bundle["ordered_parent_decision_artifact_digests"][0],
        bundle["ordered_parent_replay_artifact_digests"][0],
    )
    health = m4_v2_build_artifact_envelope(
        artifact_type="M4V2TemporalMarginalIncrementHealthAggregateArtifact",
        body=health_body,
        parent_digests=(
            bundle["source_contract_artifact_digest"],
            bundle["preregistration_artifact_digest"],
            *parent_pairs,
        ),
    )
    historical = m4_v2_build_artifact_envelope(
        artifact_type="M4V2TemporalMarginalIncrementHistoricalAggregateArtifact",
        body=historical_body,
        parent_digests=(
            bundle["source_contract_artifact_digest"],
            bundle["preregistration_artifact_digest"],
            health["artifact_digest"],
            historical_body["marginal_raw_p_artifact_digest"],
        ),
    )
    prereg = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
    candidate_body = {
        "status": "COMPLETE",
        "measurement_contract_key": prereg["measurement_contract_key"],
        "measurement_contract_digest": prereg["measurement_contract_digest"],
        "branch_id": TEMPORAL_BRANCH_ID,
        "estimand_digest": prereg["estimand_digest"],
        "model_id": TEMPORAL_MODEL_ID,
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "dataset_content_digest": bundle["dataset_content_digest"],
        "fold_manifest_digest": bundle["fold_manifest_artifact_digest"],
        "marginal_parent_model_artifact_digest": bundle[
            "accepted_support_model_artifact_digest"
        ],
        # The registered support envelope is the only accepted marginal
        # probability owner admitted by the v2 input bundle.
        "marginal_parent_probability_chain_digest": bundle[
            "accepted_support_model_artifact_digest"
        ],
        "support_model_id": SUPPORT_MODEL_ID,
        "historical_warmup_index": dict(warmup_index),
        "warmup_index_digest": warmup_index["warmup_index_digest"],
        "accepted_temporal_evaluation_index": dict(evaluation_index),
        "accepted_temporal_evaluation_index_digest": evaluation_index[
            "accepted_temporal_evaluation_index_digest"
        ],
        "composite_temporal_view": dict(composite_view),
        "composite_view_digest": composite_view["composite_view_digest"],
        "historical_fold_count": 2581,
        "production_action": "none",
        "probability_capsule_index": dict(capsule_index),
        "probability_capsule_index_digest": capsule_index["index_digest"],
        "probability_capsule_evaluator_contract_digest": capsule_index[
            "evaluator_contract_digest"
        ],
    }
    candidate = m4_v2_build_artifact_envelope(
        artifact_type="M4V2TemporalMarginalIncrementCandidateModelArtifact",
        schema_version="dehps-m4-v2-temporal-marginal-increment-candidate-model.v3",
        body=candidate_body,
        parent_digests=(
            bundle["source_contract_artifact_digest"],
            historical["artifact_digest"],
            candidate_body["marginal_parent_model_artifact_digest"],
            candidate_body["marginal_parent_probability_chain_digest"],
        ),
    )
    adjusted = float(historical_body["holm_adjusted_p_value"])
    interval = historical_body["simultaneous_effect_interval_bits_per_issue"]
    positive = (
        adjusted <= 0.05
        and float.fromhex(interval["lower_float_hex"]) > 0.01
        and historical_body["positive_stability_pass"] is True
    )
    negative = (
        not positive
        and adjusted > 0.05
        and historical_body["equivalence_power_sufficient"] is True
        and float(historical_body["equivalence_upper_bound_bits_per_issue"]) <= 0.01
        and 0.0 <= float(historical_body["mde_bits_per_issue"]) <= 0.01
    )
    terminal_decision = (
        "BRANCH_INFORMATION_ACCEPTED"
        if positive
        else "NO_DETECTABLE_INFORMATION"
        if negative
        else "INCONCLUSIVE_DUE_TO_POWER"
    )
    return {
        "execution_subpath": "EVALUATED_COMPLETE",
        "decision_path": "EVALUATED_COMPLETE",
        "failure_stage": None,
        "terminal_decision": terminal_decision,
        "scientific_decision": terminal_decision,
        "evaluation_status": "COMPLETE",
        "measurement_health": "PASS",
        "historical_evidence": (
            "POSITIVE" if positive else "NEGATIVE" if negative else "INCONCLUSIVE"
        ),
        "baseline_artifact_body_or_null": None,
        "health_artifact_body_or_null": dict(health_body),
        "historical_artifact_body_or_null": dict(historical_body),
        "candidate_artifact_body_or_null": candidate_body,
        "failure_artifact_body_or_null": None,
        "expected_baseline_artifact_digest_or_null": None,
        "expected_health_artifact_digest_or_null": health["artifact_digest"],
        "expected_historical_artifact_digest_or_null": historical["artifact_digest"],
        "expected_candidate_artifact_digest_or_null": candidate["artifact_digest"],
        "expected_failure_artifact_digest_or_null": None,
        "completed_fold_count": 2581,
        "completed_resample_count": 16_000,
        "reason_codes": [],
        "planned_counts": dict(prereg["planned_counts"]),
    }


def _iter_events(
    bundle: Mapping[str, Any], *, prefix: Sequence[Mapping[str, Any]] = ()
) -> Iterator[dict[str, Any]]:
    events = [dict(event) for event in prefix]

    def append(
        event_type: str, payload: Mapping[str, Any], coordinate_index: int = 0
    ) -> dict[str, Any]:
        event = build_event(
            branch_id=TEMPORAL_BRANCH_ID,
            input_bundle_digest=bundle["input_bundle_digest"],
            producer_execution_id=bundle["producer_execution_id"],
            event_index=len(events),
            event_type=event_type,
            coordinate_key=_coordinate(event_type, payload, coordinate_index),
            payload_schema=event_payload_schema(
                branch_id=TEMPORAL_BRANCH_ID, event_type=event_type
            ),
            payload=payload,
            payload_digest=event_payload_digest(
                branch_id=TEMPORAL_BRANCH_ID, event_type=event_type, payload=payload
            ),
            previous_event_digest_or_null=(
                events[-1]["event_digest"] if events else None
            ),
        )
        events.append(event)
        return event

    if events and events[-1]["event_type"] == "TERMINAL_OUTCOME":
        return
    if not events:
        yield append("WORKLOAD_STARTED", _started_payload(bundle))
    replicate_events = [
        event for event in events if event["event_type"] == "HEALTH_REPLICATE_COMMIT"
    ]
    for flat_index in range(len(replicate_events), 7168):
        cell_index, replicate_index = divmod(flat_index, 512)
        yield append(
            "HEALTH_REPLICATE_COMMIT",
            _health_replicate_payload(
                bundle,
                cell_index=cell_index,
                replicate_index=replicate_index,
            ),
            flat_index,
        )
    health_events = [
        event for event in events if event["event_type"] == "HEALTH_AGGREGATE_COMPLETE"
    ]
    if health_events:
        health_body = _health_aggregate_payload(bundle, events)
        if health_body != health_events[0]["payload"]:
            raise AcceptedWorkloadContractError("temporal_resume_health_rewrite")
    else:
        health_body = _health_aggregate_payload(bundle, events)
        yield append("HEALTH_AGGREGATE_COMPLETE", health_body)
    if health_body["repair_required"]:
        terminal = _terminal_payload(
            bundle=bundle,
            events=events,
            raw=_complete_grid_health_terminal(bundle, health_body),
        )
        yield append("TERMINAL_OUTCOME", terminal)
        return

    health_envelope = m4_v2_build_artifact_envelope(
        artifact_type="M4V2TemporalMarginalIncrementHealthAggregateArtifact",
        body=health_body,
        parent_digests=(
            bundle["source_contract_artifact_digest"],
            bundle["preregistration_artifact_digest"],
            bundle["ordered_parent_decision_artifact_digests"][0],
            bundle["ordered_parent_replay_artifact_digests"][0],
        ),
    )
    state = _TemporalStrictPriorState(bundle)
    warmup_rows: list[dict[str, Any]] = []
    evaluation_rows: list[dict[str, Any]] = []
    capsule_rows: list[dict[str, Any]] = []
    for _ in range(899):
        numeric = state.advance()
        capsule_row, support = _probability_capsule_row(numeric)
        capsule_rows.append(capsule_row)
        warmup_rows.append(support)
    prefix_fold_events = [
        event for event in events if event["event_type"] == "HISTORICAL_FOLD_COMMIT"
    ]
    fold_payloads: list[dict[str, Any]] = []
    for offset, ordinal in enumerate(range(901, 3482)):
        numeric = state.advance()
        capsule_row, support = _probability_capsule_row(numeric)
        capsule_rows.append(capsule_row)
        evaluation_rows.append(support)
        payload, _ = _historical_fold_payload(bundle, numeric=numeric)
        if offset < len(prefix_fold_events):
            if payload != prefix_fold_events[offset]["payload"]:
                raise AcceptedWorkloadContractError("temporal_resume_event_rewrite")
        else:
            yield append("HISTORICAL_FOLD_COMMIT", payload, ordinal - 901)
        fold_payloads.append(payload)
    warmup_rule = build_transition_local_warmup_rule()
    warmup_index = build_temporal_warmup_index(
        warmup_rows, rule_digest=warmup_rule["rule_digest"]
    )
    evaluation_index = build_accepted_temporal_evaluation_index(evaluation_rows)
    composite_view = build_temporal_composite_view(
        warmup_index_digest=warmup_index["warmup_index_digest"],
        accepted_temporal_evaluation_index_digest=evaluation_index[
            "accepted_temporal_evaluation_index_digest"
        ],
    )
    capsule_index = build_probability_capsule_index(
        producer_source_contract_digest=bundle["source_contract_artifact_digest"],
        numeric_runtime_contract_digest=NUMERIC_RUNTIME_CONTRACT_DIGEST,
        rows=capsule_rows,
    )
    scores = [
        float.fromhex(item["score_row_body"]["paired_score_float_hex"])
        for item in fold_payloads
    ]
    sensitivity_summaries: list[dict[str, Any]] = []
    sensitivity_owners: list[dict[str, Any]] = []
    prefix_sensitivity = [
        event
        for event in events
        if event["event_type"] == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT"
    ]
    for scheme_index, scheme_id in enumerate(REGISTERED_HISTORICAL_SCHEME_IDS):
        summary, owner = build_historical_sensitivity_summary(
            scores,
            branch_id=TEMPORAL_BRANCH_ID,
            root_seed_full_sha256=bundle["historical_root_seed_full_sha256"],
            scheme_index=scheme_index,
            scheme_id=scheme_id,
        )
        sensitivity_summaries.append(summary)
        sensitivity_owners.append(owner)
        if scheme_index < len(prefix_sensitivity):
            if summary != prefix_sensitivity[scheme_index]["payload"]:
                raise AcceptedWorkloadContractError("temporal_resume_event_rewrite")
        else:
            yield append(
                "HISTORICAL_SENSITIVITY_SCHEME_COMMIT",
                summary,
                scheme_index,
            )
    historical_body = _historical_aggregate_payload(
        bundle,
        health_artifact_digest=health_envelope["artifact_digest"],
        fold_payloads=fold_payloads,
        sensitivity_summaries=sensitivity_summaries,
        sensitivity_owners=sensitivity_owners,
        warmup_index_digest=warmup_index["warmup_index_digest"],
        evaluation_index_digest=evaluation_index[
            "accepted_temporal_evaluation_index_digest"
        ],
        composite_view_digest=composite_view["composite_view_digest"],
    )
    aggregate_events = [
        event
        for event in events
        if event["event_type"] == "HISTORICAL_AGGREGATE_COMPLETE"
    ]
    if aggregate_events:
        if historical_body != aggregate_events[0]["payload"]:
            raise AcceptedWorkloadContractError("temporal_resume_event_rewrite")
    else:
        yield append("HISTORICAL_AGGREGATE_COMPLETE", historical_body)
    terminal = _terminal_payload(
        bundle=bundle,
        events=events,
        raw=_evaluated_terminal(
            bundle,
            health_body=health_body,
            historical_body=historical_body,
            warmup_index=warmup_index,
            evaluation_index=evaluation_index,
            composite_view=composite_view,
            capsule_index=capsule_index,
        ),
    )
    yield append("TERMINAL_OUTCOME", terminal)


def _terminal_payload(
    *,
    bundle: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or "preterminal_transcript_digest" in raw:
        raise AcceptedWorkloadContractError("temporal_terminal_input_invalid")
    payload = dict(raw)
    payload["preterminal_transcript_digest"] = preterminal_transcript_digest(
        branch_id=TEMPORAL_BRANCH_ID,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=bundle["producer_execution_id"],
        execution_subpath=payload["execution_subpath"],
        decision_path=payload["decision_path"],
        ordered_preterminal_event_digests=[event["event_digest"] for event in events],
    )
    return payload


def iter_temporal_marginal_increment_accepted_parent_events(
    input_bundle: Mapping[str, Any],
    *,
    resume_index: Mapping[str, Any] | None = None,
) -> Iterator[Mapping[str, Any]]:
    bundle = validate_input_bundle(input_bundle, branch_id=TEMPORAL_BRANCH_ID)
    _validate_accepted_parent(bundle)
    fold_coordinates, schemes = validate_registered_computation_inputs(
        bundle, branch_id=TEMPORAL_BRANCH_ID
    )
    prefix = resume_events(
        branch_id=TEMPORAL_BRANCH_ID,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=bundle["producer_execution_id"],
        resume_index=resume_index,
    )
    owner_prefix: list[Mapping[str, Any]] = []
    for event in prefix:
        validate_event_owner_equalities(
            event,
            bundle=bundle,
            prefix=owner_prefix,
            fold_coordinates=fold_coordinates,
            sensitivity_scheme_ids=schemes,
        )
        owner_prefix.append(event)
    terminal = prefix[-1] if prefix and prefix[-1]["event_type"] == "TERMINAL_OUTCOME" else None
    if terminal is not None:
        # Every durable terminal is already reconstructed by the closed
        # seven-subpath owner validator above.  A completed stream has no next
        # event; replaying the science path would incorrectly collapse valid
        # failure terminals into the healthy continuation.
        return
    reconstructable_terminal = False
    computational_prefix = (
        prefix[:-1]
        if reconstructable_terminal
        else prefix
    )
    generated_terminal_count = 0
    for event in _iter_events(bundle, prefix=computational_prefix):
        if terminal is not None:
            generated_terminal_count += 1
            if event != terminal:
                raise AcceptedWorkloadContractError("temporal_resume_terminal_rewrite")
            continue
        validate_event_owner_equalities(
            event,
            bundle=bundle,
            prefix=owner_prefix,
            fold_coordinates=fold_coordinates,
            sensitivity_scheme_ids=schemes,
        )
        owner_prefix.append(event)
        yield event
    if reconstructable_terminal and generated_terminal_count != 1:
        raise AcceptedWorkloadContractError("temporal_resume_terminal_missing")


__all__ = ["iter_temporal_marginal_increment_accepted_parent_events"]
