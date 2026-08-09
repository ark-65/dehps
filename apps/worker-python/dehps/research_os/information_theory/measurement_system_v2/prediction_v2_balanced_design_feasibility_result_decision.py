from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_feasibility_execution import (
    BLOCK_COUNT,
    PAIR_REPLICATION_TARGET,
    POINT_REPLICATION_TARGET,
    orbit_inventory_from_artifact,
    verify_positive_certificate,
)

PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY = (
    "prediction-v2-balanced-design-feasibility-result-decision"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_CAPABILITY = (
    "prediction_v2_balanced_design_feasibility_result_decision"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_COMPLETION_FACT = (
    "prediction-v2-balanced-design-feasibility-result-decision:COMPLETE"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "prediction-v2-balanced-design-feasibility-result-decision-source-v1.json"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY = (
    "prediction-v2-balanced-design-feasibility-execution"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY = (
    "prediction-v2-balanced-design-structural-evaluation-design"
)
PREDICTION_V2_BALANCED_DESIGN_RESULT_DECISION_APPROVED_EVENT = (
    "research-contract:prediction-v2-balanced-design-result-decision:approved"
)

EXECUTION_ARTIFACT_DIGEST = (
    "4e060203c9172d13987b9e4597a70d01ccbd905aa7f0b1db8a74fa2a1f31ee6d"
)
ORBIT_INVENTORY_DIGEST = (
    "dde85462b725ec8719a30c5879dee0ba90b4a6d97f4a78b2d08b2beadc0c1f90"
)
SEARCH_RESULT_DIGEST = (
    "da9283998bd5833b6ad66f64543c42d0a94b06b7a730891eb718e21188210e79"
)
EXECUTION_COMPLETION_DIGEST = (
    "345590d896621145bb54c88e7d5a3c07e07d563cddf637ca7f021f08874717f6"
)
CERTIFICATE_DIGEST = "b7a0069edef9f6a2aeec3f2205a50a63ba39594ed555c3c89b108830cd3c28db"
TERMINAL_CHECKPOINT_DIGEST = (
    "2f130c4c729cb6e25201b997ba50361cf7172e21b0bcc8a6381df9e11613d16e"
)
EXECUTION_ID = "780cf7c1da4f4133063743fd468804d304b02b45619d219a32d6f68f3b24baaa"

POSITIVE_OUTCOME = "FOUND_EXACT_2_33_6_5_DESIGN"
BOUNDED_NEGATIVE_OUTCOME = "NOT_FOUND_WITHIN_FROZEN_BUDGET"
INVALID_OUTCOME = "INVALID_EXECUTION_NO_DECISION"
POSITIVE_DECISION = "CYCLIC_BALANCED_DESIGN_EXISTENCE_ESTABLISHED_STRUCTURAL_ONLY"
BOUNDED_NEGATIVE_DECISION = "CYCLIC_SCOPE_INCONCLUSIVE_NO_GLOBAL_NONEXISTENCE"
INVALID_DECISION = "INVALID_NO_RESEARCH_DECISION"
REPETITION_SCAN = "ABSENT_BY_CONSTRUCTION"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-balanced-design-result-decision-round-97-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-balanced-design-result-decision-round-98-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/"
    "prediction_v2_balanced_design_feasibility_result_decision.py"
)
FROZEN_CONTRACT_DIGEST = (
    "628d5e3e7acf9c8f07529e4c071804f03b9f49dc82dcc98e58e374a93385fcbb"
)


class PredictionV2BalancedDesignResultDecisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2BalancedDesignResultDecisionRun:
    decision: Mapping[str, Any]
    structural_evaluation_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.decision, self.structural_evaluation_handoff, self.completion


def load_prediction_v2_balanced_design_result_decision_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2BalancedDesignResultDecisionError(
            f"balanced_design_result_decision_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-balanced-design-result-decision-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_balanced_design_feasibility_result_decision_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 424
        or payload.get("research_execution_id") != 345
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 425
        or payload.get("engineering_execution_id") != 346
        or payload.get("result_aware") is not True
        or payload.get("post_hoc_rule_change") is not False
        or payload.get("database_queries") != 0
        or payload.get("historical_rows_read") != 0
        or payload.get("folds_executed") != 0
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
            domain="dehps.prediction-v2.balanced-design-result-decision-frozen-contract.v1",
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.prediction-v2.balanced-design-result-decision-source-set.v1",
        )
    ):
        raise PredictionV2BalancedDesignResultDecisionError(
            "balanced_design_result_decision_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2BalancedDesignResultDecisionError(
            "balanced_design_result_decision_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_balanced_design_result_decision_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2BalancedDesignResultDecisionError(
                f"balanced_design_result_decision_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2BalancedDesignResultDecisionError(
                f"balanced_design_result_decision_source_modified:{relative}"
            )


def build_prediction_v2_balanced_design_result_decision_artifacts(
    *,
    source_contract: Mapping[str, Any],
    execution: Mapping[str, Any],
    inventory: Mapping[str, Any],
    result: Mapping[str, Any],
    completion: Mapping[str, Any],
    execution_replay: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2BalancedDesignResultDecisionRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        execution=execution,
        inventory=inventory,
        result=result,
        completion=completion,
        execution_replay=execution_replay,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(execution["artifact_digest"]),
        str(inventory["artifact_digest"]),
        str(result["artifact_digest"]),
        str(completion["artifact_digest"]),
    )
    decision = _artifact(
        schema_version="dehps-prediction-v2-balanced-design-result-decision.v1",
        artifact_type="prediction_v2_balanced_design_feasibility_result_decision",
        body={
            "status": "COMPLETE",
            "execution_outcome": POSITIVE_OUTCOME,
            "decision": POSITIVE_DECISION,
            "structural_scope": "ALL_AND_ONLY_Z33_TRANSLATION_INVARIANT_SIMPLE_2_DESIGNS",
            "existence_established_in_cyclic_scope": True,
            "global_nonexistence_established": False,
            "certificate_artifact_digest": CERTIFICATE_DIGEST,
            "certificate_block_count": BLOCK_COUNT,
            "certificate_verified": True,
            "terminal_checkpoint_digest": TERMINAL_CHECKPOINT_DIGEST,
            "terminal_checkpoint_verified": True,
            "post_hoc_rule_change": False,
            "prediction_probability_claim": False,
            "decision_usefulness_established": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "portfolio_activation_authorized": False,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
            ),
            "production_action": "none",
            "repetition_scan": REPETITION_SCAN,
            "separate_duplicate_membership_or_uniqueness_scan": False,
        },
        parent_digests=parent_digests,
        domain="dehps.prediction-v2.balanced-design-result-decision.v1",
    )
    handoff = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-design-handoff.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_evaluation_design_handoff"
        ),
        body={
            "status": "COMPLETE",
            "decision": POSITIVE_DECISION,
            "fixed_certificate_artifact_digest": CERTIFICATE_DIGEST,
            "fixed_before_evaluation": True,
            "evaluation_task": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
            ),
            "evaluation_execution_authorized": False,
            "same_budget_null_required": True,
            "historical_outcomes_allowed": False,
            "automatic_threshold_relaxation": False,
            "automatic_seed_retry": False,
            "automatic_portfolio_mutation": False,
            "prediction_probability_claim": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "new_evidence_created": False,
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
            ),
            "production_action": "none",
            "repetition_scan": REPETITION_SCAN,
        },
        parent_digests=(*parent_digests, str(decision["artifact_digest"])),
        domain=(
            "dehps.prediction-v2.balanced-design-structural-evaluation-design-handoff.v1"
        ),
    )
    completion_artifact = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-result-decision-completion.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_feasibility_result_decision_completion"
        ),
        body={
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_COMPLETION_FACT
            ),
            "source_contract_digest": source_digest,
            "execution_artifact_digest": execution["artifact_digest"],
            "decision_artifact_digest": decision["artifact_digest"],
            "structural_evaluation_handoff_digest": handoff["artifact_digest"],
            "decision": POSITIVE_DECISION,
            "certificate_artifact_digest": CERTIFICATE_DIGEST,
            "certificate_verified": True,
            "registered_child_count": 3,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
            ),
            "production_action": "none",
            "repetition_scan": REPETITION_SCAN,
        },
        parent_digests=(
            source_digest,
            str(decision["artifact_digest"]),
            str(handoff["artifact_digest"]),
        ),
        domain="dehps.prediction-v2.balanced-design-result-decision-completion.v1",
    )
    return PredictionV2BalancedDesignResultDecisionRun(
        decision=decision,
        structural_evaluation_handoff=handoff,
        completion=completion_artifact,
    )


