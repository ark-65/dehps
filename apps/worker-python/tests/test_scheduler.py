from datetime import datetime, timezone

from dehps.agents.requests import AgentRequest, AgentRequestStatus, AgentRequestType, AgentRiskLevel
from dehps.agents.roles import AgentRole
from dehps.research_scheduler.budget import BudgetManager, SchedulerBudget
from dehps.research_scheduler.scheduler import AutonomousResearchScheduler
from dehps.research_scheduler.state import (
    QueueStatus,
    ResearchAction,
    SchedulerQueueItem,
)
from test_priority import state


NOW = datetime(2026, 7, 14, tzinfo=timezone.utc)


class Repository:
    def __init__(self) -> None:
        self.queue: list[SchedulerQueueItem] = []

    def ensure_schema(self) -> None:
        return None

    def list_queue(self, *, limit=100, offset=0, open_only=False):
        items = [item for item in self.queue if (not open_only or item.is_open)]
        return items[offset: offset + limit]

    def latest_queue_item(self):
        return self.queue[-1] if self.queue else None

    def latest_training_round(self):
        return {"run_id": "run-1", "round_index": 1}

    def open_agent_requests(self, *, limit=100):
        return []

    def count_queue_actions_today(self, action=None):
        return sum(1 for item in self.queue if action is None or item.action == action)

    def upsert_queue_item(self, item):
        for existing in self.queue:
            if existing.queue_key == item.queue_key:
                return existing
            if (
                existing.is_open
                and existing.action == item.action
                and existing.target_hypothesis_key == item.target_hypothesis_key
                and existing.target_family_key == item.target_family_key
                and existing.target_experiment_key == item.target_experiment_key
            ):
                return existing
        self.queue.append(item)
        return item

    def attach_request(self, *, queue_key, request_key):
        for index, item in enumerate(self.queue):
            if item.queue_key == queue_key:
                updated = SchedulerQueueItem(**{**item.__dict__, "request_key": request_key})
                self.queue[index] = updated
                return updated
        raise AssertionError("missing queue")


class Planner:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def build_state(self):
        base = state(open_queue=tuple(self.repository.list_queue(open_only=True)))
        return base

    def budget_manager(self, *, overrides=None):
        return BudgetManager(SchedulerBudget(**(overrides or {})))


class AgentRepository:
    def ensure_schema(self):
        return None

    def get_request(self, request_key):
        raise AssertionError(f"unexpected conflict lookup: {request_key}")


class AgentService:
    def __init__(self) -> None:
        self.created: list[AgentRequest] = []

    def create_draft(self, **kwargs):
        request = AgentRequest(
            id=len(self.created) + 1,
            request_key=kwargs["request_key"],
            request_type=kwargs["request_type"],
            requested_by_role=kwargs["requested_by_role"],
            requested_by=kwargs["requested_by"],
            hypothesis_id=None,
            experiment_id=None,
            parent_request_id=None,
            title=kwargs["title"],
            summary=kwargs["summary"],
            payload=dict(kwargs["payload"]),
            status=AgentRequestStatus.DRAFT,
            risk_level=kwargs["risk_level"],
            requires_review=True,
            created_at=NOW,
            updated_at=NOW,
            submitted_at=None,
            resolved_at=None,
            metadata=dict(kwargs["metadata"]),
        )
        self.created.append(request)
        return request

    def submit(self, request_key, **kwargs):
        request = self.created[-1]
        submitted = AgentRequest(
            **{
                **request.__dict__,
                "status": AgentRequestStatus.SUBMITTED,
                "submitted_at": NOW,
            }
        )
        self.created[-1] = submitted
        return submitted


def test_scheduler_once_creates_one_submitted_research_scheduler_request() -> None:
    repository = Repository()
    agent_service = AgentService()
    scheduler = AutonomousResearchScheduler(
        repository=repository,  # type: ignore[arg-type]
        planner=Planner(repository),  # type: ignore[arg-type]
        agent_repository=AgentRepository(),  # type: ignore[arg-type]
        agent_service=agent_service,  # type: ignore[arg-type]
    )

    result = scheduler.once(requested_by="research:scheduler")

    assert result.action.action == ResearchAction.CREATE_PROPOSAL_REQUEST
    assert result.queue_item is not None
    assert result.queue_item.queue_status == QueueStatus.PROPOSAL
    assert result.request is not None
    assert result.request.request_type == AgentRequestType.RESEARCH_SCHEDULER_REQUEST
    assert result.request.status == AgentRequestStatus.SUBMITTED
    assert result.request.risk_level == AgentRiskLevel.LOW


def test_scheduler_does_not_create_duplicate_request_for_open_queue() -> None:
    repository = Repository()
    agent_service = AgentService()
    scheduler = AutonomousResearchScheduler(
        repository=repository,  # type: ignore[arg-type]
        planner=Planner(repository),  # type: ignore[arg-type]
        agent_repository=AgentRepository(),  # type: ignore[arg-type]
        agent_service=agent_service,  # type: ignore[arg-type]
    )

    first = scheduler.once(requested_by="research:scheduler")
    second = scheduler.once(requested_by="research:scheduler")

    assert first.request is not None
    assert second.action.action == ResearchAction.CONTINUE_EXISTING
    assert second.request is None
    assert len(agent_service.created) == 1
