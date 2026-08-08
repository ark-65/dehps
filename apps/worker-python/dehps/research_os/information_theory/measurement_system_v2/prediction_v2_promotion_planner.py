from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY = "prediction-v2-promotion-planner"
PREDICTION_V2_PROMOTION_PLANNER_CAPABILITY = "prediction_v2_promotion_planner"
PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT = (
    "prediction-v2-promotion-planner:COMPLETE"
)
PREDICTION_V2_PROMOTION_PLANNER_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/prediction-v2-promotion-planner-source-v1.json"
)
PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY = (
    "prediction-v2-forward-evidence-or-pivot-planner"
)

MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-gate-compiler"
)
MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT = (
    "m4-v2-marginal-static-historical-measurement-gate-compiler:COMPLETE"
)
GATE_EXECUTION_ARTIFACT_DIGEST = (
    "6b761c57ea46fe8819a0a38193cfe78f613e48b348bc5d682669ad816fbea721"
)
BASELINE_MODEL_DIGEST = (
    "efbb2a3d3b711c5c63b9f05b8133f9cc4ba77b1121b90ef9f951ab56fe263b3e"
)
EVALUATED_CANDIDATE_MODEL_DIGEST = (
    "fb7eb603f7fc283ee645a38ae1d2555d47b43fb86dbb23439a91ef329f1167d6"
)
GATE_OUTPUT_DIGEST = (
    "24e4c78cc12eab32aef2ee45cbeebb2b1078e6effea49442c2f45214890e7100"
)
HISTORICAL_EVIDENCE_DIGEST = (
    "bdb89dd183846e4124654b57021be9892158b2b1387a8ca08d476283e0e2ed87"
)
PLANNING_ELIGIBILITY_DIGEST = (
    "e01d76776f93b9a308b38b0832f6a79fdc616a04ad63864e4b671152685d1abd"
)
GATE_COMPLETION_DIGEST = (
    "5ab24ae2b6f172de9efb6f739b7488865f4a23bd9305687b5f87093e16a319e6"
)
PREDICTION_V2_SHADOW_CONTRACT_DIGEST = (
    "df39fde45013c10b9c6586662d05353cebe9260788ee200c455e7e5e958e9db7"
)

BRANCH_IDS = (
    "MARGINAL_STATIC",
    "TEMPORAL_MARGINAL_INCREMENT",
    "JOINT_RESIDUAL_INCREMENT",
)
ROUTE_MAPPING: dict[str, dict[str, Any]] = {
    "POSITIVE": {
        "plan_decision": "FORWARD_SHADOW_EVIDENCE_PLAN_ELIGIBLE",
        "route": "FUTURE_ONLY_PREDICTION_V2_CANDIDATE_EVIDENCE",
        "accepted_model_required": True,
        "direct_promotion": False,
    },
    "NEGATIVE": {
        "plan_decision": "PREDICTIVE_PROMOTION_CLOSED",
        "route": "STRUCTURAL_DECISION_SUPPORT_PIVOT_REVIEW",
        "accepted_model_required": False,
        "direct_promotion": False,
    },
    "INCONCLUSIVE": {
        "plan_decision": "HOLD_BASELINE_ONLY",
        "route": "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW",
        "accepted_model_required": False,
        "direct_promotion": False,
    },
}

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-promotion-planner-round-58-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-promotion-planner-round-58-20260808"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/prediction_v2_promotion_planner.py"
)
# Filled from the immutable frozen-contract object. Changing the planner policy
# requires a new source-contract version rather than editing this identity.
FROZEN_CONTRACT_DIGEST = (
    "86cdddf15170f7b05e2be2866dd09f9e6aba82f09efb18271e20fc92dfde7a57"
)


class PredictionV2PromotionPlannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2PromotionPlannerRun:
    promotion_plan: Mapping[str, Any]
    downstream_route: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.promotion_plan, self.downstream_route, self.completion

    @property
    def historical_evidence(self) -> str:
        return str(self.promotion_plan["historical_evidence"])

    @property
    def plan_decision(self) -> str:
        return str(self.promotion_plan["plan_decision"])

    @property
    def route(self) -> str:
        return str(self.promotion_plan["route"])


