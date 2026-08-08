from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY = (
    "prediction-v2-structural-portfolio-evaluation"
)
PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_CAPABILITY = (
    "prediction_v2_structural_portfolio_evaluation"
)
PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_COMPLETION_FACT = (
    "prediction-v2-structural-portfolio-evaluation:COMPLETE"
)
PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/prediction-v2-structural-portfolio-evaluation-source-v1.json"
)
PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY = (
    "prediction-v2-structural-route-decision"
)

PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY = (
    "prediction-v2-structural-portfolio-execution"
)
PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_COMPLETION_FACT = (
    "prediction-v2-structural-portfolio-execution:COMPLETE"
)
STRUCTURAL_EXECUTION_DIGEST = (
    "a75e89e5bb0512b2e875c8b455efed60fad494b029041c9b1d8138cc96615c3d"
)
STRUCTURAL_PORTFOLIO_DIGEST = (
    "df7193046245f073c1d77526ad3e5b98ad6806d7ee566b5dd5833659b3ff7498"
)
STRUCTURAL_OPTIMIZER_INDEX_DIGEST = (
    "0cd15cf2909ef8dc0fa3a0a6089d845292d8ca6b118c280d6fcb43b5d56d77fc"
)
STRUCTURAL_NULL_COMPARISON_DIGEST = (
    "f9fed009ce30080bdcd8b471d298012a5460ed3111051b965b1782df2c20e511"
)
STRUCTURAL_EXECUTION_COMPLETION_DIGEST = (
    "6f207fbd5008f001976bb1fb3b18647065a3a858f20736a925fb0b180173a7e8"
)

CANDIDATE_BUDGET = 176
ISLAND_COUNT = 22
NULL_REPLICATE_COUNT = 4_096
MINIMUM_STRICTLY_DOMINATED_NULLS = 3_893
MAXIMUM_NULLS_DOMINATING_CANDIDATE = 0
REQUIRED_MINIMUM_REPLACEMENT_DISTANCE = 2
SINGLETON_SQUARE_SUM_IDEAL = 33_792
PAIR_SQUARE_SUM_IDEAL = 13_200
SUM_PAIRWISE_REPLACEMENT_DISTANCE_IDEAL = 76_032
SELECTED_STATS = {
    "singleton_square_sum": 33_796,
    "pair_square_sum": 14_152,
    "minimum_replacement_distance": 2,
    "sum_pairwise_replacement_distance": 76_030,
}
SELECTED_IDEAL_GAPS = {
    "singleton_square_sum_excess": 4,
    "pair_square_sum_excess": 952,
    "sum_pairwise_replacement_distance_deficit": 2,
}
UNIFORM_NULL_EXTREMA = {
    "singleton_square_sum_minimum": 34_104,
    "pair_square_sum_minimum": 15_144,
    "minimum_replacement_distance_maximum": 2,
    "sum_pairwise_replacement_distance_maximum": 75_876,
}
ISLANDS_PASSING_FROZEN_GATE = 16
ISLANDS_DOMINATING_EVERY_NULL = 16
EVALUATION_DECISION = "SUPPORTED_AT_FROZEN_B176_AGAINST_UNIFORM_RANDOM_ONLY"
ROUTE_DISPOSITION = "ADVANCE_TO_SEPARATE_STRUCTURAL_ROUTE_DECISION"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-structural-portfolio-evaluation-round-68-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-structural-portfolio-evaluation-round-68-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/prediction_v2_structural_portfolio_evaluation.py"
)
FROZEN_CONTRACT_DIGEST = (
    "0ad88295dda78b580bfc4d330d03aabb95409980745d6ebf4f1dbcf4bd1afec0"
)


class PredictionV2StructuralPortfolioEvaluationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2StructuralPortfolioEvaluationRun:
    decision: Mapping[str, Any]
    route_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.decision, self.route_handoff, self.completion


