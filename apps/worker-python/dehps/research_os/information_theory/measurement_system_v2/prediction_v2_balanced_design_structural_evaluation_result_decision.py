from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY = (
    "prediction-v2-balanced-design-structural-evaluation-result-decision"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_CAPABILITY = (
    "prediction_v2_balanced_design_structural_evaluation_result_decision"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_COMPLETION_FACT = (
    "prediction-v2-balanced-design-structural-evaluation-result-decision:COMPLETE"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_UTILITY_RESEARCH_INTAKE_TASK_KEY = (
    "prediction-v2-balanced-design-structural-utility-research-intake"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "prediction-v2-balanced-design-structural-evaluation-result-decision-source-v1.json"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_APPROVED_EVENT = (
    "research-contract:prediction-v2-balanced-design-structural-evaluation-"
    "result-decision:approved"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_UTILITY_RESEARCH_APPROVED_EVENT = (
    "research-contract:prediction-v2-balanced-design-structural-utility:approved"
)

PARENT_EXECUTION_ID = "5dd2439b5980ce8eb2a7f29269ca35b224c05a3daba13250b04629b6916ef9e1"
PARENT_EXECUTION_DIGEST = (
    "cb0be723aae6642fdc0956b42487d3daf65e72a166c9bda138f2549454ee050f"
)
EVALUATION_RESULT_DIGEST = (
    "6fb8cdc6a279295126728dac76e3c11c01f7eda839c2c7874d4fd2652ba8f259"
)
EVALUATION_DIAGNOSTICS_DIGEST = (
    "9c1fe1294b30592c6b2c6c731621f9c2609f74f7f6aed733f8332fbf696eda37"
)
EVALUATION_COMPLETION_DIGEST = (
    "6fe5390299b0d15ed98f24c8dce23a88d50819ce63f3a8ce7058f26809d452fc"
)

REGISTERED_OUTCOME = (
    "HIGHER_ORDER_STRUCTURAL_HOLDOUT_ADVANTAGE_WITHIN_MATCHED_NULL_ONLY"
)
DECISION = "RETAIN_AS_STRUCTURAL_DIVERSIFICATION_REFERENCE_ONLY"
PRIMARY_NULL = "Z33_ORBIT_PROFILE_MATCHED_WITHOUT_REPLACEMENT_5_FULL_1_SHORT_B176"
CANDIDATE_TRIPLE_COLLISION_MASS = 605
PRIMARY_LOWER_TAIL_NUMERATOR = 55
PRIMARY_UPPER_TAIL_NUMERATOR = 9_972
PRIMARY_DENOMINATOR = 10_000
SECONDARY_LOWER_TAIL_NUMERATOR = 1
SECONDARY_UPPER_TAIL_NUMERATOR = 2_000
SECONDARY_DENOMINATOR = 2_000

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-balanced-design-structural-evaluation-result-"
    "decision-round-107-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-balanced-design-structural-evaluation-result-"
    "decision-round-107-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/"
    "prediction_v2_balanced_design_structural_evaluation_result_decision.py"
)
FROZEN_DECISION_CONTRACT_DIGEST = (
    "32aed81d4bfafa7e541ea347097d364fab21a42f1dbd820bbb9e18bf53014c4f"
)

_RESULT_DOMAIN = "dehps.prediction-v2.balanced-design-structural-evaluation-result.v1"
_DIAGNOSTICS_DOMAIN = (
    "dehps.prediction-v2.balanced-design-structural-evaluation-diagnostics.v1"
)
_PARENT_COMPLETION_DOMAIN = (
    "dehps.prediction-v2.balanced-design-structural-evaluation-execution-completion.v1"
)


class PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2BalancedDesignStructuralEvaluationResultDecisionRun:
    decision: Mapping[str, Any]
    structural_utility_intake_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.decision, self.structural_utility_intake_handoff, self.completion


def load_prediction_v2_balanced_design_structural_evaluation_result_decision_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(
            f"balanced_design_structural_result_decision_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-balanced-design-structural-evaluation-result-decision-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_balanced_design_structural_evaluation_result_decision_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 438
        or payload.get("research_execution_id") != 359
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 439
        or payload.get("engineering_execution_id") != 360
        or payload.get("result_aware") is not True
        or payload.get("post_hoc_rule_change") is not False
        or payload.get("workload_rerun") is not False
        or payload.get("registered_children") != 3
        or payload.get("new_evidence_created") is not False
        or payload.get("new_model_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("frozen_contract_digest") != FROZEN_DECISION_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain=(
                "dehps.prediction-v2.balanced-design-structural-evaluation-"
                "result-decision-frozen-contract.v1"
            ),
        )
        != FROZEN_DECISION_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.prediction-v2.balanced-design-structural-evaluation-"
                "result-decision-source-set.v1"
            ),
        )
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(
            "balanced_design_structural_result_decision_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(
            "balanced_design_structural_result_decision_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_balanced_design_structural_evaluation_result_decision_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(
                f"balanced_design_structural_result_decision_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(
                f"balanced_design_structural_result_decision_source_modified:{relative}"
            )


def build_prediction_v2_balanced_design_structural_evaluation_result_decision_artifacts(
    *,
    source_contract: Mapping[str, Any],
    execution: Mapping[str, Any],
    result: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    completion: Mapping[str, Any],
    execution_replay: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2BalancedDesignStructuralEvaluationResultDecisionRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        execution=execution,
        result=result,
        diagnostics=diagnostics,
        completion=completion,
        execution_replay=execution_replay,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(execution["artifact_digest"]),
        str(result["artifact_digest"]),
        str(diagnostics["artifact_digest"]),
        str(completion["artifact_digest"]),
    )
    claim_boundary = _claim_boundary()
    decision = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-result-"
            "decision.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_evaluation_result_decision"
        ),
        body={
            "status": "COMPLETE",
            "registered_outcome": REGISTERED_OUTCOME,
            "decision": DECISION,
            "candidate_triple_collision_mass": CANDIDATE_TRIPLE_COLLISION_MASS,
            "primary_null": PRIMARY_NULL,
            "primary_lower_tail_numerator": PRIMARY_LOWER_TAIL_NUMERATOR,
            "primary_upper_tail_numerator": PRIMARY_UPPER_TAIL_NUMERATOR,
            "primary_denominator": PRIMARY_DENOMINATOR,
            "primary_alpha": "1/100",
            "primary_threshold_crossed": True,
            "secondary_lower_tail_numerator": SECONDARY_LOWER_TAIL_NUMERATOR,
            "secondary_upper_tail_numerator": SECONDARY_UPPER_TAIL_NUMERATOR,
            "secondary_denominator": SECONDARY_DENOMINATOR,
            "secondary_is_descriptive_only": True,
            "structural_advantage_established_within_matched_null": True,
            "global_structural_optimum_established": False,
            "prediction_probability_claim": False,
            "expected_payout_claim": False,
            "operational_utility_established": False,
            "portfolio_activation_authorized": False,
            "post_hoc_rule_change": False,
            "workload_rerun": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_UTILITY_RESEARCH_INTAKE_TASK_KEY
            ),
            **claim_boundary,
        },
        parent_digests=parent_digests,
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-result-"
            "decision.v1"
        ),
    )
    handoff = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-utility-research-"
            "intake-handoff.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_utility_research_intake_handoff"
        ),
        body={
            "status": "COMPLETE",
            "decision": DECISION,
            "fixed_certificate_status": "STRUCTURAL_DIVERSIFICATION_REFERENCE_ONLY",
            "future_research_event_required": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_UTILITY_RESEARCH_APPROVED_EVENT
            ),
            "future_utility_definition_must_be_result_blind": True,
            "this_result_may_tune_future_utility": False,
            "automatic_followup_execution_authorized": False,
            "prediction_probability_claim": False,
            "operational_utility_established": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_UTILITY_RESEARCH_INTAKE_TASK_KEY
            ),
            **claim_boundary,
        },
        parent_digests=(*parent_digests, str(decision["artifact_digest"])),
        domain=(
            "dehps.prediction-v2.balanced-design-structural-utility-research-"
            "intake-handoff.v1"
        ),
    )
    completion_artifact = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-result-"
            "decision-completion.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_evaluation_result_decision_completion"
        ),
        body={
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_COMPLETION_FACT
            ),
            "source_contract_digest": source_digest,
            "parent_execution_digest": execution["artifact_digest"],
            "decision_artifact_digest": decision["artifact_digest"],
            "structural_utility_intake_handoff_digest": handoff["artifact_digest"],
            "registered_child_count": 3,
            "decision": DECISION,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_UTILITY_RESEARCH_INTAKE_TASK_KEY
            ),
            **claim_boundary,
        },
        parent_digests=(
            source_digest,
            str(decision["artifact_digest"]),
            str(handoff["artifact_digest"]),
        ),
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-result-"
            "decision-completion.v1"
        ),
    )
    return PredictionV2BalancedDesignStructuralEvaluationResultDecisionRun(
        decision=decision,
        structural_utility_intake_handoff=handoff,
        completion=completion_artifact,
    )


