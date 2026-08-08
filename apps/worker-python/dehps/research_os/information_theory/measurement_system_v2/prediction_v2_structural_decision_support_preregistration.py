from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY = (
    "prediction-v2-structural-decision-support-preregistration"
)
PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_CAPABILITY = (
    "prediction_v2_structural_decision_support_preregistration"
)
PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_COMPLETION_FACT = (
    "prediction-v2-structural-decision-support-preregistration:COMPLETE"
)
PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "prediction-v2-structural-decision-support-preregistration-source-v1.json"
)
PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY = (
    "prediction-v2-structural-portfolio-execution"
)

PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY = (
    "prediction-v2-structural-decision-support-design"
)
PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT = (
    "prediction-v2-structural-decision-support-design:COMPLETE"
)
STRUCTURAL_DESIGN_EXECUTION_DIGEST = (
    "2c01404124ac1dd680ca5be7f846a982d739738ca13623b79dbc326df1cc3668"
)
STRUCTURAL_DESIGN_CONTRACT_DIGEST = (
    "37d638b1b69adb1f50cd7820ed1b284b6a1cb0b2b73413d6048fff5236049334"
)
STRUCTURAL_PREREGISTRATION_HANDOFF_DIGEST = (
    "2f7e884d160c5453b45669d129498fe403202f481f64c885c8921723c1b06117"
)
STRUCTURAL_DESIGN_COMPLETION_DIGEST = (
    "329a8d86fd083a3dcf33f1bbd480d5f6893f1be65aa228965e59cecbc02e68a9"
)

NUMBER_DOMAIN_SIZE = 33
COMBINATION_CARDINALITY = 6
LEGAL_UNIVERSE_CARDINALITY = 1_107_568
PAIR_UNIVERSE_CARDINALITY = 528
SINGLETONS_PER_BLOCK = 6
PAIRS_PER_BLOCK = 15
PRIMARY_CANDIDATE_BUDGET = 176
TARGET_SINGLETON_COUNT = 32
TARGET_PAIR_COUNT = 5
OPTIMIZER_NAME = "DETERMINISTIC_PARETO_PREFIX_EXCHANGE_V1"
OPTIMIZER_ISLAND_COUNT = 22
PROPOSALS_PER_ISLAND = 262_144
TOTAL_OPTIMIZER_PROPOSALS = 5_767_168
OPTIMIZER_ROOT_SEED_HEX = (
    "124aed827e6f68471da3733717919b9956be3c2e4ed256b11cf7ed2c8ed9b9d2"
)
NULL_ROOT_SEED_HEX = "ce969021ed72f5638d2b4534bd9c70af44854a6eb95973e5d7115a92f7a454ac"
NULL_REPLICATE_COUNT = 4_096
MINIMUM_STRICTLY_DOMINATED_NULLS = 3_893
MAXIMUM_NULLS_DOMINATING_CANDIDATE = 0
REQUIRED_MINIMUM_REPLACEMENT_DISTANCE = 2
PHASE_WALL_CLOCK_LIMIT_SECONDS = 7_200
RESIDENT_MEMORY_LIMIT_BYTES = 2_147_483_648
REFERENCE_PREFLIGHT_PROPOSALS = 1_024
NULL_BASELINE = "UNIFORM_WITHOUT_REPLACEMENT_PORTFOLIO_FROM_LEGAL_UNIVERSE"
OPTIMIZATION_GEOMETRY = "PARETO_VECTOR_WITHOUT_SCALAR_WEIGHTS"
SELECTED_PROGRAM = "STRUCTURAL_DECISION_SUPPORT_PIVOT"
PREDICTION_RESEARCH_DISPOSITION = "FROZEN_PENDING_STRUCTURAL_PORTFOLIO_EXECUTION"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-structural-preregistration-round-64-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-structural-preregistration-round-64-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/"
    "prediction_v2_structural_decision_support_preregistration.py"
)
FROZEN_CONTRACT_DIGEST = (
    "175f8134c70a6cdea99ccdccb07464f9d1a84bf356306a79d4b34d41b89d1c87"
)


