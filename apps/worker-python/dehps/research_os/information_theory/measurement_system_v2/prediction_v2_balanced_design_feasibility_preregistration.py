from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY = (
    "prediction-v2-balanced-design-feasibility-preregistration"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_CAPABILITY = (
    "prediction_v2_balanced_design_feasibility_preregistration"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_COMPLETION_FACT = (
    "prediction-v2-balanced-design-feasibility-preregistration:COMPLETE"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "prediction-v2-balanced-design-feasibility-preregistration-source-v1.json"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY = (
    "prediction-v2-balanced-design-feasibility-execution"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_APPROVED_EVENT = "research-contract:prediction-v2-balanced-design-feasibility-preregistration:approved"

FEASIBILITY_SPECIFICATION_DIGEST = (
    "821045891f32093cb2ae3375dd24bb7582b9dc4684db03bcb165d51a76cb05a7"
)
FEASIBILITY_PREREGISTRATION_HANDOFF_DIGEST = (
    "fedcddb8034d325177ee1f2e81ee824fa656c19387fa16129fe32312d14360d7"
)
FEASIBILITY_COMPLETION_DIGEST = (
    "683400d34aa3616a9efec061e875ad992478733eaaffa495d51a7dbedc70473b"
)
FEASIBILITY_MAINLINE_EXECUTION_DIGEST = (
    "8feb31267be4790ebd473547ffdeaa93cb1994d031ed157356a981ba8826411d"
)

CONSTRUCTOR_FAMILY = "Z33_TRANSLATION_ORBIT_EXACT_MULTICOVER_V1"
POSITIVE_OUTCOME = "FOUND_EXACT_2_33_6_5_DESIGN"
BOUNDED_NEGATIVE_OUTCOME = "NOT_FOUND_WITHIN_FROZEN_BUDGET"
INVALID_OUTCOME = "INVALID_EXECUTION_NO_DECISION"
REPETITION_SCAN = "ABSENT_BY_CONSTRUCTION"

POINT_COUNT = 33
BLOCK_SIZE = 6
BLOCK_COUNT = 176
POINT_REPLICATION_TARGET = 32
PAIR_COUNT = 528
PAIR_REPLICATION_TARGET = 5
LEGAL_BLOCK_COUNT = 1_107_568
FULL_ORBIT_COUNT = 33_561
SHORT_ORBIT_COUNT = 5
FULL_ORBIT_SIZE = 33
SHORT_ORBIT_SIZE = 11
PAIR_COORDINATE_COUNT = 16

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-balanced-design-preregistration-round-90-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-balanced-design-preregistration-round-91-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/"
    "prediction_v2_balanced_design_feasibility_preregistration.py"
)
FROZEN_CONTRACT_DIGEST = (
    "535c323ce334d0eb00840ee8211d162d33031a658821b418d57c0e1da3d71724"
)


class PredictionV2BalancedDesignFeasibilityPreregistrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2BalancedDesignFeasibilityPreregistrationRun:
    preregistration: Mapping[str, Any]
    execution_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.preregistration, self.execution_handoff, self.completion


def load_prediction_v2_balanced_design_feasibility_preregistration_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2BalancedDesignFeasibilityPreregistrationError(
            f"balanced_design_preregistration_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-balanced-design-feasibility-preregistration-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_balanced_design_feasibility_preregistration_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 417
        or payload.get("research_execution_id") != 338
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 418
        or payload.get("engineering_execution_id") != 339
        or payload.get("result_blind") is not True
        or payload.get("legal_block_ids_visited") != 0
        or payload.get("orbit_candidates_enumerated") != 0
        or payload.get("solver_nodes_executed") != 0
        or payload.get("certificate_blocks_generated") != 0
        or payload.get("database_queries") != 0
        or payload.get("historical_rows_read") != 0
        or payload.get("prior_scores_read") != 0
        or payload.get("prior_predictions_read") != 0
        or payload.get("prior_rankings_read") != 0
        or payload.get("registered_children") != 3
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
                "dehps.prediction-v2.balanced-design-feasibility-"
                "preregistration-frozen.v1"
            ),
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.prediction-v2.balanced-design-feasibility-"
                "preregistration-source-set.v1"
            ),
        )
    ):
        raise PredictionV2BalancedDesignFeasibilityPreregistrationError(
            "balanced_design_preregistration_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2BalancedDesignFeasibilityPreregistrationError(
            "balanced_design_preregistration_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_balanced_design_feasibility_preregistration_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2BalancedDesignFeasibilityPreregistrationError(
                f"balanced_design_preregistration_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2BalancedDesignFeasibilityPreregistrationError(
                f"balanced_design_preregistration_source_modified:{relative}"
            )


