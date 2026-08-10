from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

M4_P3_STRUCTURAL_UTILITY_GOAL_KEY = "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY"
M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY = (
    "prediction-v2-balanced-design-structural-utility-research-intake"
)
M4_P3_STRUCTURAL_UTILITY_DESIGN_CAPABILITY = (
    "m4_p3_result_blind_structural_utility_design"
)
M4_P3_STRUCTURAL_UTILITY_DESIGN_COMPLETION_FACT = (
    "m4-p3-result-blind-structural-utility-design:COMPLETE"
)
M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY = (
    "m4-p3-result-blind-structural-utility-preregistration"
)
M4_P3_STRUCTURAL_UTILITY_DESIGN_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-p3-result-blind-structural-utility-design-source-v1.json"
)
M4_P3_STRUCTURAL_UTILITY_DESIGN_APPROVED_EVENT = (
    "research-contract:prediction-v2-balanced-design-structural-utility:approved"
)
M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_APPROVED_EVENT = (
    "research-contract:m4-p3-result-blind-structural-utility-preregistration:approved"
)

PARENT_TASK_KEY = "prediction-v2-balanced-design-structural-evaluation-result-decision"
PARENT_CAPABILITY = (
    "prediction_v2_balanced_design_structural_evaluation_result_decision"
)
PARENT_EXECUTION_ID = "d8c2a769a2325bf7b44311fd53d81689553558501c887c37519966a855fa438c"
PARENT_EXECUTION_DIGEST = (
    "1647b3a3e464377c0e6a642a0c592332b983d29fad9d62e30f616e39a08dd2a7"
)
PARENT_COMPLETED_EVENT_DIGEST = (
    "bba1e122ab4e641ef517a6ec58c473c390cd4b3a8d835a6a39096b8aba30b376"
)
PARENT_MANIFEST_DIGEST = (
    "1ae8854a6189d847fce3aaa1d4f1af7d2bcb41ab80048cc9f38180b4b8653df7"
)
PARENT_TASK_DIGEST = "59770a8ffe7b9cd79ffb10a213ee1c6525fc8a3a592b725c081cab2b304a3086"
PARENT_INTAKE_HANDOFF_DIGEST = (
    "d42de641e526c0fffc2b19d12e5e9829305f9c64128002891d6b6b3535766773"
)
PARENT_COMPLETION_DIGEST = (
    "7fb28fb7feabc215afd5449afab36edb49ad6c5ff09ba69b898170e4511fe1b9"
)

PARENT_EXECUTION_REGISTRATION_DIGEST = (
    "8a1c6028966f5fded6b25dbbdc1c3d8d226df68fd6b1b7b211c6026b587a421a"
)
PARENT_INTAKE_HANDOFF_REGISTRATION_DIGEST = (
    "28fdcc70e004dc68cdb1722ea68a5d2cca09b5cf656dff3c1b64d2f8adb171c4"
)
PARENT_COMPLETION_REGISTRATION_DIGEST = (
    "2ae022e5e1b4480e9f7274e0f1d4c4d6ff265ddc6299a4f356f66eebd5e4468c"
)

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-p3-result-blind-structural-utility-design-round-111-20260810"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-p3-result-blind-structural-utility-design-round-112-20260810"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/structural_utility/"
    "m4_p3_result_blind_design.py"
)
FROZEN_CONTRACT_DIGEST = (
    "fb87502df390476ae8ab0dd8958479b6153a49b92ac0a0963c041c8de662ee51"
)

_DESIGN_DOMAIN = "dehps.m4-p3.result-blind-structural-utility-design.v1"
_HANDOFF_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility-preregistration-handoff.v1"
)
_COMPLETION_DOMAIN = "dehps.m4-p3.result-blind-structural-utility-design-completion.v1"


class M4P3ResultBlindStructuralUtilityDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class M4P3ResultBlindStructuralUtilityDesignRun:
    design: Mapping[str, Any]
    preregistration_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.design, self.preregistration_handoff, self.completion