def load_prediction_v2_promotion_planner_source_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2PromotionPlannerError(
            f"prediction_v2_promotion_planner_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-promotion-planner-source.v1"
        or payload.get("artifact_type") != "prediction_v2_promotion_planner_source"
        or payload.get("contract_key") != "PREDICTION_V2_PROMOTION_PLANNER_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 379
        or payload.get("research_execution_id") != 300
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 380
        or payload.get("engineering_execution_id") != 301
        or payload.get("result_aware") is not True
        or payload.get("historical_rows_read") != 0
        or payload.get("folds_executed") != 0
        or payload.get("bootstrap_children_executed") != 0
        or payload.get("duplicate_validation") is not False
        or payload.get("registered_children") != 3
        or payload.get("new_evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("frozen_contract_digest") != FROZEN_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain="dehps.prediction-v2.promotion-planner-frozen-contract.v1",
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.prediction-v2.promotion-planner-source-set.v1",
        )
    ):
        raise PredictionV2PromotionPlannerError(
            "prediction_v2_promotion_planner_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2PromotionPlannerError(
            "prediction_v2_promotion_planner_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_promotion_planner_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2PromotionPlannerError(
                f"prediction_v2_promotion_planner_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2PromotionPlannerError(
                f"prediction_v2_promotion_planner_source_modified:{relative}"
            )


