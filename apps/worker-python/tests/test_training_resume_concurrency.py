from test_training_resume_controller import Launcher, Reconciler, Repository, decision, noop_lock

from dehps.training_resume.controller import TrainingResumeController


def test_training_resume_shared_claim_allows_only_one_controller_to_launch(monkeypatch) -> None:
    monkeypatch.setattr("dehps.training_resume.controller.training_resume_lock", noop_lock)
    repository = Repository()
    first_launcher = Launcher()
    second_launcher = Launcher()
    first = TrainingResumeController(
        reconciler=Reconciler(decision()),  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        launcher=first_launcher,  # type: ignore[arg-type]
    )
    second = TrainingResumeController(
        reconciler=Reconciler(decision()),  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        launcher=second_launcher,  # type: ignore[arg-type]
    )

    assert first.execute()["executed"] is True
    assert second.execute()["executed"] is False
    assert len(first_launcher.calls) == 1
    assert second_launcher.calls == []