def load_prediction_v2_structural_portfolio_evaluation_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2StructuralPortfolioEvaluationError(
            f"structural_portfolio_evaluation_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-structural-portfolio-evaluation-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_structural_portfolio_evaluation_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 394
        or payload.get("research_execution_id") != 315
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 395
        or payload.get("engineering_execution_id") != 316
        or payload.get("result_aware") is not True
        or payload.get("database_queries") != 0
        or payload.get("historical_rows_read") != 0
        or payload.get("folds_executed") != 0
        or payload.get("bootstrap_children_executed") != 0
        or payload.get("optimizer_proposals_executed") != 0
        or payload.get("null_replicates_executed") != 0
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
            domain="dehps.prediction-v2.structural-portfolio-evaluation-frozen-contract.v1",
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.prediction-v2.structural-portfolio-evaluation-source-set.v1",
        )
    ):
        raise PredictionV2StructuralPortfolioEvaluationError(
            "structural_portfolio_evaluation_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2StructuralPortfolioEvaluationError(
            "structural_portfolio_evaluation_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_structural_portfolio_evaluation_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2StructuralPortfolioEvaluationError(
                f"structural_portfolio_evaluation_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2StructuralPortfolioEvaluationError(
                f"structural_portfolio_evaluation_source_modified:{relative}"
            )


