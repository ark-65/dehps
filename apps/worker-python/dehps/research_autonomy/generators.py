from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from dehps.research_autonomy.context import ResearchContext
from dehps.research_autonomy.proposal_models import HypothesisProposal


class ProposalGenerator(Protocol):
    def generate(self, context: ResearchContext) -> tuple[HypothesisProposal, ...]: ...


@dataclass(frozen=True)
class ProposalBlueprint:
    mechanism: str
    variant: str
    title: str
    scientific_question: str
    statement: str
    null_hypothesis: str
    minimal_non_null: str
    feature_keys: tuple[str, ...]
    model_keys: tuple[str, ...]
    baseline: str
    failure_rule: str
    expected_information_gain: float
    compute_cost: float
    implementation_cost: float
    confidence: float


class _BaseGenerator:
    blueprints: tuple[ProposalBlueprint, ...] = ()

    def generate(self, context: ResearchContext) -> tuple[HypothesisProposal, ...]:
        if context.data_boundary.status != "passed" or context.data_boundary.future_information_allowed:
            return ()
        available = {item.key for item in context.available_features}
        return tuple(
            self._proposal(blueprint, context)
            for blueprint in self.blueprints
            if set(blueprint.feature_keys).issubset(available)
        )

    @staticmethod
    def _proposal(blueprint: ProposalBlueprint, context: ResearchContext) -> HypothesisProposal:
        seed = f"{context.fingerprint}:{blueprint.mechanism}:{blueprint.variant}"
        suffix = sha256(seed.encode("utf-8")).hexdigest()[:12]
        search_issues = 80 if blueprint.variant.endswith("80") else 100
        return HypothesisProposal(
            proposal_key=f"auto-{blueprint.mechanism}-{suffix}",
            family_key=blueprint.mechanism,
            title=blueprint.title,
            scientific_question=blueprint.scientific_question,
            statement=blueprint.statement,
            mechanism=blueprint.mechanism,
            null_hypothesis=blueprint.null_hypothesis,
            minimal_non_null=blueprint.minimal_non_null,
            invariants=(
                "legal red-ball universe is all 6-of-33 combinations",
                "all features use only issue, draw_date, and red_numbers before the target issue",
                "candidate and baseline use identical history, compute budget, and ranking cutoffs",
                "search output cannot read frozen or forward outcomes",
                "selection_changed=false and promotion_allowed=false",
            ),
            input_boundary={
                "allowed_fields": list(context.data_boundary.training_fields),
                "forbidden_fields": ["target_red_numbers", "post_draw_metadata", "market_aggregates"],
                "as_of_rule": "all rows must precede the ranked target issue",
                "contains_future_information": False,
            },
            feature_contract={
                "feature_keys": list(blueprint.feature_keys),
                "frozen_before_evaluation": True,
                "single_declared_mechanism": blueprint.mechanism,
            },
            model_contract={
                "model_keys": list(blueprint.model_keys),
                "hyperparameter_search": "none_beyond_declared_variant",
                "random_seed_sweep": False,
                "epoch_sweep": False,
            },
            baseline_contract={
                "baseline_key": blueprint.baseline,
                "same_legal_universe": True,
                "same_history": True,
                "same_candidate_budget": True,
                "same_compute_budget": True,
            },
            metric_contract={
                "primary": "time_isolated_exact_target_rank",
                "required": ["top_100", "top_1000", "top_10000", "median_rank", "worst_rank", "rank_tail"],
                "legal_universe_size": 1107568,
                "betting_return_metric": False,
            },
            validation_protocol={
                "kind": "expanding_walk_forward",
                "random_split": False,
                "search_issue_count": search_issues,
                "frozen_issue_count": 20,
                "forward_min_paired_issues": 20,
                "search_frozen_overlap": 0,
                "search_uses_frozen_validation": False,
                "selection_uses_forward_outcomes": False,
                "variant": blueprint.variant,
            },
            failure_condition={
                "rule": blueprint.failure_rule,
                "reject_on_leakage": True,
                "reject_on_budget_mismatch": True,
                "reject_on_no_rank_tail_improvement": True,
                "prohibited_parameter_only_changes": [
                    "seed", "epochs", "depth", "nearby_weights", "same_history_search_rounds", "rename"
                ],
            },
            self_deception_risks=(
                "adaptive selection over the same history can create false lift",
                "Top-band hits are sparse and require sequential multiplicity accounting",
                "a frozen diagnostic is not independent forward evidence",
                "implementation success is not research Evidence",
            ),
            novelty_basis=(
                f"tests mechanism {blueprint.mechanism}",
                f"uses frozen variant {blueprint.variant}",
                "requires same-budget time-isolated comparison",
            ),
            differs_from_rejected_families=tuple(
                sorted(item.family_key for item in context.rejected_families)
            ),
            expected_information_gain=blueprint.expected_information_gain,
            estimated_compute_cost=blueprint.compute_cost,
            estimated_implementation_cost=blueprint.implementation_cost,
            risk_level="medium" if blueprint.compute_cost < 0.8 else "high",
            confidence=blueprint.confidence,
        )


