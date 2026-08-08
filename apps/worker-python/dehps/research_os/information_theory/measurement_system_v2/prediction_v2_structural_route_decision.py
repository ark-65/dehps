from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY = (
    "prediction-v2-structural-route-decision"
)
PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_CAPABILITY = (
    "prediction_v2_structural_route_decision"
)
PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_COMPLETION_FACT = (
    "prediction-v2-structural-route-decision:COMPLETE"
)
PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/prediction-v2-structural-route-decision-source-v1.json"
)
PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY = (
    "prediction-v2-structural-portfolio-evaluation"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY = (
    "prediction-v2-structural-baseline-comparison-preregistration"
)

EVALUATION_EXECUTION_DIGEST = (
    "f17d1a9f7aa19479599f35ce3eacf4847e9100b2548f25c7b848c19d8e02b3df"
)
EVALUATION_DECISION_DIGEST = (
    "e467e86bdac0a18d4c21d29aed3d5a41bdaf9ece545988169b13e0056cdf9893"
)
EVALUATION_ROUTE_HANDOFF_DIGEST = (
    "bd59e548910b2e727f8b5b284d4f80b8c75c206a5258961a0a4683e87c42f723"
)
EVALUATION_COMPLETION_DIGEST = (
    "95c1f01e8ea097be7b21f555d8442ae6afc69e1a5e3611f23ef86b9b6ca160e6"
)
EVALUATION_DECISION = "SUPPORTED_AT_FROZEN_B176_AGAINST_UNIFORM_RANDOM_ONLY"
EVALUATION_ROUTE_DISPOSITION = "ADVANCE_TO_SEPARATE_STRUCTURAL_ROUTE_DECISION"

ROUTE_DECISION = (
    "ROUTE_TO_NON_PREDICTIVE_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION"
)
STRUCTURAL_ARTIFACT_ROLE = "OFFLINE_STRUCTURAL_DIVERSIFICATION_REFERENCE_ONLY"
ARCHIVE_CONDITION = (
    "IF_RESULT_BLIND_PREREGISTRATION_CANNOT_FREEZE_STRONGER_SIMPLE_SAME_BUDGET_"
    "LABEL_SYMMETRIC_BASELINES_AND_AN_OBSERVED_RESULT_INDEPENDENT_FAILURE_RULE_"
    "ARCHIVE_AS_ENGINEERING_EVIDENCE_ONLY"
)

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-structural-route-decision-round-72-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-structural-route-decision-round-72-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/prediction_v2_structural_route_decision.py"
)
FROZEN_CONTRACT_DIGEST = (
    "2638c84357b2f65b2bd324bb7e520b896afad1ec613a66e94cdbfb9c032f55c8"
)


class PredictionV2StructuralRouteDecisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2StructuralRouteDecisionRun:
    decision: Mapping[str, Any]
    baseline_preregistration_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.decision, self.baseline_preregistration_handoff, self.completion


def load_prediction_v2_structural_route_decision_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2StructuralRouteDecisionError(
            f"structural_route_decision_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-structural-route-decision-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_structural_route_decision_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 399
        or payload.get("research_execution_id") != 320
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 400
        or payload.get("engineering_execution_id") != 321
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
            domain="dehps.prediction-v2.structural-route-decision-frozen-contract.v1",
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.prediction-v2.structural-route-decision-source-set.v1",
        )
    ):
        raise PredictionV2StructuralRouteDecisionError(
            "structural_route_decision_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2StructuralRouteDecisionError(
            "structural_route_decision_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_structural_route_decision_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2StructuralRouteDecisionError(
                f"structural_route_decision_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2StructuralRouteDecisionError(
                f"structural_route_decision_source_modified:{relative}"
            )


