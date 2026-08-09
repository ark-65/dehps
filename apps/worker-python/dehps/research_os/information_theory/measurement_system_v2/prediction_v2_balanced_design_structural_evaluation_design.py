from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY = (
    "prediction-v2-balanced-design-structural-evaluation-design"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_CAPABILITY = (
    "prediction_v2_balanced_design_structural_evaluation_design"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_COMPLETION_FACT = (
    "prediction-v2-balanced-design-structural-evaluation-design:COMPLETE"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY = (
    "prediction-v2-balanced-design-structural-evaluation-preregistration"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "prediction-v2-balanced-design-structural-evaluation-design-source-v1.json"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_APPROVED_EVENT = (
    "research-contract:prediction-v2-balanced-design-structural-evaluation-design:approved"
)

RESULT_DECISION_EXECUTION_DIGEST = (
    "6898d1723760fe0a44c36ec69512d0aeae30b00469a8049880eb9c82b9648e87"
)
RESULT_DECISION_DIGEST = (
    "3c3da2f43a1f99751f6f3ea3e5ee82e887a726020092164ac719aeaa4ae97637"
)
STRUCTURAL_EVALUATION_HANDOFF_DIGEST = (
    "0d411caa1c7782c51d3b2e7a972aeba245df54fd1b5eab00b8af98a808b609d7"
)
RESULT_DECISION_COMPLETION_DIGEST = (
    "ab72a5e8a663656fdf544de987016160c8fad815980568c3dbfc3bcdda955720"
)
FIXED_CERTIFICATE_DIGEST = (
    "b7a0069edef9f6a2aeec3f2205a50a63ba39594ed555c3c89b108830cd3c28db"
)
RESULT_DECISION_EXECUTION_ID = (
    "cfa11883aa13dc3f4752a167e167af3b60e40be77c38807ed7a491f0766099ce"
)

RESULT_DECISION = "CYCLIC_BALANCED_DESIGN_EXISTENCE_ESTABLISHED_STRUCTURAL_ONLY"
CONFIRMATORY_ENDPOINT = "triple_collision_mass"
PRIMARY_NULL = "Z33_ORBIT_PROFILE_MATCHED_WITHOUT_REPLACEMENT_5_FULL_1_SHORT_B176"
SECONDARY_NULL = "UNIFORM_PREFIX_WITHOUT_REPLACEMENT_FROM_ALL_1107568_LEGAL_BLOCKS_B176"
POSITIVE_OUTCOME = "HIGHER_ORDER_STRUCTURAL_HOLDOUT_ADVANTAGE_WITHIN_MATCHED_NULL_ONLY"
NULL_OUTCOME = "PAIR_BALANCE_ONLY_NO_PREREGISTERED_HIGHER_ORDER_ADVANTAGE"
REGRESSION_OUTCOME = "HIGHER_ORDER_STRUCTURAL_REGRESSION_AGAINST_MATCHED_NULL"
INVALID_OUTCOME = "INVALID_EVALUATION_NO_DECISION"
REPETITION_SCAN = "ABSENT_BY_CONSTRUCTION"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-balanced-design-structural-evaluation-design-"
    "round-101-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-balanced-design-structural-evaluation-design-"
    "round-101-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/"
    "prediction_v2_balanced_design_structural_evaluation_design.py"
)
FROZEN_CONTRACT_DIGEST = (
    "c8af0a8b287f42583d17b941826bf3246b68d448ff1d6649e52cc588fdcf70af"
)


class PredictionV2BalancedDesignStructuralEvaluationDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2BalancedDesignStructuralEvaluationDesignRun:
    design: Mapping[str, Any]
    preregistration_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.design, self.preregistration_handoff, self.completion


def load_prediction_v2_balanced_design_structural_evaluation_design_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2BalancedDesignStructuralEvaluationDesignError(
            f"balanced_design_structural_evaluation_design_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-balanced-design-structural-evaluation-design-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_balanced_design_structural_evaluation_design_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 429
        or payload.get("research_execution_id") != 350
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 430
        or payload.get("engineering_execution_id") != 351
        or payload.get("result_blind") is not True
        or payload.get("candidate_evaluation_statistics_read") is not False
        or payload.get("database_queries") != 0
        or payload.get("historical_rows_read") != 0
        or payload.get("null_replicates_executed") != 0
        or payload.get("folds_executed") != 0
        or payload.get("registered_children") != 3
        or payload.get("duplicate_or_repetition_scans") != 0
        or payload.get("new_evidence_created") is not False
        or payload.get("new_model_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("frozen_contract_digest") != FROZEN_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain=(
                "dehps.prediction-v2.balanced-design-structural-evaluation-design-"
                "frozen-contract.v1"
            ),
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.prediction-v2.balanced-design-structural-evaluation-design-"
                "source-set.v1"
            ),
        )
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationDesignError(
            "balanced_design_structural_evaluation_design_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationDesignError(
            "balanced_design_structural_evaluation_design_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_balanced_design_structural_evaluation_design_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    entry = contract["source_entries"][0]
    relative = str(entry["path"])
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise PredictionV2BalancedDesignStructuralEvaluationDesignError(
            f"balanced_design_structural_evaluation_design_source_missing:{relative}"
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
        raise PredictionV2BalancedDesignStructuralEvaluationDesignError(
            f"balanced_design_structural_evaluation_design_source_modified:{relative}"
        )


def build_prediction_v2_balanced_design_structural_evaluation_design_artifacts(
    *,
    source_contract: Mapping[str, Any],
    result_decision_execution: Mapping[str, Any],
    result_decision: Mapping[str, Any],
    structural_evaluation_handoff: Mapping[str, Any],
    result_decision_completion: Mapping[str, Any],
    result_decision_replay: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2BalancedDesignStructuralEvaluationDesignRun:
    frozen = source_contract["frozen_contract"]
    _validate_frozen_contract(frozen)
    _validate_parent_artifacts(
        result_decision_execution=result_decision_execution,
        result_decision=result_decision,
        structural_evaluation_handoff=structural_evaluation_handoff,
        result_decision_completion=result_decision_completion,
        result_decision_replay=result_decision_replay,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(result_decision_execution["artifact_digest"]),
        str(result_decision["artifact_digest"]),
        str(structural_evaluation_handoff["artifact_digest"]),
        str(result_decision_completion["artifact_digest"]),
    )
    design = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-design.v1"
        ),
        artifact_type="prediction_v2_balanced_design_structural_evaluation_design",
        body={
            "status": "COMPLETE",
            "fixed_candidate": frozen["fixed_candidate"],
            "legal_universe": frozen["legal_universe"],
            "construction_validity_only": frozen["construction_validity_only"],
            "confirmatory_endpoint": frozen["confirmatory_endpoint"],
            "metric_formulas": frozen["metric_formulas"],
            "secondary_descriptive_metrics": frozen[
                "secondary_descriptive_metrics"
            ],
            "scalar_weighted_score_allowed": False,
            "null_baselines": frozen["null_baselines"],
            "inference_boundary": frozen["inference_boundary"],
            "outcome_semantics": frozen["outcome_semantics"],
            "candidate_evaluation_statistics_read": False,
            "null_replicates_executed": 0,
            "legal_blocks_enumerated": 0,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "duplicate_or_repetition_scans": 0,
            "repetition_scan": REPETITION_SCAN,
            "separate_duplicate_membership_or_uniqueness_scan": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "evidence_created": False,
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-design.v1"
        ),
    )
    handoff = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-"
            "preregistration-handoff.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_evaluation_preregistration_handoff"
        ),
        body={
            "status": "COMPLETE",
            "design_artifact_digest": design["artifact_digest"],
            "fixed_certificate_artifact_digest": FIXED_CERTIFICATE_DIGEST,
            "confirmatory_endpoint": CONFIRMATORY_ENDPOINT,
            "primary_null": PRIMARY_NULL,
            "secondary_null": SECONDARY_NULL,
            "primary_null_may_be_replaced_by_secondary": False,
            "deferred_to_preregistration": frozen["deferred_to_preregistration"],
            "evaluation_execution_authorized": False,
            "candidate_evaluation_statistics_read": False,
            "null_replicates_executed": 0,
            "duplicate_or_repetition_scans": 0,
            "repetition_scan": REPETITION_SCAN,
            "historical_outcomes_allowed": False,
            "prediction_probability_claim": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "evidence_created": False,
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(*parent_digests, str(design["artifact_digest"])),
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-"
            "preregistration-handoff.v1"
        ),
    )
    completion = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-design-"
            "completion.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_evaluation_design_completion"
        ),
        body={
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_COMPLETION_FACT
            ),
            "source_contract_digest": source_digest,
            "result_decision_execution_digest": result_decision_execution[
                "artifact_digest"
            ],
            "design_artifact_digest": design["artifact_digest"],
            "preregistration_handoff_digest": handoff["artifact_digest"],
            "registered_child_count": 3,
            "candidate_evaluation_statistics_read": False,
            "null_replicates_executed": 0,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "duplicate_or_repetition_scans": 0,
            "repetition_scan": REPETITION_SCAN,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "evidence_created": False,
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(design["artifact_digest"]),
            str(handoff["artifact_digest"]),
        ),
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-design-"
            "completion.v1"
        ),
    )
    return PredictionV2BalancedDesignStructuralEvaluationDesignRun(
        design=design,
        preregistration_handoff=handoff,
        completion=completion,
    )


