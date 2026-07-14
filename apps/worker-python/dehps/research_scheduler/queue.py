from __future__ import annotations

from dataclasses import dataclass

from dehps.research_scheduler.state import (
    OPEN_QUEUE_STATUSES,
    NextResearchAction,
    QueueStatus,
    ResearchAction,
    SchedulerQueueItem,
)


@dataclass(frozen=True)
class QueueDecision:
    duplicate: bool
    item: SchedulerQueueItem | None
    reason: str


class ResearchQueue:
    @staticmethod
    def open_items(items: list[SchedulerQueueItem] | tuple[SchedulerQueueItem, ...]) -> tuple[SchedulerQueueItem, ...]:
        return tuple(item for item in items if item.queue_status in OPEN_QUEUE_STATUSES)

    @staticmethod
    def duplicate_for(
        items: list[SchedulerQueueItem] | tuple[SchedulerQueueItem, ...],
        action: NextResearchAction,
    ) -> QueueDecision:
        for item in ResearchQueue.open_items(items):
            if (
                item.action == action.action
                and item.target_hypothesis_key == action.target_hypothesis_key
                and item.target_family_key == action.target_family_key
                and item.target_experiment_key == action.target_experiment_key
            ):
                return QueueDecision(True, item, "open queue item already covers this action")
        return QueueDecision(False, None, "no duplicate open queue item")

    @staticmethod
    def terminal(status: QueueStatus) -> bool:
        return status in {QueueStatus.COMPLETED, QueueStatus.BLOCKED}

    @staticmethod
    def status_for_action(action: ResearchAction) -> QueueStatus:
        return {
            ResearchAction.CREATE_PROPOSAL_REQUEST: QueueStatus.PROPOSAL,
            ResearchAction.CREATE_PLANNING_REQUEST: QueueStatus.PLANNING,
            ResearchAction.CREATE_ENGINEERING_REQUEST: QueueStatus.ENGINEERING,
            ResearchAction.CREATE_OPERATOR_REQUEST: QueueStatus.OPERATOR,
            ResearchAction.CREATE_REVIEW_REQUEST: QueueStatus.REVIEW,
            ResearchAction.WAIT_FORWARD: QueueStatus.WAITING_FORWARD,
            ResearchAction.BLOCK: QueueStatus.BLOCKED,
            ResearchAction.STOP: QueueStatus.BLOCKED,
            ResearchAction.CONTINUE_EXISTING: QueueStatus.PLANNING,
        }[action]
