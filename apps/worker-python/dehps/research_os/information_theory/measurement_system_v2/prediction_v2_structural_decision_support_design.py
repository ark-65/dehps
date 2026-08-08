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

PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY = (
    "prediction-v2-structural-decision-support-design"
)
PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_CAPABILITY = (
    "prediction_v2_structural_decision_support_design"
)
PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT = (
    "prediction-v2-structural-decision-support-design:COMPLETE"
)
PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/prediction-v2-structural-decision-support-design-source-v1.json"
)
PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY = (
    "prediction-v2-structural-decision-support-preregistration"
)

PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY = (
    "prediction-v2-forward-evidence-or-pivot-planner"
)
PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT = (
    "prediction-v2-forward-evidence-or-pivot-planner:COMPLETE"
)
FORWARD_OR_PIVOT_EXECUTION_DIGEST = (
    "b46328427e2ed3f4f2c6eea6cf68bc9f1ab3dd5a82c7933c2e99c1ad00c05ac5"
)
PROSPECTIVE_EVIDENCE_FEASIBILITY_DIGEST = (
    "c7ca0ad4f08ddc40d140623154f52d76a20c907f4d11995fd1379abd2719c180"
)
STRUCTURAL_PIVOT_PLAN_DIGEST = (
    "0abe15f5795ca940e9fc6a7573949f62e0ff8da6ac9fcb47173b9d644c079ce0"
)
FORWARD_OR_PIVOT_COMPLETION_DIGEST = (
    "35808dbb4bca36b1761576c88942757dfeb87c8679c4b4d530e9d27fea59d69a"
)
PREDICTION_V2_SHADOW_CONTRACT_DIGEST = (
    "df39fde45013c10b9c6586662d05353cebe9260788ee200c455e7e5e958e9db7"
)

NUMBER_DOMAIN_SIZE = 33
COMBINATION_CARDINALITY = 6
LEGAL_UNIVERSE_CARDINALITY = 1_107_568
PAIR_UNIVERSE_CARDINALITY = 528
SINGLETONS_PER_BLOCK = 6
PAIRS_PER_BLOCK = 15
PORTFOLIO_BUDGET_LOWER_BOUND = 2
OPTIMIZATION_GEOMETRY = "PARETO_VECTOR_WITHOUT_SCALAR_WEIGHTS"
NULL_BASELINE = "UNIFORM_WITHOUT_REPLACEMENT_PORTFOLIO_FROM_LEGAL_UNIVERSE"
PENDING_PREREGISTRATION = "TO_BE_FROZEN_BY_PREREGISTRATION"
SELECTED_PROGRAM = "STRUCTURAL_DECISION_SUPPORT_PIVOT"
PREDICTION_RESEARCH_DISPOSITION = "FROZEN_PENDING_SEPARATE_RESULT_BLIND_PREREGISTRATION"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-structural-design-round-62-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-structural-design-round-62-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/prediction_v2_structural_decision_support_design.py"
)
FROZEN_CONTRACT_DIGEST = (
    "9fa80b03a081805f14f2b2be630b3bd01cf96cbc81c5f96d9650e5d6a73147b3"
)


class PredictionV2StructuralDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2StructuralDesignRun:
    design_contract: Mapping[str, Any]
    preregistration_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.design_contract, self.preregistration_handoff, self.completion


def load_prediction_v2_structural_design_source_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2StructuralDesignError(
            f"prediction_v2_structural_design_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-structural-decision-support-design-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_structural_decision_support_design_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 385
        or payload.get("research_execution_id") != 306
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 386
        or payload.get("engineering_execution_id") != 307
        or payload.get("result_blind") is not True
        or payload.get("historical_rows_read") != 0
        or payload.get("folds_executed") != 0
        or payload.get("bootstrap_children_executed") != 0
        or payload.get("candidate_portfolios_generated") != 0
        or payload.get("optimizers_executed") != 0
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
            domain="dehps.prediction-v2.structural-design-frozen-contract.v1",
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.prediction-v2.structural-design-source-set.v1",
        )
    ):
        raise PredictionV2StructuralDesignError(
            "prediction_v2_structural_design_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2StructuralDesignError(
            "prediction_v2_structural_design_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_structural_design_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2StructuralDesignError(
                f"prediction_v2_structural_design_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2StructuralDesignError(
                f"prediction_v2_structural_design_source_modified:{relative}"
            )