def replay_prediction_v2_balanced_design_structural_evaluation_design(
    **kwargs: Any,
) -> tuple[PredictionV2BalancedDesignStructuralEvaluationDesignRun, dict[str, Any]]:
    run = build_prediction_v2_balanced_design_structural_evaluation_design_artifacts(
        **kwargs
    )
    return run, {
        "schema_version": (
            "dehps-prediction-v2-balanced-design-structural-evaluation-design-"
            "replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "workload_rerun": False,
        "candidate_evaluation_statistics_read": False,
        "null_replicates_executed": 0,
        "database_queries_during_replay": 0,
        "historical_rows_read": 0,
        "folds_replayed": 0,
        "duplicate_or_repetition_scans": 0,
        "manual_input_assembly": False,
        "repetition_scan": REPETITION_SCAN,
        "next_consumer": (
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY
        ),
    }


def _validate_parent_artifacts(
    *,
    result_decision_execution: Mapping[str, Any],
    result_decision: Mapping[str, Any],
    structural_evaluation_handoff: Mapping[str, Any],
    result_decision_completion: Mapping[str, Any],
    result_decision_replay: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts_and_domains = (
        (result_decision_execution, "dehps.research-os.mainline-execution.v1"),
        (
            result_decision,
            "dehps.prediction-v2.balanced-design-result-decision.v1",
        ),
        (
            structural_evaluation_handoff,
            "dehps.prediction-v2.balanced-design-structural-evaluation-design-handoff.v1",
        ),
        (
            result_decision_completion,
            "dehps.prediction-v2.balanced-design-result-decision-completion.v1",
        ),
    )
    for artifact, domain in artifacts_and_domains:
        _verify_artifact(artifact, domain=domain)
    observed = tuple(
        str(artifact.get("artifact_digest")) for artifact, _ in artifacts_and_domains
    )
    if require_registered_identities and observed != (
        RESULT_DECISION_EXECUTION_DIGEST,
        RESULT_DECISION_DIGEST,
        STRUCTURAL_EVALUATION_HANDOFF_DIGEST,
        RESULT_DECISION_COMPLETION_DIGEST,
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationDesignError(
            "balanced_design_structural_evaluation_design_registered_identity_changed"
        )
    if (
        result_decision_execution.get("execution_id") != RESULT_DECISION_EXECUTION_ID
        or result_decision_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or result_decision_execution.get("decision") != RESULT_DECISION
        or result_decision_execution.get("certificate_artifact_digest")
        != FIXED_CERTIFICATE_DIGEST
        or result_decision_execution.get("certificate_verified") is not True
        or result_decision_execution.get("decision_usefulness_established") is not False
        or result_decision_execution.get("structural_evaluation_handoff_digest")
        != structural_evaluation_handoff.get("artifact_digest")
        or result_decision_execution.get("result_decision_digest")
        != result_decision.get("artifact_digest")
        or result_decision_execution.get("result_decision_completion_digest")
        != result_decision_completion.get("artifact_digest")
        or result_decision.get("decision") != RESULT_DECISION
        or result_decision.get("certificate_artifact_digest")
        != FIXED_CERTIFICATE_DIGEST
        or result_decision.get("certificate_verified") is not True
        or result_decision.get("decision_usefulness_established") is not False
        or structural_evaluation_handoff.get("fixed_certificate_artifact_digest")
        != FIXED_CERTIFICATE_DIGEST
        or structural_evaluation_handoff.get("fixed_before_evaluation") is not True
        or structural_evaluation_handoff.get("evaluation_execution_authorized")
        is not False
        or result_decision_completion.get("completion_fact")
        != "prediction-v2-balanced-design-feasibility-result-decision:COMPLETE"
        or result_decision_completion.get("decision_artifact_digest")
        != result_decision.get("artifact_digest")
        or result_decision_completion.get("structural_evaluation_handoff_digest")
        != structural_evaluation_handoff.get("artifact_digest")
        or result_decision_replay.get("status") != "REPLAY_VERIFIED"
        or result_decision_replay.get("same_registered_content") is not True
        or result_decision_replay.get("workload_rerun") is not False
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationDesignError(
            "balanced_design_structural_evaluation_design_parent_consistency_invalid"
        )
    if any(
        artifact.get("production_action") != "none"
        or artifact.get("historical_evidence") != "INCONCLUSIVE"
        or artifact.get("prediction_v2_mode") != "SHADOW_ONLY"
        or artifact.get("prediction_v2_route") != "BASELINE_ONLY"
        or artifact.get("new_model_created") is not False
        or artifact.get("promotion_gate_opened") is not False
        or artifact.get("p3_authorized") is not False
        for artifact in (
            result_decision_execution,
            result_decision,
            structural_evaluation_handoff,
            result_decision_completion,
        )
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationDesignError(
            "balanced_design_structural_evaluation_design_parent_claim_boundary_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if dict(frozen) != _expected_frozen_contract():
        raise PredictionV2BalancedDesignStructuralEvaluationDesignError(
            "balanced_design_structural_evaluation_design_frozen_contract_changed"
        )


def _expected_frozen_contract() -> dict[str, Any]:
    return {
        "task_key": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY,
        "capability": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_CAPABILITY,
        "completion_fact": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_COMPLETION_FACT,
        "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY,
        "registered_input_digests": [
            RESULT_DECISION_EXECUTION_DIGEST,
            RESULT_DECISION_DIGEST,
            STRUCTURAL_EVALUATION_HANDOFF_DIGEST,
            RESULT_DECISION_COMPLETION_DIGEST,
        ],
        "legal_universe": {
            "domain": "SSQ_RED_BALL_SIX_OF_33",
            "number_domain": "integers_1_through_33",
            "combination_cardinality": 6,
            "universe_cardinality": 1_107_568,
            "universe_formula": "C(33,6)",
            "pre_draw_probability": "equal_for_every_legal_combination",
        },
        "fixed_candidate": {
            "certificate_artifact_digest": FIXED_CERTIFICATE_DIGEST,
            "block_count": 176,
            "point_count": 33,
            "block_size": 6,
            "point_replication": 32,
            "pair_replication": 5,
            "full_orbit_count": 5,
            "short_orbit_count": 1,
            "fixed_before_evaluation": True,
            "automatic_portfolio_mutation": False,
        },
        "construction_validity_only": [
            "all_33_point_replications_equal_32",
            "all_528_pair_replications_equal_5",
            "singleton_concentration_excess_equals_zero",
            "pair_concentration_excess_equals_zero",
        ],
        "confirmatory_endpoint": CONFIRMATORY_ENDPOINT,
        "metric_formulas": {
            "triple_replication": "c_T=count_of_candidate_blocks_containing_triple_T",
            "triple_collision_mass": "sum_over_T_in_C(33,3)_of_C(c_T,2)",
            "triple_collision_block_pair_identity": (
                "sum_over_unordered_distinct_blocks_A_B_of_C(|A_intersection_B|,3)"
            ),
            "quadruple_collision_mass": "sum_over_Q_in_C(33,4)_of_C(c_Q,2)",
            "quintuple_collision_mass": "sum_over_Q_in_C(33,5)_of_C(c_Q,2)",
            "replacement_distance": "6-|A_intersection_B|",
        },
        "secondary_descriptive_metrics": [
            "quadruple_collision_mass",
            "quintuple_collision_mass",
            "block_intersection_histogram_0_through_5",
            "maximum_block_intersection",
            "minimum_replacement_distance",
        ],
        "null_baselines": {
            "primary": {
                "type": PRIMARY_NULL,
                "candidate_budget": 176,
                "full_orbit_inventory_count": 33_561,
                "short_orbit_inventory_count": 5,
                "selected_distinct_full_orbits": 5,
                "selected_distinct_short_orbits": 1,
                "expanded_full_blocks": 165,
                "expanded_short_blocks": 11,
                "same_point_replication_by_profile": 32,
                "selection": "uniform_without_replacement_from_each_frozen_orbit_partition",
                "metric_based_rejection_allowed": False,
                "adaptive_reroll_allowed": False,
                "uniqueness_guarantee": "disjoint_orbits_by_partition_construction",
                "duplicate_validation_pass": False,
            },
            "secondary": {
                "type": SECONDARY_NULL,
                "candidate_budget": 176,
                "selection": (
                    "first_176_ids_of_one_seeded_permutation_or_equivalent_"
                    "order_statistic_sample"
                ),
                "metric_based_rejection_allowed": False,
                "adaptive_reroll_allowed": False,
                "uniqueness_guarantee": "without_replacement_construction",
                "duplicate_validation_pass": False,
            },
            "primary_null_may_be_replaced_by_secondary": False,
        },
        "inference_boundary": {
            "primary_direction": "lower_triple_collision_mass_is_better",
            "primary_inference": (
                "one_sided_plus_one_empirical_tail_against_profile_matched_null"
            ),
            "primary_endpoint_count": 1,
            "secondary_metrics_gate_success": False,
            "same_execution_retuning_allowed": False,
            "partial_timeout_acceptance_allowed": False,
        },
        "deferred_to_preregistration": [
            "replicate_counts",
            "deterministic_seed_domains",
            "exact_orbit_expansion",
            "alpha",
            "tolerances",
            "compute_limits",
            "invalid_execution_rules",
            "quantitative_outcome_thresholds",
        ],
        "outcome_semantics": {
            "positive": POSITIVE_OUTCOME,
            "null": NULL_OUTCOME,
            "regression": REGRESSION_OUTCOME,
            "invalid": INVALID_OUTCOME,
        },
        "registered_child_count": 3,
        "registered_total_with_mainline_execution": 4,
        "candidate_evaluation_statistics_read": False,
        "null_replicates_executed": 0,
        "database_queries": 0,
        "historical_rows_read": 0,
        "folds_executed": 0,
        "duplicate_or_repetition_scans": 0,
        "repetition_scan": REPETITION_SCAN,
        "separate_duplicate_membership_or_uniqueness_scan": False,
        "scalar_weighted_score_allowed": False,
        "historical_evidence": "INCONCLUSIVE",
        "prediction_v2_mode": "SHADOW_ONLY",
        "prediction_v2_route": "BASELINE_ONLY",
        "new_evidence_created": False,
        "new_model_created": False,
        "promotion_gate_opened": False,
        "p3_authorized": False,
        "production_action": "none",
    }


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(body),
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _verify_artifact(artifact: Mapping[str, Any], *, domain: str) -> None:
    identity = dict(artifact)
    observed = identity.pop("artifact_digest", None)
    if observed != canonical_digest(identity, domain=domain):
        raise PredictionV2BalancedDesignStructuralEvaluationDesignError(
            "balanced_design_structural_evaluation_design_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
