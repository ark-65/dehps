from __future__ import annotations

from dataclasses import replace
from typing import Any

from dehps.research_autonomy.context import ResearchContext
from dehps.research_autonomy.proposal_models import HypothesisProposal
from dehps.research_planning.fingerprint import stable_fingerprint
from dehps.research_planning.models import (
    ArtifactContract,
    EvidenceContract,
    ExperimentPlan,
    ExperimentStage,
    ImplementationStep,
)
from dehps.research_planning.resource_estimator import ResourceEstimator


STAGE_ORDER = (
    "feasibility",
    "historical_search",
    "frozen_validation",
    "forward_validation",
    "decision_review",
)
DISAGREEMENT_STRATA = (
    "low_disagreement",
    "medium_disagreement",
    "high_disagreement",
    "extreme_disagreement",
)
REQUIRED_METRICS = (
    "exact_target_rank",
    "top_100_hits",
    "top_1000_hits",
    "top_10000_hits",
    "median_rank",
    "mean_rank",
    "p95_rank",
    "worst_rank",
    "mean_reciprocal_rank",
    "tail_over_750000",
    "tail_over_900000",
    "tail_over_1000000",
    "baseline_lift",
    "stratum_stability",
    "direction_consistency",
)
REQUIRED_STATISTICS = (
    "paired_rank_difference",
    "bootstrap_confidence_interval",
    "permutation_null",
    "effect_size",
    "multiple_comparison_adjusted_p_value",
)
SUCCESS_CONDITIONS = (
    "at least one preregistered disagreement stratum has the same direction in frozen and forward windows",
    "matched-baseline lift is positive under the same candidate budget and rank distribution",
    "tail risk is not worse than the current production ranker",
    "result is not driven by a single issue",
    "multiple rank cutoffs do not conflict in direction",
    "no leakage is detected",
    "no candidate or baseline budget mismatch is detected",
)
FAILURE_CONDITIONS = (
    "frozen and forward directions are opposite",
    "effect appears only in the search window",
    "effect is driven by a single issue",
    "tail risk is materially worse than the current production ranker",
    "baseline budget differs from candidate budget",
    "ranker list is modified after preregistration",
    "strata thresholds are modified after search freeze",
    "forward window has fewer than 20 issues",
    "statistical significance has no practically meaningful effect size",
)


