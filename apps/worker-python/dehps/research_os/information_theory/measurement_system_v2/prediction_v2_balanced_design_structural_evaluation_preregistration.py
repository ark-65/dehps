from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY = (
    "prediction-v2-balanced-design-structural-evaluation-preregistration"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_CAPABILITY = (
    "prediction_v2_balanced_design_structural_evaluation_preregistration"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_COMPLETION_FACT = (
    "prediction-v2-balanced-design-structural-evaluation-preregistration:COMPLETE"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY = (
    "prediction-v2-balanced-design-structural-evaluation-execution"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "prediction-v2-balanced-design-structural-evaluation-preregistration-source-v1.json"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_APPROVED_EVENT = "research-contract:prediction-v2-balanced-design-structural-evaluation-preregistration:approved"

DESIGN_EXECUTION_DIGEST = (
    "d0d4291feca83ce48047277e7cf009fa050bf7d4c4314044ef98e62bb1d0cbef"
)
DESIGN_DIGEST = "43bba42d1be7c7be73949cc151d6d7ad3175a0e9da01929e4c1fd047c4346fa1"
PREREGISTRATION_HANDOFF_DIGEST = (
    "daa9d7c844fed0c317d821089a7e6dd92d66bffec90d807c238fd3d86d0a336c"
)
DESIGN_COMPLETION_DIGEST = (
    "a8f067597496f7d81aa41aa3eb9c79416062415f473a4e3fef6ef9c56d6691c0"
)
DESIGN_EXECUTION_ID = "214c1bfb29b258c532d14f73105e54e18468ed9ef7adb20176f8210740aa8984"
FIXED_CERTIFICATE_DIGEST = (
    "b7a0069edef9f6a2aeec3f2205a50a63ba39594ed555c3c89b108830cd3c28db"
)

CONFIRMATORY_ENDPOINT = "triple_collision_mass"
PRIMARY_NULL = "Z33_ORBIT_PROFILE_MATCHED_WITHOUT_REPLACEMENT_5_FULL_1_SHORT_B176"
SECONDARY_NULL = "UNIFORM_PREFIX_WITHOUT_REPLACEMENT_FROM_ALL_1107568_LEGAL_BLOCKS_B176"
POSITIVE_OUTCOME = "HIGHER_ORDER_STRUCTURAL_HOLDOUT_ADVANTAGE_WITHIN_MATCHED_NULL_ONLY"
NULL_OUTCOME = "PAIR_BALANCE_ONLY_NO_PREREGISTERED_HIGHER_ORDER_ADVANTAGE"
REGRESSION_OUTCOME = "HIGHER_ORDER_STRUCTURAL_REGRESSION_AGAINST_MATCHED_NULL"
INVALID_OUTCOME = "INVALID_EVALUATION_NO_DECISION"
REPETITION_SCAN = "ABSENT_BY_CONSTRUCTION"
PRIMARY_REPLICATES = 9_999
SECONDARY_REPLICATES = 1_999
PRIMARY_DENOMINATOR = 10_000
SECONDARY_DENOMINATOR = 2_000
ALPHA_NUMERATOR = 1
ALPHA_DENOMINATOR = 100

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-balanced-design-structural-evaluation-preregistration-"
    "round-103-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-balanced-design-structural-evaluation-"
    "preregistration-round-103-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/"
    "prediction_v2_balanced_design_structural_evaluation_preregistration.py"
)
FROZEN_PROTOCOL_DIGEST = (
    "6092bb59c170aa53242e22e99da24561ab0fc0002e5a8960d7e1e4df8042e291"
)
FROZEN_CONTRACT_DIGEST = (
    "64c0b9f7209f7f160e3de243f42359c49ba3ceb71acdf926b9e102f8eb3bf375"
)


class PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2BalancedDesignStructuralEvaluationPreregistrationRun:
    preregistration: Mapping[str, Any]
    execution_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.preregistration, self.execution_handoff, self.completion


def load_prediction_v2_balanced_design_structural_evaluation_preregistration_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(
            f"balanced_design_structural_evaluation_preregistration_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-balanced-design-structural-evaluation-preregistration-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_balanced_design_structural_evaluation_preregistration_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 432
        or payload.get("research_execution_id") != 353
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 433
        or payload.get("engineering_execution_id") != 354
        or payload.get("result_blind") is not True
        or payload.get("candidate_evaluation_statistics_read") is not False
        or payload.get("null_replicates_executed") != 0
        or payload.get("database_queries") != 0
        or payload.get("historical_rows_read") != 0
        or payload.get("folds_executed") != 0
        or payload.get("duplicate_membership_uniqueness_or_repetition_scans") != 0
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
                "dehps.prediction-v2.balanced-design-structural-evaluation-"
                "preregistration-frozen-contract.v1"
            ),
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.prediction-v2.balanced-design-structural-evaluation-"
                "preregistration-source-set.v1"
            ),
        )
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(
            "balanced_design_structural_evaluation_preregistration_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(
            "balanced_design_structural_evaluation_preregistration_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_balanced_design_structural_evaluation_preregistration_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    entry = contract["source_entries"][0]
    relative = str(entry["path"])
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(
            f"balanced_design_structural_evaluation_preregistration_source_missing:{relative}"
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
        raise PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(
            f"balanced_design_structural_evaluation_preregistration_source_modified:{relative}"
        )


def build_prediction_v2_balanced_design_structural_evaluation_preregistration_artifacts(
    *,
    source_contract: Mapping[str, Any],
    design_execution: Mapping[str, Any],
    design: Mapping[str, Any],
    preregistration_handoff: Mapping[str, Any],
    design_completion: Mapping[str, Any],
    design_replay: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2BalancedDesignStructuralEvaluationPreregistrationRun:
    frozen = source_contract["frozen_contract"]
    _validate_frozen_contract(frozen)
    protocol = _expected_preregistration_contract()
    _validate_parent_artifacts(
        design_execution=design_execution,
        design=design,
        preregistration_handoff=preregistration_handoff,
        design_completion=design_completion,
        design_replay=design_replay,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(design_execution["artifact_digest"]),
        str(design["artifact_digest"]),
        str(preregistration_handoff["artifact_digest"]),
        str(design_completion["artifact_digest"]),
    )
    preregistration = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-"
            "preregistration.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_evaluation_preregistration"
        ),
        body={
            "status": "FROZEN",
            "fixed_candidate": protocol["fixed_candidate"],
            "primary_endpoint": protocol["primary_endpoint"],
            "random_stream": protocol["random_stream"],
            "primary_null": protocol["primary_null"],
            "secondary_null": protocol["secondary_null"],
            "inference": protocol["inference"],
            "outcome_mapping": protocol["outcome_mapping"],
            "secondary_diagnostics": protocol["secondary_diagnostics"],
            "resource_contract": protocol["resource_contract"],
            "invalid_execution_rules": protocol["invalid_execution_rules"],
            **_zero_work_boundary(),
            "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY,
        },
        parent_digests=parent_digests,
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-"
            "preregistration.v1"
        ),
    )
    handoff = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-"
            "execution-handoff.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_evaluation_execution_handoff"
        ),
        body={
            "status": "COMPLETE",
            "preregistration_artifact_digest": preregistration["artifact_digest"],
            "fixed_certificate_artifact_digest": FIXED_CERTIFICATE_DIGEST,
            "confirmatory_endpoint": CONFIRMATORY_ENDPOINT,
            "primary_null": PRIMARY_NULL,
            "primary_replicate_count": PRIMARY_REPLICATES,
            "secondary_null": SECONDARY_NULL,
            "secondary_replicate_count": SECONDARY_REPLICATES,
            "alpha": "1/100",
            "random_stream": "SHAKE256_COUNTER_MODE_RANDOM_BELOW_V1",
            "sampling": "PARTIAL_FISHER_YATES_WITHOUT_REPLACEMENT",
            "duplicate_validation_pass": False,
            "membership_validation_pass": False,
            "uniqueness_validation_pass": False,
            "execution_authorized": False,
            **_zero_work_boundary(),
            "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY,
        },
        parent_digests=(*parent_digests, str(preregistration["artifact_digest"])),
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-"
            "execution-handoff.v1"
        ),
    )
    completion = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-"
            "preregistration-completion.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_evaluation_"
            "preregistration_completion"
        ),
        body={
            "status": "COMPLETE",
            "completion_fact": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_COMPLETION_FACT,
            "source_contract_digest": source_digest,
            "design_execution_digest": design_execution["artifact_digest"],
            "preregistration_artifact_digest": preregistration["artifact_digest"],
            "execution_handoff_digest": handoff["artifact_digest"],
            "registered_child_count": 3,
            **_zero_work_boundary(),
            "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY,
        },
        parent_digests=(
            source_digest,
            str(preregistration["artifact_digest"]),
            str(handoff["artifact_digest"]),
        ),
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-"
            "preregistration-completion.v1"
        ),
    )
    return PredictionV2BalancedDesignStructuralEvaluationPreregistrationRun(
        preregistration=preregistration,
        execution_handoff=handoff,
        completion=completion,
    )


