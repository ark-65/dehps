from __future__ import annotations

from typing import Any, Protocol

from dehps.pattern_discovery.models import PatternSearchBudget
from dehps.pattern_discovery.service import PatternDiscoveryService
from dehps.research_runtime.models import HistorySnapshot, ResearchRuntimeBudget, ResearchRuntimeQueueItem


class ResearchActionExecutor(Protocol):
    def execute(
        self,
        *,
        item: ResearchRuntimeQueueItem,
        snapshot: HistorySnapshot,
        budget: ResearchRuntimeBudget,
    ) -> dict[str, Any]:
        ...


class NoopResearchActionExecutor:
    def execute(
        self,
        *,
        item: ResearchRuntimeQueueItem,
        snapshot: HistorySnapshot,
        budget: ResearchRuntimeBudget,
    ) -> dict[str, Any]:
        return {
            "executed": False,
            "reason_code": "no_research_action_executor_configured",
            "action": item.action,
            "snapshot_key": snapshot.snapshot_key,
        }


class PatternDiscoveryActionExecutor:
    """Execute safe continuous-research actions without touching production.

    This executor deliberately routes only through the Round 28 pattern
    discovery service. It may persist research artifacts and submit low-risk
    Research Proposal Requests, but it does not run the legacy training
    supervisor, modify source code, execute production training, or promote
    research evidence.
    """

    _PATTERN_ACTIONS = frozenset(
        {
            "pattern_mining",
            "feature_synthesis",
            "strategy_synthesis",
            "proposal_generation",
        }
    )

    def __init__(self, service: PatternDiscoveryService | None = None) -> None:
        self.service = service or PatternDiscoveryService()

    def execute(
        self,
        *,
        item: ResearchRuntimeQueueItem,
        snapshot: HistorySnapshot,
        budget: ResearchRuntimeBudget,
    ) -> dict[str, Any]:
        if item.action not in self._PATTERN_ACTIONS:
            return {
                "executed": False,
                "reason_code": "research_action_not_wired_to_resident_executor",
                "action": item.action,
                "snapshot_key": snapshot.snapshot_key,
            }

        pattern_budget = PatternSearchBudget(
            cpu_slots=min(16, max(1, int(budget.research_cpu))),
            memory_gb=min(20, max(1, int(budget.research_memory_gb))),
        )
        cycle = self.service.cycle(
            budget=pattern_budget,
            persist=True,
            submit=item.action == "proposal_generation",
            requested_by="research:resident-runtime",
        )
        status = self.service.status()
        return {
            "executed": True,
            "reason_code": "pattern_discovery_cycle_executed",
            "action": item.action,
            "snapshot_key": snapshot.snapshot_key,
            "pattern_cycle_key": cycle.cycle_key,
            "pattern_cycle_status": cycle.status,
            "discovered_count": len(cycle.patterns),
            "validation_count": len(cycle.validations),
            "feature_count": len(cycle.features),
            "strategy_count": len(cycle.strategies),
            "submitted_request_key": cycle.submitted_request_key,
            "writes_count": len(cycle.writes),
            "repository": status.get("repository", {}),
            "production_access": False,
            "promotion_allowed_from_research": False,
        }
