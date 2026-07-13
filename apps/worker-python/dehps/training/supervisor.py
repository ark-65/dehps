from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from dehps.runtime.heavy_job import apply_cpu_thread_env_defaults, heavy_job_lock


@dataclass(frozen=True)
class TrainingSupervisorSettings:
    run_arguments: Mapping[str, object]
    cpu_threads: int = 1
    heavy_job_lock_timeout_seconds: float = 0.0


@dataclass(frozen=True)
class SupervisorDependencies:
    run_training: Callable[..., dict]


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
            result = self.dependencies.run_training(**arguments)
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
            "enable_weight_kdj_advisor",
            "enable_ridge_kdj_advisor",
            "enable_neural_kdj_advisor",
            "enable_target_weight_inversion_advisor",
            "target_weight_inversion_max_targets",
            "target_weight_inversion_max_deltas_per_target",
        )
        return {key: arguments.get(key) for key in keys}
