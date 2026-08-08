from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY = (
    "prediction-v2-structural-baseline-comparison-route-decision"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_CAPABILITY = (
    "prediction_v2_structural_baseline_comparison_route_decision"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_COMPLETION_FACT = (
    "prediction-v2-structural-baseline-comparison-route-decision:COMPLETE"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_SOURCE_CONTRACT_PATH = (
    Path(
        "configs/research-os/"
        "prediction-v2-structural-baseline-comparison-route-decision-source-v1.json"
    )
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY = (
    "prediction-v2-structural-baseline-comparison-execution"
)
PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY = (
    "prediction-v2-next-result-blind-research-intake"
)
NEXT_RESEARCH_CONTRACT_EVENT = (
    "research-contract:prediction-v2-next-result-blind-program:approved"
)

COMPARISON_EXECUTION_DIGEST = (
    "ca8b04b63f7295744b41fa2b33fcbec4a2c3e70e115a7662e04ec2cc3d9f233f"
)
RESULT_INDEX_DIGEST = (
    "cb49d823118f682e585e1395a7124083c9c86ca36476cd975f563aca44187877"
)
GATE_OUTCOME_DIGEST = (
    "73ca03f93b2a9149d265502b75fd747370c3e493095d3a555b72c8ed6546bc20"
)
EXECUTION_COMPLETION_DIGEST = (
    "830513d1c77b6669a8e1ed2bd45d965f6644e0bb8dd543920de918e36e4b7541"
)

COMPARISON_DECISION = "ARCHIVE_AS_ENGINEERING_EVIDENCE_ONLY"
ROUTE_DECISION = (
    "ARCHIVE_B176_FROM_ACTIVATION_AND_WAIT_FOR_NEW_RESULT_BLIND_RESEARCH_CONTRACT"
)
STRUCTURAL_ARTIFACT_ROLE = "ARCHIVED_NON_PREDICTIVE_ENGINEERING_REFERENCE_ONLY"
PREDICTION_RESEARCH_DISPOSITION = "FROZEN_NO_ACCEPTED_CANDIDATE"
REPETITION_SCAN = "ABSENT_BY_CONSTRUCTION"

BASELINE_CLASS_IDS = (
    "SINGLETON_FIRST_GREEDY_V1",
    "PAIR_FIRST_GREEDY_V1",
    "DISTANCE_FIRST_GREEDY_V1",
)
CANDIDATE_STATS = {
    "singleton_square_sum": 33_796,
    "pair_square_sum": 14_152,
    "minimum_replacement_distance": 2,
    "sum_pairwise_replacement_distance": 76_030,
}
CLASS_SUMMARIES = (
    {
        "class_id": "SINGLETON_FIRST_GREEDY_V1",
        "replicate_count": 128,
        "candidate_considerations": 5_767_168,
        "candidate_dominated_replicate_count": 0,
        "baseline_dominating_candidate_count": 14,
        "candidate_dominance_required": 122,
        "baseline_dominance_maximum": 0,
        "class_gate_pass": False,
    },
    {
        "class_id": "PAIR_FIRST_GREEDY_V1",
        "replicate_count": 128,
        "candidate_considerations": 5_767_168,
        "candidate_dominated_replicate_count": 0,
        "baseline_dominating_candidate_count": 0,
        "candidate_dominance_required": 122,
        "baseline_dominance_maximum": 0,
        "class_gate_pass": False,
    },
    {
        "class_id": "DISTANCE_FIRST_GREEDY_V1",
        "replicate_count": 128,
        "candidate_considerations": 5_767_168,
        "candidate_dominated_replicate_count": 0,
        "baseline_dominating_candidate_count": 5,
        "candidate_dominance_required": 122,
        "baseline_dominance_maximum": 0,
        "class_gate_pass": False,
    },
)

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-structural-baseline-route-decision-round-80-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-structural-baseline-route-decision-round-81-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/"
    "prediction_v2_structural_baseline_comparison_route_decision.py"
)
FROZEN_CONTRACT_DIGEST = (
    "740752c2a9c2089ecc4253fbe30a78942cd23bc3c3370dbfde9e86a0ddc4e005"
)


class PredictionV2StructuralBaselineComparisonRouteDecisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2StructuralBaselineComparisonRouteDecisionRun:
    decision: Mapping[str, Any]
    research_intake_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.decision, self.research_intake_handoff, self.completion


def load_prediction_v2_structural_baseline_comparison_route_decision_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
            f"structural_baseline_route_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-structural-baseline-comparison-route-decision-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_structural_baseline_comparison_route_decision_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 408
        or payload.get("research_execution_id") != 329
        or payload.get("engineering_request_key")
        != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 409
        or payload.get("engineering_execution_id") != 330
        or payload.get("result_aware") is not True
        or payload.get("database_queries") != 0
        or payload.get("historical_rows_read") != 0
        or payload.get("folds_executed") != 0
        or payload.get("bootstrap_children_executed") != 0
        or payload.get("candidate_considerations_executed") != 0
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
                "route-decision-frozen-contract.v1"
            ),
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.prediction-v2.structural-baseline-comparison-"
                "route-decision-source-set.v1"
            ),
        )
    ):
        raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
            "structural_baseline_route_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
            "structural_baseline_route_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_structural_baseline_comparison_route_decision_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
                f"structural_baseline_route_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
                f"structural_baseline_route_source_modified:{relative}"
            )


