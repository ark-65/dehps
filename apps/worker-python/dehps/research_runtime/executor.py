from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Callable, Protocol

from dehps.agents.requests import AgentRequestStatus, AgentRequestType
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

        repository_before = (self.service.status().get("repository") or {}).copy()
        durable_cycle_index = int(repository_before.get("cycle_count") or budget.cycles_used)
        history = tuple(self.service.repository.load_history())
        max_workers = min(max(1, int(budget.research_cpu)), len(history) or 1, 16)
        lanes = _build_pattern_lanes(
            history=history,
            action=item.action,
            max_lanes=max_workers,
            budget=budget,
            cycle_index=durable_cycle_index,
        )
        lane_results = self._execute_lanes(lanes, max_workers=max_workers)
        persisted = self._persist_lanes(lanes=lanes, action=item.action)
        status = self.service.status()
        repository_after = status.get("repository", {})
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
            "persisted": persisted,
            "repository": repository_after,
            "repository_delta": _repository_delta(repository_before, repository_after),
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

    def _persist_lanes(self, *, lanes: tuple[dict[str, Any], ...], action: str) -> dict[str, Any]:
        if not lanes:
            return {"persisted": False, "reason_code": "no_research_lanes"}
        proposal_open = self._open_pattern_proposal_exists() if action == "proposal_generation" else True
        persisted_lanes: list[dict[str, Any]] = []
        submitted_request_key: str | None = None
        writes_count = 0
        for lane in lanes:
            submit = bool(lane.get("submit")) and not proposal_open and submitted_request_key is None
            cycle = self.service.cycle(
                draws=lane["draws"],
                budget=PatternSearchBudget(**dict(lane["budget"])),
                persist=True,
                submit=submit,
                requested_by="research:resident-runtime",
            )
            if cycle.submitted_request_key:
                submitted_request_key = cycle.submitted_request_key
                proposal_open = True
            writes_count += len(cycle.writes)
            persisted_lanes.append(
                {
                    "persisted": True,
                    "reason_code": "pattern_lane_persisted",
                    "lane_key": lane["lane_key"],
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
            )
        return {
            "persisted": True,
            "reason_code": "pattern_lanes_persisted_serially",
            "persisted_lane_count": len(persisted_lanes),
            "submitted_request_key": submitted_request_key,
            "writes_count": writes_count,
            "proposal_submission_skipped": submitted_request_key is None,
            "proposal_skip_reason": "open_pattern_proposal_exists" if submitted_request_key is None else None,
            "lanes": tuple(persisted_lanes),
        }

    def _open_pattern_proposal_exists(self) -> bool:
        repository = getattr(self.service, "agent_repository", None)
        if repository is None:
            return False
        try:
            repository.ensure_schema()
            for status in (
                AgentRequestStatus.SUBMITTED,
                AgentRequestStatus.UNDER_REVIEW,
                AgentRequestStatus.APPROVED,
                AgentRequestStatus.EXECUTING,
            ):
                if repository.list_requests(
                    status=status,
                    request_type=AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL,
                    limit=1,
                ):
                    return True
        except Exception:
            return True
        return False


def _build_pattern_lanes(
    *,
    history: tuple[DrawRecord, ...],
    action: str,
    max_lanes: int,
    budget: ResearchRuntimeBudget,
    cycle_index: int | None = None,
) -> tuple[dict[str, Any], ...]:
    if not history:
        return ()
    cycle_index = max(0, int(budget.cycles_used if cycle_index is None else cycle_index))
    window_sizes = (
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
        45,
        30,
    )
    lanes: list[dict[str, Any]] = []
    seen_ranges: set[tuple[str, str]] = set()
    lane_memory = min(20, max(1, int(budget.research_memory_gb) // max(1, max_lanes)))
    candidates: list[tuple[str, tuple[DrawRecord, ...]]] = []
    if cycle_index % 12 == 0:
        candidates.append(("full-history", history))
    for lane_index in range(max_lanes * 3):
        window = min(len(history), window_sizes[(cycle_index + lane_index) % len(window_sizes)])
        max_offset = max(0, len(history) - window)
        if max_offset:
            step = max(1, window // 3)
            offset = ((cycle_index * max_lanes + lane_index) * step) % (max_offset + 1)
        else:
            offset = 0
        end = len(history) - offset
        start = max(0, end - window)
        draws = history[start:end]
        if len(draws) < 30:
            continue
        issue_range = (str(draws[0][0]), str(draws[-1][0]))
        if issue_range in seen_ranges:
            continue
        seen_ranges.add(issue_range)
        lane_key = f"window-{len(draws)}-{issue_range[0]}-{issue_range[1]}"
        candidates.append((lane_key, draws))
        if len(candidates) >= max_lanes:
            break
    submit_index = cycle_index % max(1, min(max_lanes, len(candidates)))
    for index, (lane_key, draws) in enumerate(candidates[:max_lanes]):
        lanes.append(
            {
                "lane_key": lane_key,
                "draws": draws,
                "submit": action == "proposal_generation" and index == submit_index,
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


def _repository_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    keys = (
        "pattern_count",
        "discovered_count",
        "screened_count",
        "frozen_supported_count",
        "rejected_count",
        "feature_count",
        "strategy_count",
        "observation_count",
        "validation_count",
        "cycle_count",
    )
    return {
        key: int(after.get(key) or 0) - int(before.get(key) or 0)
        for key in keys
    }
