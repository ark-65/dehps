from __future__ import annotations

from dataclasses import asdict
import json

from dehps.research_autonomy.context import ResearchContext
from dehps.research_autonomy.novelty import HypothesisNoveltyDetector
from dehps.research_autonomy.proposal_models import (
    HypothesisProposal,
    ProposalValidationCheck,
    ProposalValidationReport,
)


class HypothesisProposalValidator:
    def __init__(self, novelty_detector: HypothesisNoveltyDetector | None = None) -> None:
        self.novelty_detector = novelty_detector or HypothesisNoveltyDetector()

    def validate(
        self,
        proposal: HypothesisProposal,
        context: ResearchContext,
    ) -> ProposalValidationReport:
        validation = proposal.validation_protocol
        boundary = proposal.input_boundary
        baseline = proposal.baseline_contract
        metrics = set(str(value) for value in proposal.metric_contract.get("required", ()))
        available_features = {item.key: item for item in context.available_features}
        available_models = {item.key for item in context.available_models}
        proposal_features = tuple(str(value) for value in proposal.feature_contract.get("feature_keys", ()))
        proposal_models = tuple(str(value) for value in proposal.model_contract.get("model_keys", ()))
        novelty = self.novelty_detector.compare(proposal, context)
        allowed_fields = set(str(value) for value in boundary.get("allowed_fields", ()))
        context_fields = set(context.data_boundary.training_fields)
        checks = (
            self._check("null_hypothesis", bool(proposal.null_hypothesis.strip()), "null hypothesis is required"),
            self._check("minimal_non_null", bool(proposal.minimal_non_null.strip()), "minimal non-null is required"),
            self._check(
                "failure_condition",
                bool(proposal.failure_condition.get("rule"))
                and bool(proposal.failure_condition.get("reject_on_no_rank_tail_improvement")),
                "failure condition must reject a non-improving rank tail",
            ),
            self._check(
                "same_budget_baseline",
                all(
                    baseline.get(key) is True
                    for key in ("same_legal_universe", "same_history", "same_candidate_budget", "same_compute_budget")
                ),
                "baseline and candidate must use identical universe, history, candidate budget, and compute budget",
            ),
            self._check(
                "time_boundary",
                bool(boundary.get("as_of_rule")) and validation.get("kind") == "expanding_walk_forward",
                "an explicit pre-target as-of rule and expanding walk-forward protocol are required",
            ),
            self._check(
                "formal_input_boundary",
                context.data_boundary.status == "passed"
                and allowed_fields
                and allowed_fields.issubset(context_fields),
                "proposal inputs must be a subset of the passed formal data boundary",
            ),
            self._check(
                "no_future_information",
                boundary.get("contains_future_information") is False
                and all(not available_features[key].contains_future_information for key in proposal_features if key in available_features),
                "features must not contain future or post-draw information",
            ),
            self._check(
                "no_random_split",
                validation.get("random_split") is False and "random" not in str(validation.get("kind", "")).lower(),
                "random split validation is forbidden",
            ),
            self._check(
                "frozen_search_isolation",
                validation.get("search_frozen_overlap") == 0
                and validation.get("search_uses_frozen_validation") is False
                and context.frozen_validation_status.get("selection_uses_frozen_validation") is False,
                "search and frozen windows must be disjoint and frozen outcomes cannot select candidates",
            ),
            self._check(
                "novelty",
                novelty.is_novel and not novelty.rejected_reuse_detected,
                "proposal reuses a rejected or duplicate mechanism: " + ",".join(novelty.duplicate_reasons),
            ),
            self._check(
                "compute_budget",
                proposal.estimated_compute_cost <= 0.85 and proposal.estimated_implementation_cost <= 0.85,
                "proposal exceeds the bounded compute or implementation budget",
            ),
            self._check(
                "data_sufficiency",
                bool(context.source_training_run_ids)
                and bool(context.formal_source_paths)
                and int(validation.get("search_issue_count") or 0) >= 80,
                "formal training runs, diagnostics, and at least 80 search issues are required",
            ),
            self._check(
                "ranking_metrics",
                {"top_100", "top_1000", "top_10000", "rank_tail"}.issubset(metrics)
                and proposal.metric_contract.get("primary") == "time_isolated_exact_target_rank",
                "metrics must measure exact prediction rank, Top bands, and rank tail",
            ),
            self._check(
                "forward_testability",
                int(validation.get("forward_min_paired_issues") or 0) >= 20
                and validation.get("selection_uses_forward_outcomes") is False,
                "forward protocol requires at least 20 paired issues and cannot select on forward outcomes",
            ),
            self._check(
                "feature_availability",
                bool(proposal_features) and set(proposal_features).issubset(available_features),
                "all proposal features must exist in the machine-readable catalog",
            ),
            self._check(
                "model_availability",
                bool(proposal_models) and set(proposal_models).issubset(available_models),
                "all proposal models must exist in the implementation catalog",
            ),
            self._check(
                "no_betting_promise",
                not self._contains_betting_promise(proposal),
                "proposal contains a betting or guaranteed-return promise",
            ),
            self._check(
                "registry_compatibility",
                self._registry_fields_complete(proposal),
                "proposal is missing Hypothesis Registry preregistration fields",
            ),
        )
        failures = tuple(check.reason for check in checks if not check.passed)
        return ProposalValidationReport(valid=not failures, checks=checks, failure_reasons=failures)

    @staticmethod
    def _check(key: str, passed: bool, reason: str) -> ProposalValidationCheck:
        return ProposalValidationCheck(key=key, passed=bool(passed), reason=reason)

    @staticmethod
    def _registry_fields_complete(proposal: HypothesisProposal) -> bool:
        registry = proposal.registry_preregistration()
        required = (
            "statement", "null_hypothesis", "minimal_non_null", "invariants",
            "baseline_definition", "metric_definition", "failure_condition", "self_deception_risk",
        )
        return all(registry.get(key) for key in required)

    @staticmethod
    def _contains_betting_promise(proposal: HypothesisProposal) -> bool:
        text = json.dumps(asdict(proposal), ensure_ascii=False).lower()
        return any(
            phrase in text
            for phrase in (
                "guaranteed win", "guaranteed return", "risk-free profit", "betting advice",
                "保证中奖", "稳赚", "无风险投注", "必然命中",
            )
        )
