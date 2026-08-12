from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator, Mapping, Sequence
from statistics import NormalDist
from typing import Any

from dehps.research_os.models import (
    m4_v2_build_artifact_envelope,
    m4_v2_domain_digest,
)

from .branch_decision import (
    validate_marginal_static_branch_decision,
    validate_marginal_static_branch_decision_replay,
)
from .joint_residual_increment import (
    JOINT_BASELINE_ID,
    JOINT_ESTIMATOR_ID,
    JOINT_MODEL_ID,
    MARGINAL_RAW_P_ARTIFACT_DIGEST,
    build_certificate_coordinate_identity,
    build_joint_eta_checkpoint,
    build_joint_synthetic_sequence_coordinate,
    build_joint_target_prediction_checkpoint,
    build_joint_target_prediction_index,
    build_joint_z_checkpoint_index,
    build_q_base_checkpoint,
    build_q_base_checkpoint_index,
    build_q_base_reconstruction_certificate,
    validate_joint_z_checkpoint,
    validate_normalization_certificate,
    validate_target_q_j_marginal_preservation_certificate,
)
from .m4_v2_increment_execution_support import (
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
    generate_registered_synthetic_sequence,
    historical_resample_owner_data,
    neumaier_mean,
    score_joint_residual_sequence,
    synthetic_cells,
)
from .m4_v2_legal_fixed_cardinality import (
    legal_states,
    project_registered_is4_feature,
    registered_is4_residual_value,
    solve_affine_residual_eta,
)
from .temporal_marginal_increment import validate_temporal_branch_replay
from .temporal_probability_capsule import validate_sealed_probability_capsule_index

JOINT_BRANCH_ID = "JOINT_RESIDUAL_INCREMENT"

_TOLERANCE_HEX = (1e-12).hex()


def _digest(value: Mapping[str, Any], *, domain: str) -> str:
    return m4_v2_domain_digest(value, domain=domain)


def _temporal_composite_view_digest(bundle: Mapping[str, Any]) -> str:
    body = bundle["resolved_inputs"]["accepted_support_model_envelope"]["body"]
    value = body.get("composite_view_digest")
    if not isinstance(value, str):
        raise AcceptedWorkloadContractError("joint_temporal_composite_view_missing")
    return value


def _validate_accepted_parents_and_capsule(bundle: Mapping[str, Any]) -> None:
    resolved = bundle["resolved_inputs"]
    decisions = resolved["ordered_parent_decision_envelopes"]
    replays = resolved["ordered_parent_replay_envelopes"]
    if len(decisions) != 2 or len(replays) != 2:
        raise AcceptedWorkloadContractError("joint_parent_cardinality_invalid")
    try:
        marginal_decision = validate_marginal_static_branch_decision(
            decisions[0]
        ).to_dict()
        marginal_replay = validate_marginal_static_branch_decision_replay(
            replays[0], decision=marginal_decision
        ).to_dict()
        temporal_replay = validate_temporal_branch_replay(replays[1])
    except ValueError as exc:
        raise AcceptedWorkloadContractError("joint_parent_identity_invalid") from exc
    validated_decisions = (marginal_decision, decisions[1])
    validated_replays = (marginal_replay, temporal_replay)
    if any(
        decision["artifact_digest"] != expected
        or decision["body"]["accepted_for_downstream_baseline"] is not True
        for decision, expected in zip(
            validated_decisions,
            bundle["ordered_parent_decision_artifact_digests"],
            strict=True,
        )
    ) or any(
        replay["artifact_digest"] != expected
        or replay["body"]["workload_rerun"] is not False
        or replay["body"]["replay_status"] != "REGISTERED_REPLAY_VERIFIED"
        for replay, expected in zip(
            validated_replays,
            bundle["ordered_parent_replay_artifact_digests"],
            strict=True,
        )
    ) or any(
        replay["body"]["decision_artifact_digest"] != decision["artifact_digest"]
        for replay, decision in zip(
            validated_replays, validated_decisions, strict=True
        )
    ):
        raise AcceptedWorkloadContractError("joint_parent_acceptance_invalid")
    support = resolved["accepted_support_model_envelope"]
    if support.get("schema_version") != (
        "dehps-m4-v2-temporal-marginal-increment-candidate-model.v3"
    ) or support["artifact_digest"] != decisions[-1]["body"].get(
        "accepted_model_artifact_digest"
    ):
        raise AcceptedWorkloadContractError("joint_temporal_candidate_v3_required")
    body = support.get("body")
    if not isinstance(body, Mapping):
        raise AcceptedWorkloadContractError("joint_temporal_candidate_body_missing")
    capsule = validate_sealed_probability_capsule_index(
        body.get("probability_capsule_index", {})
    )
    if (
        body.get("probability_capsule_index_digest") != capsule["index_digest"]
        or body.get("probability_capsule_evaluator_contract_digest")
        != capsule["evaluator_contract_digest"]
        or body.get("source_contract_digest")
        != capsule["producer_source_contract_digest"]
    ):
        raise AcceptedWorkloadContractError("joint_temporal_capsule_identity_mismatch")


