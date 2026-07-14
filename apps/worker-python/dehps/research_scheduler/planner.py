from __future__ import annotations

from typing import Any

from dehps.research_autonomy.context import ResearchContext, ResearchContextBuilder
from dehps.research_scheduler.budget import BudgetManager, SchedulerBudget
from dehps.research_scheduler.repository import ResearchSchedulerRepository
from dehps.research_scheduler.state import (
    OpenAgentRequest,
    ResearchAction,
    SchedulerQueueItem,
    SchedulerState,
    TrainingStatusSnapshot,
)


ACTIVE_RESEARCH_STATUSES = frozenset(
    {"proposed", "preregistered", "running", "accepted_for_followup"}
)


class ResearchSchedulePlanner:
    def __init__(
        self,
        *,
        context_builder: ResearchContextBuilder | None = None,
        repository: ResearchSchedulerRepository | None = None,
    ) -> None:
        self.context_builder = context_builder or ResearchContextBuilder()
        self.repository = repository or ResearchSchedulerRepository()

    def build_context(self) -> ResearchContext:
        return self.context_builder.build()

    def build_state(self, context: ResearchContext | None = None) -> SchedulerState:
        context = context or self.build_context()
        latest_round = self.repository.latest_training_round() or {}
        active = tuple(
            item for item in context.active_hypotheses
            if str(getattr(item, "status", "")) in ACTIVE_RESEARCH_STATUSES
        )
        return SchedulerState(
            context_fingerprint=context.fingerprint,
            active_hypotheses=active,
            rejected_families=context.rejected_families,
            recent_experiments=context.recent_experiments,
            recent_evidence=context.recent_evidence,
            open_queue=tuple(self.repository.list_queue(open_only=True)),
            open_agent_requests=tuple(self.repository.open_agent_requests()),
            training_status=TrainingStatusSnapshot(
                latest_run_id=None if latest_round.get("run_id") is None else str(latest_round["run_id"]),
                latest_round_index=(
                    None if latest_round.get("round_index") is None else int(latest_round["round_index"])
                ),
                active=False,
                source_training_run_ids=context.source_training_run_ids,
                failure_count=len(context.training_failures),
                sequential_null_status=dict(context.sequential_null_status),
                forward_evidence_status={
                    "status": context.forward_evidence_status.status,
                    "protocol": context.forward_evidence_status.protocol,
                    "paired_issue_count": context.forward_evidence_status.paired_issue_count,
                    "min_paired_issues": context.forward_evidence_status.min_paired_issues,
                    "review_ready": context.forward_evidence_status.review_ready,
                    "promotion_eligible": context.forward_evidence_status.promotion_eligible,
                    "blockers": tuple(context.forward_evidence_status.blockers),
                },
            ),
        )

    def budget_manager(self, *, overrides: dict[str, Any] | None = None) -> BudgetManager:
        used_proposals = self.repository.count_queue_actions_today(ResearchAction.CREATE_PROPOSAL_REQUEST)
        used_experiments = (
            self.repository.count_queue_actions_today(ResearchAction.CREATE_ENGINEERING_REQUEST)
            + self.repository.count_queue_actions_today(ResearchAction.CREATE_OPERATOR_REQUEST)
        )
        used_forward = self.repository.count_queue_actions_today(ResearchAction.CREATE_OPERATOR_REQUEST)
        values = {
            "daily_experiments_used": used_experiments,
            "proposal_used": used_proposals,
            "forward_used": used_forward,
        }
        values.update(overrides or {})
        return BudgetManager(SchedulerBudget(**values))


def summarize_state(state: SchedulerState) -> dict[str, Any]:
    return {
        "context_fingerprint": state.context_fingerprint,
        "active_hypotheses": len(state.active_hypotheses),
        "rejected_families": len(state.rejected_families),
        "recent_experiments": len(state.recent_experiments),
        "recent_evidence": len(state.recent_evidence),
        "open_queue": len(state.open_queue),
        "open_agent_requests": len(state.open_agent_requests),
        "training": {
            "latest_run_id": state.training_status.latest_run_id,
            "latest_round_index": state.training_status.latest_round_index,
            "source_training_run_ids": list(state.training_status.source_training_run_ids),
            "failure_count": state.training_status.failure_count,
            "forward_evidence_status": state.training_status.forward_evidence_status,
        },
    }
