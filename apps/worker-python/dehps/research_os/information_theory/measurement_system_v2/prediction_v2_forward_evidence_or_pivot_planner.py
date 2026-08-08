from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY = (
    "prediction-v2-forward-evidence-or-pivot-planner"
)
PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_CAPABILITY = (
    "prediction_v2_forward_evidence_or_pivot_planner"
)
PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT = (
    "prediction-v2-forward-evidence-or-pivot-planner:COMPLETE"
)
PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/prediction-v2-forward-evidence-or-pivot-planner-source-v1.json"
)
PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY = (
    "prediction-v2-structural-decision-support-design"
)

PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY = "prediction-v2-promotion-planner"
PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT = (
    "prediction-v2-promotion-planner:COMPLETE"
)
PROMOTION_PLANNER_EXECUTION_DIGEST = (
    "ccb6abd628920eb41330e9a05fad47b0546825f24317c6b018c796172c0231af"
)
PROMOTION_PLAN_DIGEST = (
    "333f42c54430970dd3287b56185594658b13b9f930d7ee67299c3efd4a76168b"
)
UPSTREAM_ROUTE_DIGEST = (
    "50257fa4d4d183d1dfcf110b6618f794e85e1d4d62594c49f49368055e23b9c2"
)
PROMOTION_PLANNER_COMPLETION_DIGEST = (
    "bb2f76b76e4c0a43b5194fdd850f0dfb1771b7b34aafea3e97fd22cd49790786"
)
PREDICTION_V2_SHADOW_CONTRACT_DIGEST = (
    "df39fde45013c10b9c6586662d05353cebe9260788ee200c455e7e5e958e9db7"
)
HISTORICAL_EVIDENCE_DIGEST = (
    "bdb89dd183846e4124654b57021be9892158b2b1387a8ca08d476283e0e2ed87"
)

CURRENT_FORMAL_HISTORICAL_FOLD_COUNT = 2581
CURRENT_MDE_BITS_PER_ISSUE = 0.013459908060402983
PRACTICAL_THRESHOLD_BITS_PER_ISSUE = 0.01
OPERATIONAL_HORIZON_DAYS = 14
PLANNING_CADENCE_ISSUES_PER_WEEK = 3
MAXIMUM_NEW_ISSUES_IN_HORIZON = 6
REQUIRED_TOTAL_ISSUES = 4676
ADDITIONAL_ISSUES_REQUIRED = 2095
PROJECTED_MDE_AFTER_HORIZON_BITS_PER_ISSUE = 0.01344429029293817
SELECTED_PROGRAM = "STRUCTURAL_DECISION_SUPPORT_PIVOT"
PREDICTION_RESEARCH_DISPOSITION = "FROZEN_PENDING_SEPARATE_RESULT_BLIND_PREREGISTRATION"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-forward-or-pivot-round-60-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-forward-or-pivot-round-60-20260808"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/prediction_v2_forward_evidence_or_pivot_planner.py"
)
FROZEN_CONTRACT_DIGEST = (
    "b79edc51302b0261d1fdc7e36c75bce78e9437036bcac7ac5b933d6184259091"
)


class PredictionV2ForwardOrPivotPlannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2ForwardOrPivotPlannerRun:
    feasibility: Mapping[str, Any]
    structural_pivot_plan: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.feasibility, self.structural_pivot_plan, self.completion

    @property
    def selected_program(self) -> str:
        return str(self.structural_pivot_plan["selected_program"])