class PredictionV2StructuralPreregistrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2StructuralPreregistrationRun:
    preregistration: Mapping[str, Any]
    execution_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.preregistration, self.execution_handoff, self.completion


def load_prediction_v2_structural_preregistration_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2StructuralPreregistrationError(
            f"prediction_v2_structural_preregistration_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-structural-preregistration-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_structural_decision_support_preregistration_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 388
        or payload.get("research_execution_id") != 309
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 389
        or payload.get("engineering_execution_id") != 310
        or payload.get("result_blind") is not True
        or payload.get("historical_rows_read") != 0
        or payload.get("folds_executed") != 0
        or payload.get("bootstrap_children_executed") != 0
        or payload.get("candidate_portfolios_generated") != 0
        or payload.get("optimizer_proposals_executed") != 0
        or payload.get("null_replicates_executed") != 0
        or payload.get("registered_children") != 3
        or payload.get("new_evidence_created") is not False
        or payload.get("new_model_created") is not False
        or payload.get("structural_algorithm_implemented") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("frozen_contract_digest") != FROZEN_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain="dehps.prediction-v2.structural-preregistration-frozen-contract.v1",
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.prediction-v2.structural-preregistration-source-set.v1",
        )
    ):
        raise PredictionV2StructuralPreregistrationError(
            "prediction_v2_structural_preregistration_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2StructuralPreregistrationError(
            "prediction_v2_structural_preregistration_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_structural_preregistration_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2StructuralPreregistrationError(
                f"prediction_v2_structural_preregistration_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2StructuralPreregistrationError(
                f"prediction_v2_structural_preregistration_source_modified:{relative}"
            )