def replay_prediction_v2_balanced_design_structural_evaluation_result_decision(
    **kwargs: Any,
) -> tuple[
    PredictionV2BalancedDesignStructuralEvaluationResultDecisionRun,
    dict[str, Any],
]:
    run = build_prediction_v2_balanced_design_structural_evaluation_result_decision_artifacts(
        **kwargs
    )
    return run, {
        "schema_version": (
            "dehps-prediction-v2-balanced-design-structural-evaluation-result-"
            "decision-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "decision": DECISION,
        "same_registered_content": True,
        "workload_rerun": False,
        "sample_regeneration": False,
        "manual_input_assembly": False,
        "database_queries_during_replay": 0,
        "historical_rows_read": 0,
        "folds_replayed": 0,
        "next_consumer": (
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_UTILITY_RESEARCH_INTAKE_TASK_KEY
        ),
    }


def _validate_parent_artifacts(
    *,
    execution: Mapping[str, Any],
    result: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    completion: Mapping[str, Any],
    execution_replay: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    _verify_artifact(execution, domain="dehps.research-os.mainline-execution.v1")
    _verify_artifact(result, domain=_RESULT_DOMAIN)
    _verify_artifact(diagnostics, domain=_DIAGNOSTICS_DOMAIN)
    _verify_artifact(completion, domain=_PARENT_COMPLETION_DOMAIN)
    if require_registered_identities and (
        execution.get("execution_id") != PARENT_EXECUTION_ID
        or execution.get("artifact_digest") != PARENT_EXECUTION_DIGEST
        or result.get("artifact_digest") != EVALUATION_RESULT_DIGEST
        or diagnostics.get("artifact_digest") != EVALUATION_DIAGNOSTICS_DIGEST
        or completion.get("artifact_digest") != EVALUATION_COMPLETION_DIGEST
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(
            "balanced_design_structural_result_decision_parent_identity_invalid"
        )
    inference = result.get("inference")
    if (
        execution.get("task_key")
        != "prediction-v2-balanced-design-structural-evaluation-execution"
        or execution.get("status") != "COMPLETE"
        or execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or execution.get("outcome") != REGISTERED_OUTCOME
        or execution.get("evaluation_result_digest") != result.get("artifact_digest")
        or execution.get("evaluation_diagnostics_digest")
        != diagnostics.get("artifact_digest")
        or execution.get("evaluation_completion_digest")
        != completion.get("artifact_digest")
        or execution.get("registered_artifact_count") != 4
        or result.get("artifact_type")
        != "prediction_v2_balanced_design_structural_evaluation_result"
        or result.get("status") != "COMPLETE"
        or result.get("outcome") != REGISTERED_OUTCOME
        or result.get("candidate_triple_collision_mass")
        != CANDIDATE_TRIPLE_COLLISION_MASS
        or not isinstance(inference, dict)
        or inference.get("outcome") != REGISTERED_OUTCOME
        or inference.get("primary_lower_tail_numerator") != PRIMARY_LOWER_TAIL_NUMERATOR
        or inference.get("primary_upper_tail_numerator") != PRIMARY_UPPER_TAIL_NUMERATOR
        or inference.get("primary_denominator") != PRIMARY_DENOMINATOR
        or inference.get("secondary_lower_tail_numerator")
        != SECONDARY_LOWER_TAIL_NUMERATOR
        or inference.get("secondary_upper_tail_numerator")
        != SECONDARY_UPPER_TAIL_NUMERATOR
        or inference.get("secondary_denominator") != SECONDARY_DENOMINATOR
        or inference.get("secondary_null_can_change_outcome") is not False
        or diagnostics.get("artifact_type")
        != "prediction_v2_balanced_design_structural_evaluation_diagnostics"
        or diagnostics.get("status") != "COMPLETE"
        or diagnostics.get("candidate", {}).get("triple_collision_mass")
        != CANDIDATE_TRIPLE_COLLISION_MASS
        or completion.get("artifact_type")
        != "prediction_v2_balanced_design_structural_evaluation_execution_completion"
        or completion.get("status") != "COMPLETE"
        or completion.get("outcome") != REGISTERED_OUTCOME
        or completion.get("result_artifact_digest") != result.get("artifact_digest")
        or completion.get("diagnostics_artifact_digest")
        != diagnostics.get("artifact_digest")
        or execution_replay.get("status") != "REPLAY_VERIFIED"
        or execution_replay.get("same_registered_content") is not True
        or execution_replay.get("workload_rerun") is not False
        or execution_replay.get("outcome") != REGISTERED_OUTCOME
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(
            "balanced_design_structural_result_decision_parent_consistency_invalid"
        )
    for artifact in (execution, result, diagnostics, completion):
        if (
            artifact.get("historical_evidence") != "INCONCLUSIVE"
            or artifact.get("prediction_v2_mode") != "SHADOW_ONLY"
            or artifact.get("prediction_v2_route") != "BASELINE_ONLY"
            or artifact.get("evidence_created") is not False
            or artifact.get("new_model_created") is not False
            or artifact.get("promotion_gate_opened") is not False
            or artifact.get("p3_authorized") is not False
            or artifact.get("production_action") != "none"
        ):
            raise PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(
                "balanced_design_structural_result_decision_claim_boundary_invalid"
            )


def _expected_frozen_contract() -> dict[str, Any]:
    return {
        "task_key": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY,
        "capability": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_CAPABILITY,
        "completion_fact": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_COMPLETION_FACT,
        "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_UTILITY_RESEARCH_INTAKE_TASK_KEY,
        "registered_input_digests": [
            PARENT_EXECUTION_DIGEST,
            EVALUATION_RESULT_DIGEST,
            EVALUATION_DIAGNOSTICS_DIGEST,
            EVALUATION_COMPLETION_DIGEST,
        ],
        "research_request_id": 438,
        "research_execution_id": 359,
        "registered_outcome": REGISTERED_OUTCOME,
        "decision": DECISION,
        "candidate_triple_collision_mass": CANDIDATE_TRIPLE_COLLISION_MASS,
        "primary_lower_tail_numerator": PRIMARY_LOWER_TAIL_NUMERATOR,
        "primary_upper_tail_numerator": PRIMARY_UPPER_TAIL_NUMERATOR,
        "primary_denominator": PRIMARY_DENOMINATOR,
        "secondary_lower_tail_numerator": SECONDARY_LOWER_TAIL_NUMERATOR,
        "secondary_upper_tail_numerator": SECONDARY_UPPER_TAIL_NUMERATOR,
        "secondary_denominator": SECONDARY_DENOMINATOR,
        "secondary_is_descriptive_only": True,
        "workload_rerun": False,
        "historical_evidence": "INCONCLUSIVE",
        "new_evidence_created": False,
        "new_model_created": False,
        "promotion_gate_opened": False,
        "p3_authorized": False,
        "production_action": "none",
    }


def _validate_frozen_contract(value: Mapping[str, Any]) -> None:
    if dict(value) != _expected_frozen_contract():
        raise PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(
            "balanced_design_structural_result_decision_frozen_contract_invalid"
        )


def _claim_boundary() -> dict[str, Any]:
    return {
        "database_queries_during_capability": 0,
        "historical_rows_read": 0,
        "folds_executed": 0,
        "historical_evidence": "INCONCLUSIVE",
        "prediction_v2_mode": "SHADOW_ONLY",
        "prediction_v2_route": "BASELINE_ONLY",
        "evidence_created": False,
        "new_model_created": False,
        "candidate_expert_authorized": False,
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
        raise PredictionV2BalancedDesignStructuralEvaluationResultDecisionError(
            "balanced_design_structural_result_decision_artifact_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