def build_prediction_v2_structural_portfolio_evaluation_artifacts(
    *,
    source_contract: Mapping[str, Any],
    structural_execution: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    optimizer_index: Mapping[str, Any],
    null_comparison: Mapping[str, Any],
    execution_completion: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2StructuralPortfolioEvaluationRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    observed = _validate_parent_artifacts(
        structural_execution=structural_execution,
        portfolio=portfolio,
        optimizer_index=optimizer_index,
        null_comparison=null_comparison,
        execution_completion=execution_completion,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    common_parents = (
        source_digest,
        str(structural_execution["artifact_digest"]),
        str(portfolio["artifact_digest"]),
        str(optimizer_index["artifact_digest"]),
        str(null_comparison["artifact_digest"]),
        str(execution_completion["artifact_digest"]),
    )
    decision = _artifact(
        schema_version="dehps-prediction-v2-structural-portfolio-evaluation-decision.v1",
        artifact_type="prediction_v2_structural_portfolio_evaluation_decision",
        body={
            "status": "COMPLETE",
            "decision": EVALUATION_DECISION,
            "hypothesis_scope": "FIXED_B176_OPTIMIZER_VERSUS_UNIFORM_SAME_BUDGET",
            "comparison_classification": (
                "DESCRIPTIVE_FIXED_OPTIMIZER_VS_UNIFORM_SAME_BUDGET"
            ),
            "candidate_budget": CANDIDATE_BUDGET,
            "selected_stats": dict(SELECTED_STATS),
            "finite_design_ideals": {
                "singleton_square_sum": SINGLETON_SQUARE_SUM_IDEAL,
                "pair_square_sum": PAIR_SQUARE_SUM_IDEAL,
                "sum_pairwise_replacement_distance": (
                    SUM_PAIRWISE_REPLACEMENT_DISTANCE_IDEAL
                ),
            },
            "selected_ideal_gaps": dict(SELECTED_IDEAL_GAPS),
            "uniform_null_extrema": dict(UNIFORM_NULL_EXTREMA),
            "selected_strictly_dominated_null_count": observed[
                "selected_strictly_dominated_null_count"
            ],
            "selected_null_strictly_dominating_count": observed[
                "selected_null_strictly_dominating_count"
            ],
            "island_count": ISLAND_COUNT,
            "islands_passing_frozen_gate": observed["islands_passing_frozen_gate"],
            "islands_dominating_every_null": observed["islands_dominating_every_null"],
            "mechanical_gate_status": "PASS",
            "joint_failure_fraction_label": "FROZEN_MECHANICAL_GATE_ONLY_NOT_P_VALUE",
            "p_value_claim": False,
            "global_optimality_claim": False,
            "decision_usefulness_claim": False,
            "prediction_probability_claim": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "optimizer_proposals_executed": 0,
            "null_replicates_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
        },
        parent_digests=common_parents,
        domain="dehps.prediction-v2.structural-portfolio-evaluation-decision.v1",
    )
    route_handoff = _artifact(
        schema_version="dehps-prediction-v2-structural-route-handoff.v1",
        artifact_type="prediction_v2_structural_route_handoff",
        body={
            "status": "COMPLETE",
            "evaluation_decision": EVALUATION_DECISION,
            "route_disposition": ROUTE_DISPOSITION,
            "structural_artifact_role": (
                "ELIGIBLE_FOR_SEPARATE_DECISION_SUPPORT_ROUTE_REVIEW"
            ),
            "structural_portfolio_digest": portfolio["artifact_digest"],
            "portfolio_activation_authorized": False,
            "decision_usefulness_established": False,
            "prediction_research_disposition": (
                "FROZEN_PENDING_SEPARATE_RESULT_BLIND_PREREGISTRATION"
            ),
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "prediction_probability_claim": False,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(*common_parents, str(decision["artifact_digest"])),
        domain="dehps.prediction-v2.structural-route-handoff.v1",
    )
    completion = _artifact(
        schema_version="dehps-prediction-v2-structural-portfolio-evaluation-completion.v1",
        artifact_type="prediction_v2_structural_portfolio_evaluation_completion",
        body={
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_COMPLETION_FACT
            ),
            "source_contract_digest": source_digest,
            "structural_execution_artifact_digest": structural_execution[
                "artifact_digest"
            ],
            "evaluation_decision_digest": decision["artifact_digest"],
            "route_handoff_digest": route_handoff["artifact_digest"],
            "decision": EVALUATION_DECISION,
            "route_disposition": ROUTE_DISPOSITION,
            "registered_child_count": 3,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "p_value_claim": False,
            "global_optimality_claim": False,
            "decision_usefulness_claim": False,
            "prediction_probability_claim": False,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "optimizer_proposals_executed": 0,
            "null_replicates_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(decision["artifact_digest"]),
            str(route_handoff["artifact_digest"]),
        ),
        domain="dehps.prediction-v2.structural-portfolio-evaluation-completion.v1",
    )
    return PredictionV2StructuralPortfolioEvaluationRun(
        decision=decision,
        route_handoff=route_handoff,
        completion=completion,
    )


def replay_prediction_v2_structural_portfolio_evaluation(
    *,
    source_contract: Mapping[str, Any],
    structural_execution: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    optimizer_index: Mapping[str, Any],
    null_comparison: Mapping[str, Any],
    execution_completion: Mapping[str, Any],
) -> tuple[PredictionV2StructuralPortfolioEvaluationRun, dict[str, Any]]:
    run = build_prediction_v2_structural_portfolio_evaluation_artifacts(
        source_contract=source_contract,
        structural_execution=structural_execution,
        portfolio=portfolio,
        optimizer_index=optimizer_index,
        null_comparison=null_comparison,
        execution_completion=execution_completion,
    )
    replay = {
        "schema_version": (
            "dehps-prediction-v2-structural-portfolio-evaluation-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "decision": EVALUATION_DECISION,
        "route_disposition": ROUTE_DISPOSITION,
        "same_registered_content": True,
        "workload_rerun": False,
        "optimizer_proposals_replayed": 0,
        "null_replicates_replayed": 0,
        "historical_rows_read": 0,
        "database_queries_during_replay": 0,
        "evidence_created": False,
        "manual_input_assembly": False,
        "next_consumer": PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
    }
    return run, replay


def _validate_parent_artifacts(
    *,
    structural_execution: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    optimizer_index: Mapping[str, Any],
    null_comparison: Mapping[str, Any],
    execution_completion: Mapping[str, Any],
    require_registered_identities: bool,
) -> dict[str, int]:
    artifacts_and_domains = (
        (structural_execution, "dehps.research-os.mainline-execution.v1"),
        (portfolio, "dehps.prediction-v2.canonical-structural-portfolio.v1"),
        (optimizer_index, "dehps.prediction-v2.structural-optimizer-index.v1"),
        (null_comparison, "dehps.prediction-v2.structural-null-comparison.v1"),
        (
            execution_completion,
            "dehps.prediction-v2.structural-portfolio-execution-completion.v1",
        ),
    )
    for artifact, domain in artifacts_and_domains:
        _verify_artifact(artifact, domain=domain)
    if require_registered_identities:
        observed_digests = tuple(
            str(artifact.get("artifact_digest"))
            for artifact, _ in artifacts_and_domains
        )
        expected_digests = (
            STRUCTURAL_EXECUTION_DIGEST,
            STRUCTURAL_PORTFOLIO_DIGEST,
            STRUCTURAL_OPTIMIZER_INDEX_DIGEST,
            STRUCTURAL_NULL_COMPARISON_DIGEST,
            STRUCTURAL_EXECUTION_COMPLETION_DIGEST,
        )
        if observed_digests != expected_digests:
            raise PredictionV2StructuralPortfolioEvaluationError(
                "structural_portfolio_evaluation_registered_identity_changed"
            )
    islands = optimizer_index.get("islands")
    comparisons = null_comparison.get("island_comparisons")
    replicates = null_comparison.get("ordered_replicates")
    if (
        not isinstance(islands, list)
        or len(islands) != ISLAND_COUNT
        or not isinstance(comparisons, list)
        or len(comparisons) != ISLAND_COUNT
        or not isinstance(replicates, list)
        or len(replicates) != NULL_REPLICATE_COUNT
    ):
        raise PredictionV2StructuralPortfolioEvaluationError(
            "structural_portfolio_evaluation_registered_rows_invalid"
        )
    null_stats = [item.get("stats") for item in replicates]
    if any(not isinstance(stats, dict) for stats in null_stats):
        raise PredictionV2StructuralPortfolioEvaluationError(
            "structural_portfolio_evaluation_null_stats_invalid"
        )
    null_extrema = {
        "singleton_square_sum_minimum": min(
            int(stats["singleton_square_sum"]) for stats in null_stats
        ),
        "pair_square_sum_minimum": min(
            int(stats["pair_square_sum"]) for stats in null_stats
        ),
        "minimum_replacement_distance_maximum": max(
            int(stats["minimum_replacement_distance"]) for stats in null_stats
        ),
        "sum_pairwise_replacement_distance_maximum": max(
            int(stats["sum_pairwise_replacement_distance"]) for stats in null_stats
        ),
    }
    passing = sum(
        int(row["stats"]["minimum_replacement_distance"])
        >= REQUIRED_MINIMUM_REPLACEMENT_DISTANCE
        and int(row["strictly_dominated_null_count"])
        >= MINIMUM_STRICTLY_DOMINATED_NULLS
        and int(row["null_strictly_dominating_count"])
        <= MAXIMUM_NULLS_DOMINATING_CANDIDATE
        for row in comparisons
    )
    dominating_every = sum(
        int(row["strictly_dominated_null_count"]) == NULL_REPLICATE_COUNT
        and int(row["null_strictly_dominating_count"]) == 0
        for row in comparisons
    )
    if (
        CANDIDATE_BUDGET * 6 != 1_056
        or 33 * 32 * 32 != SINGLETON_SQUARE_SUM_IDEAL
        or CANDIDATE_BUDGET * 15 != 2_640
        or 528 * 5 * 5 != PAIR_SQUARE_SUM_IDEAL
        or 6 * (CANDIDATE_BUDGET * (CANDIDATE_BUDGET - 1) // 2)
        - (SINGLETON_SQUARE_SUM_IDEAL - 6 * CANDIDATE_BUDGET) // 2
        != SUM_PAIRWISE_REPLACEMENT_DISTANCE_IDEAL
        or portfolio.get("exact_stats") != SELECTED_STATS
        or portfolio.get("candidate_budget") != CANDIDATE_BUDGET
        or portfolio.get("selected_island_index") != 14
        or portfolio.get("structural_gate_status") != "PASS"
        or portfolio.get("prediction_probability_claim") is not False
        or portfolio.get("global_optimality_claim") is not False
        or optimizer_index.get("island_count") != ISLAND_COUNT
        or optimizer_index.get("candidate_budget") != CANDIDATE_BUDGET
        or optimizer_index.get("total_proposals_executed") != 5_767_168
        or null_comparison.get("replicate_count") != NULL_REPLICATE_COUNT
        or null_comparison.get("candidate_budget") != CANDIDATE_BUDGET
        or null_comparison.get("selected_island_index") != 14
        or null_comparison.get("selected_strictly_dominated_null_count")
        != NULL_REPLICATE_COUNT
        or null_comparison.get("selected_null_strictly_dominating_count") != 0
        or null_comparison.get("mechanical_gate_status") != "PASS"
        or null_comparison.get("gate_semantics")
        != "STRUCTURAL_PERFORMANCE_GATE_NOT_PREDICTIVE_P_VALUE"
        or null_extrema != UNIFORM_NULL_EXTREMA
        or passing != ISLANDS_PASSING_FROZEN_GATE
        or dominating_every != ISLANDS_DOMINATING_EVERY_NULL
        or structural_execution.get("task_key")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
        or structural_execution.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_COMPLETION_FACT
        or structural_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or structural_execution.get("structural_gate_status") != "PASS"
        or structural_execution.get("historical_evidence") != "INCONCLUSIVE"
        or structural_execution.get("prediction_v2_mode") != "SHADOW_ONLY"
        or structural_execution.get("prediction_v2_route") != "BASELINE_ONLY"
        or structural_execution.get("evidence_created") is not False
        or structural_execution.get("new_model_created") is not False
        or structural_execution.get("candidate_expert_authorized") is not False
        or structural_execution.get("promotion_gate_opened") is not False
        or structural_execution.get("p3_authorized") is not False
        or structural_execution.get("production_action") != "none"
        or structural_execution.get("structural_portfolio_digest")
        != portfolio.get("artifact_digest")
        or structural_execution.get("structural_optimizer_index_digest")
        != optimizer_index.get("artifact_digest")
        or structural_execution.get("structural_null_comparison_digest")
        != null_comparison.get("artifact_digest")
        or structural_execution.get("structural_execution_completion_digest")
        != execution_completion.get("artifact_digest")
        or execution_completion.get("portfolio_digest")
        != portfolio.get("artifact_digest")
        or execution_completion.get("optimizer_index_digest")
        != optimizer_index.get("artifact_digest")
        or execution_completion.get("null_comparison_digest")
        != null_comparison.get("artifact_digest")
        or execution_completion.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    ):
        raise PredictionV2StructuralPortfolioEvaluationError(
            "structural_portfolio_evaluation_parent_consistency_invalid"
        )
    return {
        "selected_strictly_dominated_null_count": NULL_REPLICATE_COUNT,
        "selected_null_strictly_dominating_count": 0,
        "islands_passing_frozen_gate": passing,
        "islands_dominating_every_null": dominating_every,
    }


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key") != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
        or frozen.get("registered_input_digests")
        != [
            STRUCTURAL_EXECUTION_DIGEST,
            STRUCTURAL_PORTFOLIO_DIGEST,
            STRUCTURAL_OPTIMIZER_INDEX_DIGEST,
            STRUCTURAL_NULL_COMPARISON_DIGEST,
            STRUCTURAL_EXECUTION_COMPLETION_DIGEST,
        ]
        or frozen.get("candidate_budget") != CANDIDATE_BUDGET
        or frozen.get("finite_design_ideals")
        != {
            "singleton_square_sum": SINGLETON_SQUARE_SUM_IDEAL,
            "pair_square_sum": PAIR_SQUARE_SUM_IDEAL,
            "sum_pairwise_replacement_distance": (
                SUM_PAIRWISE_REPLACEMENT_DISTANCE_IDEAL
            ),
        }
        or frozen.get("selected_stats") != SELECTED_STATS
        or frozen.get("selected_ideal_gaps") != SELECTED_IDEAL_GAPS
        or frozen.get("uniform_null_extrema") != UNIFORM_NULL_EXTREMA
        or frozen.get("selected_strictly_dominated_null_count") != NULL_REPLICATE_COUNT
        or frozen.get("selected_null_strictly_dominating_count") != 0
        or frozen.get("island_count") != ISLAND_COUNT
        or frozen.get("islands_passing_frozen_gate") != ISLANDS_PASSING_FROZEN_GATE
        or frozen.get("islands_dominating_every_null") != ISLANDS_DOMINATING_EVERY_NULL
        or frozen.get("decision") != EVALUATION_DECISION
        or frozen.get("route_disposition") != ROUTE_DISPOSITION
        or frozen.get("p_value_claim") is not False
        or frozen.get("global_optimality_claim") is not False
        or frozen.get("decision_usefulness_claim") is not False
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
        or frozen.get("optimizer_proposals_executed") != 0
        or frozen.get("null_replicates_executed") != 0
        or frozen.get("new_evidence_created") is not False
        or frozen.get("new_model_created") is not False
        or frozen.get("candidate_expert_authorized") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("production_action") != "none"
    ):
        raise PredictionV2StructuralPortfolioEvaluationError(
            "structural_portfolio_evaluation_frozen_contract_changed"
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
        raise PredictionV2StructuralPortfolioEvaluationError(
            "structural_portfolio_evaluation_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