def build_prediction_v2_structural_baseline_comparison_route_decision_artifacts(
    *,
    source_contract: Mapping[str, Any],
    comparison_execution: Mapping[str, Any],
    result_index: Mapping[str, Any],
    gate_outcome: Mapping[str, Any],
    execution_completion: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2StructuralBaselineComparisonRouteDecisionRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        comparison_execution=comparison_execution,
        result_index=result_index,
        gate_outcome=gate_outcome,
        execution_completion=execution_completion,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(comparison_execution["artifact_digest"]),
        str(result_index["artifact_digest"]),
        str(gate_outcome["artifact_digest"]),
        str(execution_completion["artifact_digest"]),
    )
    decision = _artifact(
        schema_version=(
            "dehps-prediction-v2-structural-baseline-comparison-route-decision.v1"
        ),
        artifact_type=(
            "prediction_v2_structural_baseline_comparison_route_decision"
        ),
        body={
            "status": "COMPLETE",
            "decision": ROUTE_DECISION,
            "comparison_decision": COMPARISON_DECISION,
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "candidate_stats": dict(CANDIDATE_STATS),
            "class_summaries": [dict(item) for item in CLASS_SUMMARIES],
            "candidate_dominance_required_per_class": 122,
            "maximum_baseline_dominance_allowed_per_class": 0,
            "threshold_retuned": False,
            "portfolio_activation_authorized": False,
            "decision_usefulness_established": False,
            "prediction_probability_claim": False,
            "global_optimality_claim": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "legacy_prediction_mainline_reactivation_authorized": False,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "candidate_considerations_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY,
            "next_external_event": NEXT_RESEARCH_CONTRACT_EVENT,
            "production_action": "none",
            "repetition_scan": REPETITION_SCAN,
        },
        parent_digests=parent_digests,
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-route-decision.v1"
        ),
    )
    handoff = _artifact(
        schema_version="dehps-prediction-v2-result-blind-research-intake-handoff.v1",
        artifact_type="prediction_v2_result_blind_research_intake_handoff",
        body={
            "status": "COMPLETE",
            "route_decision": ROUTE_DECISION,
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "intake_task": PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY,
            "required_external_event": NEXT_RESEARCH_CONTRACT_EVENT,
            "state_before_external_event": "EXTERNAL_WAIT",
            "result_blind_contract_required": True,
            "requested_capability_before_event": None,
            "automatic_hypothesis_generation": False,
            "automatic_threshold_relaxation": False,
            "automatic_seed_retry": False,
            "automatic_portfolio_mutation": False,
            "legacy_route_fallback": False,
            "legacy_prediction_mainline_reactivation_authorized": False,
            "portfolio_activation_authorized": False,
            "decision_usefulness_established": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY,
            "production_action": "none",
            "repetition_scan": REPETITION_SCAN,
        },
        parent_digests=(*parent_digests, str(decision["artifact_digest"])),
        domain="dehps.prediction-v2.result-blind-research-intake-handoff.v1",
    )
    completion = _artifact(
        schema_version=(
            "dehps-prediction-v2-structural-baseline-comparison-"
            "route-decision-completion.v1"
        ),
        artifact_type=(
            "prediction_v2_structural_baseline_comparison_route_decision_completion"
        ),
        body={
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_COMPLETION_FACT
            ),
            "source_contract_digest": source_digest,
            "comparison_execution_digest": comparison_execution["artifact_digest"],
            "route_decision_digest": decision["artifact_digest"],
            "research_intake_handoff_digest": handoff["artifact_digest"],
            "decision": ROUTE_DECISION,
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "registered_child_count": 3,
            "candidate_considerations_executed": 0,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "portfolio_activation_authorized": False,
            "decision_usefulness_established": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "legacy_prediction_mainline_reactivation_authorized": False,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY,
            "next_external_event": NEXT_RESEARCH_CONTRACT_EVENT,
            "production_action": "none",
            "repetition_scan": REPETITION_SCAN,
        },
        parent_digests=(
            source_digest,
            str(decision["artifact_digest"]),
            str(handoff["artifact_digest"]),
        ),
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-"
            "route-decision-completion.v1"
        ),
    )
    return PredictionV2StructuralBaselineComparisonRouteDecisionRun(
        decision=decision,
        research_intake_handoff=handoff,
        completion=completion,
    )