def load_prediction_v2_forward_or_pivot_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2ForwardOrPivotPlannerError(
            f"prediction_v2_forward_or_pivot_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-forward-or-pivot-planner-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_forward_evidence_or_pivot_planner_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 382
        or payload.get("research_execution_id") != 303
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 383
        or payload.get("engineering_execution_id") != 304
        or payload.get("result_aware") is not True
        or payload.get("historical_rows_read") != 0
        or payload.get("folds_executed") != 0
        or payload.get("bootstrap_children_executed") != 0
        or payload.get("duplicate_validation") is not False
        or payload.get("registered_children") != 3
        or payload.get("new_evidence_created") is not False
        or payload.get("new_model_created") is not False
        or payload.get("structural_algorithm_implemented") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("frozen_contract_digest") != FROZEN_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain="dehps.prediction-v2.forward-or-pivot-frozen-contract.v1",
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.prediction-v2.forward-or-pivot-source-set.v1",
        )
    ):
        raise PredictionV2ForwardOrPivotPlannerError(
            "prediction_v2_forward_or_pivot_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise PredictionV2ForwardOrPivotPlannerError(
            "prediction_v2_forward_or_pivot_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_forward_or_pivot_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2ForwardOrPivotPlannerError(
                f"prediction_v2_forward_or_pivot_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2ForwardOrPivotPlannerError(
                f"prediction_v2_forward_or_pivot_source_modified:{relative}"
            )


