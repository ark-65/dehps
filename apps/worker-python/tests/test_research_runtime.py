from types import SimpleNamespace

from dehps.research_runtime.models import EvidenceSource, HistorySnapshot, ResearchRuntimeBudget, ResearchRuntimeStatus
from dehps.research_runtime.runtime import ContinuousResearchRuntime
from dehps.research_runtime.scheduler import ContinuousResearchScheduler


class SnapshotManager:
    def __init__(self) -> None:
        self.snapshot = HistorySnapshot("snap-79", "2026079", 1, "fp-79")

    def current(self):
        return self.snapshot

    def rotation_decision(self, *, active_snapshot, cycle_running):
        from dehps.research_runtime.models import SnapshotRotationDecision

        return SnapshotRotationDecision(False, "snapshot_unchanged", "snap-79", "snap-79", "2026079", "2026079", False)


class Planner:
    def build_state(self):
        return SimpleNamespace(pattern_discovery={"enabled": True, "pattern_count": 0}, active_hypotheses=())


def test_continuous_research_runtime_creates_research_queue_item_without_forward_gate() -> None:
    runtime = ContinuousResearchRuntime(
        snapshot_manager=SnapshotManager(),  # type: ignore[arg-type]
        scheduler=ContinuousResearchScheduler(planner=Planner()),  # type: ignore[arg-type]
    )

    result = runtime.once()

    assert result.runtime_status == ResearchRuntimeStatus.RESEARCH_RUNNING
    assert result.snapshot.snapshot_key == "snap-79"
    assert result.queue_item is not None
    assert result.queue_item.action == "pattern_mining"
    assert result.queue_item.evidence_source == EvidenceSource.RESEARCH
    assert result.queue_item.payload["forward_gate_ignored_for_research"] is True


def test_continuous_research_runtime_reports_budget_exhausted_without_forward_state() -> None:
    runtime = ContinuousResearchRuntime(
        snapshot_manager=SnapshotManager(),  # type: ignore[arg-type]
        scheduler=ContinuousResearchScheduler(planner=Planner()),  # type: ignore[arg-type]
        budget=ResearchRuntimeBudget(daily_cycle_limit=1, cycles_used=1),
    )

    result = runtime.once()

    assert result.runtime_status == ResearchRuntimeStatus.RESEARCH_BUDGET_EXHAUSTED
    assert result.queue_item is None
