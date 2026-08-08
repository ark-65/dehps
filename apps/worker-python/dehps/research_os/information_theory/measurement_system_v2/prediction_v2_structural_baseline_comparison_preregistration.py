from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY = (
    "prediction-v2-structural-baseline-comparison-preregistration"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_CAPABILITY = (
    "prediction_v2_structural_baseline_comparison_preregistration"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_COMPLETION_FACT = (
    "prediction-v2-structural-baseline-comparison-preregistration:COMPLETE"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE_CONTRACT_PATH = (
    Path(
        "configs/research-os/"
        "prediction-v2-structural-baseline-comparison-preregistration-source-v1.json"
    )
)
PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY = (
    "prediction-v2-structural-route-decision"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY = (
    "prediction-v2-structural-baseline-comparison-execution"
)

ROUTE_EXECUTION_DIGEST = (
    "13b30739d25f52e2b007c8d9720aa9d45e99825c43fde0aae4e7f1e4e7918b23"
)
ROUTE_DECISION_DIGEST = (
    "4881eb35f0fb0e8ee7d4ff3be624f75938d9b7b818fb8164ca86ccb842a22484"
)
ROUTE_HANDOFF_DIGEST = (
    "958e36d3cd956b70c451a64bda36ba21fee2216ada4d34e1093773de58b5d3ba"
)
ROUTE_COMPLETION_DIGEST = (
    "8780ded7346730cb69d15ac22b096927c7099bc11107f541a214a3c2794e9f0f"
)

ROUTE_DECISION = (
    "ROUTE_TO_NON_PREDICTIVE_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION"
)
STRUCTURAL_ARTIFACT_ROLE = "OFFLINE_STRUCTURAL_DIVERSIFICATION_REFERENCE_ONLY"
ARCHIVE_CONDITION = (
    "IF_RESULT_BLIND_PREREGISTRATION_CANNOT_FREEZE_STRONGER_SIMPLE_SAME_BUDGET_"
    "LABEL_SYMMETRIC_BASELINES_AND_AN_OBSERVED_RESULT_INDEPENDENT_FAILURE_RULE_"
    "ARCHIVE_AS_ENGINEERING_EVIDENCE_ONLY"
)
PREREGISTRATION_DECISION = (
    "FREEZE_THREE_CLASS_COMPLEXITY_MATCHED_RESULT_BLIND_COMPARISON"
)

LEGAL_LABEL_COUNT = 33
COMBINATION_SIZE = 6
LEGAL_COMBINATION_COUNT = 1_107_568
PORTFOLIO_BUDGET = 176
BASELINE_REPLICATES_PER_CLASS = 128
CANDIDATE_CHUNK_SIZE = 256
CANDIDATE_CONSIDERATIONS_PER_REPLICATE = 45_056
CANDIDATE_CONSIDERATIONS_PER_CLASS = 5_767_168
TOTAL_CANDIDATE_CONSIDERATIONS = 17_301_504
MASTER_SEED_HEX = "bbe0440383bfa1b55395ab61a195b0f1956a6d406c78b54ed318e353bdf82c3b"
CANDIDATE_STREAM = (
    "SHA256_REJECTION_SAMPLED_PARTIAL_FISHER_YATES_WITHOUT_REPLACEMENT_V1"
)
CANDIDATE_STREAM_DOMAIN = (
    "dehps.prediction-v2.structural-baseline-comparison.candidate-stream.v1"
)
COMBINATION_INDEXING = "ZERO_BASED_LEXICOGRAPHIC_COMBINADIC_6_OF_33_V1"
TIE_BREAK = "LOWEST_CANDIDATE_STREAM_POSITION"
CHECKPOINT_EVERY_PORTFOLIO_STEPS = 16
PARALLEL_WORKERS = 22
WALL_CLOCK_LIMIT_SECONDS = 7_200
RESIDENT_MEMORY_LIMIT_BYTES = 4_294_967_296

BASELINE_CLASSES = (
    {
        "class_id": "SINGLETON_FIRST_GREEDY_V1",
        "selection_tuple": [
            "singleton_square_sum:min",
            "pair_square_sum:min",
            "minimum_replacement_distance:max",
            "sum_pairwise_replacement_distance:max",
            "stream_position:min",
        ],
    },
    {
        "class_id": "PAIR_FIRST_GREEDY_V1",
        "selection_tuple": [
            "pair_square_sum:min",
            "singleton_square_sum:min",
            "minimum_replacement_distance:max",
            "sum_pairwise_replacement_distance:max",
            "stream_position:min",
        ],
    },
    {
        "class_id": "DISTANCE_FIRST_GREEDY_V1",
        "selection_tuple": [
            "minimum_replacement_distance:max",
            "sum_pairwise_replacement_distance:max",
            "singleton_square_sum:min",
            "pair_square_sum:min",
            "stream_position:min",
        ],
    },
)
METRICS = (
    {"key": "singleton_square_sum", "direction": "minimize"},
    {"key": "pair_square_sum", "direction": "minimize"},
    {"key": "minimum_replacement_distance", "direction": "maximize"},
    {"key": "sum_pairwise_replacement_distance", "direction": "maximize"},
)
STRICT_DOMINANCE = "NO_WORSE_ON_ALL_FOUR_AND_STRICTLY_BETTER_ON_AT_LEAST_ONE"
REQUIRED_CANDIDATE_DOMINATED_REPLICATES_PER_CLASS = 122
MAXIMUM_BASELINE_REPLICATES_DOMINATING_CANDIDATE_PER_CLASS = 0
SUPPORTED_LABEL = "SUPPORTED_BEYOND_FROZEN_TRANSPARENT_BASELINES"
FAILURE_LABEL = "ARCHIVE_AS_ENGINEERING_EVIDENCE_ONLY"
INVALID_LABEL = "INVALID_EXECUTION_NO_DECISION"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-structural-baseline-comparison-"
    "preregistration-round-74-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-structural-baseline-comparison-"
    "preregistration-round-75-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/"
    "prediction_v2_structural_baseline_comparison_preregistration.py"
)
FROZEN_CONTRACT_DIGEST = (
    "f571d00e71b305bf416906fa34506ec0e84ae99b57935bc4fe180e6ae715b40d"
)


class PredictionV2StructuralBaselineComparisonPreregistrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2StructuralBaselineComparisonPreregistrationRun:
    preregistration: Mapping[str, Any]
    execution_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.preregistration, self.execution_handoff, self.completion


def load_prediction_v2_structural_baseline_comparison_preregistration_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2StructuralBaselineComparisonPreregistrationError(
            f"structural_baseline_preregistration_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-structural-baseline-comparison-preregistration-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_structural_baseline_comparison_preregistration_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 402
        or payload.get("research_execution_id") != 323
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 403
        or payload.get("engineering_execution_id") != 324
        or payload.get("result_blind") is not True
        or payload.get("portfolio_results_read") != 0
        or payload.get("database_queries") != 0
        or payload.get("historical_rows_read") != 0
        or payload.get("folds_executed") != 0
        or payload.get("bootstrap_children_executed") != 0
        or payload.get("baseline_proposals_executed") != 0
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
                "dehps.prediction-v2.structural-baseline-comparison-"
                "preregistration-frozen-contract.v1"
            ),
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.prediction-v2.structural-baseline-comparison-"
                "preregistration-source-set.v1"
            ),
        )
    ):
        raise PredictionV2StructuralBaselineComparisonPreregistrationError(
            "structural_baseline_preregistration_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2StructuralBaselineComparisonPreregistrationError(
            "structural_baseline_preregistration_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_structural_baseline_comparison_preregistration_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2StructuralBaselineComparisonPreregistrationError(
                f"structural_baseline_preregistration_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2StructuralBaselineComparisonPreregistrationError(
                f"structural_baseline_preregistration_source_modified:{relative}"
            )