def build_prediction_v2_structural_preregistration_artifacts(
    *,
    source_contract: Mapping[str, Any],
    design_execution: Mapping[str, Any],
    design_contract: Mapping[str, Any],
    design_handoff: Mapping[str, Any],
    design_completion: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2StructuralPreregistrationRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        design_execution=design_execution,
        design_contract=design_contract,
        design_handoff=design_handoff,
        design_completion=design_completion,
        require_registered_identities=require_registered_identities,
    )
    execution_contract = _frozen_execution_contract()
    arithmetic_proof = _arithmetic_proof()
    source_digest = str(source_contract["artifact_digest"])
    common_parents = (
        source_digest,
        str(design_execution["artifact_digest"]),
        str(design_contract["artifact_digest"]),
        str(design_handoff["artifact_digest"]),
        str(design_completion["artifact_digest"]),
    )
    preregistration = _artifact(
        schema_version="dehps-prediction-v2-structural-execution-preregistration.v1",
        artifact_type="prediction_v2_structural_execution_preregistration",
        body={
            "status": "COMPLETE",
            "contract_status": "FROZEN",
            "historical_evidence": "INCONCLUSIVE",
            "selected_program": SELECTED_PROGRAM,
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "execution_contract": execution_contract,
            "execution_contract_digest": canonical_digest(
                execution_contract,
                domain="dehps.prediction-v2.structural-execution-contract.v1",
            ),
            "arithmetic_proof": arithmetic_proof,
            "portfolio_budget_status": "FROZEN",
            "optimizer_status": "FROZEN_NOT_EXECUTED",
            "seed_schedule_status": "FROZEN",
            "null_replicate_count_status": "FROZEN_NOT_EXECUTED",
            "tolerance_status": "FROZEN_EXACT_ZERO",
            "compute_envelope_status": "FROZEN",
            "acceptance_rule_status": "FROZEN_NOT_EVALUATED",
            "candidate_portfolios_generated": 0,
            "optimizer_proposals_executed": 0,
            "null_replicates_executed": 0,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "structural_algorithm_implemented": False,
            "production_action": "none",
        },
        parent_digests=common_parents,
        domain="dehps.prediction-v2.structural-execution-preregistration.v1",
    )
    execution_handoff = _artifact(
        schema_version="dehps-prediction-v2-structural-portfolio-execution-handoff.v1",
        artifact_type="prediction_v2_structural_portfolio_execution_handoff",
        body={
            "status": "COMPLETE",
            "preregistration_digest": preregistration["artifact_digest"],
            "execution_contract_digest": preregistration["execution_contract_digest"],
            "next_consumer": PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
            "separate_operator_authorization_required": True,
            "same_execution_retuning_allowed": False,
            "partial_timeout_acceptance_allowed": False,
            "weighted_score_allowed": False,
            "global_optimality_claimed": False,
            "historical_data_allowed": False,
            "previous_scores_predictions_or_rankings_allowed": False,
            "candidate_portfolios_generated": 0,
            "optimizer_proposals_executed": 0,
            "null_replicates_executed": 0,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "structural_algorithm_implemented": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
        },
        parent_digests=(*common_parents, str(preregistration["artifact_digest"])),
        domain="dehps.prediction-v2.structural-portfolio-execution-handoff.v1",
    )
    completion = _artifact(
        schema_version="dehps-prediction-v2-structural-preregistration-completion.v1",
        artifact_type=(
            "prediction_v2_structural_decision_support_preregistration_completion"
        ),
        body={
            "status": "COMPLETE",
            "source_contract_digest": source_digest,
            "structural_design_execution_artifact_digest": design_execution[
                "artifact_digest"
            ],
            "preregistration_digest": preregistration["artifact_digest"],
            "execution_handoff_digest": execution_handoff["artifact_digest"],
            "execution_contract_digest": preregistration["execution_contract_digest"],
            "historical_evidence": "INCONCLUSIVE",
            "selected_program": SELECTED_PROGRAM,
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "registered_child_count": 3,
            "candidate_portfolios_generated": 0,
            "optimizer_proposals_executed": 0,
            "null_replicates_executed": 0,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "structural_algorithm_implemented": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "completion_fact": (
                PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_COMPLETION_FACT
            ),
            "next_consumer": PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(preregistration["artifact_digest"]),
            str(execution_handoff["artifact_digest"]),
        ),
        domain="dehps.prediction-v2.structural-preregistration-completion.v1",
    )
    return PredictionV2StructuralPreregistrationRun(
        preregistration=preregistration,
        execution_handoff=execution_handoff,
        completion=completion,
    )