def build_prediction_v2_structural_route_decision_artifacts(
    *,
    source_contract: Mapping[str, Any],
    evaluation_execution: Mapping[str, Any],
    evaluation_decision: Mapping[str, Any],
    evaluation_route_handoff: Mapping[str, Any],
    evaluation_completion: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2StructuralRouteDecisionRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        evaluation_execution=evaluation_execution,
        evaluation_decision=evaluation_decision,
        evaluation_route_handoff=evaluation_route_handoff,
        evaluation_completion=evaluation_completion,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(evaluation_execution["artifact_digest"]),
        str(evaluation_decision["artifact_digest"]),
        str(evaluation_route_handoff["artifact_digest"]),
        str(evaluation_completion["artifact_digest"]),
    )
    decision = _artifact(
        schema_version="dehps-prediction-v2-structural-route-decision.v1",
        artifact_type="prediction_v2_structural_route_decision",
        body={
            "status": "COMPLETE",
            "decision": ROUTE_DECISION,
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "evaluation_decision": EVALUATION_DECISION,
            "evaluation_boundary": "UNIFORM_RANDOM_COMPARATOR_ONLY",
            "reason": ("UNIFORM_RANDOM_IS_TOO_WEAK_AS_THE_SOLE_OPERATIONAL_COMPARATOR"),
            "stronger_baseline_comparison_required": True,
            "same_budget_required": True,
            "label_symmetry_required": True,
            "transparent_baselines_required": True,
            "complexity_accounting_required": True,
            "observed_result_independent_failure_rule_required": True,
            "archive_condition": ARCHIVE_CONDITION,
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
            "optimizer_proposals_executed": 0,
            "null_replicates_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain="dehps.prediction-v2.structural-route-decision.v1",
    )
    handoff = _artifact(
        schema_version=(
            "dehps-prediction-v2-structural-baseline-comparison-"
            "preregistration-handoff.v1"
        ),
        artifact_type=(
            "prediction_v2_structural_baseline_comparison_preregistration_handoff"
        ),
        body={
            "status": "COMPLETE",
            "route_decision": ROUTE_DECISION,
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "preregistration_scope": (
                "STRONGER_SIMPLE_SAME_BUDGET_LABEL_SYMMETRIC_BASELINE_COMPARISON"
            ),
            "result_blind_preregistration_required": True,
            "observed_result_may_define_thresholds": False,
            "baseline_classes_frozen": False,
            "comparison_execution_authorized": False,
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
            "archive_condition": ARCHIVE_CONDITION,
            "next_consumer": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(*parent_digests, str(decision["artifact_digest"])),
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-"
            "preregistration-handoff.v1"
        ),
    )
    completion = _artifact(
        schema_version="dehps-prediction-v2-structural-route-decision-completion.v1",
        artifact_type="prediction_v2_structural_route_decision_completion",
        body={
            "status": "COMPLETE",
            "completion_fact": PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_COMPLETION_FACT,
            "source_contract_digest": source_digest,
            "evaluation_execution_digest": evaluation_execution["artifact_digest"],
            "route_decision_digest": decision["artifact_digest"],
            "baseline_preregistration_handoff_digest": handoff["artifact_digest"],
            "decision": ROUTE_DECISION,
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "registered_child_count": 3,
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
            "optimizer_proposals_executed": 0,
            "null_replicates_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "archive_condition": ARCHIVE_CONDITION,
            "next_consumer": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(decision["artifact_digest"]),
            str(handoff["artifact_digest"]),
        ),
        domain="dehps.prediction-v2.structural-route-decision-completion.v1",
    )
    return PredictionV2StructuralRouteDecisionRun(
        decision=decision,
        baseline_preregistration_handoff=handoff,
        completion=completion,
    )


def replay_prediction_v2_structural_route_decision(
    *,
    source_contract: Mapping[str, Any],
    evaluation_execution: Mapping[str, Any],
    evaluation_decision: Mapping[str, Any],
    evaluation_route_handoff: Mapping[str, Any],
    evaluation_completion: Mapping[str, Any],
) -> tuple[PredictionV2StructuralRouteDecisionRun, dict[str, Any]]:
    run = build_prediction_v2_structural_route_decision_artifacts(
        source_contract=source_contract,
        evaluation_execution=evaluation_execution,
        evaluation_decision=evaluation_decision,
        evaluation_route_handoff=evaluation_route_handoff,
        evaluation_completion=evaluation_completion,
    )
    replay = {
        "schema_version": "dehps-prediction-v2-structural-route-decision-replay.v1",
        "status": "REPLAY_VERIFIED",
        "decision": ROUTE_DECISION,
        "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
        "same_registered_content": True,
        "workload_rerun": False,
        "historical_rows_read": 0,
        "database_queries_during_replay": 0,
        "folds_replayed": 0,
        "optimizer_proposals_replayed": 0,
        "null_replicates_replayed": 0,
        "evidence_created": False,
        "manual_input_assembly": False,
        "next_consumer": (
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
        ),
    }
    return run, replay


def _validate_parent_artifacts(
    *,
    evaluation_execution: Mapping[str, Any],
    evaluation_decision: Mapping[str, Any],
    evaluation_route_handoff: Mapping[str, Any],
    evaluation_completion: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts_and_domains = (
        (evaluation_execution, "dehps.research-os.mainline-execution.v1"),
        (
            evaluation_decision,
            "dehps.prediction-v2.structural-portfolio-evaluation-decision.v1",
        ),
        (
            evaluation_route_handoff,
            "dehps.prediction-v2.structural-route-handoff.v1",
        ),
        (
            evaluation_completion,
            "dehps.prediction-v2.structural-portfolio-evaluation-completion.v1",
        ),
    )
    for artifact, domain in artifacts_and_domains:
        _verify_artifact(artifact, domain=domain)
    if require_registered_identities and tuple(
        str(artifact.get("artifact_digest")) for artifact, _ in artifacts_and_domains
    ) != (
        EVALUATION_EXECUTION_DIGEST,
        EVALUATION_DECISION_DIGEST,
        EVALUATION_ROUTE_HANDOFF_DIGEST,
        EVALUATION_COMPLETION_DIGEST,
    ):
        raise PredictionV2StructuralRouteDecisionError(
            "structural_route_decision_registered_identity_changed"
        )
    if (
        evaluation_execution.get("task_key")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
        or evaluation_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or evaluation_execution.get("completion_fact")
        != "prediction-v2-structural-portfolio-evaluation:COMPLETE"
        or evaluation_execution.get("evaluation_decision") != EVALUATION_DECISION
        or evaluation_execution.get("route_disposition") != EVALUATION_ROUTE_DISPOSITION
        or evaluation_execution.get("structural_evaluation_decision_digest")
        != evaluation_decision.get("artifact_digest")
        or evaluation_execution.get("structural_route_handoff_digest")
        != evaluation_route_handoff.get("artifact_digest")
        or evaluation_execution.get("structural_evaluation_completion_digest")
        != evaluation_completion.get("artifact_digest")
        or evaluation_execution.get("historical_evidence") != "INCONCLUSIVE"
        or evaluation_execution.get("prediction_v2_mode") != "SHADOW_ONLY"
        or evaluation_execution.get("prediction_v2_route") != "BASELINE_ONLY"
        or evaluation_execution.get("decision_usefulness_claim") is not False
        or evaluation_execution.get("prediction_probability_claim") is not False
        or evaluation_execution.get("evidence_created") is not False
        or evaluation_execution.get("new_model_created") is not False
        or evaluation_execution.get("candidate_expert_authorized") is not False
        or evaluation_execution.get("promotion_gate_opened") is not False
        or evaluation_execution.get("p3_authorized") is not False
        or evaluation_execution.get("production_action") != "none"
        or evaluation_decision.get("decision") != EVALUATION_DECISION
        or evaluation_decision.get("hypothesis_scope")
        != "FIXED_B176_OPTIMIZER_VERSUS_UNIFORM_SAME_BUDGET"
        or evaluation_decision.get("candidate_budget") != 176
        or evaluation_decision.get("selected_stats")
        != {
            "singleton_square_sum": 33_796,
            "pair_square_sum": 14_152,
            "minimum_replacement_distance": 2,
            "sum_pairwise_replacement_distance": 76_030,
        }
        or evaluation_decision.get("selected_strictly_dominated_null_count") != 4_096
        or evaluation_decision.get("selected_null_strictly_dominating_count") != 0
        or evaluation_decision.get("p_value_claim") is not False
        or evaluation_decision.get("global_optimality_claim") is not False
        or evaluation_decision.get("decision_usefulness_claim") is not False
        or evaluation_decision.get("prediction_probability_claim") is not False
        or evaluation_route_handoff.get("evaluation_decision") != EVALUATION_DECISION
        or evaluation_route_handoff.get("route_disposition")
        != EVALUATION_ROUTE_DISPOSITION
        or evaluation_route_handoff.get("portfolio_activation_authorized") is not False
        or evaluation_route_handoff.get("decision_usefulness_established") is not False
        or evaluation_route_handoff.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
        or evaluation_completion.get("completion_fact")
        != "prediction-v2-structural-portfolio-evaluation:COMPLETE"
        or evaluation_completion.get("evaluation_decision_digest")
        != evaluation_decision.get("artifact_digest")
        or evaluation_completion.get("route_handoff_digest")
        != evaluation_route_handoff.get("artifact_digest")
        or evaluation_completion.get("decision") != EVALUATION_DECISION
        or evaluation_completion.get("route_disposition")
        != EVALUATION_ROUTE_DISPOSITION
        or evaluation_completion.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
    ):
        raise PredictionV2StructuralRouteDecisionError(
            "structural_route_decision_parent_consistency_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key") != PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
        or frozen.get("registered_input_digests")
        != [
            EVALUATION_EXECUTION_DIGEST,
            EVALUATION_DECISION_DIGEST,
            EVALUATION_ROUTE_HANDOFF_DIGEST,
            EVALUATION_COMPLETION_DIGEST,
        ]
        or frozen.get("evaluation_decision") != EVALUATION_DECISION
        or frozen.get("route_decision") != ROUTE_DECISION
        or frozen.get("structural_artifact_role") != STRUCTURAL_ARTIFACT_ROLE
        or frozen.get("archive_condition") != ARCHIVE_CONDITION
        or frozen.get("stronger_baseline_comparison_required") is not True
        or frozen.get("same_budget_required") is not True
        or frozen.get("label_symmetry_required") is not True
        or frozen.get("transparent_baselines_required") is not True
        or frozen.get("complexity_accounting_required") is not True
        or frozen.get("observed_result_independent_failure_rule_required") is not True
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
        or frozen.get("optimizer_proposals_executed") != 0
        or frozen.get("null_replicates_executed") != 0
        or frozen.get("new_evidence_created") is not False
        or frozen.get("new_model_created") is not False
        or frozen.get("candidate_expert_authorized") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("production_action") != "none"
    ):
        raise PredictionV2StructuralRouteDecisionError(
            "structural_route_decision_frozen_contract_changed"
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
        raise PredictionV2StructuralRouteDecisionError(
            "structural_route_decision_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
