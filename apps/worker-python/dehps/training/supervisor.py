from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from dehps.runtime.heavy_job import apply_cpu_thread_env_defaults, heavy_job_lock
from dehps.training.round_runner import TrainingRoundRunner


@dataclass(frozen=True)
class TrainingSupervisorSettings:
    run_arguments: Mapping[str, object]
    cpu_threads: int = 1
    heavy_job_lock_timeout_seconds: float = 0.0


@dataclass(frozen=True)
class SupervisorDependencies:
    build_round_runner: Callable[[dict[str, object]], TrainingRoundRunner]


@dataclass(frozen=True)
class TrainingSupervisor:
    settings: TrainingSupervisorSettings
    dependencies: SupervisorDependencies

    def run(self) -> dict:
        arguments = dict(self.settings.run_arguments)
        apply_cpu_thread_env_defaults(self.settings.cpu_threads)
        with heavy_job_lock(
            owner="training-supervisor",
            timeout_seconds=self.settings.heavy_job_lock_timeout_seconds,
            context=self._lock_context(arguments),
        ) as lock:
            round_runner = self.dependencies.build_round_runner(arguments)
            result: dict = {}
            while True:
                round_status = round_runner.run_runtime_round()
                if round_status is None:
                    break
                result = round_status
                lock.heartbeat(
                    status="running",
                    context={
                        "run_id": result.get("run_id"),
                        "completed_rounds": len(result.get("rounds") or ()),
                    },
                )
            result = round_runner.final_status or result
            lock.heartbeat(
                status="completed",
                context={"run_id": result.get("run_id"), "rounds": result.get("rounds")},
            )
        return result

    @staticmethod
    def _lock_context(arguments: Mapping[str, object]) -> dict[str, object]:
        keys = (
            "duration_hours",
            "train_window",
            "eval_window",
            "top_n",
            "max_rounds",
            "enable_weight_kdj_advisor",
            "enable_ridge_kdj_advisor",
            "enable_neural_kdj_advisor",
            "enable_target_weight_inversion_advisor",
            "target_weight_inversion_max_targets",
            "target_weight_inversion_max_deltas_per_target",
        )
        return {key: arguments.get(key) for key in keys}
