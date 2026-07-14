from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dehps.agents.errors import AgentAuthorityError, AgentRequestConflictError
from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequest, AgentRequestStatus, AgentRequestType, AgentRiskLevel
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService
from dehps.research_scheduler.planner import ResearchSchedulePlanner, summarize_state
from dehps.research_scheduler.priority import ResearchPriorityEngine
from dehps.research_scheduler.repository import ResearchSchedulerRepository
from dehps.research_scheduler.state import (
    NextResearchAction,
    ROUND26_SCHEMA_VERSION,
    ResearchAction,
    SchedulerQueueItem,
)


@dataclass(frozen=True)
class SchedulerOnceResult:
    action: NextResearchAction
    queue_item: SchedulerQueueItem | None
    request: AgentRequest | None
    created_request: bool
    submitted_request: bool
    state_summary: dict[str, Any]


class AutonomousResearchScheduler:
    def __init__(
        self,
        *,
        repository: ResearchSchedulerRepository | None = None,
        planner: ResearchSchedulePlanner | None = None,
        agent_repository: AgentRequestRepository | None = None,
        agent_service: AgentRequestService | None = None,
    ) -> None:
        self.repository = repository or ResearchSchedulerRepository()
        self.planner = planner or ResearchSchedulePlanner(repository=self.repository)
        self.agent_repository = agent_repository or AgentRequestRepository()
        self.agent_service = agent_service or AgentRequestService(self.agent_repository)

    def ensure_schema(self) -> None:
        self.repository.ensure_schema()
        self.agent_repository.ensure_schema()

    def next_action(self, *, budget: dict[str, Any] | None = None) -> dict[str, Any]:
        self.ensure_schema()
        state = self.planner.build_state()
        manager = self.planner.budget_manager(overrides=budget)
        action = ResearchPriorityEngine(budget_manager=manager).next_action(state)
        return {"action": action, "state": summarize_state(state), "writes": []}

    def status(self) -> dict[str, Any]:
        self.ensure_schema()
        state = self.planner.build_state()
        latest = self.repository.latest_queue_item()
        return {
            "schema_version": ROUND26_SCHEMA_VERSION,
            "write_routes_enabled": False,
            "state": summarize_state(state),
            "latest_queue_item": latest,
            "open_queue": list(state.open_queue),
            "open_agent_requests": list(state.open_agent_requests),
        }

    def queue(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        self.ensure_schema()
        return {
            "entity": "research_scheduler_queue",
            "items": self.repository.list_queue(limit=limit, offset=offset),
            "limit": limit,
            "offset": offset,
        }

    def once(
        self,
        *,
        requested_by: str = "research:scheduler",
        budget: dict[str, Any] | None = None,
        create_request: bool = True,
    ) -> SchedulerOnceResult:
        self.ensure_schema()
        state = self.planner.build_state()
        manager = self.planner.budget_manager(overrides=budget)
        action = ResearchPriorityEngine(budget_manager=manager).next_action(state)
        state_summary = summarize_state(state)
        if action.action == ResearchAction.CONTINUE_EXISTING:
            queue_item = self._existing_queue(action.existing_queue_key)
            return SchedulerOnceResult(
                action=action,
                queue_item=queue_item,
                request=None,
                created_request=False,
                submitted_request=False,
                state_summary=state_summary,
            )

        queue_item = self.repository.upsert_queue_item(action.queue_item(created_by=requested_by))
        if not action.creates_request or not create_request:
            return SchedulerOnceResult(
                action=action,
                queue_item=queue_item,
                request=None,
                created_request=False,
                submitted_request=False,
                state_summary=state_summary,
            )

        request, created, submitted = self._create_scheduler_request(
            action,
            queue_item=queue_item,
            requested_by=requested_by,
            state_summary=state_summary,
        )
        queue_item = self.repository.attach_request(
            queue_key=queue_item.queue_key,
            request_key=request.request_key,
        )
        return SchedulerOnceResult(
            action=action,
            queue_item=queue_item,
            request=request,
            created_request=created,
            submitted_request=submitted,
            state_summary=state_summary,
        )

    def run(
        self,
        *,
        requested_by: str = "research:scheduler",
        max_iterations: int = 1,
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if max_iterations < 1 or max_iterations > 10:
            raise AgentAuthorityError("max_iterations must be between 1 and 10")
        results: list[SchedulerOnceResult] = []
        for _ in range(max_iterations):
            result = self.once(requested_by=requested_by, budget=budget)
            results.append(result)
            if result.action.action in {
                ResearchAction.WAIT_FORWARD,
                ResearchAction.BLOCK,
                ResearchAction.STOP,
                ResearchAction.CONTINUE_EXISTING,
            }:
                break
        return {"iterations": len(results), "results": results}

    def _create_scheduler_request(
        self,
        action: NextResearchAction,
        *,
        queue_item: SchedulerQueueItem,
        requested_by: str,
        state_summary: dict[str, Any],
    ) -> tuple[AgentRequest, bool, bool]:
        payload = {
            **action.payload(),
            "queue_key": queue_item.queue_key,
            "state_summary": state_summary,
        }
        created = False
        try:
            request = self.agent_service.create_draft(
                request_key=action.request_key,
                request_type=AgentRequestType.RESEARCH_SCHEDULER_REQUEST,
                requested_by_role=AgentRole.RESEARCH,
                requested_by=requested_by,
                title=f"Schedule next research action: {action.action.value}",
                summary=action.summary,
                payload=payload,
                environment="isolated",
                risk_level=AgentRiskLevel.LOW,
                hypothesis_key=action.target_hypothesis_key,
                metadata={
                    "schema_version": ROUND26_SCHEMA_VERSION,
                    "queue_key": queue_item.queue_key,
                    "scheduler_action": action.action.value,
                    "context_fingerprint": action.context_fingerprint,
                },
            )
            created = True
        except AgentRequestConflictError:
            request = self.agent_repository.get_request(action.request_key)
            if request.payload != payload:
                raise
        submitted = False
        if request.status == AgentRequestStatus.DRAFT:
            request = self.agent_service.submit(
                request.request_key,
                actor_role=AgentRole.RESEARCH,
                actor_id=requested_by,
                environment="isolated",
            )
            submitted = True
        return request, created, submitted

    def _existing_queue(self, queue_key: str | None) -> SchedulerQueueItem | None:
        if not queue_key:
            return None
        for item in self.repository.list_queue(limit=500):
            if item.queue_key == queue_key:
                return item
        return None