class ResidualPersistenceProposalGenerator(_BaseGenerator):
    blueprints = tuple(
        ProposalBlueprint(
            mechanism="multivariate_residual_persistence",
            variant=f"fixed_residual_windows_{window}",
            title=f"Time-isolated multivariate residual persistence ({window})",
            scientific_question="Do jointly preregistered frequency, omission, and structural residuals persist beyond an additive baseline?",
            statement="A frozen vector of lagged residual signs improves time-isolated rank tails over the same-budget additive ranker.",
            null_hypothesis="Lagged multivariate residual signs do not improve exact target ranks or rank tails over the additive baseline.",
            minimal_non_null="The candidate improves one preregistered Top band and rank tail without degrading worst rank beyond tolerance on frozen and forward windows.",
            feature_keys=("frequency", "omission", "temporal_residual"),
            model_keys=("frequency_ranker",),
            baseline="same_budget_additive_frequency_ranker",
            failure_rule="reject if frozen and forward rank-tail deltas are non-positive or unstable across the two fixed windows",
            expected_information_gain=0.88,
            compute_cost=0.42,
            implementation_cost=0.48,
            confidence=0.62,
        )
        for window in (20, 80)
    )


class ModelDisagreementProposalGenerator(_BaseGenerator):
    blueprints = tuple(
        ProposalBlueprint(
            mechanism="ranking_model_disagreement",
            variant=f"rank_disagreement_{window}",
            title=f"Frozen ranking-model disagreement audit ({window})",
            scientific_question="Does outcome-blind rank disagreement identify a stable candidate-tail regime?",
            statement="A preregistered disagreement stratum between existing rankers has different time-isolated target-rank behavior from matched consensus strata.",
            null_hypothesis="Ranker disagreement strata have the same target-rank distribution as budget-matched consensus strata.",
            minimal_non_null="A fixed disagreement stratum changes rank-tail distribution in the same direction on frozen and forward windows.",
            feature_keys=("advisor_rank_disagreement", "candidate_rank_signature_diversity"),
            model_keys=("frequency_ranker", "ridge_kdj_adapter"),
            baseline="matched_rank_consensus_strata",
            failure_rule="reject if disagreement strata do not reproduce a preregistered rank-tail delta outside search",
            expected_information_gain=0.92,
            compute_cost=0.28,
            implementation_cost=0.31,
            confidence=0.68,
        )
        for window in (20, 80)
    )


class RegimeShiftProposalGenerator(_BaseGenerator):
    blueprints = tuple(
        ProposalBlueprint(
            mechanism="regime_change_detection",
            variant=f"fixed_change_point_{window}",
            title=f"Frozen structural regime change detector ({window})",
            scientific_question="Can a fixed change-point rule distinguish stable distribution shifts without target leakage?",
            statement="A frozen change-point rule over pre-target structural distributions improves conditional ranking calibration over a stationary baseline.",
            null_hypothesis="The fixed change-point rule provides no time-isolated rank calibration improvement over a stationary baseline.",
            minimal_non_null="Detected regimes reproduce a preregistered calibration and rank-tail delta on frozen and forward issues.",
            feature_keys=("history_regime", "span_trend", "sum_trend"),
            model_keys=("frequency_ranker",),
            baseline="stationary_same_window_ranker",
            failure_rule="reject if change points are unstable or conditional rank metrics fail outside the search interval",
            expected_information_gain=0.79,
            compute_cost=0.36,
            implementation_cost=0.55,
            confidence=0.54,
        )
        for window in (20, 80)
    )


