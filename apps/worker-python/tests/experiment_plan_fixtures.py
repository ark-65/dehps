from __future__ import annotations

from dataclasses import asdict

from dehps.research_autonomy.generators import ModelDisagreementProposalGenerator
from dehps.research_autonomy.proposal_models import HypothesisProposal
from dehps.research_planning.models import ExperimentPlan
from dehps.research_planning.planner import ExperimentPlanner
from research_autonomy_fixtures import make_context


APPROVAL = {
    "previous_status": "under_review",
    "new_status": "approved",
    "decision_code": "request_approved",
    "summary": "approved for preregistration planning",
    "reason": {"review": "round23 fixture"},
    "decided_by_role": "reviewer",
    "decided_by": "reviewer:test",
    "decided_at": "2026-07-13T00:00:00+00:00",
}


def ranking_proposal() -> HypothesisProposal:
    return ModelDisagreementProposalGenerator().generate(make_context())[0]


def ranking_plan() -> ExperimentPlan:
    return ExperimentPlanner().build(
        ranking_proposal(),
        make_context(),
        reviewer_decision=APPROVAL,
    )


def plan_payload() -> dict:
    return asdict(ranking_plan())