def _frozen_execution_contract() -> dict[str, Any]:
    return {
        "legal_universe": {
            "number_domain": "integers_1_through_33",
            "combination_cardinality": COMBINATION_CARDINALITY,
            "universe_cardinality": LEGAL_UNIVERSE_CARDINALITY,
            "canonical_rank": (
                "zero_based_lexicographic_rank_matching_combinations(range(1,34),6)"
            ),
        },
        "primary_candidate_budget": {
            "B": PRIMARY_CANDIDATE_BUDGET,
            "selection_basis": (
                "smallest_positive_budget_with_integral_singleton_and_pair_targets"
            ),
            "target_singleton_count": TARGET_SINGLETON_COUNT,
            "target_pair_count": TARGET_PAIR_COUNT,
            "necessary_block_design_parameters": "2-(33,6,5);b=176;r=32",
            "existence_or_global_optimality_claimed": False,
            "compression_fraction_exact": "1-176/1107568",
            "compression_ratio_exact": "1107568/176",
        },
        "optimizer": {
            "name": OPTIMIZER_NAME,
            "optimization_geometry": OPTIMIZATION_GEOMETRY,
            "island_count": OPTIMIZER_ISLAND_COUNT,
            "proposals_per_island": PROPOSALS_PER_ISLAND,
            "total_proposals": TOTAL_OPTIMIZER_PROPOSALS,
            "initialization": "DETERMINISTIC_PARTIAL_FISHER_YATES_RANK_PERMUTATION",
            "proposal": "SELECTED_PREFIX_COMPLEMENT_SUFFIX_SWAP",
            "move_acceptance": "WEAK_PARETO_WITH_ONE_STRICT_OR_EQUAL_VECTOR_LEXICOGRAPHIC_IMPROVEMENT",
            "island_selection": (
                "MAX_STRICT_NULL_DOMINANCE_THEN_MIN_NULL_DOMINANCE_THEN_"
                "MAX_MIN_DISTANCE_THEN_LEXICOGRAPHIC_RANK_VECTOR"
            ),
            "minimize_exact": [
                "sum_of_squared_singleton_counts",
                "sum_of_squared_pair_counts",
            ],
            "maximize_exact": [
                "minimum_replacement_distance",
                "sum_of_pairwise_replacement_distances",
            ],
            "implementation_backend": (
                "NUMBA_EXACT_INTEGER_KERNEL_WITH_SCALAR_REFERENCE_PREFLIGHT"
            ),
            "weighted_scalar_score_allowed": False,
            "global_optimality_claimed": False,
            "uniqueness_boundary": "SELECTED_PREFIX_OF_ONE_MAINTAINED_PERMUTATION",
        },
        "seed_contract": {
            "optimizer_root_seed_hex": OPTIMIZER_ROOT_SEED_HEX,
            "optimizer_seed_derivation": (
                "SHA256(root|'|island|'|zero_padded_island_index)"
            ),
            "null_root_seed_hex": NULL_ROOT_SEED_HEX,
            "null_seed_derivation": (
                "SHA256(root|'|replicate|'|zero_padded_replicate_index)"
            ),
            "bounded_integer_draw": "SHA256_COUNTER_REJECTION_UNBIASED_CLOSED_OPEN",
        },
        "null_baseline": {
            "type": NULL_BASELINE,
            "same_candidate_budget": PRIMARY_CANDIDATE_BUDGET,
            "replicate_count": NULL_REPLICATE_COUNT,
            "sampler": "DETERMINISTIC_VIRTUAL_PARTIAL_FISHER_YATES_PREFIX",
            "ordered_output": "REPLICATE_INDEX_ASCENDING",
            "historical_data_used": False,
        },
        "exactness": {
            "comparison_tolerance": 0,
            "comparison_domain": "INTEGER_SUFFICIENT_STATISTICS_AND_CROSS_PRODUCTS",
            "display_decimal_places": 12,
            "display_rounding": "ROUND_HALF_EVEN",
            "mean_distance_identity": (
                "sum_distance=6*C(B,2)-(sum_singleton_count_squared-6B)/2"
            ),
            "mean_distance_role": "DERIVED_AUDIT_COORDINATE_NOT_INDEPENDENT_GAIN",
        },
        "compute_envelope": {
            "machine_scope": "CURRENT_LOCAL_HOST_ONLY",
            "parallel_workers": OPTIMIZER_ISLAND_COUNT,
            "optimizer_wall_clock_limit_seconds": PHASE_WALL_CLOCK_LIMIT_SECONDS,
            "null_wall_clock_limit_seconds": PHASE_WALL_CLOCK_LIMIT_SECONDS,
            "resident_memory_limit_bytes": RESIDENT_MEMORY_LIMIT_BYTES,
            "reference_preflight_proposals": REFERENCE_PREFLIGHT_PROPOSALS,
            "timeout_policy": "INCOMPLETE_FAIL_CLOSED_NO_PARTIAL_ACCEPTANCE",
        },
        "structural_only_acceptance": {
            "required_minimum_replacement_distance": (
                REQUIRED_MINIMUM_REPLACEMENT_DISTANCE
            ),
            "strict_dominance_definition": (
                "NO_WORSE_ALL_FOUR_EXACT_COORDINATES_AND_STRICTLY_BETTER_ONE"
            ),
            "minimum_strictly_dominated_null_replicates": (
                MINIMUM_STRICTLY_DOMINATED_NULLS
            ),
            "maximum_null_replicates_strictly_dominating_candidate": (
                MAXIMUM_NULLS_DOMINATING_CANDIDATE
            ),
            "joint_failure_fraction": (
                "(1+nulls_not_strictly_dominated_by_candidate)/4097<=0.05"
            ),
            "gate_semantics": "STRUCTURAL_PERFORMANCE_GATE_NOT_PREDICTIVE_P_VALUE",
            "same_execution_retuning_allowed": False,
            "pass_disposition": (
                "STRUCTURAL_DECISION_SUPPORT_HYPOTHESIS_SUPPORTED_AT_FROZEN_BUDGET_ONLY"
            ),
            "fail_disposition": (
                "STRUCTURAL_DECISION_SUPPORT_HYPOTHESIS_REJECTED_AT_"
                "FROZEN_BUDGET_NO_SAME_EXECUTION_RETUNING"
            ),
            "prediction_or_probability_claim_allowed": False,
        },
        "result_blind_input_boundary": {
            "allowed": [
                "legal_universe_constants",
                "frozen_preregistration_contract",
            ],
            "forbidden": [
                "draw_history",
                "previous_scores",
                "previous_predictions",
                "previous_rankings",
                "issue_outcomes",
                "post_output_retuning",
                "portfolio_or_null_results_before_execution",
            ],
        },
    }