def build_prediction_v2_structural_baseline_comparison_preregistration_artifacts(
    *,
    source_contract: Mapping[str, Any],
    route_execution: Mapping[str, Any],
    route_decision: Mapping[str, Any],
    route_handoff: Mapping[str, Any],
    route_completion: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2StructuralBaselineComparisonPreregistrationRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        route_execution=route_execution,
        route_decision=route_decision,
        route_handoff=route_handoff,
        route_completion=route_completion,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(route_execution["artifact_digest"]),
        str(route_decision["artifact_digest"]),
        str(route_handoff["artifact_digest"]),
        str(route_completion["artifact_digest"]),
    )
    program = _program_contract()
    comparison = _comparison_contract()
    preregistration = _artifact(
        schema_version=(
            "dehps-prediction-v2-structural-baseline-comparison-preregistration.v1"
        ),
        artifact_type=("prediction_v2_structural_baseline_comparison_preregistration"),
        body={
            "status": "COMPLETE",
            "preregistration_status": "FROZEN_RESULT_BLIND",
            "decision": PREREGISTRATION_DECISION,
            "route_decision": ROUTE_DECISION,
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "result_blind": True,
            "portfolio_results_read": 0,
            "program": program,
            "comparison_contract": comparison,
            "comparison_execution_authorized": True,
            "portfolio_activation_authorized": False,
            "decision_usefulness_established": False,
            "prediction_probability_claim": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "baseline_proposals_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-preregistration.v1"
        ),
    )
    execution_handoff = _artifact(
        schema_version=(
            "dehps-prediction-v2-structural-baseline-comparison-execution-handoff.v1"
        ),
        artifact_type=(
            "prediction_v2_structural_baseline_comparison_execution_handoff"
        ),
        body={
            "status": "COMPLETE",
            "preregistration_digest": preregistration["artifact_digest"],
            "preregistration_status": "FROZEN_RESULT_BLIND",
            "baseline_class_ids": [item["class_id"] for item in BASELINE_CLASSES],
            "portfolio_budget": PORTFOLIO_BUDGET,
            "replicates_per_class": BASELINE_REPLICATES_PER_CLASS,
            "candidate_considerations_per_class": (CANDIDATE_CONSIDERATIONS_PER_CLASS),
            "total_candidate_considerations": TOTAL_CANDIDATE_CONSIDERATIONS,
            "comparison_execution_authorized": True,
            "portfolio_activation_authorized": False,
            "decision_usefulness_established": False,
            "prediction_probability_claim": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(*parent_digests, str(preregistration["artifact_digest"])),
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-execution-handoff.v1"
        ),
    )
    completion = _artifact(
        schema_version=(
            "dehps-prediction-v2-structural-baseline-comparison-"
            "preregistration-completion.v1"
        ),
        artifact_type=(
            "prediction_v2_structural_baseline_comparison_preregistration_completion"
        ),
        body={
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_COMPLETION_FACT
            ),
            "source_contract_digest": source_digest,
            "route_execution_digest": route_execution["artifact_digest"],
            "preregistration_digest": preregistration["artifact_digest"],
            "execution_handoff_digest": execution_handoff["artifact_digest"],
            "decision": PREREGISTRATION_DECISION,
            "result_blind": True,
            "portfolio_results_read": 0,
            "registered_child_count": 3,
            "comparison_execution_authorized": True,
            "portfolio_activation_authorized": False,
            "decision_usefulness_established": False,
            "prediction_probability_claim": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "baseline_proposals_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(preregistration["artifact_digest"]),
            str(execution_handoff["artifact_digest"]),
        ),
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-"
            "preregistration-completion.v1"
        ),
    )
    return PredictionV2StructuralBaselineComparisonPreregistrationRun(
        preregistration=preregistration,
        execution_handoff=execution_handoff,
        completion=completion,
    )