def build_prediction_v2_promotion_planner_artifacts(
    *,
    source_contract: Mapping[str, Any],
    gate_execution: Mapping[str, Any],
    baseline_model: Mapping[str, Any],
    evaluated_candidate_model: Mapping[str, Any],
    gate_output: Mapping[str, Any],
    historical_evidence: Mapping[str, Any],
    planning_eligibility: Mapping[str, Any],
    gate_completion: Mapping[str, Any],
    shadow_contract: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2PromotionPlannerRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    evidence_value, accepted_model_digest = _validate_parent_artifacts(
        gate_execution=gate_execution,
        baseline_model=baseline_model,
        evaluated_candidate_model=evaluated_candidate_model,
        gate_output=gate_output,
        historical_evidence=historical_evidence,
        planning_eligibility=planning_eligibility,
        gate_completion=gate_completion,
        shadow_contract=shadow_contract,
        require_registered_identities=require_registered_identities,
    )
    route = ROUTE_MAPPING[evidence_value]
    source_digest = str(source_contract["artifact_digest"])
    common_parents = (
        source_digest,
        str(gate_execution["artifact_digest"]),
        str(baseline_model["artifact_digest"]),
        str(evaluated_candidate_model["artifact_digest"]),
        str(gate_output["artifact_digest"]),
        str(historical_evidence["artifact_digest"]),
        str(planning_eligibility["artifact_digest"]),
        str(gate_completion["artifact_digest"]),
        str(shadow_contract["artifact_digest"]),
    )
    promotion_plan = _artifact(
        schema_version="dehps-prediction-v2-promotion-plan.v1",
        artifact_type="prediction_v2_promotion_plan",
        body={
            "status": "COMPLETE",
            "historical_evidence": evidence_value,
            "plan_decision": route["plan_decision"],
            "route": route["route"],
            "accepted_model_artifact_digest": accepted_model_digest,
            "accepted_model_required": route["accepted_model_required"],
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "candidate_expert_authorized": False,
            "forward_evidence_required": True,
            "direct_promotion": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "duplicate_validation": False,
            "new_evidence_created": False,
            "next_consumer": (
                PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=common_parents,
        domain="dehps.prediction-v2.promotion-plan.v1",
    )
    downstream_route = _artifact(
        schema_version="dehps-prediction-v2-forward-evidence-or-pivot-route.v1",
        artifact_type="prediction_v2_forward_evidence_or_pivot_route",
        body={
            "status": "COMPLETE",
            "historical_evidence": evidence_value,
            "plan_decision": route["plan_decision"],
            "selected_route": route["route"],
            "frozen_route_mapping": ROUTE_MAPPING,
            "current_shadow_mode": "SHADOW_ONLY",
            "current_shadow_route": "BASELINE_ONLY",
            "temporal_branch_status": "NOT_RUN_NO_ACCEPTED_MARGINAL_BASELINE",
            "joint_branch_status": "NOT_RUN_NO_ACCEPTED_MARGINAL_BASELINE",
            "retrospective_forward_evidence_forbidden": True,
            "separate_preregistration_required": True,
            "duplicate_validation": False,
            "new_evidence_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "next_consumer": (
                PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(*common_parents, str(promotion_plan["artifact_digest"])),
        domain="dehps.prediction-v2.forward-evidence-or-pivot-route.v1",
    )
    completion = _artifact(
        schema_version="dehps-prediction-v2-promotion-planner-completion.v1",
        artifact_type="prediction_v2_promotion_planner_completion",
        body={
            "status": "COMPLETE",
            "source_contract_digest": source_digest,
            "gate_execution_artifact_digest": gate_execution["artifact_digest"],
            "promotion_plan_digest": promotion_plan["artifact_digest"],
            "downstream_route_digest": downstream_route["artifact_digest"],
            "historical_evidence": evidence_value,
            "plan_decision": route["plan_decision"],
            "route": route["route"],
            "registered_child_count": 3,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "duplicate_validation": False,
            "new_evidence_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "completion_fact": PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
            "next_consumer": (
                PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
            ),
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(promotion_plan["artifact_digest"]),
            str(downstream_route["artifact_digest"]),
        ),
        domain="dehps.prediction-v2.promotion-planner-completion.v1",
    )
    return PredictionV2PromotionPlannerRun(
        promotion_plan=promotion_plan,
        downstream_route=downstream_route,
        completion=completion,
    )


def _validate_parent_artifacts(
    *,
    gate_execution: Mapping[str, Any],
    baseline_model: Mapping[str, Any],
    evaluated_candidate_model: Mapping[str, Any],
    gate_output: Mapping[str, Any],
    historical_evidence: Mapping[str, Any],
    planning_eligibility: Mapping[str, Any],
    gate_completion: Mapping[str, Any],
    shadow_contract: Mapping[str, Any],
    require_registered_identities: bool,
) -> tuple[str, str | None]:
    artifacts_and_domains = (
        (gate_execution, "dehps.research-os.mainline-execution.v1"),
        (baseline_model, "dehps.m4.v2.legal-uniform-baseline-model-identity.v1"),
        (
            evaluated_candidate_model,
            "dehps.m4.v2.marginal-static-evaluated-model-identity.v1",
        ),
        (gate_output, "dehps.m4.measurement-v2.gate-output.v1"),
        (
            historical_evidence,
            "dehps.m4.v2.marginal-static-historical-evidence.v1",
        ),
        (
            planning_eligibility,
            "dehps.prediction-v2.promotion-planning-eligibility.v1",
        ),
        (
            gate_completion,
            "dehps.m4.v2.marginal-static-historical-gate-completion.v1",
        ),
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
            GATE_EXECUTION_ARTIFACT_DIGEST,
            BASELINE_MODEL_DIGEST,
            EVALUATED_CANDIDATE_MODEL_DIGEST,
            GATE_OUTPUT_DIGEST,
            HISTORICAL_EVIDENCE_DIGEST,
            PLANNING_ELIGIBILITY_DIGEST,
            GATE_COMPLETION_DIGEST,
            PREDICTION_V2_SHADOW_CONTRACT_DIGEST,
        )
        if observed != expected:
            raise PredictionV2PromotionPlannerError(
                "prediction_v2_promotion_planner_registered_identity_changed"
            )

    evidence_value = str(historical_evidence.get("historical_evidence"))
    if evidence_value not in ROUTE_MAPPING:
        raise PredictionV2PromotionPlannerError(
            "prediction_v2_promotion_planner_evidence_invalid"
        )
    eligible = evidence_value == "POSITIVE"
    accepted_model_digest = (
        str(evaluated_candidate_model["artifact_digest"]) if eligible else None
    )
    branches = gate_output.get("branch_outputs")
    marginal = branches[0] if isinstance(branches, list) and len(branches) == 3 else {}
    dependent = branches[1:] if isinstance(branches, list) else []
    evidence_fact = f"m4-v2-marginal-static-historical-evidence:{evidence_value}"
    if (
        gate_execution.get("artifact_type") != "research_os_mainline_execution"
        or gate_execution.get("task_key") != MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
        or gate_execution.get("status") != "COMPLETE"
        or gate_execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or gate_execution.get("registered_artifact_count") != 7
        or gate_execution.get("completion_fact")
        != MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT
        or gate_execution.get("baseline_model_artifact_digest")
        != baseline_model.get("artifact_digest")
        or gate_execution.get("evaluated_model_artifact_digest")
        != evaluated_candidate_model.get("artifact_digest")
        or gate_execution.get("accepted_model_artifact_digest")
        != accepted_model_digest
        or gate_execution.get("hierarchical_gate_output_digest")
        != gate_output.get("artifact_digest")
        or gate_execution.get("historical_evidence_artifact_digest")
        != historical_evidence.get("artifact_digest")
        or gate_execution.get("promotion_planning_eligibility_digest")
        != planning_eligibility.get("artifact_digest")
        or gate_execution.get("historical_gate_completion_digest")
        != gate_completion.get("artifact_digest")
        or gate_execution.get("historical_evidence") != evidence_value
        or gate_execution.get("evidence_fact") != evidence_fact
        or gate_execution.get("prediction_v2_planning_eligible") is not eligible
        or gate_execution.get("formal_historical_folds_executed") != 0
        or gate_execution.get("bootstrap_children_executed") != 0
        or gate_execution.get("database_queries_during_capability") != 0
        or gate_execution.get("duplicate_validation") is not False
        or gate_execution.get("promotion_gate_opened") is not False
        or gate_execution.get("production_action") != "none"
        or baseline_model.get("artifact_type")
        != "m4_v2_legal_uniform_baseline_model_identity"
        or baseline_model.get("status") != "COMPLETE"
        or baseline_model.get("model_id") != "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE"
        or baseline_model.get("production_action") != "none"
        or evaluated_candidate_model.get("artifact_type")
        != "m4_v2_marginal_static_evaluated_model_identity"
        or evaluated_candidate_model.get("status") != "COMPLETE"
        or evaluated_candidate_model.get("baseline_model_artifact_digest")
        != baseline_model.get("artifact_digest")
        or evaluated_candidate_model.get("candidate_baseline_distinct") is not True
        or evaluated_candidate_model.get("accepted_for_downstream_baseline")
        is not eligible
        or evaluated_candidate_model.get("eligible_for_production") is not False
        or gate_output.get("artifact_type")
        != "hierarchical_measurement_gate_output"
        or gate_output.get("status") != "COMPLETE"
        or gate_output.get("required_branch_ids") != list(BRANCH_IDS)
        or gate_output.get("global_coverage") != "PARTIAL"
        or gate_output.get("prediction_v2_planning_eligible") is not eligible
        or gate_output.get("promotion_gate_opened") is not False
        or gate_output.get("production_action") != "none"
        or marginal.get("branch_id") != "MARGINAL_STATIC"
        or marginal.get("historical_evidence") != evidence_value
        or marginal.get("baseline_artifact_digest")
        != baseline_model.get("artifact_digest")
        or marginal.get("accepted_model_artifact_digest") != accepted_model_digest
        or marginal.get("accepted_for_downstream_baseline") is not eligible
        or marginal.get("prediction_v2_planning_eligible") is not eligible
        or len(dependent) != 2
        or any(
            branch.get("branch_id") != branch_id
            or branch.get("historical_run_status") != "NOT_RUN"
            or branch.get("historical_evidence") != "NOT_RUN"
            or branch.get("accepted_model_artifact_digest") is not None
            or branch.get("accepted_for_downstream_baseline") is not False
            or branch.get("prediction_v2_planning_eligible") is not False
            for branch, branch_id in zip(dependent, BRANCH_IDS[1:], strict=True)
        )
        or historical_evidence.get("artifact_type")
        != "m4_v2_marginal_static_historical_evidence"
        or historical_evidence.get("status") != "COMPLETE"
        or historical_evidence.get("evidence_fact") != evidence_fact
        or historical_evidence.get("gate_output_digest")
        != gate_output.get("artifact_digest")
        or historical_evidence.get("baseline_model_artifact_digest")
        != baseline_model.get("artifact_digest")
        or historical_evidence.get("candidate_model_artifact_digest")
        != evaluated_candidate_model.get("artifact_digest")
        or historical_evidence.get("prediction_v2_planning_eligible") is not eligible
        or historical_evidence.get("promotion_gate_opened") is not False
        or planning_eligibility.get("artifact_type")
        != "prediction_v2_promotion_planning_eligibility"
        or planning_eligibility.get("status") != "COMPLETE"
        or planning_eligibility.get("historical_evidence") != evidence_value
        or planning_eligibility.get("eligible_for_prediction_v2_promotion_planning")
        is not eligible
        or planning_eligibility.get("eligible_for_prediction_v2_production") is not False
        or planning_eligibility.get("candidate_model_artifact_digest")
        != evaluated_candidate_model.get("artifact_digest")
        or planning_eligibility.get("evidence_artifact_digest")
        != historical_evidence.get("artifact_digest")
        or planning_eligibility.get("promotion_gate_opened") is not False
        or planning_eligibility.get("next_consumer")
        != PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
        or gate_completion.get("artifact_type")
        != "m4_v2_marginal_static_historical_gate_completion"
        or gate_completion.get("status") != "COMPLETE"
        or gate_completion.get("gate_output_digest")
        != gate_output.get("artifact_digest")
        or gate_completion.get("evidence_artifact_digest")
        != historical_evidence.get("artifact_digest")
        or gate_completion.get("eligibility_artifact_digest")
        != planning_eligibility.get("artifact_digest")
        or gate_completion.get("historical_evidence") != evidence_value
        or gate_completion.get("evidence_fact") != evidence_fact
        or gate_completion.get("registered_child_count") != 6
        or gate_completion.get("historical_rows_read") != 0
        or gate_completion.get("folds_executed") != 0
        or gate_completion.get("bootstrap_children_executed") != 0
        or gate_completion.get("promotion_gate_opened") is not False
        or gate_completion.get("completion_fact")
        != MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT
        or gate_completion.get("next_consumer")
        != PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
        or shadow_contract.get("artifact_digest")
        != PREDICTION_V2_SHADOW_CONTRACT_DIGEST
        or shadow_contract.get("mode") != "SHADOW_ONLY"
        or shadow_contract.get("route") != "BASELINE_ONLY"
        or shadow_contract.get("experts")
        != {
            "marginal": "NOT_AUTHORIZED",
            "temporal": "NOT_AUTHORIZED",
            "diversity": "OBSERVATION_ONLY",
        }
        or shadow_contract.get("promotion_gate_opened") is not False
        or shadow_contract.get("production_candidate") is not False
    ):
        raise PredictionV2PromotionPlannerError(
            "prediction_v2_promotion_planner_parent_consistency_invalid"
        )
    return evidence_value, accepted_model_digest


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key") != PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
        or frozen.get("capability") != PREDICTION_V2_PROMOTION_PLANNER_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT
        or frozen.get("next_consumer")
        != PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
        or frozen.get("gate_execution_artifact_digest")
        != GATE_EXECUTION_ARTIFACT_DIGEST
        or frozen.get("gate_child_artifact_digests")
        != [
            BASELINE_MODEL_DIGEST,
            EVALUATED_CANDIDATE_MODEL_DIGEST,
            GATE_OUTPUT_DIGEST,
            HISTORICAL_EVIDENCE_DIGEST,
            PLANNING_ELIGIBILITY_DIGEST,
            GATE_COMPLETION_DIGEST,
        ]
        or frozen.get("prediction_v2_shadow_contract_digest")
        != PREDICTION_V2_SHADOW_CONTRACT_DIGEST
        or frozen.get("route_mapping") != ROUTE_MAPPING
        or frozen.get("prediction_v2_mode") != "SHADOW_ONLY"
        or frozen.get("prediction_v2_route") != "BASELINE_ONLY"
        or frozen.get("registered_child_count") != 3
        or frozen.get("registered_total_with_mainline_execution") != 4
        or frozen.get("database_queries") != 0
        or frozen.get("historical_rows_read") != 0
        or frozen.get("folds_executed") != 0
        or frozen.get("bootstrap_children_executed") != 0
        or frozen.get("duplicate_validation") is not False
        or frozen.get("new_evidence_created") is not False
        or frozen.get("direct_promotion") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("production_action") != "none"
    ):
        raise PredictionV2PromotionPlannerError(
            "prediction_v2_promotion_planner_frozen_contract_changed"
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
        raise PredictionV2PromotionPlannerError(
            "prediction_v2_promotion_planner_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
