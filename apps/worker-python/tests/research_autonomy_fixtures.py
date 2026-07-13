from dataclasses import replace

from dehps.research_autonomy.context import (
    CandidateSourcePerformance,
    DataBoundarySummary,
    ForwardEvidenceStatus,
    HypothesisFamilySummary,
    HypothesisSummary,
    ModelDescriptor,
    ObjectivePolicySummary,
    ResearchContext,
    TrainingFailureSummary,
)
from dehps.research_autonomy.feature_catalog import FeatureCatalog
from dehps.research_autonomy.generators import ResidualPersistenceProposalGenerator


def rejected_hypothesis(mechanism: str = "generic_structural_mlp") -> HypothesisSummary:
    return HypothesisSummary(
        hypothesis_key="rejected-1", family_key="rejected-family", title="Rejected",
        mechanism=mechanism, status="rejected", input_fields=("issue", "draw_date", "red_numbers"),
        feature_keys=("structural",), model_keys=("neural_kdj_adapter",),
        validation_protocol="expanding_walk_forward", rejection_scope="parameter_region",
        rejection_reason="frozen audit failed", reopen_condition="new feature family",
    )


def rejected_family(mechanism: str = "generic_structural_mlp") -> HypothesisFamilySummary:
    return HypothesisFamilySummary(
        family_key="rejected-family", title="Generic structural MLP", mechanism=mechanism,
        status="partially_rejected", rejection_scope="parameter_region",
        rejection_reason="frozen audit failed", reopen_condition="new feature family",
    )


def make_context(*, rejected: bool = False, boundary_status: str = "passed") -> ResearchContext:
    rejected_hypotheses = (rejected_hypothesis(),) if rejected else ()
    rejected_families = (rejected_family(),) if rejected else ()
    return ResearchContext(
        active_hypotheses=(), rejected_hypotheses=rejected_hypotheses,
        rejected_families=rejected_families, recent_experiments=(), recent_evidence=(),
        training_failures=(TrainingFailureSummary(
            key="search_geometry", status="stalled", cause="same-history repeat",
            recovery="new preregistered mechanism", run_id="run-1", evidence={"repeat": 5},
        ),),
        candidate_source_performance=(CandidateSourcePerformance(
            source_key="normal", state="productive", generated=10, prefilter_selected=5,
            full_eval_top5=2, round_best_rounds=1, frozen_frontier_rounds=0,
            search_navigation_rounds=0,
        ),),
        current_objective_policy=ObjectivePolicySummary(
            version="rank_objective_v1", policy_hash="hash",
            metric_keys=("top_100", "top_1000", "top_10000", "rank_tail"),
        ),
        available_features=FeatureCatalog().build(rejected_hypotheses, rejected_families),
        available_models=(
            ModelDescriptor("frequency_ranker", "ranker", "models/frequency_ranker.py", (), "implemented"),
            ModelDescriptor("ridge_kdj_adapter", "advisor", "advisors/ridge_kdj_adapter.py", (), "implemented"),
        ),
        forward_evidence_status=ForwardEvidenceStatus(
            status="accumulating", protocol="forward-v1", paired_issue_count=1,
            min_paired_issues=20, review_ready=False, promotion_eligible=False,
            blockers=("insufficient",),
        ),
        data_boundary=DataBoundarySummary(
            protocol="boundary-v1", status=boundary_status,
            training_fields=("issue", "draw_date", "red_numbers"), excluded_fields=(),
            future_information_allowed=False, ticket_distribution_observed=False,
        ),
        sequential_null_status={"status": "noise_risk", "automatic_promotion_allowed": False},
        frozen_validation_status={"selection_uses_frozen_validation": False},
        source_training_run_ids=("run-1",),
        formal_source_paths=("training-watch-latest.json", "stall-diagnosis-latest.json"),
    )


def make_proposal(context: ResearchContext | None = None):
    value = context or make_context()
    return ResidualPersistenceProposalGenerator().generate(value)[0]
