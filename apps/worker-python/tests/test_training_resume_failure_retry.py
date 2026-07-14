from test_training_resume_controller import Launcher, Reconciler, Repository, decision, noop_lock

from dehps.training_resume.controller import TrainingResumeController


def test_training_resume_launch_failure_leaves_event_retryable(monkeypatch) -> None:
    monkeypatch.setattr("dehps.training_resume.controller.training_resume_lock", noop_lock)
    repository = Repository()
    controller = TrainingResumeController(
        reconciler=Reconciler(decision()),  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        launcher=Launcher(fail=True),  # type: ignore[arg-type]
    )

    result = controller.execute()

    assert result["executed"] is False
    assert result["reason_code"] == "launcher_failed"
    assert repository.status == "failed"
    assert repository.failed[0][0] == "event-2026080"