def load_m4_p3_result_blind_structural_utility_design_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M4P3ResultBlindStructuralUtilityDesignError(
            f"m4_p3_structural_utility_design_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-p3-result-blind-structural-utility-design-source.v1"
        or payload.get("artifact_type")
        != "m4_p3_result_blind_structural_utility_design_source"
        or payload.get("contract_key")
        != "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY_DESIGN_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 443
        or payload.get("research_execution_id") != 364
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 444
        or payload.get("engineering_execution_id") != 365
        or payload.get("result_blind") is not True
        or payload.get("result_aware") is not False
        or payload.get("parent_payloads_read") != 0
        or payload.get("portfolios_generated") != 0
        or payload.get("folds_executed") != 0
        or payload.get("metric_results_read") != 0
        or payload.get("new_prediction_evidence_created") is not False
        or payload.get("new_model_created") is not False
        or payload.get("production_action") != "none"
        or payload.get("registered_children") != 3
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("frozen_contract_digest") != FROZEN_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain="dehps.m4-p3.result-blind-structural-utility-frozen-contract.v1",
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=("dehps.m4-p3.result-blind-structural-utility-design-source-set.v1"),
        )
    ):
        raise M4P3ResultBlindStructuralUtilityDesignError(
            "m4_p3_structural_utility_design_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise M4P3ResultBlindStructuralUtilityDesignError(
            "m4_p3_structural_utility_design_source_entry_invalid"
        )
    validate_frozen_contract(frozen)
    return payload