class CooccurrenceGraphProposalGenerator(_BaseGenerator):
    blueprints = tuple(
        ProposalBlueprint(
            mechanism="cooccurrence_graph_drift",
            variant=f"graph_lag_{window}",
            title=f"Time-isolated co-occurrence graph drift ({window})",
            scientific_question="Does pre-target graph drift contain rank information beyond marginal frequency?",
            statement="Frozen graph-drift residuals improve target-rank tails over marginal-frequency controls.",
            null_hypothesis="Graph-drift residuals add no time-isolated rank information beyond marginal frequency.",
            minimal_non_null="Graph residuals improve a preregistered rank-tail metric without Top-band or worst-rank regression.",
            feature_keys=("cooccurrence_graph_drift", "frequency"),
            model_keys=("frequency_ranker",),
            baseline="marginal_frequency_same_budget",
            failure_rule="reject if graph residual effects disappear after marginal-frequency matching",
            expected_information_gain=0.83,
            compute_cost=0.71,
            implementation_cost=0.82,
            confidence=0.49,
        )
        for window in (20, 80)
    )


class CandidateDensityProposalGenerator(_BaseGenerator):
    blueprints = tuple(
        ProposalBlueprint(
            mechanism="candidate_space_density_shift",
            variant=f"density_signature_{window}",
            title=f"Candidate rank-signature density shift ({window})",
            scientific_question="Does local candidate density diagnose decision-surface fragility without using outcomes?",
            statement="A frozen local rank-signature density statistic predicts rank instability relative to a matched-density baseline.",
            null_hypothesis="Candidate density strata do not differ in time-isolated target-rank stability.",
            minimal_non_null="A fixed density stratum reproduces a target-rank tail difference on frozen and forward data.",
            feature_keys=("candidate_rank_signature_diversity",),
            model_keys=("frequency_ranker",),
            baseline="matched_candidate_density_quantiles",
            failure_rule="reject if density strata do not reproduce or only reflect objective tie-breaking",
            expected_information_gain=0.86,
            compute_cost=0.24,
            implementation_cost=0.38,
            confidence=0.64,
        )
        for window in (20, 80)
    )


class MultiScaleTemporalProposalGenerator(_BaseGenerator):
    blueprints = tuple(
        ProposalBlueprint(
            mechanism="multi_scale_frequency_residual",
            variant=f"fixed_scales_{window}",
            title=f"Multi-scale frequency residual consistency ({window})",
            scientific_question="Do fixed short/medium/long frequency residuals agree outside the search window?",
            statement="Agreement across preregistered frequency scales improves time-isolated rank tails over one-scale frequency.",
            null_hypothesis="Multi-scale frequency agreement adds no rank information beyond the same-budget single-scale baseline.",
            minimal_non_null="Scale agreement improves one Top band and rank-tail stability on frozen and forward windows.",
            feature_keys=("frequency", "short_hot_frequency", "temporal_residual"),
            model_keys=("frequency_ranker",),
            baseline="single_scale_frequency_same_budget",
            failure_rule="reject if scale agreement fails to outperform the best frozen single scale without tail regression",
            expected_information_gain=0.74,
            compute_cost=0.32,
            implementation_cost=0.44,
            confidence=0.57,
        )
        for window in (20, 80)
    )


DEFAULT_GENERATORS: tuple[ProposalGenerator, ...] = (
    ResidualPersistenceProposalGenerator(),
    ModelDisagreementProposalGenerator(),
    RegimeShiftProposalGenerator(),
    CooccurrenceGraphProposalGenerator(),
    CandidateDensityProposalGenerator(),
    MultiScaleTemporalProposalGenerator(),
)
