from types import SimpleNamespace

from dehps.forward_runtime.models import ForwardRuntimeStatus
from dehps.forward_runtime.runtime import ForwardValidationRuntime
from dehps.forward_state.models import ForwardReconcileDecision
from dehps.research_runtime.models import HistorySnapshot, SnapshotRotationDecision
from dehps.research_runtime.runtime import ContinuousResearchRuntime
from dehps.research_runtime.scheduler import ContinuousResearchScheduler


class SnapshotManager:
    def current(self):
        return HistorySnapshot("snap-79", "2026079", 1, "fp-79")

    def rotation_decision(self, *, active_snapshot, cycle_running):
        return SnapshotRotationDecision(False, "snapshot_unchanged", "snap-79", "snap-79", "2026079", "2026079", False)


class Planner:
    def build_state(self):
        return SimpleNamespace(pattern_discovery={"enabled": True, "pattern_count": 0}, active_hypotheses=())


class Reconciler:
    def reconcile(self, *, event_key=None):
        return ForwardReconcileDecision(False, "no_pending_event", "2026080", None, 1, 1, None)


def test_research_and_forward_runtimes_have_independent_states() -> None:
    research = ContinuousResearchRuntime(
        snapshot_manager=SnapshotManager(),  # type: ignore[arg-type]
        scheduler=ContinuousResearchScheduler(planner=Planner()),  # type: ignore[arg-type]
    ).once()
    forward = ForwardValidationRuntime(Reconciler()).status()  # type: ignore[arg-type]

    assert research.queue_item is not None
    assert research.queue_item.action == "pattern_mining"
    assert forward.status == ForwardRuntimeStatus.FORWARD_WAITING
