from dehps.research_scheduler.priority import ResearchPriorityEngine
from dehps.research_scheduler.state import QueueStatus, ResearchAction
from test_priority import state


def with_pattern_summary(summary: dict):
    base = state(forward_ready=True)
    return type(base)(**{**base.__dict__, "pattern_discovery": {"enabled": True, **summary}})


def test_scheduler_discovers_patterns_when_pattern_memory_is_empty() -> None:
    action = ResearchPriorityEngine().next_action(with_pattern_summary({"pattern_count": 0}))

    assert action.action == ResearchAction.DISCOVER_PATTERNS
    assert action.queue_status == QueueStatus.PROPOSAL


def test_scheduler_waits_instead_of_random_proposal_when_no_valid_pattern_action() -> None:
    action = ResearchPriorityEngine().next_action(
        with_pattern_summary({"pattern_count": 3, "discovered_count": 0, "screened_count": 0})
    )

    assert action.action == ResearchAction.WAIT_FORWARD_PATTERN
    assert action.creates_request is False


def test_scheduler_submits_pattern_hypothesis_when_strategy_exists() -> None:
    action = ResearchPriorityEngine().next_action(
        with_pattern_summary({"pattern_count": 3, "strategy_count": 1})
    )

    assert action.action == ResearchAction.SUBMIT_PATTERN_HYPOTHESIS
    assert action.creates_request is True
