from dehps.research_runtime.models import HistorySnapshot
from dehps.research_runtime.snapshot import HistorySnapshotManager


class SnapshotManager(HistorySnapshotManager):
    def __init__(self, rows):
        self.rows = tuple(rows)

    def _load_history(self):
        return self.rows

    def _load_contract_history(self):
        return tuple((issue, None, numbers) for issue, numbers in self.rows)


def test_history_snapshot_is_fingerprint_stable_for_same_rows() -> None:
    rows = (("2026079", (1, 2, 3, 4, 5, 6)),)
    first = SnapshotManager(rows).current()
    second = SnapshotManager(rows).current()

    assert first.snapshot_key == second.snapshot_key
    assert first.history_fingerprint == second.history_fingerprint
    assert first.latest_issue == "2026079"


def test_contract_snapshot_is_opt_in_and_does_not_replace_legacy_fingerprint() -> None:
    rows = (("2026079", (1, 2, 3, 4, 5, 6)),)
    manager = SnapshotManager(rows)

    legacy = manager.current()
    contracted = manager.contract_current()

    assert contracted.latest_issue == legacy.latest_issue
    assert contracted.draw_count == legacy.issue_count
    assert contracted.history_digest != legacy.history_fingerprint
    assert contracted.contract.key == "history_snapshot.v1.0.0"


def test_snapshot_rotation_defers_while_cycle_is_running() -> None:
    active = HistorySnapshot("snap-79", "2026079", 1, "old")
    manager = SnapshotManager((("2026079", (1, 2, 3, 4, 5, 6)), ("2026080", (3, 8, 12, 18, 25, 33))))

    decision = manager.rotation_decision(active_snapshot=active, cycle_running=True)

    assert decision.rotate is False
    assert decision.defer_until_cycle_complete is True
    assert decision.candidate_latest_issue == "2026080"


def test_snapshot_rotation_happens_at_cycle_boundary() -> None:
    active = HistorySnapshot("snap-79", "2026079", 1, "old")
    manager = SnapshotManager((("2026080", (3, 8, 12, 18, 25, 33)),))

    decision = manager.rotation_decision(active_snapshot=active, cycle_running=False)

    assert decision.rotate is True
    assert decision.defer_until_cycle_complete is False
