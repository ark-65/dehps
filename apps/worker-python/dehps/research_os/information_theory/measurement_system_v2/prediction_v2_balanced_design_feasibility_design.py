from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY = (
    "prediction-v2-next-result-blind-research-intake"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_CAPABILITY = (
    "prediction_v2_balanced_design_feasibility_design"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_COMPLETION_FACT = (
    "prediction-v2-balanced-design-feasibility-design:COMPLETE"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "prediction-v2-balanced-design-feasibility-design-source-v1.json"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY = (
    "prediction-v2-balanced-design-feasibility-preregistration"
)
PREDICTION_V2_APPROVED_RESULT_BLIND_RESEARCH_CONTRACT_EVENT = (
    "research-contract:prediction-v2-next-result-blind-program:approved"
)

ARCHIVE_ROUTE_DECISION_DIGEST = (
    "886b03fc5873edec8ac2f154ade73fc5c0309ddace83915c8ccc946241150bdb"
)
RESEARCH_INTAKE_HANDOFF_DIGEST = (
    "ad9a142bcd8f70548d985d0483b003cf2d4374ecd0994a35e2c3a26545671105"
)
ARCHIVE_ROUTE_COMPLETION_DIGEST = (
    "147cd0819bca3da1a925812e4f1ac556eeef79b1973b1027406b9d6a511887"
)

ROUTE_DECISION = (
    "ARCHIVE_B176_FROM_ACTIVATION_AND_WAIT_FOR_NEW_RESULT_BLIND_RESEARCH_CONTRACT"
)
STRUCTURAL_ARTIFACT_ROLE = "ARCHIVED_NON_PREDICTIVE_ENGINEERING_REFERENCE_ONLY"
PREDICTION_RESEARCH_DISPOSITION = "FROZEN_NO_ACCEPTED_CANDIDATE"
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

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-balanced-design-feasibility-round-83-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-balanced-design-feasibility-round-84-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/"
    "prediction_v2_balanced_design_feasibility_design.py"
)
FROZEN_CONTRACT_DIGEST = (
    "f428cc9df3a988f8d2919efa3b369ca3b5cdc4a64c4e29a03787bc14d4fe0271"
)


class PredictionV2BalancedDesignFeasibilityDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2BalancedDesignFeasibilityDesignRun:
    specification: Mapping[str, Any]
    preregistration_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.specification, self.preregistration_handoff, self.completion


def load_prediction_v2_balanced_design_feasibility_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2BalancedDesignFeasibilityDesignError(
            f"balanced_design_feasibility_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-balanced-design-feasibility-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_balanced_design_feasibility_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 411
        or payload.get("research_execution_id") != 332
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 412
        or payload.get("engineering_execution_id") != 333
        or payload.get("result_blind") is not True
        or payload.get("database_queries") != 0
        or payload.get("historical_rows_read") != 0
        or payload.get("prior_scores_read") != 0
        or payload.get("prior_predictions_read") != 0
        or payload.get("prior_rankings_read") != 0
        or payload.get("solver_nodes_executed") != 0
        or payload.get("candidate_blocks_generated") != 0
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
            domain="dehps.prediction-v2.balanced-design-feasibility-frozen.v1",
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.prediction-v2.balanced-design-feasibility-source-set.v1",
        )
    ):
        raise PredictionV2BalancedDesignFeasibilityDesignError(
            "balanced_design_feasibility_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2BalancedDesignFeasibilityDesignError(
            "balanced_design_feasibility_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_balanced_design_feasibility_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2BalancedDesignFeasibilityDesignError(
                f"balanced_design_feasibility_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2BalancedDesignFeasibilityDesignError(
                f"balanced_design_feasibility_source_modified:{relative}"
            )


def build_prediction_v2_balanced_design_feasibility_artifacts(
    *,
    source_contract: Mapping[str, Any],
    archive_route_decision_digest: str,
    research_intake_handoff: Mapping[str, Any],
    archive_route_completion: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2BalancedDesignFeasibilityDesignRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        archive_route_decision_digest=archive_route_decision_digest,
        research_intake_handoff=research_intake_handoff,
        archive_route_completion=archive_route_completion,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        archive_route_decision_digest,
        str(research_intake_handoff["artifact_digest"]),
        str(archive_route_completion["artifact_digest"]),
    )
    parameters = {
        "point_count": POINT_COUNT,
        "block_size": BLOCK_SIZE,
        "block_count": BLOCK_COUNT,
        "point_replication_target": POINT_REPLICATION_TARGET,
        "pair_count": PAIR_COUNT,
        "pair_replication_target": PAIR_REPLICATION_TARGET,
        "legal_block_count": LEGAL_BLOCK_COUNT,
    }
    incidence_identities = {
        "block_point_incidences": BLOCK_COUNT * BLOCK_SIZE,
        "point_replication_incidences": POINT_COUNT * POINT_REPLICATION_TARGET,
        "block_pair_incidences": BLOCK_COUNT * 15,
        "pair_replication_incidences": PAIR_COUNT * PAIR_REPLICATION_TARGET,
        "local_point_pair_incidences": POINT_REPLICATION_TARGET * (BLOCK_SIZE - 1),
        "local_pair_incidences": PAIR_REPLICATION_TARGET * (POINT_COUNT - 1),
    }
    specification = _artifact(
        schema_version="dehps-prediction-v2-balanced-design-feasibility.v1",
        artifact_type="prediction_v2_balanced_design_feasibility_specification",
        body={
            "status": "COMPLETE",
            "design_status": "FROZEN_NOT_EXECUTED",
            "domain": "SSQ_RED_BALL_SIX_OF_33",
            "design_class": "SIMPLE_2_DESIGN",
            "parameters": parameters,
            "incidence_identities": incidence_identities,
            "necessary_incidence_conditions_pass": True,
            "existence_established": False,
            "nonexistence_established": False,
            "simple_design_required": True,
            "uniqueness_boundary": (
                "STRICTLY_INCREASING_COMBINADIC_BLOCK_IDS_BY_CONSTRUCTION"
            ),
            "repetition_scan": REPETITION_SCAN,
            "result_blind": True,
            "positive_outcome": POSITIVE_OUTCOME,
            "bounded_negative_outcome": BOUNDED_NEGATIVE_OUTCOME,
            "invalid_outcome": INVALID_OUTCOME,
            "bounded_negative_is_nonexistence_proof": False,
            "constructor_family_frozen": False,
            "search_budget_frozen": False,
            "execution_authorized": False,
            "solver_nodes_executed": 0,
            "candidate_blocks_generated": 0,
            "database_queries_during_capability": 0,
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
            "legacy_prediction_mainline_reactivation_authorized": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain="dehps.prediction-v2.balanced-design-feasibility.v1",
    )
    handoff = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-feasibility-preregistration-handoff.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_feasibility_preregistration_handoff"
        ),
        body={
            "status": "COMPLETE",
            "design_task": PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY,
            "next_task": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
            ),
            "feasibility_specification_digest": specification["artifact_digest"],
            "required_frozen_fields": [
                "constructor_family",
                "canonical_variable_and_branch_order",
                "representation_scope_and_symmetry_breaks",
                "hardware_independent_work_budget",
                "positive_certificate_format",
                "independent_exact_integer_verifier",
                "three_valued_outcome_rule",
            ],
            "positive_outcome": POSITIVE_OUTCOME,
            "bounded_negative_outcome": BOUNDED_NEGATIVE_OUTCOME,
            "invalid_outcome": INVALID_OUTCOME,
            "bounded_negative_is_nonexistence_proof": False,
            "execution_authorized": False,
            "result_blind": True,
            "repetition_scan": REPETITION_SCAN,
            "solver_nodes_executed": 0,
            "candidate_blocks_generated": 0,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "legacy_route_fallback": False,
            "production_action": "none",
        },
        parent_digests=(*parent_digests, str(specification["artifact_digest"])),
        domain=(
            "dehps.prediction-v2.balanced-design-feasibility-preregistration-handoff.v1"
        ),
    )
    completion = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-feasibility-completion.v1"
        ),
        artifact_type="prediction_v2_balanced_design_feasibility_completion",
        body={
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_COMPLETION_FACT
            ),
            "source_contract_digest": source_digest,
            "archive_route_decision_digest": archive_route_decision_digest,
            "research_intake_handoff_digest": research_intake_handoff[
                "artifact_digest"
            ],
            "archive_route_completion_digest": archive_route_completion[
                "artifact_digest"
            ],
            "feasibility_specification_digest": specification["artifact_digest"],
            "preregistration_handoff_digest": handoff["artifact_digest"],
            "registered_child_count": 3,
            "design_status": "FROZEN_NOT_EXECUTED",
            "existence_established": False,
            "nonexistence_established": False,
            "solver_nodes_executed": 0,
            "candidate_blocks_generated": 0,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "prior_scores_read": 0,
            "prior_predictions_read": 0,
            "prior_rankings_read": 0,
            "repetition_scan": REPETITION_SCAN,
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
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(specification["artifact_digest"]),
            str(handoff["artifact_digest"]),
        ),
        domain="dehps.prediction-v2.balanced-design-feasibility-completion.v1",
    )
    return PredictionV2BalancedDesignFeasibilityDesignRun(
        specification=specification,
        preregistration_handoff=handoff,
        completion=completion,
    )