def build_prediction_v2_balanced_design_feasibility_preregistration_artifacts(
    *,
    source_contract: Mapping[str, Any],
    feasibility_specification: Mapping[str, Any],
    feasibility_preregistration_handoff: Mapping[str, Any],
    feasibility_completion: Mapping[str, Any],
    feasibility_mainline_execution: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2BalancedDesignFeasibilityPreregistrationRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        feasibility_specification=feasibility_specification,
        feasibility_preregistration_handoff=feasibility_preregistration_handoff,
        feasibility_completion=feasibility_completion,
        feasibility_mainline_execution=feasibility_mainline_execution,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(feasibility_specification["artifact_digest"]),
        str(feasibility_preregistration_handoff["artifact_digest"]),
        str(feasibility_completion["artifact_digest"]),
        str(feasibility_mainline_execution["artifact_digest"]),
    )
    orbit_inventory = {
        "legal_block_count": LEGAL_BLOCK_COUNT,
        "short_orbit_count": SHORT_ORBIT_COUNT,
        "blocks_per_short_orbit": SHORT_ORBIT_SIZE,
        "full_orbit_count": FULL_ORBIT_COUNT,
        "blocks_per_full_orbit": FULL_ORBIT_SIZE,
        "inventory_identity": "55 + 33561*33 = 1107568",
    }
    representation = {
        "scope": "ALL_AND_ONLY_Z33_TRANSLATION_INVARIANT_SIMPLE_2_DESIGN_CANDIDATES",
        "point_labels": "Z_33",
        "short_orbit_subgroup": [0, 11, 22],
        "short_orbit_representatives": (
            "UNION_OF_TWO_SUBGROUP_COSETS_WITH_QUOTIENT_DISTANCE_1_THROUGH_5"
        ),
        "canonical_full_orbit_representative": (
            "MINIMUM_COMBINADIC_ID_OVER_33_TRANSLATES"
        ),
        "pair_coordinates": "UNDIRECTED_CIRCULAR_DISTANCE_1_THROUGH_16",
        "allowed_orbit_count_profiles": [
            {"full_orbits": 5, "short_orbits": 1},
            {"full_orbits": 4, "short_orbits": 4},
        ],
        "other_automorphism_restrictions": "NONE",
    }
    branch_order = {
        "profile_order": ["5_FULL_1_SHORT", "4_FULL_4_SHORT"],
        "short_subset_order": "LEXICOGRAPHIC_BY_QUOTIENT_DISTANCE",
        "signature_grouping": ("IDENTICAL_16_INTEGER_VECTORS_WITH_EXACT_MULTIPLICITY"),
        "branch_coordinate": "FEWEST_COMPATIBLE_SIGNATURES_THEN_LOWEST_DISTANCE",
        "candidate_order": ("LEXICOGRAPHIC_SIGNATURE_THEN_MINIMUM_REPRESENTATIVE_ID"),
        "selection_order": "STRICTLY_INCREASING_ORBIT_REPRESENTATIVE_ID",
        "full_signature_filter": (
            "REJECT_IF_ANY_DISTANCE_COMPONENT_EXCEEDS_CURRENT_NONNEGATIVE_RESIDUAL"
        ),
        "seed_policy": "NONE",
    }
    work_budget = {
        "legal_block_ids_visited": LEGAL_BLOCK_COUNT,
        "maximum_full_orbit_representatives": FULL_ORBIT_COUNT,
        "maximum_short_orbit_representatives": SHORT_ORBIT_COUNT,
        "maximum_multicover_node_expansions": 100_000_000,
        "checkpoint_interval_node_expansions": 1_000_000,
        "maximum_resident_bytes": 4_294_967_296,
        "wall_clock_is_not_a_decision_boundary": True,
    }
    checkpoint_contract = {
        "append_only": True,
        "binds_source_contract_digest": True,
        "binds_preregistration_digest": True,
        "binds_profile_short_subset_branch_stack_residual_and_node_count": True,
        "resume_from_latest_valid_checkpoint_only": True,
        "completed_branch_skip": True,
        "changed_identity_outcome": INVALID_OUTCOME,
    }
    certificate_format = {
        "block_count": BLOCK_COUNT,
        "encoding": ("FIRST_COMBINADIC_ID_PLUS_175_GAP_MINUS_ONE_UNSIGNED_INTEGERS"),
        "strict_order_is_unrepresentable_to_violate": True,
        "includes_selected_orbit_representatives": True,
        "includes_profile_and_certificate_sha256": True,
    }
    exact_verifier = {
        "reconstruct_orbit_certificate": True,
        "decode_exactly_176_legal_combinadic_ids": True,
        "point_counter_width": "uint16",
        "pair_counter_width": "uint16",
        "required_point_counts": "33_VALUES_ALL_32",
        "required_pair_counts": "528_VALUES_ALL_5",
        "floating_point_operations": 0,
        "separate_duplicate_membership_or_uniqueness_scan": False,
        "repetition_scan": REPETITION_SCAN,
    }
    outcomes = {
        "positive": POSITIVE_OUTCOME,
        "bounded_negative": BOUNDED_NEGATIVE_OUTCOME,
        "invalid": INVALID_OUTCOME,
        "bounded_negative_is_global_nonexistence": False,
        "cyclic_subspace_exhaustion_is_global_nonexistence": False,
    }
    zero_work = {
        "legal_block_ids_visited": 0,
        "orbit_candidates_enumerated": 0,
        "solver_nodes_executed": 0,
        "certificate_blocks_generated": 0,
        "checkpoints_written": 0,
        "database_queries_during_capability": 0,
        "historical_rows_read": 0,
        "prior_scores_read": 0,
        "prior_predictions_read": 0,
        "prior_rankings_read": 0,
    }
    preregistration = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-feasibility-preregistration.v1"
        ),
        artifact_type=("prediction_v2_balanced_design_feasibility_preregistration"),
        body={
            "status": "COMPLETE",
            "preregistration_status": "FROZEN_NOT_EXECUTED",
            "constructor_family": CONSTRUCTOR_FAMILY,
            "parameters": {
                "point_count": POINT_COUNT,
                "block_size": BLOCK_SIZE,
                "block_count": BLOCK_COUNT,
                "point_replication_target": POINT_REPLICATION_TARGET,
                "pair_count": PAIR_COUNT,
                "pair_replication_target": PAIR_REPLICATION_TARGET,
            },
            "orbit_inventory": orbit_inventory,
            "representation_scope_and_symmetry_breaks": representation,
            "exact_multicover_equation": (
                "For each circular distance d in 1..16, "
                "sum(full_base_pair_count[d]) + "
                "sum(short_base_pair_count[d]/3) = 5."
            ),
            "canonical_variable_and_branch_order": branch_order,
            "hardware_independent_work_budget": work_budget,
            "checkpoint_contract": checkpoint_contract,
            "positive_certificate_format": certificate_format,
            "independent_exact_integer_verifier": exact_verifier,
            "three_valued_outcome_rule": outcomes,
            "result_blind": True,
            "existence_established": False,
            "nonexistence_established": False,
            "execution_authorized": False,
            "repetition_scan": REPETITION_SCAN,
            **zero_work,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "legacy_route_fallback": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain=("dehps.prediction-v2.balanced-design-feasibility-preregistration.v1"),
    )
    execution_handoff = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-feasibility-execution-handoff.v1"
        ),
        artifact_type=("prediction_v2_balanced_design_feasibility_execution_handoff"),
        body={
            "status": "COMPLETE",
            "preregistration_task": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
            ),
            "next_task": PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
            "preregistration_digest": preregistration["artifact_digest"],
            "constructor_family": CONSTRUCTOR_FAMILY,
            "scope": representation["scope"],
            "allowed_orbit_count_profiles": representation[
                "allowed_orbit_count_profiles"
            ],
            "positive_outcome": POSITIVE_OUTCOME,
            "bounded_negative_outcome": BOUNDED_NEGATIVE_OUTCOME,
            "invalid_outcome": INVALID_OUTCOME,
            "bounded_negative_is_global_nonexistence": False,
            "execution_authorized": False,
            "result_blind": True,
            "repetition_scan": REPETITION_SCAN,
            **zero_work,
            "new_evidence_created": False,
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
        },
        parent_digests=(*parent_digests, str(preregistration["artifact_digest"])),
        domain=("dehps.prediction-v2.balanced-design-feasibility-execution-handoff.v1"),
    )
    completion = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-feasibility-"
            "preregistration-completion.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_feasibility_preregistration_completion"
        ),
        body={
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_COMPLETION_FACT
            ),
            "source_contract_digest": source_digest,
            "feasibility_specification_digest": feasibility_specification[
                "artifact_digest"
            ],
            "feasibility_preregistration_handoff_digest": (
                feasibility_preregistration_handoff["artifact_digest"]
            ),
            "feasibility_completion_digest": feasibility_completion["artifact_digest"],
            "feasibility_mainline_execution_digest": feasibility_mainline_execution[
                "artifact_digest"
            ],
            "preregistration_digest": preregistration["artifact_digest"],
            "execution_handoff_digest": execution_handoff["artifact_digest"],
            "registered_child_count": 3,
            "preregistration_status": "FROZEN_NOT_EXECUTED",
            "constructor_family": CONSTRUCTOR_FAMILY,
            "result_blind": True,
            "existence_established": False,
            "nonexistence_established": False,
            "execution_authorized": False,
            "repetition_scan": REPETITION_SCAN,
            **zero_work,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "legacy_route_fallback": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(preregistration["artifact_digest"]),
            str(execution_handoff["artifact_digest"]),
        ),
        domain=(
            "dehps.prediction-v2.balanced-design-feasibility-"
            "preregistration-completion.v1"
        ),
    )
    return PredictionV2BalancedDesignFeasibilityPreregistrationRun(
        preregistration=preregistration,
        execution_handoff=execution_handoff,
        completion=completion,
    )