def replay_prediction_v2_structural_baseline_comparison_route_decision(
    *,
    source_contract: Mapping[str, Any],
    comparison_execution: Mapping[str, Any],
    result_index: Mapping[str, Any],
    gate_outcome: Mapping[str, Any],
    execution_completion: Mapping[str, Any],
) -> tuple[PredictionV2StructuralBaselineComparisonRouteDecisionRun, dict[str, Any]]:
    run = build_prediction_v2_structural_baseline_comparison_route_decision_artifacts(
        source_contract=source_contract,
        comparison_execution=comparison_execution,
        result_index=result_index,
        gate_outcome=gate_outcome,
        execution_completion=execution_completion,
    )
    return run, {
        "schema_version": (
            "dehps-prediction-v2-structural-baseline-comparison-"
            "route-decision-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "decision": ROUTE_DECISION,
        "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
        "same_registered_content": True,
        "workload_rerun": False,
        "candidate_considerations_replayed": 0,
        "historical_rows_read": 0,
        "database_queries_during_replay": 0,
        "folds_replayed": 0,
        "bootstrap_children_replayed": 0,
        "manual_input_assembly": False,
        "legacy_route_fallback": False,
        "repetition_scan": REPETITION_SCAN,
        "next_consumer": PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY,
        "next_external_event": NEXT_RESEARCH_CONTRACT_EVENT,
    }


def _validate_parent_artifacts(
    *,
    comparison_execution: Mapping[str, Any],
    result_index: Mapping[str, Any],
    gate_outcome: Mapping[str, Any],
    execution_completion: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts_and_domains = (
        (comparison_execution, "dehps.research-os.mainline-execution.v1"),
        (
            result_index,
            "dehps.prediction-v2.structural-baseline-comparison-result-index.v1",
        ),
        (
            gate_outcome,
            "dehps.prediction-v2.structural-baseline-comparison-gate-outcome.v1",
        ),
        (
            execution_completion,
            (
                "dehps.prediction-v2.structural-baseline-comparison-"
                "execution-completion.v1"
            ),
        ),
    )
    for artifact, domain in artifacts_and_domains:
        _verify_artifact(artifact, domain=domain)
    observed = tuple(
        str(artifact.get("artifact_digest")) for artifact, _ in artifacts_and_domains
    )
    if require_registered_identities and observed != (
        COMPARISON_EXECUTION_DIGEST,
        RESULT_INDEX_DIGEST,
        GATE_OUTCOME_DIGEST,
        EXECUTION_COMPLETION_DIGEST,
    ):
        raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
            "structural_baseline_route_registered_identity_changed"
        )
    summaries = [dict(item) for item in CLASS_SUMMARIES]
    if (
        comparison_execution.get("task_key")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
        or comparison_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or comparison_execution.get("completion_fact")
        != "prediction-v2-structural-baseline-comparison-execution:COMPLETE"
        or comparison_execution.get("structural_baseline_result_index_digest")
        != result_index.get("artifact_digest")
        or comparison_execution.get("structural_baseline_gate_outcome_digest")
        != gate_outcome.get("artifact_digest")
        or comparison_execution.get(
            "structural_baseline_execution_completion_digest"
        )
        != execution_completion.get("artifact_digest")
        or comparison_execution.get("decision") != COMPARISON_DECISION
        or comparison_execution.get("candidate_stats") != CANDIDATE_STATS
        or comparison_execution.get("class_summaries") != summaries
        or comparison_execution.get("baseline_replicates_executed") != 384
        or comparison_execution.get("total_candidate_considerations") != 17_301_504
        or comparison_execution.get("repetition_scan") != REPETITION_SCAN
        or result_index.get("status") != "COMPLETE"
        or result_index.get("baseline_class_ids") != list(BASELINE_CLASS_IDS)
        or result_index.get("replicates_per_class") != 128
        or result_index.get("portfolio_budget") != 176
        or result_index.get("total_candidate_considerations") != 17_301_504
        or result_index.get("candidate_stats") != CANDIDATE_STATS
        or result_index.get("class_summaries") != summaries
        or result_index.get("repetition_scan") != REPETITION_SCAN
        or gate_outcome.get("status") != "COMPLETE"
        or gate_outcome.get("valid_execution") is not True
        or gate_outcome.get("decision") != COMPARISON_DECISION
        or gate_outcome.get("result_index_digest")
        != result_index.get("artifact_digest")
        or gate_outcome.get("candidate_stats") != CANDIDATE_STATS
        or gate_outcome.get("class_summaries") != summaries
        or gate_outcome.get("required_candidate_dominated_replicates_per_class")
        != 122
        or gate_outcome.get(
            "maximum_baseline_replicates_dominating_candidate_per_class"
        )
        != 0
        or gate_outcome.get("repetition_scan") != REPETITION_SCAN
        or execution_completion.get("status") != "COMPLETE"
        or execution_completion.get("completion_fact")
        != "prediction-v2-structural-baseline-comparison-execution:COMPLETE"
        or execution_completion.get("result_index_digest")
        != result_index.get("artifact_digest")
        or execution_completion.get("gate_outcome_digest")
        != gate_outcome.get("artifact_digest")
        or execution_completion.get("decision") != COMPARISON_DECISION
        or execution_completion.get("registered_child_count") != 3
        or execution_completion.get("baseline_replicates_executed") != 384
        or execution_completion.get("total_candidate_considerations") != 17_301_504
        or execution_completion.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
        or execution_completion.get("repetition_scan") != REPETITION_SCAN
    ):
        raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
            "structural_baseline_route_parent_consistency_invalid"
        )
    for artifact in (comparison_execution, gate_outcome):
        if (
            artifact.get("historical_evidence") != "INCONCLUSIVE"
            or artifact.get("prediction_v2_mode") != "SHADOW_ONLY"
            or artifact.get("prediction_v2_route") != "BASELINE_ONLY"
            or artifact.get("portfolio_activation_authorized") is not False
            or artifact.get("new_model_created") is not False
            or artifact.get("candidate_expert_authorized") is not False
            or artifact.get("promotion_gate_opened") is not False
            or artifact.get("p3_authorized") is not False
            or artifact.get("production_action") != "none"
        ):
            raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
                "structural_baseline_route_parent_claim_boundary_invalid"
            )
    if (
        execution_completion.get("prediction_v2_mode") != "SHADOW_ONLY"
        or execution_completion.get("prediction_v2_route") != "BASELINE_ONLY"
        or execution_completion.get("portfolio_activation_authorized") is not False
        or execution_completion.get("new_evidence_created") is not False
        or execution_completion.get("new_model_created") is not False
        or execution_completion.get("candidate_expert_authorized") is not False
        or execution_completion.get("promotion_gate_opened") is not False
        or execution_completion.get("p3_authorized") is not False
        or execution_completion.get("production_action") != "none"
    ):
        raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
            "structural_baseline_route_parent_claim_boundary_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY
        or frozen.get("next_external_event") != NEXT_RESEARCH_CONTRACT_EVENT
        or frozen.get("registered_input_digests")
        != [
            COMPARISON_EXECUTION_DIGEST,
            RESULT_INDEX_DIGEST,
            GATE_OUTCOME_DIGEST,
            EXECUTION_COMPLETION_DIGEST,
        ]
        or frozen.get("comparison_decision") != COMPARISON_DECISION
        or frozen.get("route_decision") != ROUTE_DECISION
        or frozen.get("structural_artifact_role") != STRUCTURAL_ARTIFACT_ROLE
        or frozen.get("prediction_research_disposition")
        != PREDICTION_RESEARCH_DISPOSITION
        or frozen.get("candidate_stats") != CANDIDATE_STATS
        or frozen.get("class_summaries")
        != [dict(item) for item in CLASS_SUMMARIES]
        or frozen.get("required_candidate_dominated_replicates_per_class") != 122
        or frozen.get(
            "maximum_baseline_replicates_dominating_candidate_per_class"
        )
        != 0
        or frozen.get("result_blind_contract_required") is not True
        or frozen.get("legacy_prediction_mainline_reactivation_authorized")
        is not False
        or frozen.get("portfolio_activation_authorized") is not False
        or frozen.get("decision_usefulness_established") is not False
        or frozen.get("historical_evidence") != "INCONCLUSIVE"
        or frozen.get("prediction_v2_mode") != "SHADOW_ONLY"
        or frozen.get("prediction_v2_route") != "BASELINE_ONLY"
        or frozen.get("registered_child_count") != 3
        or frozen.get("registered_total_with_mainline_execution") != 4
        or frozen.get("candidate_considerations_executed") != 0
        or frozen.get("database_queries") != 0
        or frozen.get("historical_rows_read") != 0
        or frozen.get("folds_executed") != 0
        or frozen.get("bootstrap_children_executed") != 0
        or frozen.get("new_evidence_created") is not False
        or frozen.get("new_model_created") is not False
        or frozen.get("candidate_expert_authorized") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("production_action") != "none"
        or frozen.get("repetition_scan") != REPETITION_SCAN
    ):
        raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
            "structural_baseline_route_frozen_contract_changed"
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
        raise PredictionV2StructuralBaselineComparisonRouteDecisionError(
            "structural_baseline_route_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
