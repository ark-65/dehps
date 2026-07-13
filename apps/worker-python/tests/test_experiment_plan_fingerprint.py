from dataclasses import replace

from experiment_plan_fixtures import APPROVAL, ranking_proposal
from dehps.research_planning.planner import ExperimentPlanner
from research_autonomy_fixtures import make_context


def test_plan_fingerprint_repeats_for_same_proposal_and_planner_version() -> None:
    proposal = ranking_proposal()
    context = make_context()

    first = ExperimentPlanner(plan_version="planner-v").build(proposal, context, reviewer_decision=APPROVAL)
    second = ExperimentPlanner(plan_version="planner-v").build(proposal, context, reviewer_decision=APPROVAL)

    assert first.plan_fingerprint == second.plan_fingerprint


def test_recomputed_fingerprint_detects_plan_tampering() -> None:
    plan = ranking_plan = ExperimentPlanner().build(
        ranking_proposal(),
        make_context(),
        reviewer_decision=APPROVAL,
    )
    tampered = replace(ranking_plan, minimal_non_null="changed")

    assert tampered.recomputed_fingerprint != plan.plan_fingerprint
