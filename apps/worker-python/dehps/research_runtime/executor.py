from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Callable, Protocol

from dehps.pattern_discovery.models import PatternSearchBudget
from dehps.pattern_discovery.service import PatternDiscoveryService
from dehps.research_runtime.models import HistorySnapshot, ResearchRuntimeBudget, ResearchRuntimeQueueItem


DrawRecord = tuple[str, tuple[int, ...]]
LaneRunner = Callable[[dict[str, Any]], dict[str, Any]]


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

    def __init__(
        self,
        service: PatternDiscoveryService | None = None,
        *,
        lane_runner: LaneRunner | None = None,
    ) -> None:
        self.service = service or PatternDiscoveryService()
        self.lane_runner = lane_runner

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

        history = tuple(self.service.repository.load_history())
        max_workers = min(max(1, int(budget.research_cpu)), len(history) or 1, 16)
        lanes = _build_pattern_lanes(
            history=history,
            action=item.action,
            max_lanes=max_workers,
            budget=budget,
        )
        lane_results = self._execute_lanes(lanes, max_workers=max_workers)
        persisted = self._persist_primary_lane(lanes=lanes, action=item.action)
        status = self.service.status()
        successful = [result for result in lane_results if result.get("executed")]
        return {
            "executed": True,
            "reason_code": "parallel_pattern_discovery_executed",
            "action": item.action,
            "snapshot_key": snapshot.snapshot_key,
            "parallel_lanes": len(lanes),
            "max_workers": max_workers,
            "lane_results": lane_results,
            "discovered_count": sum(int(result.get("discovered_count") or 0) for result in successful),
            "validation_count": sum(int(result.get("validation_count") or 0) for result in successful),
            "feature_count": sum(int(result.get("feature_count") or 0) for result in successful),
            "strategy_count": sum(int(result.get("strategy_count") or 0) for result in successful),
            "submitted_request_key": persisted.get("submitted_request_key"),
            "writes_count": persisted.get("writes_count", 0),
            "persisted_cycle": persisted,
            "repository": status.get("repository", {}),
            "production_access": False,
            "promotion_allowed_from_research": False,
        }

    def _execute_lanes(self, lanes: tuple[dict[str, Any], ...], *, max_workers: int) -> tuple[dict[str, Any], ...]:
        if not lanes:
            return ()
        if self.lane_runner is not None:
            return tuple(self.lane_runner(lane) for lane in lanes)
        if max_workers <= 1 or len(lanes) == 1:
            return tuple(_run_pattern_lane(lane) for lane in lanes)
        results: list[dict[str, Any]] = []
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_by_lane = {executor.submit(_run_pattern_lane, lane): lane for lane in lanes}
            for future in as_completed(future_by_lane):
                lane = future_by_lane[future]
                try:
                    results.append(future.result())
                except Exception as exc:  # keep the resident runtime alive and audit failed lanes.
                    results.append(
                        {
                            "executed": False,
                            "reason_code": "pattern_lane_failed",
                            "lane_key": lane.get("lane_key"),
                            "error": {"type": type(exc).__name__, "message": str(exc)},
                        }
                    )
        return tuple(sorted(results, key=lambda item: str(item.get("lane_key") or "")))

    def _persist_primary_lane(self, *, lanes: tuple[dict[str, Any], ...], action: str) -> dict[str, Any]:
        if not lanes:
            return {"persisted": False, "reason_code": "no_research_lanes"}
        primary = lanes[0]
        cycle = self.service.cycle(
            draws=primary["draws"],
            budget=PatternSearchBudget(**dict(primary["budget"])),
            persist=True,
            submit=action == "proposal_generation",
            requested_by="research:resident-runtime",
        )
        return {
            "persisted": True,
            "reason_code": "primary_pattern_lane_persisted",
            "lane_key": primary["lane_key"],
            "pattern_cycle_key": cycle.cycle_key,
            "pattern_cycle_status": cycle.status,
            "discovered_count": len(cycle.patterns),
            "validation_count": len(cycle.validations),
            "feature_count": len(cycle.features),
            "strategy_count": len(cycle.strategies),
            "submitted_request_key": cycle.submitted_request_key,
            "writes_count": len(cycle.writes),
            "search_issue_range": cycle.search_issue_range,
        }


def _build_pattern_lanes(
    *,
    history: tuple[DrawRecord, ...],
    action: str,
    max_lanes: int,
    budget: ResearchRuntimeBudget,
) -> tuple[dict[str, Any], ...]:
    if not history:
        return ()
    windows = (
        None,
        3200,
        2800,
        2400,
        2000,
        1600,
        1200,
        900,
        700,
        500,
        365,
        250,
        180,
        120,
        90,
        60,
    )
    lanes: list[dict[str, Any]] = []
    seen_ranges: set[tuple[str, str]] = set()
    lane_memory = min(20, max(1, int(budget.research_memory_gb) // max(1, max_lanes)))
    for window in windows:
        draws = history if window is None or window >= len(history) else history[-window:]
        if len(draws) < 30:
            continue
        issue_range = (str(draws[0][0]), str(draws[-1][0]))
        if issue_range in seen_ranges:
            continue
        seen_ranges.add(issue_range)
        lane_key = "full-history" if window is None or window >= len(history) else f"tail-{len(draws)}"
        lanes.append(
            {
                "lane_key": lane_key,
                "draws": draws,
                "submit": action == "proposal_generation" and not lanes,
                "requested_by": "research:resident-runtime",
                "budget": {
                    "families": 10,
                    "patterns_per_family": 20,
                    "feature_candidates": 50,
                    "strategy_candidates": 30,
                    "weight_candidates": 200,
                    "cpu_slots": 1,
                    "memory_gb": lane_memory,
                },
            }
        )
        if len(lanes) >= max_lanes:
            break
    return tuple(lanes)


def _run_pattern_lane(payload: dict[str, Any]) -> dict[str, Any]:
    service = PatternDiscoveryService()
    budget = PatternSearchBudget(**dict(payload["budget"]))
    cycle = service.cycle(
        draws=payload["draws"],
        budget=budget,
        persist=False,
        submit=False,
        requested_by=str(payload.get("requested_by") or "research:resident-runtime"),
    )
    return {
        "executed": True,
        "reason_code": "pattern_lane_dry_run_executed",
        "lane_key": payload["lane_key"],
        "pattern_cycle_key": cycle.cycle_key,
        "pattern_cycle_status": cycle.status,
        "discovered_count": len(cycle.patterns),
        "validation_count": len(cycle.validations),
        "feature_count": len(cycle.features),
        "strategy_count": len(cycle.strategies),
        "submitted_request_key": None,
        "writes_count": 0,
        "search_issue_range": cycle.search_issue_range,
    }
