from __future__ import annotations

from dehps.research_runtime.budget import RuntimeBudgetScheduler
from dehps.research_runtime.models import (
    HistorySnapshot,
    ResearchCycleResult,
    ResearchCycleStatus,
    ResearchRuntimeBudget,
    ResearchRuntimeStatus,
)
from dehps.research_runtime.scheduler import ContinuousResearchScheduler
from dehps.research_runtime.snapshot import HistorySnapshotManager


class ContinuousResearchRuntime:
    """Run research cycles against immutable history snapshots.

    This runtime deliberately has no forward-wait state. Forward validation is
    modeled by ``dehps.forward_runtime``.
    """

    def __init__(
        self,
        *,
        snapshot_manager: HistorySnapshotManager | None = None,
        scheduler: ContinuousResearchScheduler | None = None,
        budget: ResearchRuntimeBudget | None = None,
    ) -> None:
        self.snapshot_manager = snapshot_manager or HistorySnapshotManager()
        self.scheduler = scheduler or ContinuousResearchScheduler()
        self.budget = budget or ResearchRuntimeBudget()
        self.active_snapshot: HistorySnapshot | None = None

    def status(self) -> dict:
        snapshot = self.active_snapshot or self.snapshot_manager.current()
        decision = self.snapshot_manager.rotation_decision(active_snapshot=self.active_snapshot, cycle_running=False)
        budget = RuntimeBudgetScheduler(self.budget).authorize_research_cycle()
        return {
            "runtime": "continuous_research",
            "status": budget.status.value if not budget.allowed else ResearchRuntimeStatus.RESEARCH_RUNNING.value,
            "active_snapshot": snapshot,
            "rotation": decision,
            "budget": self.budget,
            "forward_wait_blocks_research": False,
        }

    def once(self, *, cycle_running: bool = False) -> ResearchCycleResult:
        if self.active_snapshot is None:
            self.active_snapshot = self.snapshot_manager.current()
        rotation = self.snapshot_manager.rotation_decision(
            active_snapshot=self.active_snapshot,
            cycle_running=cycle_running,
        )
        if rotation.rotate:
            self.active_snapshot = self.snapshot_manager.current()
        budget_decision = RuntimeBudgetScheduler(self.budget).authorize_research_cycle()
        if not budget_decision.allowed:
            return ResearchCycleResult(
                cycle_key=f"research-cycle-blocked-{self.active_snapshot.snapshot_key}",
                status=ResearchCycleStatus.FAILED,
                runtime_status=budget_decision.status,
                snapshot=self.active_snapshot,
                queue_item=None,
                scheduler_result=None,
                rotation=rotation,
                budget=self.budget,
                warnings=(budget_decision.reason_code,),
            )
        item = self.scheduler.next_item(snapshot=self.active_snapshot)
        return ResearchCycleResult(
            cycle_key=f"research-cycle-{item.queue_key}",
            status=ResearchCycleStatus.COMPLETED,
            runtime_status=ResearchRuntimeStatus.RESEARCH_RUNNING,
            snapshot=self.active_snapshot,
            queue_item=item,
            scheduler_result=item,
            rotation=rotation,
            budget=self.budget,
        )