def replay_prediction_v2_balanced_design_feasibility_preregistration(
    *,
    source_contract: Mapping[str, Any],
    feasibility_specification: Mapping[str, Any],
    feasibility_preregistration_handoff: Mapping[str, Any],
    feasibility_completion: Mapping[str, Any],
    feasibility_mainline_execution: Mapping[str, Any],
) -> tuple[PredictionV2BalancedDesignFeasibilityPreregistrationRun, dict[str, Any]]:
    run = build_prediction_v2_balanced_design_feasibility_preregistration_artifacts(
        source_contract=source_contract,
        feasibility_specification=feasibility_specification,
        feasibility_preregistration_handoff=feasibility_preregistration_handoff,
        feasibility_completion=feasibility_completion,
        feasibility_mainline_execution=feasibility_mainline_execution,
    )
    return run, {
        "schema_version": (
            "dehps-prediction-v2-balanced-design-feasibility-preregistration-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "preregistration_status": "FROZEN_NOT_EXECUTED",
        "workload_rerun": False,
        "legal_block_ids_revisited": 0,
        "orbit_candidates_replayed": 0,
        "solver_nodes_replayed": 0,
        "certificate_blocks_regenerated": 0,
        "checkpoints_read": 0,
        "database_queries_during_replay": 0,
        "historical_rows_read": 0,
        "prior_scores_read": 0,
        "prior_predictions_read": 0,
        "prior_rankings_read": 0,
        "manual_input_assembly": False,
        "repetition_scan": REPETITION_SCAN,
        "next_consumer": PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
    }


def _validate_parent_artifacts(
    *,
    feasibility_specification: Mapping[str, Any],
    feasibility_preregistration_handoff: Mapping[str, Any],
    feasibility_completion: Mapping[str, Any],
    feasibility_mainline_execution: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    _verify_artifact(
        feasibility_specification,
        domain="dehps.prediction-v2.balanced-design-feasibility.v1",
    )
    _verify_artifact(
        feasibility_preregistration_handoff,
        domain=(
            "dehps.prediction-v2.balanced-design-feasibility-preregistration-handoff.v1"
        ),
    )
    _verify_artifact(
        feasibility_completion,
        domain="dehps.prediction-v2.balanced-design-feasibility-completion.v1",
    )
    _verify_artifact(
        feasibility_mainline_execution,
        domain="dehps.research-os.mainline-execution.v1",
    )
    observed = (
        str(feasibility_specification.get("artifact_digest")),
        str(feasibility_preregistration_handoff.get("artifact_digest")),
        str(feasibility_completion.get("artifact_digest")),
        str(feasibility_mainline_execution.get("artifact_digest")),
    )
    if require_registered_identities and observed != (
        FEASIBILITY_SPECIFICATION_DIGEST,
        FEASIBILITY_PREREGISTRATION_HANDOFF_DIGEST,
        FEASIBILITY_COMPLETION_DIGEST,
        FEASIBILITY_MAINLINE_EXECUTION_DIGEST,
    ):
        raise PredictionV2BalancedDesignFeasibilityPreregistrationError(
            "balanced_design_preregistration_registered_identity_changed"
        )
    if (
        feasibility_specification.get("status") != "COMPLETE"
        or feasibility_specification.get("design_status") != "FROZEN_NOT_EXECUTED"
        or feasibility_specification.get("parameters", {}).get("legal_block_count")
        != LEGAL_BLOCK_COUNT
        or feasibility_specification.get("existence_established") is not False
        or feasibility_specification.get("nonexistence_established") is not False
        or feasibility_specification.get("result_blind") is not True
        or feasibility_specification.get("repetition_scan") != REPETITION_SCAN
        or feasibility_preregistration_handoff.get("status") != "COMPLETE"
        or feasibility_preregistration_handoff.get("feasibility_specification_digest")
        != feasibility_specification.get("artifact_digest")
        or feasibility_preregistration_handoff.get("result_blind") is not True
        or feasibility_preregistration_handoff.get("repetition_scan") != REPETITION_SCAN
        or feasibility_completion.get("status") != "COMPLETE"
        or feasibility_completion.get("completion_fact")
        != "prediction-v2-balanced-design-feasibility-design:COMPLETE"
        or feasibility_completion.get("feasibility_specification_digest")
        != feasibility_specification.get("artifact_digest")
        or feasibility_completion.get("preregistration_handoff_digest")
        != feasibility_preregistration_handoff.get("artifact_digest")
        or feasibility_completion.get("solver_nodes_executed") != 0
        or feasibility_completion.get("candidate_blocks_generated") != 0
        or feasibility_completion.get("repetition_scan") != REPETITION_SCAN
        or feasibility_mainline_execution.get("status") != "COMPLETE"
        or feasibility_mainline_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or feasibility_mainline_execution.get("task_key")
        != "prediction-v2-next-result-blind-research-intake"
        or feasibility_mainline_execution.get("capability")
        != "prediction_v2_balanced_design_feasibility_design"
        or feasibility_mainline_execution.get("feasibility_specification_digest")
        != feasibility_specification.get("artifact_digest")
        or feasibility_mainline_execution.get("preregistration_handoff_digest")
        != feasibility_preregistration_handoff.get("artifact_digest")
        or feasibility_mainline_execution.get("feasibility_completion_digest")
        != feasibility_completion.get("artifact_digest")
        or feasibility_mainline_execution.get("solver_nodes_executed") != 0
        or feasibility_mainline_execution.get("candidate_blocks_generated") != 0
        or feasibility_mainline_execution.get("repetition_scan") != REPETITION_SCAN
        or feasibility_mainline_execution.get("evidence_created") is not False
        or feasibility_mainline_execution.get("new_model_created") is not False
        or feasibility_mainline_execution.get("production_action") != "none"
    ):
        raise PredictionV2BalancedDesignFeasibilityPreregistrationError(
            "balanced_design_preregistration_parent_consistency_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if frozen != _expected_frozen_contract():
        raise PredictionV2BalancedDesignFeasibilityPreregistrationError(
            "balanced_design_preregistration_frozen_contract_changed"
        )


def _expected_frozen_contract() -> dict[str, Any]:
    return {
        "task_key": PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY,
        "capability": (
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_CAPABILITY
        ),
        "completion_fact": (
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_COMPLETION_FACT
        ),
        "approved_external_event": (
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_APPROVED_EVENT
        ),
        "next_consumer": PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
        "registered_input_digests": [
            FEASIBILITY_SPECIFICATION_DIGEST,
            FEASIBILITY_PREREGISTRATION_HANDOFF_DIGEST,
            FEASIBILITY_COMPLETION_DIGEST,
            FEASIBILITY_MAINLINE_EXECUTION_DIGEST,
        ],
        "constructor_family": CONSTRUCTOR_FAMILY,
        "exact_parameters": {
            "point_count": POINT_COUNT,
            "block_size": BLOCK_SIZE,
            "block_count": BLOCK_COUNT,
            "point_replication_target": POINT_REPLICATION_TARGET,
            "pair_count": PAIR_COUNT,
            "pair_replication_target": PAIR_REPLICATION_TARGET,
        },
        "orbit_inventory": {
            "legal_block_count": LEGAL_BLOCK_COUNT,
            "short_orbit_count": SHORT_ORBIT_COUNT,
            "blocks_per_short_orbit": SHORT_ORBIT_SIZE,
            "full_orbit_count": FULL_ORBIT_COUNT,
            "blocks_per_full_orbit": FULL_ORBIT_SIZE,
            "inventory_identity": "55 + 33561*33 = 1107568",
        },
        "representation_scope_and_symmetry_breaks": {
            "scope": (
                "ALL_AND_ONLY_Z33_TRANSLATION_INVARIANT_SIMPLE_2_DESIGN_CANDIDATES"
            ),
            "point_labels": "Z_33",
            "short_orbit_subgroup": [0, 11, 22],
            "short_orbit_representatives": (
                "UNION_OF_TWO_SUBGROUP_COSETS_WITH_QUOTIENT_DISTANCE_1_THROUGH_5"
            ),
            "canonical_full_orbit_representative": (
                "MINIMUM_COMBINADIC_ID_OVER_33_TRANSLATES"
            ),
            "pair_coordinates": "UNDIRECTED_CIRCULAR_DISTANCE_1_THROUGH_16",
            "allowed_orbit_count_profiles": [
                {"full_orbits": 5, "short_orbits": 1},
                {"full_orbits": 4, "short_orbits": 4},
            ],
            "other_automorphism_restrictions": "NONE",
        },
        "exact_multicover_equation": (
            "For each circular distance d in 1..16, "
            "sum(full_base_pair_count[d]) + "
            "sum(short_base_pair_count[d]/3) = 5."
        ),
        "canonical_variable_and_branch_order": {
            "profile_order": ["5_FULL_1_SHORT", "4_FULL_4_SHORT"],
            "short_subset_order": "LEXICOGRAPHIC_BY_QUOTIENT_DISTANCE",
            "signature_grouping": (
                "IDENTICAL_16_INTEGER_VECTORS_WITH_EXACT_MULTIPLICITY"
            ),
            "branch_coordinate": ("FEWEST_COMPATIBLE_SIGNATURES_THEN_LOWEST_DISTANCE"),
            "candidate_order": (
                "LEXICOGRAPHIC_SIGNATURE_THEN_MINIMUM_REPRESENTATIVE_ID"
            ),
            "selection_order": "STRICTLY_INCREASING_ORBIT_REPRESENTATIVE_ID",
            "full_signature_filter": (
                "REJECT_IF_ANY_DISTANCE_COMPONENT_EXCEEDS_CURRENT_NONNEGATIVE_RESIDUAL"
            ),
            "seed_policy": "NONE",
        },
        "hardware_independent_work_budget": {
            "legal_block_ids_visited": LEGAL_BLOCK_COUNT,
            "maximum_full_orbit_representatives": FULL_ORBIT_COUNT,
            "maximum_short_orbit_representatives": SHORT_ORBIT_COUNT,
            "maximum_multicover_node_expansions": 100_000_000,
            "checkpoint_interval_node_expansions": 1_000_000,
            "maximum_resident_bytes": 4_294_967_296,
            "wall_clock_is_not_a_decision_boundary": True,
        },
        "checkpoint_contract": {
            "append_only": True,
            "binds_source_contract_digest": True,
            "binds_preregistration_digest": True,
            "binds_profile_short_subset_branch_stack_residual_and_node_count": True,
            "resume_from_latest_valid_checkpoint_only": True,
            "completed_branch_skip": True,
            "changed_identity_outcome": INVALID_OUTCOME,
        },
        "positive_certificate_format": {
            "block_count": BLOCK_COUNT,
            "encoding": (
                "FIRST_COMBINADIC_ID_PLUS_175_GAP_MINUS_ONE_UNSIGNED_INTEGERS"
            ),
            "strict_order_is_unrepresentable_to_violate": True,
            "includes_selected_orbit_representatives": True,
            "includes_profile_and_certificate_sha256": True,
        },
        "independent_exact_integer_verifier": {
            "reconstruct_orbit_certificate": True,
            "decode_exactly_176_legal_combinadic_ids": True,
            "point_counter_width": "uint16",
            "pair_counter_width": "uint16",
            "required_point_counts": "33_VALUES_ALL_32",
            "required_pair_counts": "528_VALUES_ALL_5",
            "floating_point_operations": 0,
            "separate_duplicate_membership_or_uniqueness_scan": False,
            "repetition_scan": REPETITION_SCAN,
        },
        "three_valued_outcome_rule": {
            "positive": POSITIVE_OUTCOME,
            "bounded_negative": BOUNDED_NEGATIVE_OUTCOME,
            "invalid": INVALID_OUTCOME,
            "bounded_negative_is_global_nonexistence": False,
            "cyclic_subspace_exhaustion_is_global_nonexistence": False,
        },
        "result_blind": True,
        "registered_child_count": 3,
        "registered_total_with_mainline_execution": 4,
        "legal_block_ids_visited": 0,
        "orbit_candidates_enumerated": 0,
        "solver_nodes_executed": 0,
        "certificate_blocks_generated": 0,
        "checkpoints_written": 0,
        "database_queries": 0,
        "historical_rows_read": 0,
        "prior_scores_read": 0,
        "prior_predictions_read": 0,
        "prior_rankings_read": 0,
        "new_evidence_created": False,
        "new_model_created": False,
        "candidate_expert_authorized": False,
        "promotion_gate_opened": False,
        "p3_authorized": False,
        "historical_evidence": "INCONCLUSIVE",
        "prediction_v2_mode": "SHADOW_ONLY",
        "prediction_v2_route": "BASELINE_ONLY",
        "legacy_route_fallback": False,
        "production_action": "none",
        "repetition_scan": REPETITION_SCAN,
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
        raise PredictionV2BalancedDesignFeasibilityPreregistrationError(
            "balanced_design_preregistration_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
