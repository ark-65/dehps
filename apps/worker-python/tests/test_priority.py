from dehps.research_scheduler.budget import BudgetManager, SchedulerBudget
from dehps.research_scheduler.priority import ResearchPriorityEngine
from dehps.research_scheduler.state import (
    OpenAgentRequest,
    QueueStatus,
    ResearchAction,
    SchedulerState,
    TrainingStatusSnapshot,
)


def state(
    *,
    forward_ready: bool = True,
    active_hypotheses=(),
    open_queue=(),
    open_requests=(),
) -> SchedulerState:
    return SchedulerState(
        context_fingerprint="context",
        active_hypotheses=tuple(active_hypotheses),
        rejected_families=(),
        recent_experiments=(),
        recent_evidence=(),
        open_queue=tuple(open_queue),
        open_agent_requests=tuple(open_requests),
        training_status=TrainingStatusSnapshot(
            latest_run_id="run-1",
            latest_round_index=1,
            active=False,
            source_training_run_ids=("run-1",),
            failure_count=0,
            sequential_null_status={},
            forward_evidence_status={
                "paired_issue_count": 20 if forward_ready else 0,
                "min_paired_issues": 20,
                "review_ready": forward_ready,
                "blockers": [] if forward_ready else ["incomplete_forward_pairs"],
            },
        ),
    )


def test_priority_waits_when_forward_evidence_is_not_ready() -> None:
    action = ResearchPriorityEngine().next_action(state(forward_ready=False))

    assert action.action == ResearchAction.WAIT_FORWARD
    assert action.queue_status == QueueStatus.WAITING_FORWARD
    assert action.creates_request is False


def test_priority_creates_proposal_when_forward_ready_and_no_active_work() -> None:
    action = ResearchPriorityEngine().next_action(state(forward_ready=True))

    assert action.action == ResearchAction.CREATE_PROPOSAL_REQUEST
    assert action.queue_status == QueueStatus.PROPOSAL
    assert action.creates_request is True


def test_priority_stops_when_budget_is_exhausted() -> None:
    manager = BudgetManager(
        SchedulerBudget(
            daily_experiment_limit=1,
            daily_experiments_used=1,
            proposal_quota=1,
            proposal_used=1,
            forward_quota=1,
            forward_used=1,
        )
    )

    action = ResearchPriorityEngine(budget_manager=manager).next_action(state(forward_ready=True))

    assert action.action == ResearchAction.STOP
    assert action.queue_status == QueueStatus.BLOCKED


def test_priority_waits_for_open_agent_request_before_new_work() -> None:
    request = OpenAgentRequest(
        request_key="research-scheduler-open",
        request_type="research_scheduler_request",
        status="submitted",
        requested_by_role="research",
        requested_by="research:scheduler",
        title="open",
    )

    action = ResearchPriorityEngine().next_action(state(open_requests=(request,)))

    assert action.action == ResearchAction.WAIT_FORWARD
    assert action.reason["reason_code"] == "open_agent_request"