def _arithmetic_proof() -> dict[str, Any]:
    universe = math.comb(NUMBER_DOMAIN_SIZE, COMBINATION_CARDINALITY)
    pairs = math.comb(NUMBER_DOMAIN_SIZE, 2)
    pairs_per_block = math.comb(COMBINATION_CARDINALITY, 2)
    singleton_budget_period = NUMBER_DOMAIN_SIZE // math.gcd(
        NUMBER_DOMAIN_SIZE, SINGLETONS_PER_BLOCK
    )
    pair_budget_period = PAIR_UNIVERSE_CARDINALITY // math.gcd(
        PAIR_UNIVERSE_CARDINALITY, PAIRS_PER_BLOCK
    )
    simultaneous_budget_period = math.lcm(singleton_budget_period, pair_budget_period)
    total_proposals = OPTIMIZER_ISLAND_COUNT * PROPOSALS_PER_ISLAND
    non_dominated_null_limit = NULL_REPLICATE_COUNT - MINIMUM_STRICTLY_DOMINATED_NULLS
    distance_one_neighbours = COMBINATION_CARDINALITY * (
        NUMBER_DOMAIN_SIZE - COMBINATION_CARDINALITY
    )
    greedy_distance_two_lower_bound = LEGAL_UNIVERSE_CARDINALITY // (
        distance_one_neighbours + 1
    )
    if (
        universe != LEGAL_UNIVERSE_CARDINALITY
        or pairs != PAIR_UNIVERSE_CARDINALITY
        or pairs_per_block != PAIRS_PER_BLOCK
        or simultaneous_budget_period != PRIMARY_CANDIDATE_BUDGET
        or SINGLETONS_PER_BLOCK * PRIMARY_CANDIDATE_BUDGET
        != NUMBER_DOMAIN_SIZE * TARGET_SINGLETON_COUNT
        or PAIRS_PER_BLOCK * PRIMARY_CANDIDATE_BUDGET
        != PAIR_UNIVERSE_CARDINALITY * TARGET_PAIR_COUNT
        or total_proposals != TOTAL_OPTIMIZER_PROPOSALS
        or non_dominated_null_limit != 203
        or (1 + non_dominated_null_limit) * 20 > NULL_REPLICATE_COUNT + 1
        or (2 + non_dominated_null_limit) * 20 <= NULL_REPLICATE_COUNT + 1
        or greedy_distance_two_lower_bound <= PRIMARY_CANDIDATE_BUDGET
    ):
        raise PredictionV2StructuralPreregistrationError(
            "prediction_v2_structural_preregistration_arithmetic_changed"
        )
    return {
        "legal_universe_cardinality": universe,
        "pair_universe_cardinality": pairs,
        "singleton_budget_period": singleton_budget_period,
        "pair_budget_period": pair_budget_period,
        "simultaneous_minimum_budget": simultaneous_budget_period,
        "target_singleton_count": TARGET_SINGLETON_COUNT,
        "target_pair_count": TARGET_PAIR_COUNT,
        "total_optimizer_proposals": total_proposals,
        "maximum_nulls_not_strictly_dominated": non_dominated_null_limit,
        "joint_failure_threshold_is_tight": True,
        "distance_one_neighbours_per_block": distance_one_neighbours,
        "greedy_distance_two_portfolio_lower_bound": (greedy_distance_two_lower_bound),
        "minimum_distance_two_feasible_at_budget_176": True,
        "exact_block_design_existence_claimed": False,
    }


