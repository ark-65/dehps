import json
from pathlib import Path

import pytest

from dehps.research_runtime.models import (
    EvidenceSource,
    HistorySnapshot,
    ResearchRuntimeQueueItem,
    SnapshotRotationDecision,
    ResidentResearchRuntimeConfig,
)
from dehps.research_runtime.resident import LegacySupervisorActiveError, ResidentResearchRuntime
from dehps.research_runtime.runtime import ContinuousResearchRuntime


class SnapshotManager:
    def __init__(self) -> None:
        self.snapshot = HistorySnapshot("snapshot-2026079", "2026079", 1, "fp-79")

    def current(self) -> HistorySnapshot:
        return self.snapshot

    def rotation_decision(self, *, active_snapshot, cycle_running):
        candidate = self.current()
        return SnapshotRotationDecision(
            rotate=active_snapshot is None,
            reason_code="test",
            active_snapshot_key=getattr(active_snapshot, "snapshot_key", None),
            candidate_snapshot_key=candidate.snapshot_key,
            active_latest_issue=getattr(active_snapshot, "latest_issue", None),
            candidate_latest_issue=candidate.latest_issue,
            defer_until_cycle_complete=cycle_running,
        )


class Scheduler:
    def next_item(self, *, snapshot):
        return ResearchRuntimeQueueItem(
            queue_key=f"queue-{snapshot.snapshot_key}",
            action="pattern_mining",
            status="queued",
            snapshot_key=snapshot.snapshot_key,
            history_fingerprint=snapshot.history_fingerprint,
            evidence_source=EvidenceSource.RESEARCH,
            priority_score=0.74,
            payload={"forward_gate_ignored_for_research": True},
        )


def test_resident_research_runtime_runs_ten_cycles_and_audits_snapshot(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("dehps.research_runtime.resident.legacy_supervisor_processes", lambda patterns: ())
    runtime = ContinuousResearchRuntime(snapshot_manager=SnapshotManager(), scheduler=Scheduler())  # type: ignore[arg-type]
    resident = ResidentResearchRuntime(
        runtime=runtime,
        config=ResidentResearchRuntimeConfig(
            interval_seconds=0,
            max_cycles=10,
            lock_path="research-runtime.lock",
            pid_path="research-runtime.pid",
            state_path="research-runtime-state.json",
            cycle_log_path="research-runtime-cycles.jsonl",
        ),
        root_dir=tmp_path,
    )

    state = resident.run()

    assert state["cycles_completed"] == 10
    assert state["status"] == "stopped"
    cycle_lines = (tmp_path / "research-runtime-cycles.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(cycle_lines) == 10
    cycles = [json.loads(line) for line in cycle_lines]
    assert all(cycle["forward_wait_blocks_research"] is False for cycle in cycles)
    assert all(cycle["evidence_source"] == "research" for cycle in cycles)
    assert all(cycle["snapshot_stable_within_cycle"] is True for cycle in cycles)
    assert cycles[-1]["cycle_number"] == 10


def test_resident_research_runtime_blocks_when_legacy_supervisor_is_active(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "dehps.research_runtime.resident.legacy_supervisor_processes",
        lambda patterns: ("123 scripts/run_training_supervisor.py",),
    )
    resident = ResidentResearchRuntime(
        config=ResidentResearchRuntimeConfig(
            interval_seconds=0,
            max_cycles=1,
            lock_path="research-runtime.lock",
            pid_path="research-runtime.pid",
            state_path="research-runtime-state.json",
            cycle_log_path="research-runtime-cycles.jsonl",
        ),
        root_dir=tmp_path,
    )

    with pytest.raises(LegacySupervisorActiveError):
        resident.run()

    state = json.loads((tmp_path / "research-runtime-state.json").read_text(encoding="utf-8"))
    assert state["status"] == "blocked"
    assert state["reason_code"] == "legacy_supervisor_active"