def replay_prediction_v2_balanced_design_structural_evaluation_preregistration(
    **kwargs: Any,
) -> tuple[
    PredictionV2BalancedDesignStructuralEvaluationPreregistrationRun,
    dict[str, Any],
]:
    run = build_prediction_v2_balanced_design_structural_evaluation_preregistration_artifacts(
        **kwargs
    )
    return run, {
        "schema_version": (
            "dehps-prediction-v2-balanced-design-structural-evaluation-"
            "preregistration-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "workload_rerun": False,
        "manual_input_assembly": False,
        "candidate_evaluation_statistics_read": False,
        "null_replicates_executed": 0,
        "database_queries_during_replay": 0,
        "historical_rows_read": 0,
        "folds_replayed": 0,
        "duplicate_membership_uniqueness_or_repetition_scans": 0,
        "repetition_scan": REPETITION_SCAN,
        "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY,
    }


def _validate_parent_artifacts(
    *,
    design_execution: Mapping[str, Any],
    design: Mapping[str, Any],
    preregistration_handoff: Mapping[str, Any],
    design_completion: Mapping[str, Any],
    design_replay: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts_and_domains = (
        (design_execution, "dehps.research-os.mainline-execution.v1"),
        (
            design,
            "dehps.prediction-v2.balanced-design-structural-evaluation-design.v1",
        ),
        (
            preregistration_handoff,
            "dehps.prediction-v2.balanced-design-structural-evaluation-preregistration-handoff.v1",
        ),
        (
            design_completion,
            "dehps.prediction-v2.balanced-design-structural-evaluation-design-completion.v1",
        ),
    )
    for artifact, domain in artifacts_and_domains:
        _verify_artifact(artifact, domain=domain)
    observed = tuple(
        str(artifact.get("artifact_digest")) for artifact, _ in artifacts_and_domains
    )
    if require_registered_identities and observed != (
        DESIGN_EXECUTION_DIGEST,
        DESIGN_DIGEST,
        PREREGISTRATION_HANDOFF_DIGEST,
        DESIGN_COMPLETION_DIGEST,
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(
            "balanced_design_structural_evaluation_preregistration_registered_identity_changed"
        )
    if (
        design_execution.get("execution_id") != DESIGN_EXECUTION_ID
        or design_execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or design_execution.get("design_artifact_digest")
        != design.get("artifact_digest")
        or design_execution.get("preregistration_handoff_digest")
        != preregistration_handoff.get("artifact_digest")
        or design_execution.get("design_completion_digest")
        != design_completion.get("artifact_digest")
        or design.get("status") != "COMPLETE"
        or design.get("fixed_candidate", {}).get("certificate_artifact_digest")
        != FIXED_CERTIFICATE_DIGEST
        or design.get("confirmatory_endpoint") != CONFIRMATORY_ENDPOINT
        or design.get("repetition_scan") != REPETITION_SCAN
        or design.get("separate_duplicate_membership_or_uniqueness_scan") is not False
        or preregistration_handoff.get("design_artifact_digest")
        != design.get("artifact_digest")
        or preregistration_handoff.get("evaluation_execution_authorized") is not False
        or preregistration_handoff.get("candidate_evaluation_statistics_read")
        is not False
        or preregistration_handoff.get("null_replicates_executed") != 0
        or preregistration_handoff.get("repetition_scan") != REPETITION_SCAN
        or design_completion.get("completion_fact")
        != "prediction-v2-balanced-design-structural-evaluation-design:COMPLETE"
        or design_completion.get("design_artifact_digest")
        != design.get("artifact_digest")
        or design_completion.get("preregistration_handoff_digest")
        != preregistration_handoff.get("artifact_digest")
        or design_replay.get("status") != "REPLAY_VERIFIED"
        or design_replay.get("same_registered_content") is not True
        or design_replay.get("workload_rerun") is not False
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(
            "balanced_design_structural_evaluation_preregistration_parent_consistency_invalid"
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
            design_execution,
            design,
            preregistration_handoff,
            design_completion,
        )
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(
            "balanced_design_structural_evaluation_preregistration_parent_claim_boundary_invalid"
        )


def _zero_work_boundary() -> dict[str, Any]:
    return {
        "candidate_evaluation_statistics_read": False,
        "null_replicates_executed": 0,
        "legal_blocks_enumerated": 0,
        "database_queries_during_capability": 0,
        "historical_rows_read": 0,
        "folds_executed": 0,
        "duplicate_membership_uniqueness_or_repetition_scans": 0,
        "repetition_scan": REPETITION_SCAN,
        "historical_evidence": "INCONCLUSIVE",
        "prediction_v2_mode": "SHADOW_ONLY",
        "prediction_v2_route": "BASELINE_ONLY",
        "evidence_created": False,
        "new_model_created": False,
        "promotion_gate_opened": False,
        "p3_authorized": False,
        "production_action": "none",
    }


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if dict(frozen) != _expected_frozen_contract():
        raise PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(
            "balanced_design_structural_evaluation_preregistration_frozen_contract_changed"
        )


def _expected_frozen_contract() -> dict[str, Any]:
    return {
        "task_key": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY,
        "capability": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_CAPABILITY,
        "completion_fact": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_COMPLETION_FACT,
        "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY,
        "registered_input_digests": [
            DESIGN_EXECUTION_DIGEST,
            DESIGN_DIGEST,
            PREREGISTRATION_HANDOFF_DIGEST,
            DESIGN_COMPLETION_DIGEST,
        ],
        "research_request_id": 432,
        "research_execution_id": 353,
        "frozen_protocol_digest": FROZEN_PROTOCOL_DIGEST,
        "primary_replicate_count": PRIMARY_REPLICATES,
        "secondary_replicate_count": SECONDARY_REPLICATES,
        "alpha": "1/100",
        "duplicate_validation_pass": False,
        "membership_validation_pass": False,
        "uniqueness_validation_pass": False,
        "repetition_scan": REPETITION_SCAN,
        "candidate_evaluation_statistics_read": False,
        "null_replicates_executed": 0,
        "database_queries": 0,
        "historical_rows_read": 0,
        "folds_executed": 0,
        "new_evidence_created": False,
        "new_model_created": False,
        "promotion_gate_opened": False,
        "p3_authorized": False,
        "production_action": "none",
    }


def _expected_preregistration_contract() -> dict[str, Any]:
    return {
        "task_key": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_TASK_KEY,
        "capability": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_CAPABILITY,
        "completion_fact": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_PREREGISTRATION_COMPLETION_FACT,
        "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY,
        "registered_input_digests": [
            DESIGN_EXECUTION_DIGEST,
            DESIGN_DIGEST,
            PREREGISTRATION_HANDOFF_DIGEST,
            DESIGN_COMPLETION_DIGEST,
        ],
        "fixed_candidate": {
            "certificate_artifact_digest": FIXED_CERTIFICATE_DIGEST,
            "block_count": 176,
            "candidate_endpoint_reads_before_execution": 0,
            "automatic_portfolio_mutation": False,
        },
        "primary_endpoint": {
            "name": CONFIRMATORY_ENDPOINT,
            "formula": "sum_over_T_in_C(33,3)_of_C(c_T,2)",
            "direction": "lower_is_better",
            "numeric_type": "exact_nonnegative_integer",
            "floating_tolerance": 0,
            "candidate_evaluations": 1,
        },
        "random_stream": {
            "algorithm": "SHAKE256_COUNTER_MODE_RANDOM_BELOW_V1",
            "byte_order": "big",
            "counter_origin": 0,
            "range_reduction": (
                "draw_minimum_bytes_mask_unused_high_bits_and_advance_counter_"
                "until_value_is_less_than_exclusive_bound"
            ),
            "range_reduction_is_duplicate_validation": False,
            "domain_template": (
                "dehps|prediction-v2|balanced-design|structural-evaluation|v1|"
                "{family}|replicate={zero_based_index}|stream"
            ),
            "worker_count_affects_stream": False,
            "schedule_order_affects_stream": False,
            "adaptive_seed_retry": False,
        },
        "primary_null": {
            "name": PRIMARY_NULL,
            "replicate_count": PRIMARY_REPLICATES,
            "full_orbit_inventory_count": 33_561,
            "short_orbit_inventory_count": 5,
            "sample": (
                "partial_fisher_yates_prefix_of_length_5_from_full_inventory_"
                "and_length_1_from_short_inventory"
            ),
            "expansion": "canonical_complete_Z33_orbit_expansion_in_frozen_inventory_order",
            "expected_block_count": 176,
            "metric_based_rejection": False,
            "duplicate_validation_pass": False,
            "membership_validation_pass": False,
            "uniqueness_validation_pass": False,
            "repetition_scan": REPETITION_SCAN,
        },
        "secondary_null": {
            "name": SECONDARY_NULL,
            "replicate_count": SECONDARY_REPLICATES,
            "legal_block_count": 1_107_568,
            "sample": (
                "partial_fisher_yates_prefix_of_length_176_from_canonical_"
                "lexicographic_legal_block_ids"
            ),
            "expected_block_count": 176,
            "gates_primary_decision": False,
            "may_rescue_primary_failure": False,
            "metric_based_rejection": False,
            "duplicate_validation_pass": False,
            "membership_validation_pass": False,
            "uniqueness_validation_pass": False,
            "repetition_scan": REPETITION_SCAN,
        },
        "inference": {
            "alpha_numerator": ALPHA_NUMERATOR,
            "alpha_denominator": ALPHA_DENOMINATOR,
            "primary_lower_tail_numerator": "1+count(primary_null_mass<=candidate_mass)",
            "primary_upper_tail_numerator": "1+count(primary_null_mass>=candidate_mass)",
            "primary_denominator": PRIMARY_DENOMINATOR,
            "secondary_denominator": SECONDARY_DENOMINATOR,
            "ties_included": True,
            "multiple_testing_adjustment": "not_applicable_one_confirmatory_endpoint",
            "secondary_metrics_gate_success": False,
            "weighted_score_allowed": False,
        },
        "outcome_mapping": {
            "positive": f"primary_lower_tail_numerator<=100 -> {POSITIVE_OUTCOME}",
            "regression": f"primary_upper_tail_numerator<=100 -> {REGRESSION_OUTCOME}",
            "null": f"otherwise -> {NULL_OUTCOME}",
            "invalid": (
                "any_identity_algorithm_count_resource_or_completeness_violation -> "
                f"{INVALID_OUTCOME}"
            ),
            "secondary_null_can_change_outcome": False,
            "prediction_probability_claim_allowed": False,
            "expected_payout_claim_allowed": False,
            "operational_utility_claim_allowed": False,
        },
        "secondary_diagnostics": {
            "metrics": [
                "quadruple_collision_mass",
                "quintuple_collision_mass",
                "block_intersection_histogram_0_through_5",
                "maximum_block_intersection",
                "minimum_replacement_distance",
            ],
            "candidate_computations": 1,
            "null_diagnostic_replicates_per_family": 199,
            "null_diagnostic_subset": "first_199_replicate_indices_only",
            "may_change_primary_outcome": False,
        },
        "resource_contract": {
            "local_machine_only": True,
            "maximum_wall_seconds": 1_800,
            "maximum_resident_memory_bytes": 4_294_967_296,
            "worker_range": "1_through_detected_logical_cpu_count",
            "deterministic_across_worker_count": True,
            "database_queries": 0,
            "historical_rows_read": 0,
            "csv_reads": 0,
            "model_fits": 0,
            "partial_timeout_acceptance": False,
            "checkpoint_resume": (
                "allowed_only_by_immutable_replicate_index_with_digest_verified_"
                "completed_chunks_and_no_recomputation_or_skipping"
            ),
            "same_execution_retuning": False,
        },
        "invalid_execution_rules": [
            "any_parent_certificate_or_source_identity_mismatch",
            "candidate_endpoint_read_before_frozen_preregistration",
            "sample_or_metric_algorithm_drift",
            "replicate_count_or_domain_drift",
            "metric_based_reroll_or_seed_retry",
            "duplicate_membership_uniqueness_or_repetition_validation_pass",
            "missing_or_extra_replicate_index",
            "partial_timeout_output",
            "resource_contract_violation",
            "secondary_null_changes_primary_outcome",
            "historical_prediction_ranking_score_or_database_input",
            "post_hoc_alpha_tolerance_threshold_or_metric_change",
        ],
        "registered_child_count": 3,
        "registered_total_with_mainline_execution": 4,
        "candidate_evaluation_statistics_read": False,
        "null_replicates_executed": 0,
        "database_queries": 0,
        "historical_rows_read": 0,
        "folds_executed": 0,
        "duplicate_membership_uniqueness_or_repetition_scans": 0,
        "repetition_scan": REPETITION_SCAN,
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
        raise PredictionV2BalancedDesignStructuralEvaluationPreregistrationError(
            "balanced_design_structural_evaluation_preregistration_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