def build_prediction_v2_structural_design_artifacts(
    *,
    source_contract: Mapping[str, Any],
    forward_execution: Mapping[str, Any],
    feasibility: Mapping[str, Any],
    structural_pivot_plan: Mapping[str, Any],
    forward_completion: Mapping[str, Any],
    shadow_contract: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2StructuralDesignRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        forward_execution=forward_execution,
        feasibility=feasibility,
        structural_pivot_plan=structural_pivot_plan,
        forward_completion=forward_completion,
        shadow_contract=shadow_contract,
        require_registered_identities=require_registered_identities,
    )
    legal_identity = _legal_identity()
    design_spec = _design_spec()
    source_digest = str(source_contract["artifact_digest"])
    common_parents = (
        source_digest,
        str(forward_execution["artifact_digest"]),
        str(feasibility["artifact_digest"]),
        str(structural_pivot_plan["artifact_digest"]),
        str(forward_completion["artifact_digest"]),
        str(shadow_contract["artifact_digest"]),
    )
    design_contract = _artifact(
        schema_version="dehps-prediction-v2-structural-design-contract.v1",
        artifact_type="prediction_v2_structural_decision_support_design_contract",
        body={
            "status": "COMPLETE",
            "contract_status": "FROZEN",
            "historical_evidence": "INCONCLUSIVE",
            "selected_program": SELECTED_PROGRAM,
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "legal_identity": legal_identity,
            "design_spec": design_spec,
            "portfolio_budget_status": PENDING_PREREGISTRATION,
            "optimizer_status": PENDING_PREREGISTRATION,
            "seed_schedule_status": PENDING_PREREGISTRATION,
            "null_replicate_count_status": PENDING_PREREGISTRATION,
            "acceptance_threshold_status": PENDING_PREREGISTRATION,
            "candidate_portfolios_generated": 0,
            "optimizers_executed": 0,
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
        domain="dehps.prediction-v2.structural-design-contract.v1",
    )
    preregistration_handoff = _artifact(
        schema_version="dehps-prediction-v2-structural-preregistration-handoff.v1",
        artifact_type="prediction_v2_structural_preregistration_handoff",
        body={
            "status": "COMPLETE",
            "design_contract_digest": design_contract["artifact_digest"],
            "next_consumer": (
                PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
            ),
            "required_frozen_choices": [
                "one_primary_candidate_budget",
                "one_transparent_optimizer",
                "deterministic_optimizer_seed",
                "deterministic_null_seed_schedule",
                "null_replicate_count",
                "metric_tolerances",
                "compute_budget",
                "structural_only_acceptance_rule",
            ],
            "same_budget_null_required": True,
            "null_baseline": NULL_BASELINE,
            "optimization_geometry": OPTIMIZATION_GEOMETRY,
            "weighted_score_allowed": False,
            "historical_data_allowed": False,
            "previous_scores_predictions_or_rankings_allowed": False,
            "candidate_portfolios_generated": 0,
            "optimizers_executed": 0,
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
        parent_digests=(*common_parents, str(design_contract["artifact_digest"])),
        domain="dehps.prediction-v2.structural-preregistration-handoff.v1",
    )
    completion = _artifact(
        schema_version="dehps-prediction-v2-structural-design-completion.v1",
        artifact_type="prediction_v2_structural_decision_support_design_completion",
        body={
            "status": "COMPLETE",
            "source_contract_digest": source_digest,
            "forward_or_pivot_execution_artifact_digest": forward_execution[
                "artifact_digest"
            ],
            "design_contract_digest": design_contract["artifact_digest"],
            "preregistration_handoff_digest": preregistration_handoff[
                "artifact_digest"
            ],
            "historical_evidence": "INCONCLUSIVE",
            "selected_program": SELECTED_PROGRAM,
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "registered_child_count": 3,
            "candidate_portfolios_generated": 0,
            "optimizers_executed": 0,
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
                PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT
            ),
            "next_consumer": (
                PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(design_contract["artifact_digest"]),
            str(preregistration_handoff["artifact_digest"]),
        ),
        domain="dehps.prediction-v2.structural-design-completion.v1",
    )
    return PredictionV2StructuralDesignRun(
        design_contract=design_contract,
        preregistration_handoff=preregistration_handoff,
        completion=completion,
    )


def _legal_identity() -> dict[str, Any]:
    universe = math.comb(NUMBER_DOMAIN_SIZE, COMBINATION_CARDINALITY)
    pairs = math.comb(NUMBER_DOMAIN_SIZE, 2)
    pairs_per_block = math.comb(COMBINATION_CARDINALITY, 2)
    if (
        universe != LEGAL_UNIVERSE_CARDINALITY
        or pairs != PAIR_UNIVERSE_CARDINALITY
        or pairs_per_block != PAIRS_PER_BLOCK
    ):
        raise PredictionV2StructuralDesignError(
            "prediction_v2_structural_design_legal_identity_changed"
        )
    return {
        "number_domain": "integers_1_through_33",
        "number_domain_size": NUMBER_DOMAIN_SIZE,
        "combination_cardinality": COMBINATION_CARDINALITY,
        "combination_representation": "strictly_increasing_six_tuple",
        "legal_universe_formula": "C(33,6)",
        "legal_universe_cardinality": universe,
        "pair_universe_formula": "C(33,2)",
        "pair_universe_cardinality": pairs,
        "singletons_per_block": SINGLETONS_PER_BLOCK,
        "pairs_per_block": pairs_per_block,
        "pre_draw_probability": "equal_for_every_legal_combination",
        "universe_enumerated": False,
    }


def _design_spec() -> dict[str, Any]:
    return {
        "decision_object": {
            "type": "unordered_fixed_budget_set_of_legal_combinations",
            "candidate_budget_symbol": "B",
            "candidate_budget_lower_bound": PORTFOLIO_BUDGET_LOWER_BOUND,
            "candidate_budget_upper_bound_exclusive": LEGAL_UNIVERSE_CARDINALITY,
            "candidate_budget_status": PENDING_PREREGISTRATION,
            "duplicate_handling": "CANONICAL_SET_CONSTRUCTION_NO_VALIDATION_PASS",
        },
        "metrics": {
            "compression_fraction": "1-B/1107568",
            "compression_ratio": "1107568/B",
            "singleton_exposure_share": "p_i=count_i/(6B)",
            "singleton_concentration_excess": "sum_i(p_i^2)-1/33",
            "pair_exposure_share": "q_ij=count_ij/(15B)",
            "pair_concentration_excess": "sum_ij(q_ij^2)-1/528",
            "replacement_distance": "d(A,B)=6-|A_intersection_B|",
            "minimum_replacement_distance": "min_distinct_pairs_d(A,B)",
            "mean_replacement_distance": "mean_unordered_distinct_pairs_d(A,B)",
        },
        "metric_invariants": {
            "singleton_share_sum": 1,
            "pair_share_sum": 1,
            "singleton_hhi_lower_bound": "1/33",
            "pair_hhi_lower_bound": "1/528",
            "finite_budget_integrality_may_prevent_lower_bound_attainment": True,
            "replacement_distance_range_for_set_members": [1, 6],
            "label_permutation_invariant": True,
            "historical_outcome_dependency": False,
        },
        "optimization_geometry": {
            "type": OPTIMIZATION_GEOMETRY,
            "minimize": [
                "singleton_concentration_excess",
                "pair_concentration_excess",
            ],
            "maximize": [
                "minimum_replacement_distance",
                "mean_replacement_distance",
            ],
            "fixed_by_budget": ["compression_fraction", "compression_ratio"],
            "weighted_score_allowed": False,
            "optimizer_selected": False,
            "global_optimality_claimed": False,
        },
        "null_baseline": {
            "type": NULL_BASELINE,
            "same_candidate_budget_required": True,
            "seed_schedule_status": PENDING_PREREGISTRATION,
            "replicate_count_status": PENDING_PREREGISTRATION,
            "acceptance_threshold_status": PENDING_PREREGISTRATION,
            "historical_data_used": False,
        },
        "result_blind_input_boundary": {
            "allowed": [
                "legal_universe_constants",
                "future_preregistered_budget_optimizer_and_seeds",
            ],
            "forbidden": [
                "draw_history",
                "previous_scores",
                "previous_predictions",
                "previous_rankings",
                "issue_outcomes",
                "post_hoc_budget_or_weight_selection",
                "duplicate_index",
            ],
        },
    }


def _validate_parent_artifacts(
    *,
    forward_execution: Mapping[str, Any],
    feasibility: Mapping[str, Any],
    structural_pivot_plan: Mapping[str, Any],
    forward_completion: Mapping[str, Any],
    shadow_contract: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts_and_domains = (
        (forward_execution, "dehps.research-os.mainline-execution.v1"),
        (feasibility, "dehps.prediction-v2.prospective-evidence-feasibility.v1"),
        (
            structural_pivot_plan,
            "dehps.prediction-v2.structural-decision-support-pivot-plan.v1",
        ),
        (forward_completion, "dehps.prediction-v2.forward-or-pivot-completion.v1"),
        (shadow_contract, "dehps.prediction-v2.shadow-contract.v1"),
    )
    for artifact, domain in artifacts_and_domains:
        _verify_artifact(artifact, domain=domain)
    if require_registered_identities:
        observed = tuple(
            str(artifact.get("artifact_digest"))
            for artifact, _ in artifacts_and_domains
        )
        expected = (
            FORWARD_OR_PIVOT_EXECUTION_DIGEST,
            PROSPECTIVE_EVIDENCE_FEASIBILITY_DIGEST,
            STRUCTURAL_PIVOT_PLAN_DIGEST,
            FORWARD_OR_PIVOT_COMPLETION_DIGEST,
            PREDICTION_V2_SHADOW_CONTRACT_DIGEST,
        )
        if observed != expected:
            raise PredictionV2StructuralDesignError(
                "prediction_v2_structural_design_registered_identity_changed"
            )
    zero_work_keys = (
        "historical_rows_read",
        "folds_executed",
        "bootstrap_children_executed",
    )
    if (
        forward_execution.get("artifact_type") != "research_os_mainline_execution"
        or forward_execution.get("task_key")
        != PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
        or forward_execution.get("status") != "COMPLETE"
        or forward_execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or forward_execution.get("registered_artifact_count") != 4
        or forward_execution.get("completion_fact")
        != PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT
        or forward_execution.get("prospective_evidence_feasibility_digest")
        != feasibility.get("artifact_digest")
        or forward_execution.get("structural_decision_support_pivot_plan_digest")
        != structural_pivot_plan.get("artifact_digest")
        or forward_execution.get("forward_or_pivot_completion_digest")
        != forward_completion.get("artifact_digest")
        or forward_execution.get("historical_evidence") != "INCONCLUSIVE"
        or forward_execution.get("selected_program") != SELECTED_PROGRAM
        or forward_execution.get("prediction_research_disposition")
        != PREDICTION_RESEARCH_DISPOSITION
        or forward_execution.get("prediction_v2_mode") != "SHADOW_ONLY"
        or forward_execution.get("prediction_v2_route") != "BASELINE_ONLY"
        or forward_execution.get("candidate_expert_authorized") is not False
        or forward_execution.get("database_queries_during_capability") != 0
        or forward_execution.get("historical_rows_read") != 0
        or forward_execution.get("formal_historical_folds_executed") != 0
        or forward_execution.get("bootstrap_children_executed") != 0
        or forward_execution.get("evidence_created") is not False
        or forward_execution.get("new_model_created") is not False
        or forward_execution.get("structural_algorithm_implemented") is not False
        or forward_execution.get("promotion_gate_opened") is not False
        or forward_execution.get("p3_authorized") is not False
        or forward_execution.get("production_action") != "none"
        or feasibility.get("artifact_type")
        != "prediction_v2_prospective_evidence_feasibility"
        or feasibility.get("status") != "COMPLETE"
        or feasibility.get("historical_evidence") != "INCONCLUSIVE"
        or feasibility.get("candidate_model_available") is not False
        or feasibility.get("accepted_model_artifact_digest") is not None
        or feasibility.get("formal_power_claim") is not False
        or feasibility.get("candidate_forward_evidence_eligible") is not False
        or feasibility.get("feasibility_decision")
        != "NOT_FEASIBLE_WITHIN_OPERATIONAL_HORIZON"
        or any(feasibility.get(key) != 0 for key in zero_work_keys)
        or feasibility.get("new_evidence_created") is not False
        or feasibility.get("production_action") != "none"
        or structural_pivot_plan.get("artifact_type")
        != "prediction_v2_structural_decision_support_pivot_plan"
        or structural_pivot_plan.get("status") != "COMPLETE"
        or structural_pivot_plan.get("selected_program") != SELECTED_PROGRAM
        or structural_pivot_plan.get("prediction_research_disposition")
        != PREDICTION_RESEARCH_DISPOSITION
        or structural_pivot_plan.get("structural_pivot_scope")
        != [
            "combination_space_compression",
            "risk_control",
            "candidate_diversity",
        ]
        or structural_pivot_plan.get("structural_algorithm_implemented") is not False
        or structural_pivot_plan.get("prediction_v2_mode") != "SHADOW_ONLY"
        or structural_pivot_plan.get("prediction_v2_route") != "BASELINE_ONLY"
        or any(structural_pivot_plan.get(key) != 0 for key in zero_work_keys)
        or structural_pivot_plan.get("new_evidence_created") is not False
        or structural_pivot_plan.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
        or structural_pivot_plan.get("production_action") != "none"
        or forward_completion.get("artifact_type")
        != "prediction_v2_forward_evidence_or_pivot_planner_completion"
        or forward_completion.get("status") != "COMPLETE"
        or forward_completion.get("feasibility_digest")
        != feasibility.get("artifact_digest")
        or forward_completion.get("structural_pivot_plan_digest")
        != structural_pivot_plan.get("artifact_digest")
        or forward_completion.get("selected_program") != SELECTED_PROGRAM
        or forward_completion.get("registered_child_count") != 3
        or any(forward_completion.get(key) != 0 for key in zero_work_keys)
        or forward_completion.get("new_evidence_created") is not False
        or forward_completion.get("structural_algorithm_implemented") is not False
        or forward_completion.get("completion_fact")
        != PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT
        or forward_completion.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
        or forward_completion.get("production_action") != "none"
        or shadow_contract.get("artifact_digest")
        != PREDICTION_V2_SHADOW_CONTRACT_DIGEST
        or shadow_contract.get("mode") != "SHADOW_ONLY"
        or shadow_contract.get("route") != "BASELINE_ONLY"
        or shadow_contract.get("promotion_gate_opened") is not False
        or shadow_contract.get("production_candidate") is not False
    ):
        raise PredictionV2StructuralDesignError(
            "prediction_v2_structural_design_parent_consistency_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT
        or frozen.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
        or frozen.get("forward_or_pivot_execution_artifact_digest")
        != FORWARD_OR_PIVOT_EXECUTION_DIGEST
        or frozen.get("forward_or_pivot_child_artifact_digests")
        != [
            PROSPECTIVE_EVIDENCE_FEASIBILITY_DIGEST,
            STRUCTURAL_PIVOT_PLAN_DIGEST,
            FORWARD_OR_PIVOT_COMPLETION_DIGEST,
        ]
        or frozen.get("prediction_v2_shadow_contract_digest")
        != PREDICTION_V2_SHADOW_CONTRACT_DIGEST
        or frozen.get("legal_identity") != _legal_identity()
        or frozen.get("design_spec") != _design_spec()
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
        or frozen.get("optimizers_executed") != 0
        or frozen.get("new_evidence_created") is not False
        or frozen.get("new_model_created") is not False
        or frozen.get("structural_algorithm_implemented") is not False
        or frozen.get("candidate_expert_authorized") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("production_action") != "none"
    ):
        raise PredictionV2StructuralDesignError(
            "prediction_v2_structural_design_frozen_contract_changed"
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
        raise PredictionV2StructuralDesignError(
            "prediction_v2_structural_design_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
