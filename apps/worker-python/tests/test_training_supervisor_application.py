from __future__ import annotations

from contextlib import contextmanager

import dehps.training.supervisor as application
from dehps.training.round_runner import TrainingRoundRunner
from dehps.training.supervisor import (
    SupervisorDependencies,
    TrainingSupervisor,
    TrainingSupervisorSettings,
)


class FakeLock:
    def __init__(self) -> None:
        self.heartbeats: list[tuple[str, dict]] = []

    def heartbeat(self, *, status: str, context: dict) -> None:
        self.heartbeats.append((status, context))


def test_training_supervisor_owns_lifecycle_and_loops_through_round_runner(monkeypatch) -> None:
    lock = FakeLock()

    @contextmanager
    def fake_heavy_job_lock(**_kwargs):
        yield lock

    monkeypatch.setattr(application, "heavy_job_lock", fake_heavy_job_lock)
    monkeypatch.setattr(application, "apply_cpu_thread_env_defaults", lambda _threads: None)

    def runtime_rounds():
        yield {"run_id": "run-1", "rounds": [{"round": 1}], "status": "running"}
        yield {"run_id": "run-1", "rounds": [{"round": 1}, {"round": 2}], "status": "running"}
        return {"run_id": "run-1", "rounds": [{"round": 1}, {"round": 2}], "status": "completed"}

    supervisor = TrainingSupervisor(
        settings=TrainingSupervisorSettings(run_arguments={"max_rounds": 2}),
        dependencies=SupervisorDependencies(
            build_round_runner=lambda _arguments: TrainingRoundRunner.for_runtime(runtime_rounds())
        ),
    )

    result = supervisor.run()

    assert result["status"] == "completed"
    assert len(result["rounds"]) == 2
    assert [status for status, _context in lock.heartbeats] == ["running", "running", "completed"]