def build_prediction_v2_forward_or_pivot_artifacts(
    *,
    source_contract: Mapping[str, Any],
    promotion_execution: Mapping[str, Any],
    promotion_plan: Mapping[str, Any],
    upstream_route: Mapping[str, Any],
    promotion_completion: Mapping[str, Any],
    shadow_contract: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> PredictionV2ForwardOrPivotPlannerRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        promotion_execution=promotion_execution,
        promotion_plan=promotion_plan,
        upstream_route=upstream_route,
        promotion_completion=promotion_completion,
        shadow_contract=shadow_contract,
        require_registered_identities=require_registered_identities,
    )
    projection = _planning_projection()
    source_digest = str(source_contract["artifact_digest"])
    common_parents = (
        source_digest,
        str(promotion_execution["artifact_digest"]),
        str(promotion_plan["artifact_digest"]),
        str(upstream_route["artifact_digest"]),
        str(promotion_completion["artifact_digest"]),
        str(shadow_contract["artifact_digest"]),
    )
    feasibility = _artifact(
        schema_version="dehps-prediction-v2-prospective-evidence-feasibility.v1",
        artifact_type="prediction_v2_prospective_evidence_feasibility",
        body={
            "status": "COMPLETE",
            "classification": "NON_EVIDENTIARY_SAME_LAW_SQUARE_ROOT_PROJECTION",
            "historical_evidence": "INCONCLUSIVE",
            "candidate_model_available": False,
            "accepted_model_artifact_digest": None,
            **projection,
            "formal_power_claim": False,
            "candidate_forward_evidence_eligible": False,
            "feasibility_decision": "NOT_FEASIBLE_WITHIN_OPERATIONAL_HORIZON",
            "future_program_requirement": "SEPARATE_RESULT_BLIND_PREREGISTRATION",
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "duplicate_validation": False,
            "new_evidence_created": False,
            "production_action": "none",
        },
        parent_digests=common_parents,
        domain="dehps.prediction-v2.prospective-evidence-feasibility.v1",
    )
    structural_pivot_plan = _artifact(
        schema_version=(
            "dehps-prediction-v2-structural-decision-support-pivot-plan.v1"
        ),
        artifact_type="prediction_v2_structural_decision_support_pivot_plan",
        body={
            "status": "COMPLETE",
            "historical_evidence": "INCONCLUSIVE",
            "upstream_plan_decision": "HOLD_BASELINE_ONLY",
            "upstream_route": "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW",
            "selected_program": SELECTED_PROGRAM,
            "selection_reason": (
                "NO_ACCEPTED_CANDIDATE_AND_NO_TWO_WEEK_MDE_FEASIBILITY"
            ),
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "passive_future_observation": (
                "LATER_SEPARATELY_PREREGISTERED_PROGRAM_ONLY"
            ),
            "structural_pivot_scope": [
                "combination_space_compression",
                "risk_control",
                "candidate_diversity",
            ],
            "structural_algorithm_implemented": False,
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "duplicate_validation": False,
            "new_evidence_created": False,
            "next_consumer": PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(*common_parents, str(feasibility["artifact_digest"])),
        domain="dehps.prediction-v2.structural-decision-support-pivot-plan.v1",
    )
    completion = _artifact(
        schema_version="dehps-prediction-v2-forward-or-pivot-completion.v1",
        artifact_type="prediction_v2_forward_evidence_or_pivot_planner_completion",
        body={
            "status": "COMPLETE",
            "source_contract_digest": source_digest,
            "promotion_execution_artifact_digest": promotion_execution[
                "artifact_digest"
            ],
            "feasibility_digest": feasibility["artifact_digest"],
            "structural_pivot_plan_digest": structural_pivot_plan["artifact_digest"],
            "historical_evidence": "INCONCLUSIVE",
            "selected_program": SELECTED_PROGRAM,
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "registered_child_count": 3,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "duplicate_validation": False,
            "new_evidence_created": False,
            "new_model_created": False,
            "structural_algorithm_implemented": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "completion_fact": (
                PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT
            ),
            "next_consumer": PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(feasibility["artifact_digest"]),
            str(structural_pivot_plan["artifact_digest"]),
        ),
        domain="dehps.prediction-v2.forward-or-pivot-completion.v1",
    )
    return PredictionV2ForwardOrPivotPlannerRun(
        feasibility=feasibility,
        structural_pivot_plan=structural_pivot_plan,
        completion=completion,
    )


def _planning_projection() -> dict[str, int | float]:
    required_total = math.ceil(
        CURRENT_FORMAL_HISTORICAL_FOLD_COUNT
        * (CURRENT_MDE_BITS_PER_ISSUE / PRACTICAL_THRESHOLD_BITS_PER_ISSUE) ** 2
    )
    projected_mde = CURRENT_MDE_BITS_PER_ISSUE * math.sqrt(
        CURRENT_FORMAL_HISTORICAL_FOLD_COUNT
        / (CURRENT_FORMAL_HISTORICAL_FOLD_COUNT + MAXIMUM_NEW_ISSUES_IN_HORIZON)
    )
    additional = required_total - CURRENT_FORMAL_HISTORICAL_FOLD_COUNT
    weeks = additional / PLANNING_CADENCE_ISSUES_PER_WEEK
    years = weeks / (365.2425 / 7)
    if (
        required_total != REQUIRED_TOTAL_ISSUES
        or additional != ADDITIONAL_ISSUES_REQUIRED
        or projected_mde != PROJECTED_MDE_AFTER_HORIZON_BITS_PER_ISSUE
    ):
        raise PredictionV2ForwardOrPivotPlannerError(
            "prediction_v2_forward_or_pivot_projection_changed"
        )
    return {
        "current_formal_historical_fold_count": CURRENT_FORMAL_HISTORICAL_FOLD_COUNT,
        "current_mde_bits_per_issue": CURRENT_MDE_BITS_PER_ISSUE,
        "frozen_practical_threshold_bits_per_issue": (
            PRACTICAL_THRESHOLD_BITS_PER_ISSUE
        ),
        "required_total_issues": required_total,
        "additional_issues_required": additional,
        "planning_cadence_issues_per_week": PLANNING_CADENCE_ISSUES_PER_WEEK,
        "weeks_required_at_planning_cadence": weeks,
        "years_required_at_365_2425_days": years,
        "operational_horizon_days": OPERATIONAL_HORIZON_DAYS,
        "maximum_new_issues_in_horizon": MAXIMUM_NEW_ISSUES_IN_HORIZON,
        "projected_mde_after_horizon_bits_per_issue": projected_mde,
    }


def _validate_parent_artifacts(
    *,
    promotion_execution: Mapping[str, Any],
    promotion_plan: Mapping[str, Any],
    upstream_route: Mapping[str, Any],
    promotion_completion: Mapping[str, Any],
    shadow_contract: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts_and_domains = (
        (promotion_execution, "dehps.research-os.mainline-execution.v1"),
        (promotion_plan, "dehps.prediction-v2.promotion-plan.v1"),
        (upstream_route, "dehps.prediction-v2.forward-evidence-or-pivot-route.v1"),
        (
            promotion_completion,
            "dehps.prediction-v2.promotion-planner-completion.v1",
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
            PROMOTION_PLANNER_EXECUTION_DIGEST,
            PROMOTION_PLAN_DIGEST,
            UPSTREAM_ROUTE_DIGEST,
            PROMOTION_PLANNER_COMPLETION_DIGEST,
            PREDICTION_V2_SHADOW_CONTRACT_DIGEST,
        )
        if observed != expected:
            raise PredictionV2ForwardOrPivotPlannerError(
                "prediction_v2_forward_or_pivot_registered_identity_changed"
            )
    zero_work_keys = (
        "historical_rows_read",
        "folds_executed",
        "bootstrap_children_executed",
    )
    if (
        promotion_execution.get("artifact_type") != "research_os_mainline_execution"
        or promotion_execution.get("task_key")
        != PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
        or promotion_execution.get("status") != "COMPLETE"
        or promotion_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or promotion_execution.get("registered_artifact_count") != 4
        or promotion_execution.get("completion_fact")
        != PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT
        or promotion_execution.get("promotion_plan_digest")
        != promotion_plan.get("artifact_digest")
        or promotion_execution.get("downstream_route_digest")
        != upstream_route.get("artifact_digest")
        or promotion_execution.get("promotion_planner_completion_digest")
        != promotion_completion.get("artifact_digest")
        or promotion_execution.get("historical_evidence_artifact_digest")
        != HISTORICAL_EVIDENCE_DIGEST
        or promotion_execution.get("historical_evidence") != "INCONCLUSIVE"
        or promotion_execution.get("plan_decision") != "HOLD_BASELINE_ONLY"
        or promotion_execution.get("route")
        != "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW"
        or promotion_execution.get("prediction_v2_mode") != "SHADOW_ONLY"
        or promotion_execution.get("prediction_v2_route") != "BASELINE_ONLY"
        or promotion_execution.get("candidate_expert_authorized") is not False
        or promotion_execution.get("database_queries_during_capability") != 0
        or promotion_execution.get("historical_rows_read") != 0
        or promotion_execution.get("formal_historical_folds_executed") != 0
        or promotion_execution.get("bootstrap_children_executed") != 0
        or promotion_execution.get("duplicate_validation") is not False
        or promotion_execution.get("evidence_created") is not False
        or promotion_execution.get("promotion_gate_opened") is not False
        or promotion_execution.get("p3_authorized") is not False
        or promotion_execution.get("production_action") != "none"
        or promotion_plan.get("artifact_type") != "prediction_v2_promotion_plan"
        or promotion_plan.get("status") != "COMPLETE"
        or promotion_plan.get("historical_evidence") != "INCONCLUSIVE"
        or promotion_plan.get("plan_decision") != "HOLD_BASELINE_ONLY"
        or promotion_plan.get("route") != "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW"
        or promotion_plan.get("accepted_model_artifact_digest") is not None
        or promotion_plan.get("candidate_expert_authorized") is not False
        or promotion_plan.get("prediction_v2_mode") != "SHADOW_ONLY"
        or promotion_plan.get("prediction_v2_route") != "BASELINE_ONLY"
        or upstream_route.get("artifact_type")
        != "prediction_v2_forward_evidence_or_pivot_route"
        or upstream_route.get("status") != "COMPLETE"
        or upstream_route.get("historical_evidence") != "INCONCLUSIVE"
        or upstream_route.get("plan_decision") != "HOLD_BASELINE_ONLY"
        or upstream_route.get("selected_route")
        != "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW"
        or upstream_route.get("current_shadow_mode") != "SHADOW_ONLY"
        or upstream_route.get("current_shadow_route") != "BASELINE_ONLY"
        or upstream_route.get("retrospective_forward_evidence_forbidden") is not True
        or upstream_route.get("separate_preregistration_required") is not True
        or upstream_route.get("duplicate_validation") is not False
        or upstream_route.get("new_evidence_created") is not False
        or upstream_route.get("promotion_gate_opened") is not False
        or upstream_route.get("p3_authorized") is not False
        or upstream_route.get("production_action") != "none"
        or promotion_completion.get("artifact_type")
        != "prediction_v2_promotion_planner_completion"
        or promotion_completion.get("status") != "COMPLETE"
        or promotion_completion.get("promotion_plan_digest")
        != promotion_plan.get("artifact_digest")
        or promotion_completion.get("downstream_route_digest")
        != upstream_route.get("artifact_digest")
        or promotion_completion.get("historical_evidence") != "INCONCLUSIVE"
        or promotion_completion.get("plan_decision") != "HOLD_BASELINE_ONLY"
        or promotion_completion.get("route")
        != "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW"
        or promotion_completion.get("registered_child_count") != 3
        or any(promotion_completion.get(key) != 0 for key in zero_work_keys)
        or promotion_completion.get("duplicate_validation") is not False
        or promotion_completion.get("new_evidence_created") is not False
        or promotion_completion.get("promotion_gate_opened") is not False
        or promotion_completion.get("p3_authorized") is not False
        or promotion_completion.get("completion_fact")
        != PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT
        or promotion_completion.get("next_consumer")
        != PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
        or promotion_completion.get("production_action") != "none"
        or shadow_contract.get("artifact_digest")
        != PREDICTION_V2_SHADOW_CONTRACT_DIGEST
        or shadow_contract.get("mode") != "SHADOW_ONLY"
        or shadow_contract.get("route") != "BASELINE_ONLY"
        or shadow_contract.get("promotion_gate_opened") is not False
        or shadow_contract.get("production_candidate") is not False
    ):
        raise PredictionV2ForwardOrPivotPlannerError(
            "prediction_v2_forward_or_pivot_parent_consistency_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    projection = _planning_projection()
    if (
        frozen.get("task_key")
        != PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT
        or frozen.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
        or frozen.get("promotion_planner_execution_artifact_digest")
        != PROMOTION_PLANNER_EXECUTION_DIGEST
        or frozen.get("promotion_planner_child_artifact_digests")
        != [
            PROMOTION_PLAN_DIGEST,
            UPSTREAM_ROUTE_DIGEST,
            PROMOTION_PLANNER_COMPLETION_DIGEST,
        ]
        or frozen.get("prediction_v2_shadow_contract_digest")
        != PREDICTION_V2_SHADOW_CONTRACT_DIGEST
        or frozen.get("historical_evidence_digest") != HISTORICAL_EVIDENCE_DIGEST
        or frozen.get("planning_projection") != projection
        or frozen.get("projection_classification")
        != "NON_EVIDENTIARY_SAME_LAW_SQUARE_ROOT_PROJECTION"
        or frozen.get("formal_power_claim") is not False
        or frozen.get("selected_program") != SELECTED_PROGRAM
        or frozen.get("prediction_research_disposition")
        != PREDICTION_RESEARCH_DISPOSITION
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
        or frozen.get("new_model_created") is not False
        or frozen.get("structural_algorithm_implemented") is not False
        or frozen.get("candidate_expert_authorized") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("production_action") != "none"
    ):
        raise PredictionV2ForwardOrPivotPlannerError(
            "prediction_v2_forward_or_pivot_frozen_contract_changed"
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
        raise PredictionV2ForwardOrPivotPlannerError(
            "prediction_v2_forward_or_pivot_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