def replay_prediction_v2_structural_baseline_comparison_preregistration(
    *,
    source_contract: Mapping[str, Any],
    route_execution: Mapping[str, Any],
    route_decision: Mapping[str, Any],
    route_handoff: Mapping[str, Any],
    route_completion: Mapping[str, Any],
) -> tuple[
    PredictionV2StructuralBaselineComparisonPreregistrationRun,
    dict[str, Any],
]:
    run = build_prediction_v2_structural_baseline_comparison_preregistration_artifacts(
        source_contract=source_contract,
        route_execution=route_execution,
        route_decision=route_decision,
        route_handoff=route_handoff,
        route_completion=route_completion,
    )
    replay = {
        "schema_version": (
            "dehps-prediction-v2-structural-baseline-comparison-"
            "preregistration-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "decision": PREREGISTRATION_DECISION,
        "result_blind": True,
        "portfolio_results_read": 0,
        "same_registered_content": True,
        "workload_rerun": False,
        "database_queries_during_replay": 0,
        "historical_rows_read": 0,
        "folds_replayed": 0,
        "baseline_proposals_replayed": 0,
        "evidence_created": False,
        "manual_input_assembly": False,
        "next_consumer": (
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
        ),
    }
    return run, replay


def _program_contract() -> dict[str, Any]:
    return {
        "legal_space": {
            "labels": LEGAL_LABEL_COUNT,
            "combination_size": COMBINATION_SIZE,
            "combination_count": LEGAL_COMBINATION_COUNT,
            "label_order_used_by_selection": False,
        },
        "portfolio_budget": PORTFOLIO_BUDGET,
        "baseline_classes": [dict(item) for item in BASELINE_CLASSES],
        "replicates_per_class": BASELINE_REPLICATES_PER_CLASS,
        "candidate_chunk_size_per_step": CANDIDATE_CHUNK_SIZE,
        "portfolio_steps_per_replicate": PORTFOLIO_BUDGET,
        "candidate_considerations_per_replicate": (
            CANDIDATE_CONSIDERATIONS_PER_REPLICATE
        ),
        "candidate_considerations_per_class": CANDIDATE_CONSIDERATIONS_PER_CLASS,
        "total_candidate_considerations": TOTAL_CANDIDATE_CONSIDERATIONS,
        "master_seed_hex": MASTER_SEED_HEX,
        "candidate_stream": CANDIDATE_STREAM,
        "candidate_stream_domain": CANDIDATE_STREAM_DOMAIN,
        "combination_indexing": COMBINATION_INDEXING,
        "tie_break": TIE_BREAK,
        "empty_or_singleton_minimum_replacement_distance": COMBINATION_SIZE,
        "checkpoint_every_portfolio_steps": CHECKPOINT_EVERY_PORTFOLIO_STEPS,
        "parallel_workers": PARALLEL_WORKERS,
        "wall_clock_limit_seconds": WALL_CLOCK_LIMIT_SECONDS,
        "resident_memory_limit_bytes": RESIDENT_MEMORY_LIMIT_BYTES,
        "construction_invariant": (
            "DISJOINT_CHUNKS_OF_ONE_WITHOUT_REPLACEMENT_STREAM_PER_REPLICATE"
        ),
    }


def _comparison_contract() -> dict[str, Any]:
    return {
        "metrics": [dict(item) for item in METRICS],
        "strict_dominance": STRICT_DOMINANCE,
        "required_candidate_dominated_replicates_per_class": (
            REQUIRED_CANDIDATE_DOMINATED_REPLICATES_PER_CLASS
        ),
        "maximum_baseline_replicates_dominating_candidate_per_class": (
            MAXIMUM_BASELINE_REPLICATES_DOMINATING_CANDIDATE_PER_CLASS
        ),
        "supported_label": SUPPORTED_LABEL,
        "failure_label": FAILURE_LABEL,
        "invalid_label": INVALID_LABEL,
        "p_value_claim": False,
        "global_optimality_claim": False,
        "decision_usefulness_claim": False,
        "prediction_probability_claim": False,
    }


def _validate_parent_artifacts(
    *,
    route_execution: Mapping[str, Any],
    route_decision: Mapping[str, Any],
    route_handoff: Mapping[str, Any],
    route_completion: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts_and_domains = (
        (route_execution, "dehps.research-os.mainline-execution.v1"),
        (route_decision, "dehps.prediction-v2.structural-route-decision.v1"),
        (
            route_handoff,
            (
                "dehps.prediction-v2.structural-baseline-comparison-"
                "preregistration-handoff.v1"
            ),
        ),
        (
            route_completion,
            "dehps.prediction-v2.structural-route-decision-completion.v1",
        ),
    )
    for artifact, domain in artifacts_and_domains:
        _verify_artifact(artifact, domain=domain)
    if require_registered_identities and tuple(
        str(artifact.get("artifact_digest")) for artifact, _ in artifacts_and_domains
    ) != (
        ROUTE_EXECUTION_DIGEST,
        ROUTE_DECISION_DIGEST,
        ROUTE_HANDOFF_DIGEST,
        ROUTE_COMPLETION_DIGEST,
    ):
        raise PredictionV2StructuralBaselineComparisonPreregistrationError(
            "structural_baseline_preregistration_registered_identity_changed"
        )
    if (
        route_execution.get("task_key")
        != PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
        or route_execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or route_execution.get("completion_fact")
        != "prediction-v2-structural-route-decision:COMPLETE"
        or route_execution.get("route_decision") != ROUTE_DECISION
        or route_execution.get("structural_artifact_role") != STRUCTURAL_ARTIFACT_ROLE
        or route_execution.get("structural_route_decision_digest")
        != route_decision.get("artifact_digest")
        or route_execution.get("structural_baseline_preregistration_handoff_digest")
        != route_handoff.get("artifact_digest")
        or route_execution.get("structural_route_decision_completion_digest")
        != route_completion.get("artifact_digest")
        or route_execution.get("stronger_baseline_comparison_required") is not True
        or route_execution.get("same_budget_required") is not True
        or route_execution.get("label_symmetry_required") is not True
        or route_execution.get("transparent_baselines_required") is not True
        or route_execution.get("observed_result_independent_failure_rule_required")
        is not True
        or route_execution.get("portfolio_activation_authorized") is not False
        or route_execution.get("decision_usefulness_established") is not False
        or route_execution.get("prediction_probability_claim") is not False
        or route_execution.get("historical_evidence") != "INCONCLUSIVE"
        or route_execution.get("prediction_v2_mode") != "SHADOW_ONLY"
        or route_execution.get("prediction_v2_route") != "BASELINE_ONLY"
        or route_execution.get("evidence_created") is not False
        or route_execution.get("new_model_created") is not False
        or route_execution.get("candidate_expert_authorized") is not False
        or route_execution.get("promotion_gate_opened") is not False
        or route_execution.get("p3_authorized") is not False
        or route_execution.get("production_action") != "none"
        or route_decision.get("decision") != ROUTE_DECISION
        or route_decision.get("structural_artifact_role") != STRUCTURAL_ARTIFACT_ROLE
        or route_decision.get("archive_condition") != ARCHIVE_CONDITION
        or route_decision.get("stronger_baseline_comparison_required") is not True
        or route_decision.get("portfolio_activation_authorized") is not False
        or route_decision.get("decision_usefulness_established") is not False
        or route_handoff.get("route_decision") != ROUTE_DECISION
        or route_handoff.get("preregistration_scope")
        != "STRONGER_SIMPLE_SAME_BUDGET_LABEL_SYMMETRIC_BASELINE_COMPARISON"
        or route_handoff.get("result_blind_preregistration_required") is not True
        or route_handoff.get("observed_result_may_define_thresholds") is not False
        or route_handoff.get("baseline_classes_frozen") is not False
        or route_handoff.get("comparison_execution_authorized") is not False
        or route_handoff.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
        or route_completion.get("completion_fact")
        != "prediction-v2-structural-route-decision:COMPLETE"
        or route_completion.get("route_decision_digest")
        != route_decision.get("artifact_digest")
        or route_completion.get("baseline_preregistration_handoff_digest")
        != route_handoff.get("artifact_digest")
        or route_completion.get("decision") != ROUTE_DECISION
        or route_completion.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
    ):
        raise PredictionV2StructuralBaselineComparisonPreregistrationError(
            "structural_baseline_preregistration_parent_consistency_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
        or frozen.get("registered_input_digests")
        != [
            ROUTE_EXECUTION_DIGEST,
            ROUTE_DECISION_DIGEST,
            ROUTE_HANDOFF_DIGEST,
            ROUTE_COMPLETION_DIGEST,
        ]
        or frozen.get("decision") != PREREGISTRATION_DECISION
        or frozen.get("route_decision") != ROUTE_DECISION
        or frozen.get("structural_artifact_role") != STRUCTURAL_ARTIFACT_ROLE
        or frozen.get("result_blind") is not True
        or frozen.get("portfolio_results_read") != 0
        or frozen.get("program") != _program_contract()
        or frozen.get("comparison_contract") != _comparison_contract()
        or frozen.get("comparison_execution_authorized") is not True
        or frozen.get("portfolio_activation_authorized") is not False
        or frozen.get("decision_usefulness_established") is not False
        or frozen.get("prediction_probability_claim") is not False
        or frozen.get("historical_evidence") != "INCONCLUSIVE"
        or frozen.get("prediction_v2_mode") != "SHADOW_ONLY"
        or frozen.get("prediction_v2_route") != "BASELINE_ONLY"
        or frozen.get("registered_child_count") != 3
        or frozen.get("registered_total_with_mainline_execution") != 4
        or frozen.get("database_queries") != 0
        or frozen.get("historical_rows_read") != 0
        or frozen.get("folds_executed") != 0
        or frozen.get("bootstrap_children_executed") != 0
        or frozen.get("baseline_proposals_executed") != 0
        or frozen.get("new_evidence_created") is not False
        or frozen.get("new_model_created") is not False
        or frozen.get("candidate_expert_authorized") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("production_action") != "none"
    ):
        raise PredictionV2StructuralBaselineComparisonPreregistrationError(
            "structural_baseline_preregistration_frozen_contract_changed"
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
        raise PredictionV2StructuralBaselineComparisonPreregistrationError(
            "structural_baseline_preregistration_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