def replay_prediction_v2_balanced_design_result_decision(
    **kwargs: Any,
) -> tuple[PredictionV2BalancedDesignResultDecisionRun, dict[str, Any]]:
    run = build_prediction_v2_balanced_design_result_decision_artifacts(**kwargs)
    return run, {
        "schema_version": (
            "dehps-prediction-v2-balanced-design-result-decision-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "decision": POSITIVE_DECISION,
        "certificate_verified": True,
        "same_registered_content": True,
        "workload_rerun": False,
        "historical_rows_read": 0,
        "database_queries_during_replay": 0,
        "folds_replayed": 0,
        "manual_input_assembly": False,
        "repetition_scan": REPETITION_SCAN,
        "next_consumer": (
            PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
        ),
    }


def _validate_parent_artifacts(
    *,
    execution: Mapping[str, Any],
    inventory: Mapping[str, Any],
    result: Mapping[str, Any],
    completion: Mapping[str, Any],
    execution_replay: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts_and_domains = (
        (execution, "dehps.research-os.mainline-execution.v1"),
        (inventory, "dehps.prediction-v2.balanced-design.orbit-inventory.v1"),
        (result, "dehps.prediction-v2.balanced-design.search-result.v1"),
        (completion, "dehps.prediction-v2.balanced-design.execution-completion.v1"),
    )
    for artifact, domain in artifacts_and_domains:
        _verify_artifact(artifact, domain=domain)
    observed = tuple(
        str(artifact.get("artifact_digest")) for artifact, _ in artifacts_and_domains
    )
    if require_registered_identities and observed != (
        EXECUTION_ARTIFACT_DIGEST,
        ORBIT_INVENTORY_DIGEST,
        SEARCH_RESULT_DIGEST,
        EXECUTION_COMPLETION_DIGEST,
    ):
        raise PredictionV2BalancedDesignResultDecisionError(
            "balanced_design_result_decision_registered_identity_changed"
        )
    certificate = result.get("certificate")
    if not isinstance(certificate, Mapping):
        raise PredictionV2BalancedDesignResultDecisionError(
            "balanced_design_result_decision_certificate_missing"
        )
    _verify_artifact(
        certificate,
        domain="dehps.prediction-v2.balanced-design.certificate.v1",
    )
    compiled = orbit_inventory_from_artifact(inventory, require_formal_identity=True)
    verification = verify_positive_certificate(
        inventory=compiled,
        certificate=certificate,
        expected_block_count=BLOCK_COUNT,
        point_replication_target=POINT_REPLICATION_TARGET,
        pair_replication_target=PAIR_REPLICATION_TARGET,
    )
    if (
        execution.get("task_key")
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
        or execution.get("execution_id") != EXECUTION_ID
        or execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or execution.get("outcome") != POSITIVE_OUTCOME
        or execution.get("existence_established_in_cyclic_scope") is not True
        or execution.get("global_nonexistence_established") is not False
        or execution.get("orbit_inventory_digest") != inventory.get("artifact_digest")
        or execution.get("search_result_digest") != result.get("artifact_digest")
        or execution.get("execution_completion_digest")
        != completion.get("artifact_digest")
        or execution.get("checkpoint_count") != 2
        or execution.get("repetition_scan") != REPETITION_SCAN
        or result.get("status") != "COMPLETE"
        or result.get("outcome") != POSITIVE_OUTCOME
        or result.get("certificate_artifact_digest") != CERTIFICATE_DIGEST
        or certificate.get("artifact_digest") != CERTIFICATE_DIGEST
        or certificate.get("block_count") != BLOCK_COUNT
        or certificate.get("profile") != [5, 1]
        or result.get("terminal_checkpoint_digest") != TERMINAL_CHECKPOINT_DIGEST
        or result.get("repetition_scan") != REPETITION_SCAN
        or result.get("separate_duplicate_membership_or_uniqueness_scan") is not False
        or completion.get("status") != "COMPLETE"
        or completion.get("completion_fact")
        != "prediction-v2-balanced-design-feasibility-execution:COMPLETE"
        or completion.get("outcome") != POSITIVE_OUTCOME
        or completion.get("result_artifact_digest") != result.get("artifact_digest")
        or completion.get("inventory_artifact_digest")
        != inventory.get("artifact_digest")
        or completion.get("terminal_checkpoint_digest") != TERMINAL_CHECKPOINT_DIGEST
        or completion.get("repetition_scan") != REPETITION_SCAN
        or verification.certificate_digest != CERTIFICATE_DIGEST
        or execution_replay.get("status") != "REPLAY_VERIFIED"
        or execution_replay.get("outcome") != POSITIVE_OUTCOME
        or execution_replay.get("certificate_verified") is not True
        or execution_replay.get("terminal_checkpoint_verified") is not True
        or execution_replay.get("workload_rerun") is not False
        or execution_replay.get("repetition_scan") != REPETITION_SCAN
    ):
        raise PredictionV2BalancedDesignResultDecisionError(
            "balanced_design_result_decision_parent_consistency_invalid"
        )
    if (
        any(
            artifact.get("production_action") != "none"
            for artifact in (execution, result, completion)
        )
        or result.get("evidence_created") is not False
        or result.get("new_model_created") is not False
        or execution.get("evidence_created") is not False
        or execution.get("new_model_created") is not False
        or execution.get("promotion_gate_opened") is not False
        or execution.get("p3_authorized") is not False
        or completion.get("evidence_created") is not False
        or completion.get("new_model_created") is not False
        or completion.get("promotion_gate_opened") is not False
        or completion.get("p3_authorized") is not False
    ):
        raise PredictionV2BalancedDesignResultDecisionError(
            "balanced_design_result_decision_parent_claim_boundary_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key")
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_DESIGN_TASK_KEY
        or frozen.get("registered_input_digests")
        != [
            EXECUTION_ARTIFACT_DIGEST,
            ORBIT_INVENTORY_DIGEST,
            SEARCH_RESULT_DIGEST,
            EXECUTION_COMPLETION_DIGEST,
        ]
        or frozen.get("outcome_mapping")
        != {
            POSITIVE_OUTCOME: POSITIVE_DECISION,
            BOUNDED_NEGATIVE_OUTCOME: BOUNDED_NEGATIVE_DECISION,
            INVALID_OUTCOME: INVALID_DECISION,
        }
        or frozen.get("live_outcome") != POSITIVE_OUTCOME
        or frozen.get("live_decision") != POSITIVE_DECISION
        or frozen.get("certificate_digest") != CERTIFICATE_DIGEST
        or frozen.get("terminal_checkpoint_digest") != TERMINAL_CHECKPOINT_DIGEST
        or frozen.get("certificate_block_count") != BLOCK_COUNT
        or frozen.get("registered_child_count") != 3
        or frozen.get("registered_total_with_mainline_execution") != 4
        or frozen.get("post_hoc_rule_change") is not False
        or frozen.get("prediction_probability_claim") is not False
        or frozen.get("decision_usefulness_established") is not False
        or frozen.get("historical_evidence") != "INCONCLUSIVE"
        or frozen.get("prediction_v2_mode") != "SHADOW_ONLY"
        or frozen.get("prediction_v2_route") != "BASELINE_ONLY"
        or frozen.get("database_queries") != 0
        or frozen.get("historical_rows_read") != 0
        or frozen.get("folds_executed") != 0
        or frozen.get("new_evidence_created") is not False
        or frozen.get("new_model_created") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("production_action") != "none"
        or frozen.get("repetition_scan") != REPETITION_SCAN
        or frozen.get("separate_duplicate_membership_or_uniqueness_scan") is not False
    ):
        raise PredictionV2BalancedDesignResultDecisionError(
            "balanced_design_result_decision_frozen_contract_changed"
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
        raise PredictionV2BalancedDesignResultDecisionError(
            "balanced_design_result_decision_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
