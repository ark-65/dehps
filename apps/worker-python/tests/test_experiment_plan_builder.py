from experiment_plan_fixtures import APPROVAL, ranking_proposal
from dehps.research_planning.planner import ExperimentPlanner
from research_autonomy_fixtures import make_context


def test_planner_builds_deterministic_plan_for_same_proposal_and_version() -> None:
    context = make_context()
    proposal = ranking_proposal()
    planner = ExperimentPlanner(plan_version="test-plan-v1")

    first = planner.build(proposal, context, reviewer_decision=APPROVAL)
    second = planner.build(proposal, context, reviewer_decision=APPROVAL)

    assert first == second
    assert first.plan_fingerprint == second.plan_fingerprint
    assert first.plan_version == "test-plan-v1"
    assert first.proposal_fingerprint == proposal.content_hash


def test_planner_freezes_stage_order_rankers_and_disagreement_features() -> None:
    plan = ExperimentPlanner().build(ranking_proposal(), make_context(), reviewer_decision=APPROVAL)

    assert tuple(stage.key for stage in plan.experiment_stages) == (
        "feasibility",
        "historical_search",
        "frozen_validation",
        "forward_validation",
        "decision_review",
    )
    assert [ranker["key"] for ranker in plan.model_contract["rankers"]] == [
        "frequency_based_ranker",
        "structural_ranker",
        "omission_based_ranker",
    ]
    assert set(plan.feature_contract["disagreement_features"]) >= {
        "rank_mean",
        "rank_median",
        "rank_min",
        "rank_max",
        "rank_std",
        "rank_range",
        "pairwise_rank_gap",
        "ranker_order_entropy",
        "consensus_band",
        "disagreement_band",
    }
