from test_training_resume_controller import Launcher, Reconciler, Repository, decision, noop_lock

from dehps.training_resume.controller import TrainingResumeController


def test_training_resume_claim_prevents_duplicate_launch(monkeypatch) -> None:
    monkeypatch.setattr("dehps.training_resume.controller.training_resume_lock", noop_lock)
    repository = Repository()
    repository.status = "consumed"
    launcher = Launcher()
    controller = TrainingResumeController(
        reconciler=Reconciler(decision()),  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        launcher=launcher,  # type: ignore[arg-type]
    )

    result = controller.execute()

    assert result["executed"] is False
    assert result["reason_code"] == "event_already_claimed_or_consumed"
    assert launcher.calls == []