def _started_payload(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "input_bundle_digest": bundle["input_bundle_digest"],
        "producer_task_key": producer_task_key(JOINT_BRANCH_ID),
        "producer_execution_id": bundle["producer_execution_id"],
        "branch_id": JOINT_BRANCH_ID,
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


def _lexicographic_rank(state: Sequence[int]) -> int:
    rank = 0
    previous = -1
    for position, selected in enumerate(state):
        remaining = 5 - position
        for candidate in range(previous + 1, selected):
            rank += math.comb(32 - candidate, remaining)
        previous = selected
    return rank


def _history_state(draw: Sequence[int]) -> int:
    zero_based = tuple(label - 1 for label in draw)
    return -1 if _lexicographic_rank(zero_based) < math.comb(33, 6) // 2 else 1


class _Neumaier:
    def __init__(self) -> None:
        self.total = 0.0
        self.correction = 0.0

    def add(self, value: float) -> None:
        updated = self.total + value
        if abs(self.total) >= abs(value):
            self.correction += (self.total - updated) + value
        else:
            self.correction += (value - updated) + self.total
        self.total = updated

    def value(self) -> float:
        return self.total + self.correction


def _evaluate_q_j_distribution(
    *,
    row: Mapping[str, Any],
    projection: Any,
    eta: float,
) -> dict[str, Any]:
    """Serialize Q_J in the registered canonical legal-state byte order."""

    weights = [
        float.fromhex(value)
        for value in row[
            "candidate_weight_float_hex_in_ball_order_1_through_33"
        ]
    ]
    partition = float.fromhex(row["partition_float_hex"])
    if not math.isfinite(partition) or partition <= 0.0:
        raise AcceptedWorkloadContractError("joint_q_base_partition_invalid")
    domain = "dehps.m4.v2.legal-joint-probability-content.v1"
    digest = hashlib.sha256()
    digest.update(domain.encode())
    digest.update(b"\0")
    digest.update(
        b'{"legal_space_id":"LEGAL_SIX_OF_33_COMBINATIONS",'
        b'"legal_state_order_id":"INCREASING_LEXICOGRAPHIC_SIX_LABEL_TUPLE",'
        b'"probabilities_float_hex_in_canonical_1107568_state_order":['
    )
    total = _Neumaier()
    marginals = [_Neumaier() for _ in range(33)]
    base_marginals = [_Neumaier() for _ in range(33)]
    minimum = math.inf
    count = 0
    for state in legal_states():
        base_probability = math.prod(weights[index] for index in state) / partition
        z_value = registered_is4_residual_value(projection, state)
        probability = base_probability * (1.0 + eta * z_value)
        if not math.isfinite(probability) or probability <= 0.0:
            raise AcceptedWorkloadContractError("joint_q_j_probability_invalid")
        if count:
            digest.update(b",")
        digest.update(json.dumps(probability.hex()).encode())
        total.add(probability)
        minimum = min(minimum, probability)
        for index in state:
            marginals[index].add(probability)
            base_marginals[index].add(base_probability)
        count += 1
    digest.update(b"]}")
    if count != math.comb(33, 6):
        raise AcceptedWorkloadContractError("joint_q_j_legal_state_count_invalid")
    marginal_hex = [accumulator.value().hex() for accumulator in marginals]
    base_marginal_hex = [
        accumulator.value().hex() for accumulator in base_marginals
    ]
    return {
        "full_distribution_content_digest": digest.hexdigest(),
        "marginal_float_hex": marginal_hex,
        "marginal_content_digest": _digest(
            {"probabilities_float_hex_in_ball_order_1_through_33": marginal_hex},
            domain="dehps.m4.v2.marginal-vector.v1",
        ),
        "base_marginal_float_hex": base_marginal_hex,
        "sum_probability": total.value(),
        "minimum_probability": minimum,
    }


class _JointHistoricalState:
    """Persistent strict-prior sufficient state for one generator invocation."""

    def __init__(self, bundle: Mapping[str, Any]) -> None:
        self.bundle = bundle
        resolved = bundle["resolved_inputs"]
        self.records = resolved["dataset_snapshot_envelope"]["body"][
            "history_snapshot"
        ]["records"]
        self.folds = resolved["fold_manifest_envelope"]["body"]["folds"]
        self.capsule_rows = resolved["accepted_support_model_envelope"]["body"][
            "probability_capsule_index"
        ]["rows"]
        if len(self.records) != 3481 or len(self.capsule_rows) != 3480:
            raise AcceptedWorkloadContractError("joint_registered_support_count_invalid")
        self.preregistration = resolved["preregistration_envelope"]["body"]
        self.temporal_composite_view_digest = _temporal_composite_view_digest(bundle)
        self.q_base_rows: list[dict[str, Any]] = []
        self.z_rows: list[dict[str, Any]] = []
        self.z_values: list[float] = []
        self.eta_rows: list[dict[str, Any]] = []
        self.prediction_rows: list[dict[str, Any]] = []
        self.score_values: list[float] = []
        self.score_row_digests: list[str] = []
        self.next_ordinal = 2

    def _support_row(self, ordinal: int) -> Mapping[str, Any]:
        row = self.capsule_rows[ordinal - 2]
        if row.get("transition_ordinal") != ordinal:
            raise AcceptedWorkloadContractError("joint_capsule_ordinal_mismatch")
        return row

    def _q_base(self, ordinal: int, row: Mapping[str, Any]) -> dict[str, Any]:
        reconstruction = build_q_base_reconstruction_certificate(
            transition_ordinal=ordinal,
            temporal_support_row_digest=row["temporal_support_row_digest"],
            q_t_full_distribution_content_digest=row[
                "q_t_full_distribution_content_digest"
            ],
            q_base_full_distribution_content_digest=row[
                "q_t_full_distribution_content_digest"
            ],
            max_probability_difference_float_hex="0x0.0p+0",
            max_marginal_difference_float_hex="0x0.0p+0",
            normalization_residual_float_hex="0x0.0p+0",
        )
        return build_q_base_checkpoint(
            transition_ordinal=ordinal,
            issue=row["issue"],
            temporal_support_row_digest=row["temporal_support_row_digest"],
            temporal_composite_view_digest=self.temporal_composite_view_digest,
            q_t_marginal_content_digest=row["q_t_marginal_content_digest"],
            q_t_full_distribution_content_digest=row[
                "q_t_full_distribution_content_digest"
            ],
            baseline_contract_digest=self.preregistration["baseline_contract_digest"],
            reconstruction_certificate=reconstruction,
        )

    def _z_checkpoint(
        self,
        *,
        ordinal: int,
        q_base: Mapping[str, Any],
        row: Mapping[str, Any],
        projection: Any,
    ) -> dict[str, Any]:
        coefficients = [value.hex() for value in projection.label_coefficients]
        raw_feature_digest = _digest(
            {
                "feature_id": "SIGNED_IS4_BY_LEXICOGRAPHIC_HISTORY_HALF",
                "history_state": projection.history_state,
            },
            domain="dehps.m4.v2.joint-residual.raw-feature-content.v2",
        )
        coordinate_owner = {
            "source_contract_digest": self.bundle["source_contract_artifact_digest"],
            "preregistration_artifact_digest": self.bundle[
                "preregistration_artifact_digest"
            ],
            "producer_execution_id": self.bundle["producer_execution_id"],
            "transition_ordinal": ordinal,
            "issue": row["issue"],
        }
        orthogonality_digest = _digest(
            {
                **coordinate_owner,
                "q_base_full_distribution_content_digest": q_base[
                    "q_base_full_distribution_content_digest"
                ],
                "raw_feature_content_digest": raw_feature_digest,
                "projection_coefficients_float_hex": coefficients,
                "normalization_residual_float_hex": (
                    projection.normalization_residual.hex()
                ),
                "singleton_residuals_float_hex": [
                    value.hex() for value in projection.singleton_residuals
                ],
            },
            domain="dehps.m4.v2.joint-residual.orthogonality-owner.v2",
        )
        neutrality_digest = _digest(
            {
                **coordinate_owner,
                "q_base_full_distribution_content_digest": q_base[
                    "q_base_full_distribution_content_digest"
                ],
                "scale_B_float_hex": projection.scale.hex(),
                "singleton_residuals_float_hex": [
                    value.hex() for value in projection.singleton_residuals
                ],
            },
            domain="dehps.m4.v2.joint-residual.z-neutrality-owner.v2",
        )
        z_identity = {
            "q_base_full_distribution_content_digest": q_base[
                "q_base_full_distribution_content_digest"
            ],
            "history_state": projection.history_state,
            "raw_feature_content_digest": raw_feature_digest,
            "projection_coefficients_float_hex": coefficients,
            "scale_B_float_hex": projection.scale.hex(),
            "orthogonality_certificate_digest": orthogonality_digest,
            "marginal_preservation_certificate_digest": neutrality_digest,
        }
        previous = [item["checkpoint_digest"] for item in self.z_rows]
        checkpoint = {
            "source_contract_digest": self.bundle["source_contract_artifact_digest"],
            "preregistration_artifact_digest": self.bundle[
                "preregistration_artifact_digest"
            ],
            "producer_execution_id": self.bundle["producer_execution_id"],
            "joint_estimator_id": JOINT_ESTIMATOR_ID,
            "temporal_composite_view_digest": self.temporal_composite_view_digest,
            "transition_ordinal": ordinal,
            "issue": row["issue"],
            "support_kind": q_base["support_kind"],
            "creation_phase": (
                "PRE_T901_SUPPORT" if ordinal <= 900 else "TARGET_PRE_REVEAL"
            ),
            "creation_target_ordinal": 901 if ordinal <= 900 else ordinal,
            "prefix_last_ordinal": ordinal - 1,
            "prefix_outcome_chain_digest": row["weight_derivation_certificate"][
                "prefix_outcome_chain_digest"
            ],
            "q_base_checkpoint_digest": q_base["checkpoint_digest"],
            **z_identity,
            "z_function_identity_digest": _digest(
                z_identity,
                domain="dehps.m4.v2.joint-residual.z-function-content.v2",
            ),
            "checkpoint_key_digest": _digest(
                {
                    "source_contract_digest": self.bundle[
                        "source_contract_artifact_digest"
                    ],
                    "preregistration_artifact_digest": self.bundle[
                        "preregistration_artifact_digest"
                    ],
                    "producer_execution_id": self.bundle["producer_execution_id"],
                    "transition_ordinal": ordinal,
                },
                domain="dehps.m4.v2.joint-residual.z-checkpoint-key.v2",
            ),
            "previous_z_chain_digest": _digest(
                {"ordered_checkpoint_digests": previous},
                domain="dehps.m4.v2.joint-residual.z-checkpoint-chain.v2",
            ),
        }
        checkpoint["checkpoint_digest"] = _digest(
            checkpoint, domain="dehps.m4.v2.joint-residual.z-checkpoint.v2"
        )
        return validate_joint_z_checkpoint(
            checkpoint, previous_z_checkpoint_digests=previous
        )

    def advance(self, ordinal: int) -> dict[str, Any] | None:
        if ordinal != self.next_ordinal:
            raise AcceptedWorkloadContractError("joint_historical_state_order_invalid")
        row = self._support_row(ordinal)
        record = self.records[ordinal - 1]
        if record["issue"] != row["issue"]:
            raise AcceptedWorkloadContractError("joint_capsule_issue_owner_mismatch")
        weights = [
            float.fromhex(value)
            for value in row[
                "candidate_weight_float_hex_in_ball_order_1_through_33"
            ]
        ]
        projection = project_registered_is4_feature(
            weights,
            history_state=_history_state(
                self.records[ordinal - 2]["red_numbers"]
            ),
        )
        q_base = self._q_base(ordinal, row)
        z_checkpoint = self._z_checkpoint(
            ordinal=ordinal, q_base=q_base, row=row, projection=projection
        )
        actual_z = registered_is4_residual_value(
            projection, [label - 1 for label in record["red_numbers"]]
        )
        fold_payload: dict[str, Any] | None = None
        if ordinal >= 901:
            try:
                eta_solution = solve_affine_residual_eta(self.z_values)
            except ValueError as exc:
                raise AcceptedWorkloadContractError("joint_eta_fit_failed") from exc
            prior_z_digests = [item["checkpoint_digest"] for item in self.z_rows]
            eta = build_joint_eta_checkpoint(
                target_ordinal=ordinal,
                issue=record["issue"],
                ordered_prior_z_checkpoint_digests=prior_z_digests,
                settled_training_outcome_prefix_digest=row[
                    "weight_derivation_certificate"
                ]["prefix_outcome_chain_digest"],
                eta_float_hex=eta_solution.eta.hex(),
                solver_terminal_code="REGISTERED_SCORE_ROOT_CONVERGED",
            )
            q_j = _evaluate_q_j_distribution(
                row=row, projection=projection, eta=eta_solution.eta
            )
            if _digest(
                {
                    "probabilities_float_hex_in_ball_order_1_through_33": q_j[
                        "base_marginal_float_hex"
                    ]
                },
                domain="dehps.m4.v2.marginal-vector.v1",
            ) != q_base["q_base_marginal_content_digest"]:
                raise AcceptedWorkloadContractError(
                    "joint_q_base_rehydrated_marginal_digest_mismatch"
                )
            base_marginals = [
                float.fromhex(value) for value in q_j["base_marginal_float_hex"]
            ]
            candidate_marginals = [
                float.fromhex(value) for value in q_j["marginal_float_hex"]
            ]
            residuals = [
                candidate - base
                for candidate, base in zip(
                    candidate_marginals, base_marginals, strict=True
                )
            ]
            maximum_residual = max(abs(value) for value in residuals)
            coordinate = build_certificate_coordinate_identity(
                scope="HISTORICAL_TARGET_Q_J",
                source_contract_digest=self.bundle[
                    "source_contract_artifact_digest"
                ],
                preregistration_artifact_digest=self.bundle[
                    "preregistration_artifact_digest"
                ],
                producer_execution_id=self.bundle["producer_execution_id"],
                transition_ordinal=ordinal,
                issue_or_sequence_coordinate_digest=record["issue"],
                support_kind=q_base["support_kind"],
            )
            normalization = {
                "coordinate_identity_digest": coordinate["coordinate_digest"],
                "full_distribution_content_digest": q_j[
                    "full_distribution_content_digest"
                ],
                "sum_probability_float_hex": q_j["sum_probability"].hex(),
                "normalization_residual_float_hex": abs(
                    q_j["sum_probability"] - 1.0
                ).hex(),
                "minimum_probability_float_hex": q_j[
                    "minimum_probability"
                ].hex(),
                "finite_nonnegative": True,
                "tolerance_float_hex": _TOLERANCE_HEX,
                "certificate_pass": (
                    abs(q_j["sum_probability"] - 1.0) <= 1e-12
                ),
            }
            normalization["certificate_digest"] = _digest(
                normalization,
                domain="dehps.m4.v2.joint-residual.normalization-certificate.v2",
            )
            normalization = validate_normalization_certificate(normalization)
            marginal = {
                "coordinate_identity_digest": coordinate["coordinate_digest"],
                "reference_marginal_content_digest": q_base[
                    "q_base_marginal_content_digest"
                ],
                "candidate_full_distribution_content_digest": q_j[
                    "full_distribution_content_digest"
                ],
                "derived_candidate_marginal_content_digest": q_j[
                    "marginal_content_digest"
                ],
                "per_ball_residuals_float_hex_in_ball_order_1_through_33": [
                    value.hex() for value in residuals
                ],
                "max_abs_residual_float_hex": maximum_residual.hex(),
                "tolerance_float_hex": _TOLERANCE_HEX,
                "certificate_pass": maximum_residual <= 1e-12,
            }
            marginal["certificate_digest"] = _digest(
                marginal,
                domain=(
                    "dehps.m4.v2.joint-residual."
                    "marginal-preservation-certificate.v2"
                ),
            )
            marginal = validate_target_q_j_marginal_preservation_certificate(
                marginal
            )
            prediction = build_joint_target_prediction_checkpoint(
                eta_checkpoint=eta,
                target_z_checkpoint=z_checkpoint,
                q_base_checkpoint=q_base,
                q_j_marginal_content_digest=q_j["marginal_content_digest"],
                q_j_full_distribution_content_digest=q_j[
                    "full_distribution_content_digest"
                ],
                certificate_coordinate_identity=coordinate,
                normalization_certificate=normalization,
                marginal_preservation_certificate=marginal,
            )
            factor = 1.0 + eta_solution.eta * actual_z
            if not math.isfinite(factor) or factor <= 0.0:
                raise AcceptedWorkloadContractError("joint_target_factor_invalid")
            score = math.log2(factor)
            settled = historical_settled_outcome_digest(
                evaluation_ordinal=ordinal,
                issue=record["issue"],
                red_numbers=record["red_numbers"],
            )
            score_row = {
                "evaluation_ordinal": ordinal,
                "issue": record["issue"],
                "prediction_checkpoint_digest": prediction["checkpoint_digest"],
                "settled_outcome_digest": settled,
                "paired_score_float_hex": score.hex(),
            }
            score_row["score_row_digest"] = _digest(
                score_row,
                domain="dehps.m4.v2.joint.historical-score-row.v2",
            )
            fold = self.folds[ordinal - 901]
            fold_payload = {
                "evaluation_ordinal": ordinal,
                "issue": record["issue"],
                "fold_digest": fold["fold_digest"],
                "prediction_checkpoint_body": prediction,
                "prediction_checkpoint_digest": prediction["checkpoint_digest"],
                "score_row_body": score_row,
                "score_row_digest": score_row["score_row_digest"],
            }
            fold_payload["fold_commit_digest"] = _digest(
                fold_payload,
                domain=(
                    "dehps.m4.v2.joint."
                    "accepted-workload-historical-fold-commit.v1"
                ),
            )
            self.eta_rows.append(eta)
            self.prediction_rows.append(prediction)
            self.score_values.append(score)
            self.score_row_digests.append(score_row["score_row_digest"])
        self.q_base_rows.append(q_base)
        self.z_rows.append(z_checkpoint)
        self.z_values.append(actual_z)
        self.next_ordinal += 1
        return fold_payload

    def initialize_warmup(self) -> None:
        while self.next_ordinal <= 900:
            if self.advance(self.next_ordinal) is not None:
                raise AcceptedWorkloadContractError("joint_warmup_emitted_fold")


def _coordinate(event_type: str, payload: Mapping[str, Any], index: int) -> dict[str, Any]:
    if event_type == "WORKLOAD_STARTED":
        return {"phase": "HEALTH_PRE_DRAW_VALIDATION"}
    if event_type == "HEALTH_REPLICATE_COMMIT":
        return {"cell_index": index // 512, "replicate_index": index % 512}
    if event_type == "HEALTH_AGGREGATE_COMPLETE":
        return {"phase": "HEALTH_AGGREGATE"}
    if event_type == "HISTORICAL_FOLD_COMMIT":
        return {"evaluation_ordinal": payload["evaluation_ordinal"], "issue": payload["issue"]}
    if event_type == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT":
        return {"scheme_index": index, "scheme_id": payload["scheme_id"]}
    if event_type == "HISTORICAL_AGGREGATE_COMPLETE":
        return {"phase": "HISTORICAL_AGGREGATE"}
    return {
        "phase": "TERMINAL_OUTCOME", "execution_subpath": payload["execution_subpath"],
        "decision_path": payload["decision_path"],
    }


def _terminal_payload(
    *, bundle: Mapping[str, Any], events: Sequence[Mapping[str, Any]], raw: Mapping[str, Any]
) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or "preterminal_transcript_digest" in raw:
        raise AcceptedWorkloadContractError("joint_terminal_input_invalid")
    payload = dict(raw)
    payload["preterminal_transcript_digest"] = preterminal_transcript_digest(
        branch_id=JOINT_BRANCH_ID, input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=bundle["producer_execution_id"],
        execution_subpath=payload["execution_subpath"], decision_path=payload["decision_path"],
        ordered_preterminal_event_digests=[event["event_digest"] for event in events],
    )
    return payload


def _health_replicate_payload(
    bundle: Mapping[str, Any], *, cell_index: int, replicate_index: int
) -> dict[str, Any]:
    preregistration = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
    coordinate = build_joint_synthetic_sequence_coordinate(
        health_contract_digest=preregistration["health_contract_digest"],
        seed_contract_digest=preregistration["seed_contract_digest"],
        cell_index=cell_index,
        replicate_index=replicate_index,
    )
    generated = generate_registered_synthetic_sequence(
        branch_id=JOINT_BRANCH_ID,
        root_seed_full_sha256=bundle["synthetic_root_seed_full_sha256"],
        cell_index=cell_index,
        replicate_index=replicate_index,
    )
    if generated.sequence_seed_full_sha256 != coordinate["sequence_seed_full_sha256"]:
        raise AcceptedWorkloadContractError("joint_health_sequence_seed_owner_mismatch")
    scored = score_joint_residual_sequence(
        generated.draws,
        evaluation_issue_count=generated.cell.evaluation_issue_count,
    )
    payload, _ = build_synthetic_health_replicate_evidence(
        scored.score_values,
        branch_id=JOINT_BRANCH_ID,
        root_seed_full_sha256=bundle["synthetic_root_seed_full_sha256"],
        cell_index=cell_index,
        cell_id=generated.cell.cell_id,
        fixture_id=generated.cell.fixture_id,
        horizon_id=generated.cell.horizon_id,
        replicate_index=replicate_index,
        sequence_coordinate_digest=coordinate["coordinate_digest"],
        prediction_checkpoint_chain_digest=(
            scored.prediction_checkpoint_chain_digest
        ),
        score_row_chain_digest=scored.score_row_chain_digest,
        analytic_truth_bits_per_issue=(
            generated.cell.analytic_target_bits_per_issue
        ),
    )
    return payload


def _health_aggregate_payload(
    bundle: Mapping[str, Any], events: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    replicates = [
        event["payload"]
        for event in events
        if event["event_type"] == "HEALTH_REPLICATE_COMMIT"
    ]
    if len(replicates) != 7168:
        raise AcceptedWorkloadContractError("joint_health_grid_incomplete")
    cells = synthetic_cells(JOINT_BRANCH_ID)
    summaries = [
        build_synthetic_health_cell_summary(
            replicates[index * 512 : (index + 1) * 512],
            branch_id=JOINT_BRANCH_ID,
            cell=cells[index],
        )
        for index in range(14)
    ]
    failed = [
        summary["cell_id"]
        for summary in summaries
        if summary["threshold_pass"] is False
    ]
    preregistration = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
    return {
        "status": "COMPLETE",
        "measurement_contract_key": preregistration["measurement_contract_key"],
        "measurement_contract_digest": preregistration[
            "measurement_contract_digest"
        ],
        "branch_id": JOINT_BRANCH_ID,
        "estimand_digest": preregistration["estimand_digest"],
        "decision_path": (
            "IDENTITY_VALID_HEALTH_REPAIR" if failed else "EVALUATED_COMPLETE"
        ),
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "preregistration_artifact_digest": bundle[
            "preregistration_artifact_digest"
        ],
        "marginal_decision_digest": bundle[
            "ordered_parent_decision_artifact_digests"
        ][0],
        "marginal_replay_digest": bundle[
            "ordered_parent_replay_artifact_digests"
        ][0],
        "temporal_decision_digest": bundle[
            "ordered_parent_decision_artifact_digests"
        ][1],
        "temporal_replay_digest": bundle[
            "ordered_parent_replay_artifact_digests"
        ][1],
        "transition_local_warmup_rule_digest": preregistration[
            "transition_local_warmup_rule_digest"
        ],
        "synthetic_warmup_application_or_null": None,
        "synthetic_warmup_application_digest_or_null": None,
        "warmup_alias_position_count": 6_444_032,
        "cell_summaries": summaries,
        "cell_summary_chain_digest": _digest(
            {
                "ordered_cell_summary_digests": [
                    summary["cell_summary_digest"] for summary in summaries
                ]
            },
            domain="dehps.m4.v2.joint.health-cell-summary-chain.v2",
        ),
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


def _artifact(
    *, artifact_type: str, body: Mapping[str, Any], parents: Sequence[str]
) -> dict[str, Any]:
    return m4_v2_build_artifact_envelope(
        artifact_type=artifact_type,
        body=body,
        parent_digests=tuple(parents),
    )


def _baseline_body(
    bundle: Mapping[str, Any], state: _JointHistoricalState
) -> dict[str, Any]:
    preregistration = state.preregistration
    q_base_index = build_q_base_checkpoint_index(state.q_base_rows)
    return {
        "status": "COMPLETE",
        "measurement_contract_key": preregistration["measurement_contract_key"],
        "measurement_contract_digest": preregistration[
            "measurement_contract_digest"
        ],
        "branch_id": JOINT_BRANCH_ID,
        "estimand_digest": preregistration["estimand_digest"],
        "baseline_id": JOINT_BASELINE_ID,
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "dataset_content_digest": bundle["dataset_content_digest"],
        "fold_manifest_digest": bundle["fold_manifest_artifact_digest"],
        "temporal_parent_candidate_artifact_digest": bundle[
            "accepted_support_model_artifact_digest"
        ],
        "temporal_composite_view_digest": state.temporal_composite_view_digest,
        "q_base_checkpoint_index": q_base_index,
        "q_base_checkpoint_index_digest": q_base_index["index_digest"],
        "same_distribution_as_temporal_parent": True,
        "distinct_artifact_from_temporal_parent": True,
        "historical_support_count": 3480,
        "historical_fold_count": 2581,
        "production_action": "none",
    }


def _parent_raw_p_values(bundle: Mapping[str, Any]) -> tuple[float, float]:
    rows = bundle["resolved_inputs"]["ordered_holm_lineage_envelopes"]
    if len(rows) != 2:
        raise AcceptedWorkloadContractError("joint_holm_parent_cardinality_invalid")
    values: list[float] = []
    for row in rows:
        body = row.get("body") if isinstance(row, Mapping) else None
        value = body.get("raw_primary_p_value") if isinstance(body, Mapping) else None
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not 0.0 <= float(value) <= 1.0
        ):
            raise AcceptedWorkloadContractError("joint_holm_parent_raw_p_missing")
        values.append(float(value))
    return values[0], values[1]


def _holm_adjusted(
    marginal: float, temporal: float, joint: float
) -> float:
    tie_order = {
        "MARGINAL_STATIC": 0,
        "TEMPORAL_MARGINAL_INCREMENT": 1,
        JOINT_BRANCH_ID: 2,
    }
    ordered = sorted(
        (
            (marginal, "MARGINAL_STATIC"),
            (temporal, "TEMPORAL_MARGINAL_INCREMENT"),
            (joint, JOINT_BRANCH_ID),
        ),
        key=lambda item: (item[0], tie_order[item[1]]),
    )
    running = 0.0
    adjusted: dict[str, float] = {}
    for index, (value, branch_id) in enumerate(ordered):
        running = max(running, min(1.0, (3 - index) * value))
        adjusted[branch_id] = running
    return adjusted[JOINT_BRANCH_ID]


def _historical_aggregate_body(
    bundle: Mapping[str, Any],
    *,
    state: _JointHistoricalState,
    health_body: Mapping[str, Any],
    sensitivity_summaries: Sequence[Mapping[str, Any]],
    joint_raw_p_value: float,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    preregistration = state.preregistration
    baseline_body = _baseline_body(bundle, state)
    baseline = _artifact(
        artifact_type="M4V2JointResidualMaximumEntropyBaselineArtifact",
        body=baseline_body,
        parents=(
            bundle["source_contract_artifact_digest"],
            bundle["preregistration_artifact_digest"],
            bundle["accepted_support_model_artifact_digest"],
        ),
    )
    parent_pairs = [
        digest
        for pair in zip(
            bundle["ordered_parent_decision_artifact_digests"],
            bundle["ordered_parent_replay_artifact_digests"],
            strict=True,
        )
        for digest in pair
    ]
    health = _artifact(
        artifact_type="M4V2JointResidualMeasurementHealthArtifact",
        body=health_body,
        parents=(
            bundle["source_contract_artifact_digest"],
            bundle["preregistration_artifact_digest"],
            *parent_pairs,
            baseline["artifact_digest"],
        ),
    )
    marginal_raw_p, temporal_raw_p = _parent_raw_p_values(bundle)
    primary = sensitivity_summaries[0]
    scores = state.score_values
    midpoint = 1291
    first_half = neumaier_mean(scores[:midpoint])
    second_half = neumaier_mean(scores[midpoint:])
    standard_error = float(primary["bootstrap_standard_error"])
    branch_alpha = 0.05 / 3.0
    mde = max(
        0.0,
        (
            NormalDist().inv_cdf(1.0 - branch_alpha)
            + NormalDist().inv_cdf(0.8)
        )
        * standard_error,
    )
    equivalence_margin = float(
        primary["equivalence_upper_bound_bits_per_issue"]
    )
    power = NormalDist().cdf(
        0.01 / standard_error - NormalDist().inv_cdf(1.0 - branch_alpha)
    )
    checkpoint_chain = _digest(
        {
            "ordered_checkpoint_digests": [
                row["checkpoint_digest"] for row in state.prediction_rows
            ]
        },
        domain="dehps.m4.v2.joint.historical-checkpoint-chain.v2",
    )
    score_chain = _digest(
        {
            "ordered_score_row_digests": [
                event_digest
                for event_digest in getattr(state, "score_row_digests", [])
            ]
        },
        domain="dehps.m4.v2.joint.historical-score-sequence.v2",
    )
    if len(getattr(state, "score_row_digests", [])) != 2581:
        raise AcceptedWorkloadContractError("joint_score_digest_state_incomplete")
    target_index = build_joint_target_prediction_index(
        eta_rows=state.eta_rows, prediction_rows=state.prediction_rows
    )
    z_index = build_joint_z_checkpoint_index(state.z_rows)
    q_base_index = baseline_body["q_base_checkpoint_index"]
    historical_body = {
        "status": "COMPLETE",
        "measurement_contract_key": preregistration["measurement_contract_key"],
        "measurement_contract_digest": preregistration[
            "measurement_contract_digest"
        ],
        "branch_id": JOINT_BRANCH_ID,
        "estimand_digest": preregistration["estimand_digest"],
        "decision_path": "EVALUATED_COMPLETE",
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "preregistration_artifact_digest": bundle[
            "preregistration_artifact_digest"
        ],
        "health_artifact_digest": health["artifact_digest"],
        "marginal_raw_p_artifact_digest": MARGINAL_RAW_P_ARTIFACT_DIGEST,
        "temporal_raw_p_artifact_digest": bundle[
            "resolved_inputs"
        ]["ordered_holm_lineage_envelopes"][1]["artifact_digest"],
        "dataset_content_digest": bundle["dataset_content_digest"],
        "fold_manifest_digest": bundle["fold_manifest_artifact_digest"],
        "checkpoint_chain_digest": checkpoint_chain,
        "score_sequence_digest": score_chain,
        "score_count": 2581,
        "observed_mean_bits_per_issue": neumaier_mean(scores),
        "raw_primary_p_value": joint_raw_p_value,
        "holm_family_raw_p_values": {
            "MARGINAL_STATIC": marginal_raw_p,
            "TEMPORAL_MARGINAL_INCREMENT": temporal_raw_p,
            JOINT_BRANCH_ID: joint_raw_p_value,
        },
        "holm_adjusted_p_value": _holm_adjusted(
            marginal_raw_p, temporal_raw_p, joint_raw_p_value
        ),
        "simultaneous_effect_interval_bits_per_issue": {
            "lower_float_hex": float(
                primary["effect_interval_bits_per_issue"][0]
            ).hex(),
            "upper_float_hex": float(
                primary["effect_interval_bits_per_issue"][1]
            ).hex(),
        },
        "equivalence_upper_bound_bits_per_issue": equivalence_margin,
        "bootstrap_standard_error": standard_error,
        "mde_bits_per_issue": mde,
        "equivalence_power_at_zero": power,
        "equivalence_power_sufficient": power >= 0.8,
        "half_means_bits_per_issue": {
            "first_half_float_hex": first_half.hex(),
            "second_half_float_hex": second_half.hex(),
        },
        "positive_stability_pass": first_half > 0.0 and second_half > 0.0,
        "sensitivity_summaries": [dict(item) for item in sensitivity_summaries],
        "historical_child_count": 16_000,
        "temporal_composite_view_digest": state.temporal_composite_view_digest,
        "q_base_checkpoint_index_digest": q_base_index["index_digest"],
        "joint_z_checkpoint_index_digest": z_index["index_digest"],
        "joint_eta_checkpoint_chain_digest": target_index["eta_chain_digest"],
        "joint_target_prediction_index_digest": target_index["index_digest"],
        "production_action": "none",
    }
    return baseline, health, historical_body


def _evaluated_terminal(
    bundle: Mapping[str, Any],
    *,
    state: _JointHistoricalState,
    health_body: Mapping[str, Any],
    historical_body: Mapping[str, Any],
    baseline: Mapping[str, Any],
    health: Mapping[str, Any],
) -> dict[str, Any]:
    historical = _artifact(
        artifact_type="M4V2JointResidualHistoricalExecutionArtifact",
        body=historical_body,
        parents=(
            bundle["source_contract_artifact_digest"],
            bundle["preregistration_artifact_digest"],
            baseline["artifact_digest"],
            health["artifact_digest"],
            historical_body["marginal_raw_p_artifact_digest"],
            historical_body["temporal_raw_p_artifact_digest"],
        ),
    )
    z_index = build_joint_z_checkpoint_index(state.z_rows)
    target_index = build_joint_target_prediction_index(
        eta_rows=state.eta_rows, prediction_rows=state.prediction_rows
    )
    candidate_body = {
        "status": "COMPLETE",
        "measurement_contract_key": state.preregistration[
            "measurement_contract_key"
        ],
        "measurement_contract_digest": state.preregistration[
            "measurement_contract_digest"
        ],
        "branch_id": JOINT_BRANCH_ID,
        "estimand_digest": state.preregistration["estimand_digest"],
        "model_id": JOINT_MODEL_ID,
        "joint_estimator_id": JOINT_ESTIMATOR_ID,
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "dataset_content_digest": bundle["dataset_content_digest"],
        "fold_manifest_digest": bundle["fold_manifest_artifact_digest"],
        "joint_baseline_artifact_digest": baseline["artifact_digest"],
        "temporal_parent_candidate_artifact_digest": bundle[
            "accepted_support_model_artifact_digest"
        ],
        "temporal_composite_view_digest": state.temporal_composite_view_digest,
        "q_base_checkpoint_index_digest": historical_body[
            "q_base_checkpoint_index_digest"
        ],
        "joint_z_checkpoint_index": z_index,
        "joint_z_checkpoint_index_digest": z_index["index_digest"],
        "joint_target_prediction_index": target_index,
        "joint_target_prediction_index_digest": target_index["index_digest"],
        "fitted_parameter_chain_digest": target_index["eta_chain_digest"],
        "orthogonality_certificate_chain_digest": _digest(
            {
                "ordered_certificate_digests": [
                    row["orthogonality_certificate_digest"]
                    for row in state.z_rows
                ]
            },
            domain="dehps.m4.v2.joint-residual.orthogonality-certificate-chain.v2",
        ),
        "marginal_preservation_certificate_chain_digest": _digest(
            {
                "ordered_certificate_digests": [
                    row["marginal_preservation_certificate_digest"]
                    for row in state.z_rows
                ]
            },
            domain=(
                "dehps.m4.v2.joint-residual."
                "marginal-preservation-certificate-chain.v2"
            ),
        ),
        "historical_fold_count": 2581,
        "production_action": "none",
    }
    candidate = _artifact(
        artifact_type="M4V2JointResidualCandidateModelArtifact",
        body=candidate_body,
        parents=(
            bundle["source_contract_artifact_digest"],
            historical["artifact_digest"],
            baseline["artifact_digest"],
            bundle["accepted_support_model_artifact_digest"],
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
        and float(historical_body["equivalence_upper_bound_bits_per_issue"])
        <= 0.01
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
        "baseline_artifact_body_or_null": baseline["body"],
        "health_artifact_body_or_null": dict(health_body),
        "historical_artifact_body_or_null": dict(historical_body),
        "candidate_artifact_body_or_null": candidate_body,
        "failure_artifact_body_or_null": None,
        "expected_baseline_artifact_digest_or_null": baseline["artifact_digest"],
        "expected_health_artifact_digest_or_null": health["artifact_digest"],
        "expected_historical_artifact_digest_or_null": historical[
            "artifact_digest"
        ],
        "expected_candidate_artifact_digest_or_null": candidate["artifact_digest"],
        "expected_failure_artifact_digest_or_null": None,
        "completed_fold_count": 2581,
        "completed_resample_count": 16_000,
        "reason_codes": [],
        "planned_counts": dict(state.preregistration["planned_counts"]),
    }


def _health_repair_terminal(
    bundle: Mapping[str, Any], *, health_body: Mapping[str, Any]
) -> dict[str, Any]:
    parent_pairs = [
        digest
        for pair in zip(
            bundle["ordered_parent_decision_artifact_digests"],
            bundle["ordered_parent_replay_artifact_digests"],
            strict=True,
        )
        for digest in pair
    ]
    health = _artifact(
        artifact_type="M4V2JointResidualMeasurementHealthArtifact",
        body=health_body,
        parents=(
            bundle["source_contract_artifact_digest"],
            bundle["preregistration_artifact_digest"],
            *parent_pairs,
        ),
    )
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
        "reason_codes": sorted(
            f"HEALTH_CELL_FAILED:{cell_id}"
            for cell_id in health_body["failed_cell_ids"]
        ),
        "planned_counts": dict(
            bundle["resolved_inputs"]["preregistration_envelope"]["body"][
                "planned_counts"
            ]
        ),
    }


def _pre_draw_terminal(bundle: Mapping[str, Any]) -> dict[str, Any] | None:
    records = bundle["resolved_inputs"]["dataset_snapshot_envelope"]["body"][
        "history_snapshot"
    ]["records"]
    issues: set[str] = set()
    reason_codes: list[str] = []
    for record in records:
        issue = record.get("issue")
        draw = record.get("red_numbers")
        if not isinstance(issue, str) or issue in issues:
            reason_codes.append("REGISTERED_DATASET_ISSUE_IDENTITY_INVALID")
            break
        issues.add(issue)
        if (
            not isinstance(draw, list)
            or len(draw) != 6
            or any(type(value) is not int or not 1 <= value <= 33 for value in draw)
            or draw != sorted(set(draw))
        ):
            reason_codes.append("REGISTERED_DATASET_LEGAL_STATE_INVALID")
            break
    if not reason_codes:
        return None
    preregistration = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
    failure_body = {
        "status": "COMPLETE",
        "measurement_contract_key": preregistration["measurement_contract_key"],
        "measurement_contract_digest": preregistration["measurement_contract_digest"],
        "branch_id": JOINT_BRANCH_ID,
        "estimand_digest": preregistration["estimand_digest"],
        "decision_path": "IDENTITY_VALID_HEALTH_REPAIR",
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "preregistration_artifact_digest": bundle["preregistration_artifact_digest"],
        "failure_stage": "HEALTH",
        "failure_code": reason_codes[0],
        "repairable": True,
        "scientific_execution_started": True,
        "historical_started": False,
        "message_digest": event_payload_digest(
            branch_id=JOINT_BRANCH_ID,
            event_type="WORKLOAD_STARTED",
            payload={"structured_diagnostic_codes_in_order": reason_codes},
        ),
        "partial_evidence_created": False,
        "completed_fold_count": 0,
        "completed_resample_count": 0,
        "production_action": "none",
    }
    failure = m4_v2_build_artifact_envelope(
        artifact_type="M4V2JointResidualScientificFailureArtifact",
        schema_version="dehps-m4-v2-joint-residual-scientific-failure.v3",
        body=failure_body,
        parent_digests=(
            bundle["source_contract_artifact_digest"],
            bundle["preregistration_artifact_digest"],
        ),
    )
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
        "failure_artifact_body_or_null": failure_body,
        "expected_baseline_artifact_digest_or_null": None,
        "expected_health_artifact_digest_or_null": None,
        "expected_historical_artifact_digest_or_null": None,
        "expected_candidate_artifact_digest_or_null": None,
        "expected_failure_artifact_digest_or_null": failure["artifact_digest"],
        "completed_fold_count": 0,
        "completed_resample_count": 0,
        "reason_codes": reason_codes,
        "planned_counts": dict(preregistration["planned_counts"]),
    }


def _iter_events(
    bundle: Mapping[str, Any], *, prefix: Sequence[Mapping[str, Any]]
) -> Iterator[dict[str, Any]]:
    """Continue one event stream without regenerating its verified prefix."""

    events: list[dict[str, Any]] = [dict(event) for event in prefix]

    def append(event_type: str, payload: Mapping[str, Any], coordinate_index: int = 0) -> dict[str, Any]:
        event = build_event(
            branch_id=JOINT_BRANCH_ID, input_bundle_digest=bundle["input_bundle_digest"],
            producer_execution_id=bundle["producer_execution_id"], event_index=len(events),
            event_type=event_type, coordinate_key=_coordinate(event_type, payload, coordinate_index),
            payload_schema=event_payload_schema(branch_id=JOINT_BRANCH_ID, event_type=event_type),
            payload=payload,
            payload_digest=event_payload_digest(
                branch_id=JOINT_BRANCH_ID, event_type=event_type, payload=payload
            ),
            previous_event_digest_or_null=(events[-1]["event_digest"] if events else None),
        )
        events.append(event)
        return event

    if not events:
        yield append("WORKLOAD_STARTED", _started_payload(bundle))
    if events[-1]["event_type"] == "TERMINAL_OUTCOME":
        return
    early = _pre_draw_terminal(bundle)
    if early is not None:
        if len(events) != 1 or events[0]["event_type"] != "WORKLOAD_STARTED":
            raise AcceptedWorkloadContractError("joint_early_terminal_prefix_invalid")
        yield append(
            "TERMINAL_OUTCOME",
            _terminal_payload(bundle=bundle, events=events, raw=early),
        )
        return

    replicate_count = sum(
        event["event_type"] == "HEALTH_REPLICATE_COMMIT" for event in events
    )
    while replicate_count < 7168:
        payload = _health_replicate_payload(
            bundle,
            cell_index=replicate_count // 512,
            replicate_index=replicate_count % 512,
        )
        yield append("HEALTH_REPLICATE_COMMIT", payload, replicate_count)
        replicate_count += 1

    health_events = [
        event for event in events if event["event_type"] == "HEALTH_AGGREGATE_COMPLETE"
    ]
    if len(health_events) > 1:
        raise AcceptedWorkloadContractError("joint_health_aggregate_duplicate")
    if health_events:
        health_body = _health_aggregate_payload(bundle, events)
        if health_body != health_events[0]["payload"]:
            raise AcceptedWorkloadContractError("joint_resume_health_rewrite")
    else:
        health_body = _health_aggregate_payload(bundle, events)
        yield append("HEALTH_AGGREGATE_COMPLETE", health_body)
    if health_body["measurement_health"] != "PASS":
        raw = _health_repair_terminal(bundle, health_body=health_body)
        yield append(
            "TERMINAL_OUTCOME",
            _terminal_payload(bundle=bundle, events=events, raw=raw),
        )
        return

    state = _JointHistoricalState(bundle)
    state.initialize_warmup()
    prior_folds = [
        event for event in events if event["event_type"] == "HISTORICAL_FOLD_COMMIT"
    ]
    for event in prior_folds:
        ordinal = event["coordinate_key"]["evaluation_ordinal"]
        rebuilt = state.advance(ordinal)
        if rebuilt != event["payload"]:
            raise AcceptedWorkloadContractError("joint_resume_fold_rewrite")
    while state.next_ordinal <= 3481:
        payload = state.advance(state.next_ordinal)
        if payload is None:
            raise AcceptedWorkloadContractError("joint_target_fold_missing")
        yield append("HISTORICAL_FOLD_COMMIT", payload)

    scheme_events = [
        event
        for event in events
        if event["event_type"] == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT"
    ]
    scheme_ids = bundle["resolved_inputs"]["resampling_manifest_envelope"]["body"][
        "schemes"
    ]
    for scheme_index in range(len(scheme_events), 8):
        summary, _ = build_historical_sensitivity_summary(
            state.score_values,
            branch_id=JOINT_BRANCH_ID,
            root_seed_full_sha256=bundle["historical_root_seed_full_sha256"],
            scheme_index=scheme_index,
            scheme_id=scheme_ids[scheme_index],
        )
        yield append(
            "HISTORICAL_SENSITIVITY_SCHEME_COMMIT", summary, scheme_index
        )

    historical_events = [
        event
        for event in events
        if event["event_type"] == "HISTORICAL_AGGREGATE_COMPLETE"
    ]
    if len(historical_events) > 1:
        raise AcceptedWorkloadContractError("joint_historical_aggregate_duplicate")
    observed_mean = neumaier_mean(state.score_values)
    centered_null = [value - observed_mean + 0.01 for value in state.score_values]
    primary_null_owner = historical_resample_owner_data(
        centered_null,
        branch_id=JOINT_BRANCH_ID,
        root_seed_full_sha256=bundle["historical_root_seed_full_sha256"],
        scheme_index=0,
        scheme_id=scheme_ids[0],
    )
    primary_null_means = [
        float.fromhex(value)
        for value in primary_null_owner["ordered_child_mean_float_hex"]
    ]
    joint_raw_p = (
        1 + sum(value >= observed_mean for value in primary_null_means)
    ) / 2001
    if historical_events:
        historical_body = historical_events[0]["payload"]
        baseline, health, rebuilt = _historical_aggregate_body(
            bundle,
            state=state,
            health_body=health_body,
            sensitivity_summaries=[
                event["payload"]
                for event in events
                if event["event_type"]
                == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT"
            ],
            joint_raw_p_value=joint_raw_p,
        )
        if rebuilt != historical_body:
            raise AcceptedWorkloadContractError("joint_resume_historical_rewrite")
    else:
        summaries = [
            event["payload"]
            for event in events
            if event["event_type"] == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT"
        ]
        baseline, health, historical_body = _historical_aggregate_body(
            bundle,
            state=state,
            health_body=health_body,
            sensitivity_summaries=summaries,
            joint_raw_p_value=joint_raw_p,
        )
        yield append("HISTORICAL_AGGREGATE_COMPLETE", historical_body)

    raw_terminal = _evaluated_terminal(
        bundle,
        state=state,
        health_body=health_body,
        historical_body=historical_body,
        baseline=baseline,
        health=health,
    )
    yield append(
        "TERMINAL_OUTCOME",
        _terminal_payload(bundle=bundle, events=events, raw=raw_terminal),
    )


def iter_joint_residual_increment_accepted_parent_events(
    input_bundle: Mapping[str, Any], *, resume_index: Mapping[str, Any] | None = None,
) -> Iterator[Mapping[str, Any]]:
    bundle = validate_input_bundle(input_bundle, branch_id=JOINT_BRANCH_ID)
    _validate_accepted_parents_and_capsule(bundle)
    fold_coordinates, schemes = validate_registered_computation_inputs(
        bundle, branch_id=JOINT_BRANCH_ID
    )
    prefix = resume_events(
        branch_id=JOINT_BRANCH_ID, input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=bundle["producer_execution_id"], resume_index=resume_index,
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
        # The owner validator reconstructs all seven terminal unions.  A
        # terminal resume is complete and therefore has no successor event.
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
                raise AcceptedWorkloadContractError("joint_resume_terminal_rewrite")
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
        raise AcceptedWorkloadContractError("joint_resume_terminal_missing")


__all__ = ["iter_joint_residual_increment_accepted_parent_events"]
