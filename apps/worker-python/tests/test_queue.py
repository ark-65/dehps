from dehps.research_scheduler.queue import ResearchQueue
from dehps.research_scheduler.state import NextResearchAction, QueueStatus, ResearchAction, SchedulerQueueItem


def test_research_queue_detects_duplicate_open_action() -> None:
    existing = SchedulerQueueItem(
        queue_key="queue-1",
        queue_status=QueueStatus.PROPOSAL,
        action=ResearchAction.CREATE_PROPOSAL_REQUEST,
        priority_score=0.5,
        context_fingerprint="context",
        reason={},
        budget={},
        policy={},
    )
    action = NextResearchAction(
        action=ResearchAction.CREATE_PROPOSAL_REQUEST,
        queue_status=QueueStatus.PROPOSAL,
        summary="proposal",
        reason={},
        priority_score=0.5,
        context_fingerprint="context",
        budget={},
        policy={},
    )

    decision = ResearchQueue.duplicate_for((existing,), action)

    assert decision.duplicate is True
    assert decision.item == existing


def test_research_queue_completed_items_do_not_block_new_actions() -> None:
    existing = SchedulerQueueItem(
        queue_key="queue-1",
        queue_status=QueueStatus.COMPLETED,
        action=ResearchAction.CREATE_PROPOSAL_REQUEST,
        priority_score=0.5,
        context_fingerprint="context",
        reason={},
        budget={},
        policy={},
    )
    action = NextResearchAction(
        action=ResearchAction.CREATE_PROPOSAL_REQUEST,
        queue_status=QueueStatus.PROPOSAL,
        summary="proposal",
        reason={},
        priority_score=0.5,
        context_fingerprint="context",
        budget={},
        policy={},
    )

    decision = ResearchQueue.duplicate_for((existing,), action)

    assert decision.duplicate is False