def verify_m4_p3_result_blind_structural_utility_design_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    entry = contract["source_entries"][0]
    relative = str(entry["path"])
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise M4P3ResultBlindStructuralUtilityDesignError(
            f"m4_p3_structural_utility_design_source_missing:{relative}"
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
        raise M4P3ResultBlindStructuralUtilityDesignError(
            f"m4_p3_structural_utility_design_source_modified:{relative}"
        )


def build_m4_p3_result_blind_structural_utility_design_artifacts(
    *,
    source_contract: Mapping[str, Any],
    completed_event: Mapping[str, Any],
    parent_registrations: Sequence[Mapping[str, Any]],
) -> M4P3ResultBlindStructuralUtilityDesignRun:
    frozen = source_contract["frozen_contract"]
    validate_frozen_contract(frozen)
    _validate_result_blind_parent_projection(
        completed_event=completed_event,
        parent_registrations=parent_registrations,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        PARENT_EXECUTION_DIGEST,
        PARENT_INTAKE_HANDOFF_DIGEST,
        PARENT_COMPLETION_DIGEST,
    )
    boundary = _claim_boundary()
    zero_work = _zero_work_counters()
    design = _artifact(
        schema_version="dehps-m4-p3-result-blind-structural-utility-design.v1",
        artifact_type="m4_p3_result_blind_structural_utility_design",
        body={
            "status": "COMPLETE",
            "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
            "question": frozen["question"],
            "estimand": frozen["estimand"],
            "legal_universe": frozen["legal_universe"],
            "portfolio_budget": frozen["portfolio_budget"],
            "fold_count_range": frozen["fold_count_range"],
            "arms": frozen["arms"],
            "constructive_invariant": frozen["constructive_invariant"],
            "confirmatory_coordinates": frozen["confirmatory_coordinates"],
            "aggregation_rule": frozen["aggregation_rule"],
            "result_blind_input_boundary": frozen["result_blind_input_boundary"],
            "null": frozen["null"],
            "minimal_non_null": frozen["minimal_non_null"],
            "failure_condition": frozen["failure_condition"],
            "allowed_decisions": frozen["allowed_decisions"],
            "route_policy": frozen["route_policy"],
            "deferred_to_preregistration": frozen["deferred_to_preregistration"],
            "scalar_utility_score_allowed": False,
            "next_consumer": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
            **zero_work,
            **boundary,
        },
        parent_digests=parent_digests,
        domain=_DESIGN_DOMAIN,
    )
    handoff = _artifact(
        schema_version=(
            "dehps-m4-p3-result-blind-structural-utility-preregistration-handoff.v1"
        ),
        artifact_type=("m4_p3_result_blind_structural_utility_preregistration_handoff"),
        body={
            "status": "COMPLETE",
            "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
            "design_artifact_digest": design["artifact_digest"],
            "required_research_event": (
                M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_APPROVED_EVENT
            ),
            "fold_count_range": frozen["fold_count_range"],
            "portfolio_budget": frozen["portfolio_budget"],
            "arm_keys": [item["arm"] for item in frozen["arms"]],
            "confirmatory_coordinate_keys": [
                item["metric"] for item in frozen["confirmatory_coordinates"]
            ],
            "deferred_to_preregistration": frozen["deferred_to_preregistration"],
            "generator_or_evaluation_execution_authorized": False,
            "previous_structural_result_may_tune_preregistration": False,
            "next_consumer": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
            **zero_work,
            **boundary,
        },
        parent_digests=(*parent_digests, str(design["artifact_digest"])),
        domain=_HANDOFF_DOMAIN,
    )
    completion = _artifact(
        schema_version=(
            "dehps-m4-p3-result-blind-structural-utility-design-completion.v1"
        ),
        artifact_type="m4_p3_result_blind_structural_utility_design_completion",
        body={
            "status": "COMPLETE",
            "completion_fact": M4_P3_STRUCTURAL_UTILITY_DESIGN_COMPLETION_FACT,
            "source_contract_digest": source_digest,
            "parent_execution_digest": PARENT_EXECUTION_DIGEST,
            "parent_intake_handoff_digest": PARENT_INTAKE_HANDOFF_DIGEST,
            "parent_completion_digest": PARENT_COMPLETION_DIGEST,
            "design_artifact_digest": design["artifact_digest"],
            "preregistration_handoff_digest": handoff["artifact_digest"],
            "registered_child_count": 3,
            "next_consumer": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
            **zero_work,
            **boundary,
        },
        parent_digests=(
            source_digest,
            str(design["artifact_digest"]),
            str(handoff["artifact_digest"]),
        ),
        domain=_COMPLETION_DOMAIN,
    )
    return M4P3ResultBlindStructuralUtilityDesignRun(
        design=design,
        preregistration_handoff=handoff,
        completion=completion,
    )


def replay_m4_p3_result_blind_structural_utility_design(
    **kwargs: Any,
) -> tuple[M4P3ResultBlindStructuralUtilityDesignRun, dict[str, Any]]:
    run = build_m4_p3_result_blind_structural_utility_design_artifacts(**kwargs)
    return run, {
        "schema_version": (
            "dehps-m4-p3-result-blind-structural-utility-design-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "workload_rerun": False,
        "parent_payloads_read": 0,
        "portfolios_generated": 0,
        "folds_replayed": 0,
        "metric_results_read": 0,
        "raw_outcome_rows_read": 0,
        "previous_structural_result_values_read": 0,
        "manual_input_assembly": False,
        "next_consumer": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
    }


def validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if dict(frozen) != expected_frozen_contract():
        raise M4P3ResultBlindStructuralUtilityDesignError(
            "m4_p3_structural_utility_design_frozen_contract_changed"
        )


def expected_frozen_contract() -> dict[str, Any]:
    return {
        "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
        "task_key": M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY,
        "capability": M4_P3_STRUCTURAL_UTILITY_DESIGN_CAPABILITY,
        "completion_fact": M4_P3_STRUCTURAL_UTILITY_DESIGN_COMPLETION_FACT,
        "next_consumer": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
        "registered_input_digests": [
            PARENT_EXECUTION_DIGEST,
            PARENT_INTAKE_HANDOFF_DIGEST,
            PARENT_COMPLETION_DIGEST,
        ],
        "registered_parent_execution_id": PARENT_EXECUTION_ID,
        "registered_parent_completed_event_digest": PARENT_COMPLETED_EVENT_DIGEST,
        "registered_parent_registration_digests": [
            PARENT_EXECUTION_REGISTRATION_DIGEST,
            PARENT_INTAKE_HANDOFF_REGISTRATION_DIGEST,
            PARENT_COMPLETION_REGISTRATION_DIGEST,
        ],
        "question": (
            "Does a frozen candidate-portfolio construction produce stable, "
            "transparent structural utility at the same 100-ticket budget, "
            "independent of any target result?"
        ),
        "estimand": {
            "unit": (
                "one cutoff-safe fold by one frozen generator arm producing "
                "exactly 100 canonical six-of-33 tickets"
            ),
            "population": ("60 to 120 consecutive preregistered cutoff-safe folds"),
            "contrast": (
                "paired fold-level difference between the candidate arm and "
                "each equal-budget control arm"
            ),
        },
        "legal_universe": {
            "domain": "SSQ_RED_BALL_SIX_OF_33",
            "universe_formula": "C(33,6)",
            "universe_cardinality": 1_107_568,
            "pre_draw_probability": "equal_for_every_legal_combination",
        },
        "portfolio_budget": 100,
        "fold_count_range": {"minimum": 60, "maximum": 120},
        "arms": [
            {
                "arm": "uniform_random_without_replacement",
                "role": "primary_null",
                "eligibility": "same_legal_universe_budget_cutoffs_and_frozen_seed_family",
            },
            {
                "arm": "legacy_structural_top100",
                "role": "frozen_legacy_comparator",
                "eligibility": (
                    "existing_source_pinned_structural_only_ordering_with_no_"
                    "target_result_input_or_fail_closed"
                ),
            },
            {
                "arm": "prediction_v2_structural_selection_100",
                "role": "candidate",
                "eligibility": (
                    "existing_source_pinned_result_blind_selector_with_explicit_"
                    "budget_100_rule_and_no_retuning"
                ),
            },
        ],
        "constructive_invariant": {
            "canonical_distinct_ticket_count": 100,
            "unique_ticket_fraction": "1/1",
            "confirmatory_advantage_metric": False,
        },
        "confirmatory_coordinates": [
            {
                "metric": "pair_coverage_ratio",
                "formula": "distinct_number_pairs_present/C(33,2)",
                "direction": "higher",
            },
            {
                "metric": "triple_coverage_ratio",
                "formula": "distinct_number_triples_present/C(33,3)",
                "direction": "higher",
            },
            {
                "metric": "high_overlap_ticket_pair_rate",
                "formula": "ticket_pairs_with_intersection_at_least_3/C(100,2)",
                "direction": "lower",
            },
            {
                "metric": "normalized_pair_usage_entropy",
                "formula": "shannon_entropy_of_528_pair_use_shares/log(528)",
                "direction": "higher",
            },
            {
                "metric": "largest_similarity_cluster_fraction",
                "formula": (
                    "largest_component_size/100_in_ticket_graph_with_"
                    "intersection_at_least_3_edges"
                ),
                "direction": "lower",
            },
            {
                "metric": "family_concentration_hhi",
                "formula": (
                    "sum_of_squared_shares_over_a_preregistered_label_invariant_"
                    "structural_family_partition"
                ),
                "direction": "lower",
            },
        ],
        "aggregation_rule": (
            "report_all_coordinates_and_paired_fold_distributions_separately_"
            "with_no_unfrozen_scalar_score_or_post_hoc_pareto_preference"
        ),
        "result_blind_input_boundary": {
            "allowed": [
                "legal_universe_descriptor_and_canonical_combination_encoding",
                "candidate_internal_structural_features",
                "digest_pinned_cutoff_safe_strictly_prior_only_feature_snapshots",
                "frozen_generator_sources_configurations_and_seed_domains",
            ],
            "forbidden": [
                "target_or_future_draw_numbers",
                "winning_hit_payout_return_reward_or_settlement_labels",
                "target_result_ranks_or_realized_outcome_rankings",
                "raw_outcome_rows_in_generator_or_evaluator_interfaces",
                "previous_structural_result_values_used_to_select_any_choice",
                "post_hoc_arm_threshold_fold_seed_or_metric_changes",
            ],
            "generator_accepts_target_result_parameter": False,
            "evaluator_accepts_target_result_parameter": False,
        },
        "null": (
            "at_equal_budget_and_legal_universe_the_candidate_has_no_stable_"
            "fold_level_structural_improvement_over_both_controls"
        ),
        "minimal_non_null": (
            "direction_consistent_improvement_on_multiple_independent_"
            "coordinates_without_a_protected_coordinate_regression"
        ),
        "failure_condition": (
            "leakage_unequal_arm_contract_unavailable_comparator_post_hoc_choice_"
            "insufficient_valid_folds_unstable_direction_protected_regression_"
            "missing_replay_or_failure_under_the_preregistered_rule"
        ),
        "allowed_decisions": [
            "STRUCTURAL_UTILITY_SUPPORTED_WITHIN_FROZEN_SCOPE",
            "NO_STABLE_STRUCTURAL_UTILITY",
            "INCONCLUSIVE_STRUCTURAL_UTILITY",
            "INVALID_RESULT_BLIND_EXECUTION",
        ],
        "route_policy": {
            "supported": (
                "continue_only_candidate_portfolio_optimizer_research_or_small_"
                "shadow_use_without_prediction_promotion"
            ),
            "unsupported": (
                "stop_lottery_structural_optimization_while_retaining_research_os"
            ),
        },
        "deferred_to_preregistration": [
            "exact_fold_count_and_cutoff_endpoints_within_60_to_120",
            "minimum_prior_history_requirement",
            "exact_source_hashes_and_configs_for_non_random_arms",
            "seed_schedule_and_random_replicate_count",
            "label_invariant_structural_family_partition",
            "paired_stability_statistic_uncertainty_multiplicity_tolerances_and_thresholds",
            "invalid_fold_and_missing_snapshot_rules",
            "resource_and_timeout_limits",
        ],
        "registered_child_count": 3,
        "registered_total_with_mainline_execution": 4,
        "result_blind": True,
        "parent_payloads_read": 0,
        "portfolios_generated": 0,
        "folds_executed": 0,
        "metric_results_read": 0,
        "raw_outcome_rows_read": 0,
        "previous_structural_result_values_read": 0,
        "historical_prediction_evidence": "INCONCLUSIVE",
        "prediction_v2_mode": "SHADOW_ONLY",
        "prediction_v2_route": "BASELINE_ONLY",
        "old_training_lines": "FROZEN",
        "new_prediction_evidence_created": False,
        "new_model_created": False,
        "promotion_gate_opened": False,
        "predictive_p3_authorized": False,
        "production_action": "none",
    }


def _validate_result_blind_parent_projection(
    *,
    completed_event: Mapping[str, Any],
    parent_registrations: Sequence[Mapping[str, Any]],
) -> None:
    forbidden_keys = {
        "decision",
        "outcome",
        "registered_outcome",
        "candidate_triple_collision_mass",
        "primary_lower_tail_numerator",
        "secondary_lower_tail_numerator",
    }
    if forbidden_keys.intersection(completed_event):
        raise M4P3ResultBlindStructuralUtilityDesignError(
            "m4_p3_structural_utility_parent_event_not_result_blind"
        )
    if dict(completed_event) != {
        "event_digest": PARENT_COMPLETED_EVENT_DIGEST,
        "execution_id": PARENT_EXECUTION_ID,
        "control_plane_key": "m4-information-theory-mainline",
        "manifest_digest": PARENT_MANIFEST_DIGEST,
        "task_digest": PARENT_TASK_DIGEST,
        "task_key": PARENT_TASK_KEY,
        "capability": PARENT_CAPABILITY,
        "event_type": "completed",
        "sequence": 1,
    }:
        raise M4P3ResultBlindStructuralUtilityDesignError(
            "m4_p3_structural_utility_parent_event_identity_changed"
        )
    expected = {
        "research_os_mainline_execution": (
            PARENT_EXECUTION_REGISTRATION_DIGEST,
            PARENT_EXECUTION_DIGEST,
            "dehps-research-os-mainline-execution.v1",
        ),
        "prediction_v2_balanced_design_structural_utility_research_intake_handoff": (
            PARENT_INTAKE_HANDOFF_REGISTRATION_DIGEST,
            PARENT_INTAKE_HANDOFF_DIGEST,
            (
                "dehps-prediction-v2-balanced-design-structural-utility-research-"
                "intake-handoff.v1"
            ),
        ),
        "prediction_v2_balanced_design_structural_evaluation_result_decision_completion": (
            PARENT_COMPLETION_REGISTRATION_DIGEST,
            PARENT_COMPLETION_DIGEST,
            (
                "dehps-prediction-v2-balanced-design-structural-evaluation-"
                "result-decision-completion.v1"
            ),
        ),
    }
    if len(parent_registrations) != len(expected):
        raise M4P3ResultBlindStructuralUtilityDesignError(
            "m4_p3_structural_utility_parent_registration_count_changed"
        )
    observed: dict[str, tuple[str, str, str]] = {}
    for registration in parent_registrations:
        if forbidden_keys.intersection(registration):
            raise M4P3ResultBlindStructuralUtilityDesignError(
                "m4_p3_structural_utility_parent_registration_not_result_blind"
            )
        if (
            registration.get("execution_id") != PARENT_EXECUTION_ID
            or registration.get("control_plane_key") != "m4-information-theory-mainline"
            or registration.get("task_key") != PARENT_TASK_KEY
            or registration.get("task_digest") != PARENT_TASK_DIGEST
        ):
            raise M4P3ResultBlindStructuralUtilityDesignError(
                "m4_p3_structural_utility_parent_registration_identity_changed"
            )
        observed[str(registration.get("artifact_type"))] = (
            str(registration.get("registration_digest")),
            str(registration.get("artifact_digest")),
            str(registration.get("schema_version")),
        )
    if observed != expected:
        raise M4P3ResultBlindStructuralUtilityDesignError(
            "m4_p3_structural_utility_parent_registration_identity_changed"
        )


def _zero_work_counters() -> dict[str, Any]:
    return {
        "result_blind": True,
        "parent_payloads_read": 0,
        "portfolios_generated": 0,
        "folds_executed": 0,
        "metric_results_read": 0,
        "raw_outcome_rows_read": 0,
        "previous_structural_result_values_read": 0,
    }


def _claim_boundary() -> dict[str, Any]:
    return {
        "historical_prediction_evidence": "INCONCLUSIVE",
        "prediction_v2_mode": "SHADOW_ONLY",
        "prediction_v2_route": "BASELINE_ONLY",
        "old_training_lines": "FROZEN",
        "portfolio_activation_authorized": False,
        "new_prediction_evidence_created": False,
        "new_model_created": False,
        "promotion_gate_opened": False,
        "predictive_p3_authorized": False,
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


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