class RankingDisagreementProtocolBuilder:
    def __init__(self, resource_estimator: ResourceEstimator | None = None) -> None:
        self.resource_estimator = resource_estimator or ResourceEstimator()

    def build(
        self,
        proposal: HypothesisProposal,
        context: ResearchContext,
        *,
        plan_version: str,
        reviewer_decision: dict[str, Any] | None = None,
    ) -> ExperimentPlan:
        if proposal.mechanism != "ranking_model_disagreement":
            raise ValueError(f"unsupported planning mechanism: {proposal.mechanism}")
        proposal_fingerprint = proposal.content_hash
        plan_key = f"plan-{proposal.proposal_key}-v1"
        ranker_contract = self._ranker_contract()
        validation_protocol = self._validation_protocol(
            proposal=proposal,
            context=context,
            ranker_contract=ranker_contract,
            reviewer_decision=reviewer_decision or {},
        )
        resource_budget = self.resource_estimator.estimate()
        artifact_base = f"data/output/research-planning/{plan_key}"
        plan = ExperimentPlan(
            plan_key=plan_key,
            plan_version=plan_version,
            proposal_key=proposal.proposal_key,
            hypothesis_key=proposal.proposal_key,
            family_key=proposal.family_key,
            mechanism=proposal.mechanism,
            scientific_question=(
                "Do disagreements between fixed legal rankers over the same combination identify "
                "target-rank regions not covered by the current single-ranker view?"
            ),
            null_hypothesis=proposal.null_hypothesis,
            minimal_non_null=proposal.minimal_non_null,
            invariants=tuple(dict.fromkeys((
                *proposal.invariants,
                "ranker list, ranker versions, and config hashes are fixed before frozen validation",
                "disagreement strata are determined only from the search window and then frozen",
                "all strata and all baselines must report complete results, including failures",
            ))),
            input_boundary=self._input_boundary(proposal),
            feature_contract=self._feature_contract(proposal),
            model_contract={
                **dict(proposal.model_contract),
                "rankers": ranker_contract,
                "fixed_ranker_list": True,
                "dynamic_ranker_selection": False,
                "result_conditioned_ranker_selection": False,
            },
            baseline_contract=self._baseline_contract(proposal),
            metric_contract=self._metric_contract(proposal),
            validation_protocol=validation_protocol,
            failure_condition=dict(proposal.failure_condition),
            self_deception_controls=tuple(dict.fromkeys((
                *proposal.self_deception_risks,
                "do not choose or remove strata after frozen or forward results are observed",
                "do not report only the best-performing stratum",
                "do not weaken matched baselines after seeing target ranks",
            ))),
            implementation_steps=self._implementation_steps(),
            experiment_stages=self._stages(plan_key, resource_budget.candidate_budget_per_stage),
            resource_budget=resource_budget,
            artifact_contract=ArtifactContract(
                schema_version="ranking-disagreement-artifacts-v1",
                base_directory=artifact_base,
                required_artifacts=(
                    "ranker_snapshots.json",
                    "disagreement_features.json",
                    "strata_thresholds.json",
                    "matched_baselines.json",
                    "metrics_by_stage.json",
                    "complete_strata_results.json",
                ),
                forbidden_artifacts=(
                    "production-training-update",
                    "promotion-decision",
                    "evidence-write-during-planning",
                ),
                retention_policy="keep all stage artifacts until Reviewer decision",
                complete_stage_results_required=True,
            ),
            evidence_contract=EvidenceContract(
                evidence_type="ranking_disagreement_experiment_result",
                evidence_writes_allowed_during_planning=False,
                minimum_forward_issues=20,
                required_result_fields=(
                    "plan_key",
                    "plan_fingerprint",
                    "stage_results",
                    "all_strata",
                    "all_baselines",
                    "leakage_report",
                    "budget_report",
                    "effect_size",
                ),
                decision_requires_reviewer=True,
            ),
            stop_conditions=(
                "stop before execution until Engineering implementation is reviewed and accepted",
                "stop before Evidence creation until an audited isolated Operator execution exists",
                "stop before any production write, Objective change, Promotion action, or Supervisor restart",
            ),
            proposal_fingerprint=proposal_fingerprint,
            plan_fingerprint="",
        )
        return replace(plan, plan_fingerprint=plan.recomputed_fingerprint)

    @staticmethod
    def _ranker_contract() -> tuple[dict[str, Any], ...]:
        rankers = (
            {
                "key": "frequency_based_ranker",
                "ranker_family": "frequency",
                "version": "frequency_ranker:v1",
                "implementation_path": "apps/worker-python/dehps/models/frequency_ranker.py",
                "config": {"mode": "pre_target_frequency", "random_seed": 23},
            },
            {
                "key": "structural_ranker",
                "ranker_family": "structural",
                "version": "structural_formula:v1",
                "implementation_path": "apps/worker-python/dehps/scoring/formula.py",
                "config": {"mode": "structural_plausibility", "random_seed": 23},
            },
            {
                "key": "omission_based_ranker",
                "ranker_family": "omission",
                "version": "omission_ranker:v1",
                "implementation_path": "apps/worker-python/dehps/features/red_ball_features.py",
                "config": {"mode": "pre_target_omission", "random_seed": 23},
            },
        )
        return tuple({**item, "config_hash": stable_fingerprint(item["config"])} for item in rankers)

    @staticmethod
    def _input_boundary(proposal: HypothesisProposal) -> dict[str, Any]:
        return {
            **dict(proposal.input_boundary),
            "ranker_output_boundary": "only ranker outputs computed as of the current issue are allowed",
            "target_issue_result_allowed": False,
            "post_draw_update_allowed": False,
            "random_split": False,
        }

    @staticmethod
    def _feature_contract(proposal: HypothesisProposal) -> dict[str, Any]:
        formulas = {
            "rank_mean": "mean(rank_i for i in fixed_rankers)",
            "rank_median": "median(rank_i for i in fixed_rankers)",
            "rank_min": "min(rank_i for i in fixed_rankers)",
            "rank_max": "max(rank_i for i in fixed_rankers)",
            "rank_std": "population_stddev(rank_i for i in fixed_rankers)",
            "rank_range": "rank_max - rank_min",
            "pairwise_rank_gap": "all absolute pairwise rank differences over fixed rankers",
            "ranker_order_entropy": "entropy of ranker ordering buckets for the same combination",
            "consensus_band": "fixed search-window band assigned by low rank_range and low entropy",
            "disagreement_band": "fixed search-window band assigned by rank_range and entropy quantiles",
        }
        return {
            **dict(proposal.feature_contract),
            "disagreement_features": {
                key: {
                    "formula": formula,
                    "inputs": ["fixed_ranker_outputs_before_target_issue"],
                    "implementation_path": "apps/worker-python/dehps/research_planning/protocol_builder.py",
                    "dtype": "float64" if key not in {"consensus_band", "disagreement_band"} else "string",
                    "shape": "scalar_per_candidate"
                    if key != "pairwise_rank_gap"
                    else "pairwise_vector_per_candidate",
                    "sort_direction": "ascending"
                    if key in {"rank_mean", "rank_median", "rank_min", "rank_max"}
                    else "descending",
                    "missing_values": "fail_stage",
                    "future_information_allowed": False,
                    "target_result_used": False,
                    "post_draw_update_allowed": False,
                }
                for key, formula in formulas.items()
            },
            "strata": {
                "keys": list(DISAGREEMENT_STRATA),
                "threshold_source": "search_window_only",
                "threshold_freeze": "before_frozen_validation",
                "report_all_strata": True,
                "delete_failed_strata_allowed": False,
                "boundaries": {
                    "low_disagreement": {"search_quantile": [0.0, 0.25]},
                    "medium_disagreement": {"search_quantile": [0.25, 0.50]},
                    "high_disagreement": {"search_quantile": [0.50, 0.75]},
                    "extreme_disagreement": {"search_quantile": [0.75, 1.0]},
                },
            },
        }

    @staticmethod
    def _baseline_contract(proposal: HypothesisProposal) -> dict[str, Any]:
        return {
            **dict(proposal.baseline_contract),
            "proposal_baseline_key": proposal.baseline_contract.get("baseline_key"),
            "null": (
                "Under identical candidate budget and rank distribution, disagreement strata and "
                "matched baselines have no systematic target-rank distribution difference."
            ),
            "matched_baselines": {
                "budget_matched_random": {
                    "candidate_count": "match_disagreement_stratum",
                    "rank_mean_interval": "best_effort_match",
                    "time_window": "identical",
                    "legal_universe": "identical_6_of_33_red_ball",
                    "top_k_budget": "identical",
                    "random_seed": 23,
                    "sampling_algorithm_version": "budget_matched_random:v1",
                },
                "rank_matched_consensus": {
                    "candidate_count": "match_disagreement_stratum",
                    "rank_mean_interval": "match_disagreement_stratum",
                    "time_window": "identical",
                    "legal_universe": "identical_6_of_33_red_ball",
                    "top_k_budget": "identical",
                    "random_seed": 23,
                    "sampling_algorithm_version": "rank_matched_consensus:v1",
                },
                "current_production_ranker": {
                    "candidate_count": "match_disagreement_stratum",
                    "rank_mean_interval": "production_ranker_native",
                    "time_window": "identical",
                    "legal_universe": "identical_6_of_33_red_ball",
                    "top_k_budget": "identical",
                    "random_seed": 23,
                    "sampling_algorithm_version": "current_production_ranker:v1",
                },
            },
            "same_legal_universe": True,
            "same_history": True,
            "same_candidate_budget": True,
            "same_compute_budget": True,
            "report_all_baselines": True,
        }

    @staticmethod
    def _metric_contract(proposal: HypothesisProposal) -> dict[str, Any]:
        return {
            **dict(proposal.metric_contract),
            "required": list(REQUIRED_METRICS),
            "statistics": list(REQUIRED_STATISTICS),
            "single_issue_success_forbidden": True,
            "all_strata_required": True,
            "all_baselines_required": True,
            "legal_universe_size": 1_107_568,
        }

    @staticmethod
    def _validation_protocol(
        *,
        proposal: HypothesisProposal,
        context: ResearchContext,
        ranker_contract: tuple[dict[str, Any], ...],
        reviewer_decision: dict[str, Any],
    ) -> dict[str, Any]:
        validation = dict(proposal.validation_protocol)
        search_count = 100
        frozen_count = 20
        forward_minimum = 20
        return {
            **validation,
            "protocol_key": "ranking_model_disagreement_preregistration_v1",
            "search_issue_count": search_count,
            "frozen_issue_count": frozen_count,
            "forward_min_paired_issues": forward_minimum,
            "train_mode": "expanding",
            "random_split": False,
            "search_frozen_overlap": 0,
            "search_forward_overlap": 0,
            "frozen_forward_overlap": 0,
            "search_issue_range": {
                "kind": "latest_pre_frozen_issues",
                "count": search_count,
                "source": "approved_proposal_context_boundary",
            },
            "frozen_issue_range": {
                "kind": "disjoint_holdout_after_search",
                "count": frozen_count,
                "source": "approved_proposal_context_boundary",
            },
            "forward_start_issue": "first_future_issue_after_frozen_window",
            "history_fingerprint": context.fingerprint,
            "as_of_issue": "approved_proposal_context_boundary",
            "legal_universe_fingerprint": stable_fingerprint(
                {"domain": "ssq_red_ball", "choose": "6_of_33", "size": 1_107_568}
            ),
            "objective_policy_version": context.current_objective_policy.version,
            "objective_policy_hash": context.current_objective_policy.policy_hash,
            "ranker_versions": [item["version"] for item in ranker_contract],
            "ranker_config_hashes": {item["key"]: item["config_hash"] for item in ranker_contract},
            "stage_order": list(STAGE_ORDER),
            "frozen_validation_required_before_forward": True,
            "success_conditions": list(SUCCESS_CONDITIONS),
            "failure_conditions": list(FAILURE_CONDITIONS),
            "promotion_allowed": False,
            "production_training_change_allowed": False,
            "reviewer_approval": {
                "status": reviewer_decision.get("new_status", "approved"),
                "decision_code": reviewer_decision.get("decision_code", "request_approved"),
                "decided_by": reviewer_decision.get("decided_by", "reviewer:unknown"),
            },
        }

    @staticmethod
    def _implementation_steps() -> tuple[ImplementationStep, ...]:
        return (
            ImplementationStep(
                key="freeze_ranker_outputs",
                order=1,
                actor_role="engineering",
                purpose="Build an isolated tool that snapshots fixed ranker outputs as of each issue.",
                required_interface={"output": "ranker_snapshots.json", "production_access": False},
                acceptance_criteria=("ranker list and config hashes match the plan", "no target result input"),
                non_goals=("change production rankers", "select rankers by observed performance"),
            ),
            ImplementationStep(
                key="compute_disagreement_features",
                order=2,
                actor_role="engineering",
                purpose="Compute preregistered disagreement features for every candidate and issue.",
                required_interface={"output": "disagreement_features.json"},
                acceptance_criteria=("all required features are present", "missing ranks fail the stage"),
                non_goals=("add unregistered features", "use post-draw updates"),
            ),
            ImplementationStep(
                key="build_matched_baselines",
                order=3,
                actor_role="engineering",
                purpose="Construct same-budget matched baselines for every disagreement stratum.",
                required_interface={"output": "matched_baselines.json"},
                acceptance_criteria=("candidate and baseline budgets match", "random seed is fixed"),
                non_goals=("drop failed strata", "weaken the baseline after results"),
            ),
            ImplementationStep(
                key="emit_stage_metrics",
                order=4,
                actor_role="engineering",
                purpose="Emit complete stage metrics without research conclusions.",
                required_interface={"output": "metrics_by_stage.json"},
                acceptance_criteria=("all strata and baselines are reported", "no Evidence row is written"),
                non_goals=("accept or reject the hypothesis", "promote a strategy"),
            ),
        )

    @staticmethod
    def _stages(plan_key: str, budgets: dict[str, int]) -> tuple[ExperimentStage, ...]:
        purposes = {
            "feasibility": "Confirm interfaces, ranker snapshots, and feature schemas can be produced in isolation.",
            "historical_search": "Derive disagreement strata thresholds from search-window ranker outputs only.",
            "frozen_validation": "Evaluate frozen thresholds on a disjoint frozen window before forward use.",
            "forward_validation": "Evaluate the frozen protocol on at least 20 future issues.",
            "decision_review": "Reviewer compares complete results without execution or promotion authority.",
        }
        windows = {
            "feasibility": {"kind": "schema_probe", "uses_target_results": False},
            "historical_search": {"kind": "search", "count": 100, "disjoint_from": ["frozen_validation", "forward_validation"]},
            "frozen_validation": {"kind": "frozen", "count": 20, "must_precede": "forward_validation"},
            "forward_validation": {"kind": "forward", "minimum_count": 20, "future_only": True},
            "decision_review": {"kind": "review", "uses_complete_artifacts": True},
        }
        return tuple(
            ExperimentStage(
                key=key,
                order=index + 1,
                purpose=purposes[key],
                input_window=windows[key],
                candidate_budget=int(budgets[key]),
                baseline_budget=int(budgets[key]),
                metrics=REQUIRED_METRICS,
                entry_conditions=_entry_conditions(key),
                success_conditions=SUCCESS_CONDITIONS,
                failure_conditions=FAILURE_CONDITIONS,
                artifact_paths=(f"data/output/research-planning/{plan_key}/{key}.json",),
                execution_environment="isolated",
            )
            for index, key in enumerate(STAGE_ORDER)
        )


def _entry_conditions(key: str) -> tuple[str, ...]:
    if key == "feasibility":
        return ("approved proposal is materialized and preregistered",)
    if key == "historical_search":
        return ("feasibility artifacts exist",)
    if key == "frozen_validation":
        return ("historical_search thresholds are frozen",)
    if key == "forward_validation":
        return ("frozen_validation completed before forward start",)
    return ("all executable stages have complete artifacts",)
