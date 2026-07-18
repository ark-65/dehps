import json
from datetime import datetime
from zoneinfo import ZoneInfo

from dehps.draw_sync.scheduler import DrawSyncSchedulePolicy
from dehps.draw_sync.scheduler import DrawSyncWatch
from dehps.draw_sync.models import DrawSyncResult, DrawSyncStatus


def test_draw_sync_scheduler_uses_hot_interval_on_draw_evening() -> None:
    policy = DrawSyncSchedulePolicy(interval_seconds=900, hot_interval_seconds=300, timezone="Asia/Shanghai")

    interval = policy.next_interval(datetime(2026, 7, 14, 21, 45, tzinfo=ZoneInfo("Asia/Shanghai")))

    assert interval == 300


def test_draw_sync_scheduler_defers_draw_update_until_2145() -> None:
    policy = DrawSyncSchedulePolicy(interval_seconds=900, hot_interval_seconds=300, timezone="Asia/Shanghai")
    moment = datetime(2026, 7, 14, 21, 32, tzinfo=ZoneInfo("Asia/Shanghai"))

    deferred_until = policy.deferred_until(moment)

    assert deferred_until == datetime(2026, 7, 14, 21, 45, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert policy.next_interval(moment) == 13 * 60


def test_draw_sync_scheduler_defaults_to_cold_safe_interval() -> None:
    policy = DrawSyncSchedulePolicy(interval_seconds=900, hot_interval_seconds=300, timezone="Asia/Shanghai")

    interval = policy.next_interval(datetime(2026, 7, 15, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")))

    assert interval == 900


class Service:
    def __init__(self, event_key: str | None) -> None:
        self.event_key = event_key
        self.calls = 0

    def once(self):
        self.calls += 1
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
        code_commit="a" * 40,
    )

    watch.run(once=True)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert evaluator.calls == 1
    assert state["watch_code_commit"] == "a" * 40
    assert state["watch_started_at"]
    assert (tmp_path / "pid.version").read_text(encoding="utf-8").strip() == "a" * 40
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


def test_no_change_poll_still_backfills_pending_forward_evaluation(tmp_path) -> None:
    evaluator = ForwardEvaluator()
    watch = DrawSyncWatch(
        service=Service(None),  # type: ignore[arg-type]
        forward_evaluator=evaluator,
        state_path=tmp_path / "state.json",
        pid_path=tmp_path / "pid",
        code_commit="c" * 40,
    )

    watch.run(once=True)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["last_result"]["status"] == "no_change"
    assert evaluator.calls == 1
    assert state["forward_evaluation"]["status"] == "ok"


def test_deferred_draw_poll_skips_remote_sync_but_still_evaluates_pending(
    tmp_path,
) -> None:
    service = Service("must-not-be-used")
    evaluator = ForwardEvaluator()
    moment = datetime(2026, 7, 14, 21, 32, tzinfo=ZoneInfo("Asia/Shanghai"))
    watch = DrawSyncWatch(
        service=service,  # type: ignore[arg-type]
        forward_evaluator=evaluator,
        policy=DrawSyncSchedulePolicy(timezone="Asia/Shanghai"),
        state_path=tmp_path / "state.json",
        pid_path=tmp_path / "pid",
        code_commit="d" * 40,
        clock=lambda: moment,
    )
    watch.run(once=True)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert service.calls == 0
    assert evaluator.calls == 1
    assert state["sync_deferred"] is True
    assert state["last_result"] == {
        "status": "deferred_until_update_window",
        "deferred_until": "2026-07-14T21:45:00+08:00",
    }


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


def test_draw_sync_watch_error_state_retains_loaded_code_identity(tmp_path) -> None:
    class BrokenService:
        def once(self):
            raise RuntimeError("sync exploded")

    watch = DrawSyncWatch(
        service=BrokenService(),  # type: ignore[arg-type]
        forward_evaluator=ForwardEvaluator(),
        state_path=tmp_path / "state.json",
        pid_path=tmp_path / "pid",
        code_commit="b" * 40,
    )

    watch.run(once=True)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "error"
    assert state["watch_code_commit"] == "b" * 40
    assert state["error"] == {"type": "RuntimeError", "message": "sync exploded"}


def test_draw_sync_watch_seals_and_closes_shadow_after_evaluation(tmp_path) -> None:
    cycles = []

    class Attestor:
        def close_cycle(self, cycle):
            cycles.append(cycle)
            return {
                "protocol": "forward-shadow-attestation-closure.v1",
                "status": "ok",
                "attested_count": 3,
                "automatic_promotion_allowed": False,
            }

    watch = DrawSyncWatch(
        service=Service("event-2026080"),  # type: ignore[arg-type]
        forward_evaluator=ForwardEvaluator(),
        state_path=tmp_path / "state.json",
        pid_path=tmp_path / "pid",
        code_commit="a" * 40,
        shadow_attestor=Attestor(),
        shadow_attestation_enabled=True,
    )

    watch.run(once=True)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert len(cycles) == 1
    assert cycles[0]["watch_code_commit"] == "a" * 40
    assert cycles[0]["current_latest_issue"] == "2026080"
    assert cycles[0]["sync_audit_passed"] is True
    assert cycles[0]["evaluation_batch_status"] == "ok"
    assert state["shadow_watch_cycle"]["cycle_digest"] == cycles[0]["cycle_digest"]
    assert state["shadow_attestation"]["attested_count"] == 3
    assert state["shadow_attestation"]["automatic_promotion_allowed"] is False


def test_draw_sync_watch_records_shadow_failure_without_replacing_evaluation(tmp_path) -> None:
    class BrokenAttestor:
        def close_cycle(self, cycle):
            raise RuntimeError("shadow replay failed")

    watch = DrawSyncWatch(
        service=Service("event-2026080"),  # type: ignore[arg-type]
        forward_evaluator=ForwardEvaluator(),
        state_path=tmp_path / "state.json",
        pid_path=tmp_path / "pid",
        shadow_attestor=BrokenAttestor(),
        shadow_attestation_enabled=True,
    )

    watch.run(once=True)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "ok"
    assert state["forward_evaluation"]["status"] == "ok"
    assert state["shadow_attestation"]["status"] == "failed"
    assert state["shadow_attestation"]["error"]["message"] == "shadow replay failed"
    assert state["shadow_attestation"]["automatic_promotion_allowed"] is False
