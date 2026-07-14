from __future__ import annotations

from typing import Any

from dehps.research_autonomy.context import ResearchContext
from dehps.research_autonomy.proposal_models import HypothesisProposal
from dehps.research_planning.models import (
    ExperimentPlan,
    ExperimentPlanValidationCheck,
    ExperimentPlanValidationReport,
)
from dehps.research_planning.protocol_builder import DISAGREEMENT_STRATA, STAGE_ORDER


class ExperimentPlanValidator:
    def validate(
        self,
        plan: ExperimentPlan,
        proposal: HypothesisProposal,
        context: ResearchContext,
    ) -> ExperimentPlanValidationReport:
        checks = (
            self._check(
                "proposal_approved",
                plan.validation_protocol.get("reviewer_approval", {}).get("status") == "approved",
                "proposal must have a frozen Reviewer approval before planning",
            ),
            self._check(
                "proposal_fingerprint",
                plan.proposal_fingerprint == proposal.content_hash,
                "plan proposal fingerprint must match the approved proposal payload",
            ),
            self._check(
                "plan_fingerprint",
                plan.plan_fingerprint == plan.recomputed_fingerprint,
                "plan fingerprint must be stable and reproducible",
            ),
            self._check(
                "null_unchanged",
                plan.null_hypothesis == proposal.null_hypothesis,
                "null hypothesis may not be rewritten by the planner",
            ),
            self._check(
                "failure_condition_unchanged",
                plan.failure_condition == proposal.failure_condition,
                "failure condition may not be rewritten by the planner",
            ),
            self._check(
                "baseline_not_weakened",
                self._baseline_not_weakened(plan.baseline_contract, proposal.baseline_contract),
                "plan baseline must preserve proposal baseline constraints and add matched baselines",
            ),
            self._check(
                "validation_window_not_shortened",
                self._windows_not_shortened(plan, proposal),
                "planner may not shorten search, frozen, or forward validation windows",
            ),
            self._check(
                "forward_minimum",
                int(plan.validation_protocol.get("forward_min_paired_issues") or 0) >= 20,
                "forward validation requires at least 20 paired issues",
            ),
            self._check(
                "stage_order",
                tuple(stage.key for stage in plan.experiment_stages) == STAGE_ORDER,
                "stage order must be feasibility, historical_search, frozen_validation, forward_validation, decision_review",
            ),
            self._check(
                "frozen_before_forward",
                plan.validation_protocol.get("frozen_validation_required_before_forward") is True
                and self._stage_index(plan, "frozen_validation") < self._stage_index(plan, "forward_validation"),
                "frozen validation may not be skipped before forward validation",
            ),
            self._check(
                "window_isolation",
                all(
                    int(plan.validation_protocol.get(key, -1)) == 0
                    for key in ("search_frozen_overlap", "search_forward_overlap", "frozen_forward_overlap")
                ),
                "search, frozen, and forward windows must be disjoint",
            ),
            self._check(
                "candidate_baseline_budget_match",
                all(stage.candidate_budget == stage.baseline_budget for stage in plan.experiment_stages),
                "candidate and baseline budgets must match in every stage",
            ),
            self._check(
                "feature_inputs_no_future",
                self._feature_inputs_are_pre_target(plan.feature_contract),
                "disagreement features must use only pre-target ranker outputs",
            ),
            self._check(
                "ranker_list_fixed",
                self._ranker_list_fixed(plan.model_contract),
                "ranker list, versions, and config hashes must be fixed",
            ),
            self._check(
                "strata_fixed",
                self._strata_fixed(plan.feature_contract),
                "disagreement strata must be fixed from the search window and all reported",
            ),
            self._check(
                "no_production_write",
                plan.resource_budget.production_access is False
                and all(stage.execution_environment == "isolated" for stage in plan.experiment_stages)
                and plan.validation_protocol.get("production_training_change_allowed") is False,
                "planning and execution contracts may not write production state",
            ),
            self._check(
                "no_promotion_action",
                plan.validation_protocol.get("promotion_allowed") is False,
                "plan must not authorize promotion actions",
            ),
            self._check(
                "resource_budget_executable",
                plan.resource_budget.cpu_hours > 0
                and plan.resource_budget.memory_gb > 0
                and plan.resource_budget.timeout_seconds >= 300
                and plan.resource_budget.storage_mb > 0,
                "resource budget must be positive and executable in isolation",
            ),
            self._check(
                "artifact_contract_complete",
                bool(plan.artifact_contract.base_directory)
                and len(plan.artifact_contract.required_artifacts) >= 4
                and plan.artifact_contract.complete_stage_results_required,
                "artifact contract must require complete stage and strata outputs",
            ),
            self._check(
                "context_boundary",
                context.data_boundary.status == "passed"
                and not context.data_boundary.future_information_allowed,
                "ResearchContext boundary must pass and forbid future information",
            ),
        )
        failures = tuple(check.reason for check in checks if not check.passed)
        return ExperimentPlanValidationReport(
            valid=not failures,
            checks=checks,
            failure_reasons=failures,
        )

    @staticmethod
    def _check(key: str, passed: bool, reason: str) -> ExperimentPlanValidationCheck:
        return ExperimentPlanValidationCheck(key=key, passed=bool(passed), reason=reason)

    @staticmethod
    def _baseline_not_weakened(plan: dict[str, Any], proposal: dict[str, Any]) -> bool:
        for key, value in proposal.items():
            if plan.get(key) != value:
                return False
        baselines = plan.get("matched_baselines")
        if not isinstance(baselines, dict):
            return False
        required = {"budget_matched_random", "rank_matched_consensus", "current_production_ranker"}
        if not required.issubset(baselines):
            return False
        return all(
            item.get("candidate_count") == "match_disagreement_stratum"
            and item.get("time_window") == "identical"
            and item.get("legal_universe") == "identical_6_of_33_red_ball"
            and item.get("top_k_budget") == "identical"
            for item in baselines.values()
            if isinstance(item, dict)
        )

    @staticmethod
    def _windows_not_shortened(plan: ExperimentPlan, proposal: HypothesisProposal) -> bool:
        protocol = plan.validation_protocol
        proposal_protocol = proposal.validation_protocol
        return (
            int(protocol.get("search_issue_count") or 0)
            >= int(proposal_protocol.get("search_issue_count") or 0)
            and int(protocol.get("frozen_issue_count") or 0)
            >= int(proposal_protocol.get("frozen_issue_count") or 0)
            and int(protocol.get("forward_min_paired_issues") or 0)
            >= int(proposal_protocol.get("forward_min_paired_issues") or 0)
        )

    @staticmethod
    def _stage_index(plan: ExperimentPlan, stage_key: str) -> int:
        return next(index for index, stage in enumerate(plan.experiment_stages) if stage.key == stage_key)

    @staticmethod
    def _feature_inputs_are_pre_target(contract: dict[str, Any]) -> bool:
        features = contract.get("disagreement_features")
        if not isinstance(features, dict) or not features:
            return False
        for descriptor in features.values():
            if not isinstance(descriptor, dict):
                return False
            if descriptor.get("future_information_allowed") is not False:
                return False
            if descriptor.get("target_result_used") is not False:
                return False
            if descriptor.get("post_draw_update_allowed") is not False:
                return False
            inputs = " ".join(str(value) for value in descriptor.get("inputs") or ())
            if "target_red_numbers" in inputs or "post_draw" in inputs:
                return False
        return True

    @staticmethod
    def _ranker_list_fixed(contract: dict[str, Any]) -> bool:
        rankers = contract.get("rankers")
        if not isinstance(rankers, (list, tuple)) or len(rankers) < 3:
            return False
        keys = {str(item.get("key")) for item in rankers if isinstance(item, dict)}
        required = {"frequency_based_ranker", "structural_ranker", "omission_based_ranker"}
        if not required.issubset(keys):
            return False
        return (
            contract.get("fixed_ranker_list") is True
            and contract.get("dynamic_ranker_selection") is False
            and all(item.get("version") and item.get("config_hash") for item in rankers)
        )

    @staticmethod
    def _strata_fixed(contract: dict[str, Any]) -> bool:
        strata = contract.get("strata")
        if not isinstance(strata, dict):
            return False
        return (
            tuple(strata.get("keys") or ()) == DISAGREEMENT_STRATA
            and strata.get("threshold_source") == "search_window_only"
            and strata.get("threshold_freeze") == "before_frozen_validation"
            and strata.get("report_all_strata") is True
            and strata.get("delete_failed_strata_allowed") is False
        )