def replay_prediction_v2_balanced_design_feasibility(
    *,
    source_contract: Mapping[str, Any],
    archive_route_decision_digest: str,
    research_intake_handoff: Mapping[str, Any],
    archive_route_completion: Mapping[str, Any],
) -> tuple[PredictionV2BalancedDesignFeasibilityDesignRun, dict[str, Any]]:
    run = build_prediction_v2_balanced_design_feasibility_artifacts(
        source_contract=source_contract,
        archive_route_decision_digest=archive_route_decision_digest,
        research_intake_handoff=research_intake_handoff,
        archive_route_completion=archive_route_completion,
    )
    return run, {
        "schema_version": ("dehps-prediction-v2-balanced-design-feasibility-replay.v1"),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "design_status": "FROZEN_NOT_EXECUTED",
        "workload_rerun": False,
        "solver_nodes_replayed": 0,
        "candidate_blocks_regenerated": 0,
        "database_queries_during_replay": 0,
        "historical_rows_read": 0,
        "prior_scores_read": 0,
        "prior_predictions_read": 0,
        "prior_rankings_read": 0,
        "manual_input_assembly": False,
        "legacy_route_fallback": False,
        "repetition_scan": REPETITION_SCAN,
        "next_consumer": (
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
        ),
    }


def _validate_parent_artifacts(
    *,
    archive_route_decision_digest: str,
    research_intake_handoff: Mapping[str, Any],
    archive_route_completion: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    _verify_artifact(
        research_intake_handoff,
        domain="dehps.prediction-v2.result-blind-research-intake-handoff.v1",
    )
    _verify_artifact(
        archive_route_completion,
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-"
            "route-decision-completion.v1"
        ),
    )
    observed = (
        archive_route_decision_digest,
        str(research_intake_handoff.get("artifact_digest")),
        str(archive_route_completion.get("artifact_digest")),
    )
    if require_registered_identities and observed != (
        ARCHIVE_ROUTE_DECISION_DIGEST,
        RESEARCH_INTAKE_HANDOFF_DIGEST,
        ARCHIVE_ROUTE_COMPLETION_DIGEST,
    ):
        raise PredictionV2BalancedDesignFeasibilityDesignError(
            "balanced_design_feasibility_registered_identity_changed"
        )
    if (
        research_intake_handoff.get("status") != "COMPLETE"
        or research_intake_handoff.get("route_decision") != ROUTE_DECISION
        or research_intake_handoff.get("structural_artifact_role")
        != STRUCTURAL_ARTIFACT_ROLE
        or research_intake_handoff.get("prediction_research_disposition")
        != PREDICTION_RESEARCH_DISPOSITION
        or research_intake_handoff.get("intake_task")
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY
        or research_intake_handoff.get("required_external_event")
        != PREDICTION_V2_APPROVED_RESULT_BLIND_RESEARCH_CONTRACT_EVENT
        or research_intake_handoff.get("state_before_external_event") != "EXTERNAL_WAIT"
        or research_intake_handoff.get("result_blind_contract_required") is not True
        or research_intake_handoff.get("requested_capability_before_event") is not None
        or research_intake_handoff.get("automatic_hypothesis_generation") is not False
        or research_intake_handoff.get("automatic_threshold_relaxation") is not False
        or research_intake_handoff.get("automatic_seed_retry") is not False
        or research_intake_handoff.get("automatic_portfolio_mutation") is not False
        or research_intake_handoff.get("legacy_route_fallback") is not False
        or research_intake_handoff.get("historical_evidence") != "INCONCLUSIVE"
        or research_intake_handoff.get("prediction_v2_mode") != "SHADOW_ONLY"
        or research_intake_handoff.get("prediction_v2_route") != "BASELINE_ONLY"
        or research_intake_handoff.get("new_evidence_created") is not False
        or research_intake_handoff.get("new_model_created") is not False
        or research_intake_handoff.get("promotion_gate_opened") is not False
        or research_intake_handoff.get("p3_authorized") is not False
        or research_intake_handoff.get("production_action") != "none"
        or research_intake_handoff.get("repetition_scan") != REPETITION_SCAN
        or archive_route_completion.get("status") != "COMPLETE"
        or archive_route_completion.get("completion_fact")
        != "prediction-v2-structural-baseline-comparison-route-decision:COMPLETE"
        or archive_route_completion.get("route_decision_digest")
        != archive_route_decision_digest
        or archive_route_completion.get("research_intake_handoff_digest")
        != research_intake_handoff.get("artifact_digest")
        or archive_route_completion.get("decision") != ROUTE_DECISION
        or archive_route_completion.get("next_external_event")
        != PREDICTION_V2_APPROVED_RESULT_BLIND_RESEARCH_CONTRACT_EVENT
        or archive_route_completion.get("historical_evidence") != "INCONCLUSIVE"
        or archive_route_completion.get("prediction_v2_mode") != "SHADOW_ONLY"
        or archive_route_completion.get("prediction_v2_route") != "BASELINE_ONLY"
        or archive_route_completion.get("portfolio_activation_authorized") is not False
        or archive_route_completion.get("new_evidence_created") is not False
        or archive_route_completion.get("new_model_created") is not False
        or archive_route_completion.get("promotion_gate_opened") is not False
        or archive_route_completion.get("p3_authorized") is not False
        or archive_route_completion.get("production_action") != "none"
        or archive_route_completion.get("repetition_scan") != REPETITION_SCAN
    ):
        raise PredictionV2BalancedDesignFeasibilityDesignError(
            "balanced_design_feasibility_parent_consistency_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key") != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_COMPLETION_FACT
        or frozen.get("approved_external_event")
        != PREDICTION_V2_APPROVED_RESULT_BLIND_RESEARCH_CONTRACT_EVENT
        or frozen.get("next_consumer")
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
        or frozen.get("registered_input_digests")
        != [
            ARCHIVE_ROUTE_DECISION_DIGEST,
            RESEARCH_INTAKE_HANDOFF_DIGEST,
            ARCHIVE_ROUTE_COMPLETION_DIGEST,
        ]
        or frozen.get("point_count") != POINT_COUNT
        or frozen.get("block_size") != BLOCK_SIZE
        or frozen.get("block_count") != BLOCK_COUNT
        or frozen.get("point_replication_target") != POINT_REPLICATION_TARGET
        or frozen.get("pair_count") != PAIR_COUNT
        or frozen.get("pair_replication_target") != PAIR_REPLICATION_TARGET
        or frozen.get("legal_block_count") != LEGAL_BLOCK_COUNT
        or frozen.get("simple_design_required") is not True
        or frozen.get("uniqueness_boundary")
        != "STRICTLY_INCREASING_COMBINADIC_BLOCK_IDS_BY_CONSTRUCTION"
        or frozen.get("positive_outcome") != POSITIVE_OUTCOME
        or frozen.get("bounded_negative_outcome") != BOUNDED_NEGATIVE_OUTCOME
        or frozen.get("invalid_outcome") != INVALID_OUTCOME
        or frozen.get("bounded_negative_is_nonexistence_proof") is not False
        or frozen.get("result_blind") is not True
        or frozen.get("registered_child_count") != 3
        or frozen.get("registered_total_with_mainline_execution") != 4
        or frozen.get("solver_nodes_executed") != 0
        or frozen.get("candidate_blocks_generated") != 0
        or frozen.get("database_queries") != 0
        or frozen.get("historical_rows_read") != 0
        or frozen.get("prior_scores_read") != 0
        or frozen.get("prior_predictions_read") != 0
        or frozen.get("prior_rankings_read") != 0
        or frozen.get("new_evidence_created") is not False
        or frozen.get("new_model_created") is not False
        or frozen.get("candidate_expert_authorized") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("historical_evidence") != "INCONCLUSIVE"
        or frozen.get("prediction_v2_mode") != "SHADOW_ONLY"
        or frozen.get("prediction_v2_route") != "BASELINE_ONLY"
        or frozen.get("legacy_route_fallback") is not False
        or frozen.get("production_action") != "none"
        or frozen.get("repetition_scan") != REPETITION_SCAN
    ):
        raise PredictionV2BalancedDesignFeasibilityDesignError(
            "balanced_design_feasibility_frozen_contract_changed"
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
        raise PredictionV2BalancedDesignFeasibilityDesignError(
            "balanced_design_feasibility_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
