import json
from datetime import datetime
from zoneinfo import ZoneInfo

from dehps.draw_sync.scheduler import DrawSyncSchedulePolicy
from dehps.draw_sync.scheduler import DrawSyncWatch
from dehps.draw_sync.models import DrawSyncResult, DrawSyncStatus


def test_draw_sync_scheduler_uses_hot_interval_on_draw_evening() -> None:
    policy = DrawSyncSchedulePolicy(interval_seconds=900, hot_interval_seconds=300, timezone="Asia/Shanghai")

    interval = policy.next_interval(datetime(2026, 7, 14, 21, 30, tzinfo=ZoneInfo("Asia/Shanghai")))

    assert interval == 300


def test_draw_sync_scheduler_defaults_to_cold_safe_interval() -> None:
    policy = DrawSyncSchedulePolicy(interval_seconds=900, hot_interval_seconds=300, timezone="Asia/Shanghai")

    interval = policy.next_interval(datetime(2026, 7, 15, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")))

    assert interval == 900


class Service:
    def __init__(self, event_key: str | None) -> None:
        self.event_key = event_key

    def once(self):
        return DrawSyncResult(
            status=DrawSyncStatus.NEW_ISSUE if self.event_key else DrawSyncStatus.NO_CHANGE,
            previous_latest_issue="2026079",
            current_latest_issue="2026080" if self.event_key else "2026079",
            inserted_issues=("2026080",) if self.event_key else (),
            updated_issues=(),
            audit_passed=True,
            history_fingerprint_before="before",
            history_fingerprint_after="after" if self.event_key else "before",
            event_key=self.event_key,
        )


class ForwardEvaluator:
    def __init__(self, *, failed_count: int = 0) -> None:
        self.failed_count = failed_count
        self.calls = 0

    def evaluate_pending(self):
        self.calls += 1
        return {
            "status": "failed" if self.failed_count else "ok",
            "pending_count": self.failed_count,
            "evaluated_count": 0,
            "missing_draw_count": 0,
            "failed_count": self.failed_count,
            "results": [],
        }


def test_draw_sync_watch_resumes_once_when_new_event_is_seen(monkeypatch, tmp_path) -> None:
    calls = []

    class ResumeService:
        def execute(self, *, event_key=None):
            calls.append(event_key)
            return {"executed": True, "event_key": event_key}

    monkeypatch.setattr("dehps.training_resume.service.TrainingResumeService", ResumeService)
    evaluator = ForwardEvaluator()
    watch = DrawSyncWatch(
        service=Service("event-2026080"),  # type: ignore[arg-type]
        forward_evaluator=evaluator,
        policy=DrawSyncSchedulePolicy(),
        resume_on_event=True,
        state_path=tmp_path / "state.json",
        pid_path=tmp_path / "pid",
    )

    watch.run(once=True)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert evaluator.calls == 1
    assert calls == ["event-2026080"]
    assert state["forward_evaluation"]["failed_count"] == 0
    assert state["resume_result"]["executed"] is True


def test_draw_sync_watch_defaults_to_no_legacy_training_resume(monkeypatch, tmp_path) -> None:
    calls = []

    class ResumeService:
        def execute(self, *, event_key=None):
            calls.append(event_key)
            return {"executed": True}

    monkeypatch.setattr("dehps.training_resume.service.TrainingResumeService", ResumeService)
    watch = DrawSyncWatch(
        service=Service("event-2026080"),  # type: ignore[arg-type]
        forward_evaluator=ForwardEvaluator(),
        policy=DrawSyncSchedulePolicy(),
        state_path=tmp_path / "state.json",
        pid_path=tmp_path / "pid",
    )

    watch.run(once=True)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert calls == []
    assert state["resume_on_event"] is False
    assert state["resume_result"] is None


def test_draw_sync_watch_can_disable_resume_on_event(monkeypatch, tmp_path) -> None:
    calls = []

    class ResumeService:
        def execute(self, *, event_key=None):
            calls.append(event_key)
            return {"executed": True}

    monkeypatch.setattr("dehps.training_resume.service.TrainingResumeService", ResumeService)
    watch = DrawSyncWatch(
        service=Service("event-2026080"),  # type: ignore[arg-type]
        forward_evaluator=ForwardEvaluator(),
        policy=DrawSyncSchedulePolicy(),
        resume_on_event=False,
        state_path=tmp_path / "state.json",
        pid_path=tmp_path / "pid",
    )

    watch.run(once=True)

    assert calls == []


def test_draw_sync_watch_withholds_resume_when_forward_evaluation_fails(monkeypatch, tmp_path) -> None:
    calls = []

    class ResumeService:
        def execute(self, *, event_key=None):
            calls.append(event_key)
            return {"executed": True}

    monkeypatch.setattr("dehps.training_resume.service.TrainingResumeService", ResumeService)
    evaluator = ForwardEvaluator(failed_count=1)
    watch = DrawSyncWatch(
        service=Service("event-2026080"),  # type: ignore[arg-type]
        forward_evaluator=evaluator,
        policy=DrawSyncSchedulePolicy(),
        resume_on_event=True,
        state_path=tmp_path / "state.json",
        pid_path=tmp_path / "pid",
    )

    watch.run(once=True)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert evaluator.calls == 1
    assert calls == []
    assert state["status"] == "error"
    assert state["error"]["type"] == "ForwardEvaluationBatchFailed"
