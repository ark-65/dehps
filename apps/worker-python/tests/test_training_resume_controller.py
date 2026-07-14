from __future__ import annotations

from contextlib import contextmanager

from dehps.forward_state.models import ForwardReconcileDecision
from dehps.training_resume.controller import TrainingResumeController
from dehps.training_resume.launcher import LaunchResult


@contextmanager
def noop_lock(**_kwargs):
    yield


class Reconciler:
    def __init__(self, decision: ForwardReconcileDecision) -> None:
        self.decision = decision

    def reconcile(self, *, event_key=None):
        return self.decision


class Repository:
    def __init__(self) -> None:
        self.status = "pending"
        self.consumed: list[tuple[str, str]] = []
        self.failed: list[tuple[str, dict]] = []
        self.attempts: list[dict] = []

    def ensure_schema(self):
        return None

    def claim_event(self, event_key):
        if self.status in {"pending", "failed"}:
            self.status = "consuming"
            return {"event_key": event_key}
        return None

    def mark_event_consumed(self, *, event_key, run_id):
        self.status = "consumed"
        self.consumed.append((event_key, run_id))

    def mark_event_failed(self, *, event_key, reason):
        self.status = "failed"
        self.failed.append((event_key, reason))

    def record_attempt(self, **kwargs):
        self.attempts.append(kwargs)
        return f"attempt-{len(self.attempts)}"


class Launcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def launch(self, *, as_of_issue, run_id=None):
        self.calls.append((as_of_issue, run_id))
        if self.fail:
            raise RuntimeError("boom")
        return LaunchResult(True, "new-run", 4242, "/tmp/log", ("python", "run_training_supervisor.py"))


def decision() -> ForwardReconcileDecision:
    return ForwardReconcileDecision(
        resume_allowed=True,
        reason_code="new_forward_issue_available",
        previous_pending_issue="2026080",
        observed_issue="2026080",
        forward_count_before=2,
        forward_count_after=3,
        event_key="event-2026080",
        old_run_id="old-run",
    )


def test_training_resume_controller_launches_and_consumes_event(monkeypatch) -> None:
    monkeypatch.setattr("dehps.training_resume.controller.training_resume_lock", noop_lock)
    repository = Repository()
    launcher = Launcher()
    controller = TrainingResumeController(
        reconciler=Reconciler(decision()),  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        launcher=launcher,  # type: ignore[arg-type]
    )

    result = controller.execute()

    assert result["executed"] is True
    assert repository.status == "consumed"
    assert repository.consumed == [("event-2026080", "new-run")]
    assert launcher.calls == [("2026080", None)]


def test_training_resume_controller_records_wait_when_policy_blocks(monkeypatch) -> None:
    monkeypatch.setattr("dehps.training_resume.controller.training_resume_lock", noop_lock)
    blocked = ForwardReconcileDecision(False, "no_pending_event", None, None, 0, 0, None)
    repository = Repository()
    controller = TrainingResumeController(
        reconciler=Reconciler(blocked),  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        launcher=Launcher(),  # type: ignore[arg-type]
    )

    result = controller.execute()

    assert result["executed"] is False
    assert result["reason_code"] == "no_pending_event"
    assert repository.status == "pending"
