from types import SimpleNamespace

from dehps.research_runtime.models import HistorySnapshot
from dehps.research_runtime.scheduler import ContinuousResearchScheduler


class Planner:
    def build_state(self):
        return SimpleNamespace(
            pattern_discovery={"enabled": True, "pattern_count": 0},
            active_hypotheses=(),
            training_status=SimpleNamespace(
                forward_evidence_status={"status": "waiting", "review_ready": False, "promotion_eligible": False}
            ),
        )


def test_research_scheduler_ignores_forward_wait_and_still_schedules_pattern_mining() -> None:
    item = ContinuousResearchScheduler(planner=Planner()).next_item(  # type: ignore[arg-type]
        snapshot=HistorySnapshot("snap-79", "2026079", 1, "fp")
    )

    assert item.action == "pattern_mining"
    assert item.snapshot_key == "snap-79"
    assert item.payload["forward_gate_ignored_for_research"] is True
