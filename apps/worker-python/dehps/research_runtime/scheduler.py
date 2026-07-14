from __future__ import annotations

from typing import Any

from dehps.research_runtime.models import HistorySnapshot
from dehps.research_runtime.queue import ContinuousResearchQueue
from dehps.research_scheduler.planner import ResearchSchedulePlanner


class ContinuousResearchScheduler:
    """Select research work without consulting forward readiness."""

    def __init__(
        self,
        *,
        planner: ResearchSchedulePlanner | None = None,
        queue: ContinuousResearchQueue | None = None,
    ) -> None:
        self.planner = planner or ResearchSchedulePlanner()
        self.queue = queue or ContinuousResearchQueue()

    def next_item(self, *, snapshot: HistorySnapshot) -> Any:
        state = self.planner.build_state()
        summary = dict(state.pattern_discovery or {})
        action = self._action_from_state(summary=summary, active_hypotheses=len(state.active_hypotheses))
        return self.queue.create_item(
            action=action,
            snapshot=snapshot,
            priority_score=self._priority(action),
            payload={
                "snapshot_key": snapshot.snapshot_key,
                "history_fingerprint": snapshot.history_fingerprint,
                "forward_gate_ignored_for_research": True,
                "pattern_discovery": summary,
                "active_hypotheses": len(state.active_hypotheses),
            },
        )

    @staticmethod
    def _action_from_state(*, summary: dict[str, Any], active_hypotheses: int) -> str:
        if int(summary.get("pattern_count") or 0) == 0:
            return "pattern_mining"
        if int(summary.get("screened_count") or 0) > 0 and int(summary.get("feature_count") or 0) == 0:
            return "feature_synthesis"
        if int(summary.get("feature_count") or 0) > 0 and int(summary.get("strategy_count") or 0) == 0:
            return "strategy_synthesis"
        if active_hypotheses > 0:
            return "evidence_aggregation"
        return "proposal_generation"

    @staticmethod
    def _priority(action: str) -> float:
        return {
            "pattern_mining": 0.74,
            "feature_synthesis": 0.72,
            "strategy_synthesis": 0.71,
            "evidence_aggregation": 0.76,
            "proposal_generation": 0.65,
        }.get(action, 0.5)
