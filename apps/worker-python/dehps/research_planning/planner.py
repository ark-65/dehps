from __future__ import annotations

from typing import Any

from dehps.research_autonomy.context import ResearchContext
from dehps.research_autonomy.proposal_models import HypothesisProposal
from dehps.research_planning.models import ExperimentPlan
from dehps.research_planning.protocol_builder import RankingDisagreementProtocolBuilder


DEFAULT_PLANNER_VERSION = "autonomous-experiment-planner-v1"


class ExperimentPlanner:
    def __init__(
        self,
        *,
        plan_version: str = DEFAULT_PLANNER_VERSION,
        ranking_disagreement_builder: RankingDisagreementProtocolBuilder | None = None,
    ) -> None:
        self.plan_version = plan_version
        self.ranking_disagreement_builder = (
            ranking_disagreement_builder or RankingDisagreementProtocolBuilder()
        )

    def build(
        self,
        proposal: HypothesisProposal,
        context: ResearchContext,
        *,
        reviewer_decision: dict[str, Any] | None = None,
    ) -> ExperimentPlan:
        if proposal.mechanism == "ranking_model_disagreement":
            return self.ranking_disagreement_builder.build(
                proposal,
                context,
                plan_version=self.plan_version,
                reviewer_decision=reviewer_decision,
            )
        raise ValueError(f"no experiment protocol is registered for {proposal.mechanism}")