def _validate_parent_artifacts(
    *,
    design_execution: Mapping[str, Any],
    design_contract: Mapping[str, Any],
    design_handoff: Mapping[str, Any],
    design_completion: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts_and_domains = (
        (design_execution, "dehps.research-os.mainline-execution.v1"),
        (design_contract, "dehps.prediction-v2.structural-design-contract.v1"),
        (
            design_handoff,
            "dehps.prediction-v2.structural-preregistration-handoff.v1",
        ),
        (design_completion, "dehps.prediction-v2.structural-design-completion.v1"),
    )
    for artifact, domain in artifacts_and_domains:
        _verify_artifact(artifact, domain=domain)
    if require_registered_identities:
        observed = tuple(
            str(artifact.get("artifact_digest"))
            for artifact, _ in artifacts_and_domains
        )
        expected = (
            STRUCTURAL_DESIGN_EXECUTION_DIGEST,
            STRUCTURAL_DESIGN_CONTRACT_DIGEST,
            STRUCTURAL_PREREGISTRATION_HANDOFF_DIGEST,
            STRUCTURAL_DESIGN_COMPLETION_DIGEST,
        )
        if observed != expected:
            raise PredictionV2StructuralPreregistrationError(
                "prediction_v2_structural_preregistration_registered_identity_changed"
            )
    design_spec = design_contract.get("design_spec")
    if (
        design_execution.get("artifact_type") != "research_os_mainline_execution"
        or design_execution.get("task_key")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
        or design_execution.get("status") != "COMPLETE"
        or design_execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or design_execution.get("registered_artifact_count") != 4
        or design_execution.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT
        or design_execution.get("structural_design_contract_digest")
        != design_contract.get("artifact_digest")
        or design_execution.get("structural_preregistration_handoff_digest")
        != design_handoff.get("artifact_digest")
        or design_execution.get("structural_design_completion_digest")
        != design_completion.get("artifact_digest")
        or design_execution.get("downstream_consumer")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
        or design_execution.get("historical_evidence") != "INCONCLUSIVE"
        or design_execution.get("prediction_v2_mode") != "SHADOW_ONLY"
        or design_execution.get("prediction_v2_route") != "BASELINE_ONLY"
        or design_execution.get("candidate_portfolios_generated") != 0
        or design_execution.get("optimizers_executed") != 0
        or design_execution.get("database_queries_during_capability") != 0
        or design_execution.get("historical_rows_read") != 0
        or design_execution.get("formal_historical_folds_executed") != 0
        or design_execution.get("bootstrap_children_executed") != 0
        or design_execution.get("evidence_created") is not False
        or design_execution.get("new_model_created") is not False
        or design_execution.get("structural_algorithm_implemented") is not False
        or design_execution.get("promotion_gate_opened") is not False
        or design_execution.get("p3_authorized") is not False
        or design_execution.get("production_action") != "none"
        or design_contract.get("artifact_type")
        != "prediction_v2_structural_decision_support_design_contract"
        or design_contract.get("status") != "COMPLETE"
        or design_contract.get("contract_status") != "FROZEN"
        or design_contract.get("portfolio_budget_status")
        != "TO_BE_FROZEN_BY_PREREGISTRATION"
        or design_contract.get("optimizer_status") != "TO_BE_FROZEN_BY_PREREGISTRATION"
        or not isinstance(design_spec, dict)
        or design_spec.get("optimization_geometry", {}).get("type")
        != OPTIMIZATION_GEOMETRY
        or design_spec.get("optimization_geometry", {}).get("weighted_score_allowed")
        is not False
        or design_handoff.get("artifact_type")
        != "prediction_v2_structural_preregistration_handoff"
        or design_handoff.get("status") != "COMPLETE"
        or design_handoff.get("design_contract_digest")
        != design_contract.get("artifact_digest")
        or design_handoff.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
        or design_handoff.get("required_frozen_choices")
        != [
            "one_primary_candidate_budget",
            "one_transparent_optimizer",
            "deterministic_optimizer_seed",
            "deterministic_null_seed_schedule",
            "null_replicate_count",
            "metric_tolerances",
            "compute_budget",
            "structural_only_acceptance_rule",
        ]
        or design_handoff.get("same_budget_null_required") is not True
        or design_handoff.get("weighted_score_allowed") is not False
        or design_handoff.get("historical_data_allowed") is not False
        or design_handoff.get("candidate_portfolios_generated") != 0
        or design_handoff.get("optimizers_executed") != 0
        or design_handoff.get("production_action") != "none"
        or design_completion.get("artifact_type")
        != "prediction_v2_structural_decision_support_design_completion"
        or design_completion.get("status") != "COMPLETE"
        or design_completion.get("design_contract_digest")
        != design_contract.get("artifact_digest")
        or design_completion.get("preregistration_handoff_digest")
        != design_handoff.get("artifact_digest")
        or design_completion.get("registered_child_count") != 3
        or design_completion.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT
        or design_completion.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
        or design_completion.get("candidate_portfolios_generated") != 0
        or design_completion.get("optimizers_executed") != 0
        or design_completion.get("new_evidence_created") is not False
        or design_completion.get("structural_algorithm_implemented") is not False
        or design_completion.get("production_action") != "none"
    ):
        raise PredictionV2StructuralPreregistrationError(
            "prediction_v2_structural_preregistration_parent_consistency_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
        or frozen.get("structural_design_execution_artifact_digest")
        != STRUCTURAL_DESIGN_EXECUTION_DIGEST
        or frozen.get("structural_design_child_artifact_digests")
        != [
            STRUCTURAL_DESIGN_CONTRACT_DIGEST,
            STRUCTURAL_PREREGISTRATION_HANDOFF_DIGEST,
            STRUCTURAL_DESIGN_COMPLETION_DIGEST,
        ]
        or frozen.get("execution_contract") != _frozen_execution_contract()
        or frozen.get("arithmetic_proof") != _arithmetic_proof()
        or frozen.get("historical_evidence") != "INCONCLUSIVE"
        or frozen.get("selected_program") != SELECTED_PROGRAM
        or frozen.get("prediction_research_disposition")
        != PREDICTION_RESEARCH_DISPOSITION
        or frozen.get("prediction_v2_mode") != "SHADOW_ONLY"
        or frozen.get("prediction_v2_route") != "BASELINE_ONLY"
        or frozen.get("registered_child_count") != 3
        or frozen.get("registered_total_with_mainline_execution") != 4
        or frozen.get("database_queries") != 0
        or frozen.get("historical_rows_read") != 0
        or frozen.get("folds_executed") != 0
        or frozen.get("bootstrap_children_executed") != 0
        or frozen.get("candidate_portfolios_generated") != 0
        or frozen.get("optimizer_proposals_executed") != 0
        or frozen.get("null_replicates_executed") != 0
        or frozen.get("new_evidence_created") is not False
        or frozen.get("new_model_created") is not False
        or frozen.get("structural_algorithm_implemented") is not False
        or frozen.get("candidate_expert_authorized") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("production_action") != "none"
    ):
        raise PredictionV2StructuralPreregistrationError(
            "prediction_v2_structural_preregistration_frozen_contract_changed"
        )


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
        raise PredictionV2StructuralPreregistrationError(
            "prediction_v2_structural_preregistration_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
