from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from dehps.config import ROOT_DIR


@dataclass(frozen=True)
class LaunchResult:
    launched: bool
    run_id: str
    pid: int | None
    log_path: str | None
    command: tuple[str, ...]


class TrainingLauncher(Protocol):
    def launch(self, *, as_of_issue: str | None, run_id: str | None = None) -> LaunchResult:
        ...


class SupervisorTrainingLauncher:
    def __init__(
        self,
        *,
        worker_dir: Path = ROOT_DIR / "apps/worker-python",
        log_dir: Path = ROOT_DIR / "runtime/logs",
        pid_path: Path = ROOT_DIR / "runtime/logs/training-supervisor-kdj-ridge-neural.pid",
    ) -> None:
        self.worker_dir = worker_dir
        self.log_dir = log_dir
        self.pid_path = pid_path

    def launch(self, *, as_of_issue: str | None, run_id: str | None = None) -> LaunchResult:
        run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / f"training-resume-supervisor-{run_id}.log"
        command = [
            str(self.worker_dir / ".venv/bin/python"),
            "scripts/run_training_supervisor.py",
            "--duration-hours",
            "0",
            "--train-window",
            "900",
            "--eval-window",
            "100",
            "--top-n",
            "10000",
            "--workers",
            os.getenv("DEHPS_TRAINING_WORKERS", "16"),
            "--train-mode",
            "expanding",
            "--history-scope",
            "current_regime_default",
            "--regime-years",
            "10",
            "--progress-interval",
            "10",
            "--max-configs-per-round",
            "28",
            "--memory-budget-gb",
            "20",
            "--write-status-json",
            "--enable-weight-kdj-advisor",
            "--weight-kdj-budget-share",
            os.getenv("DEHPS_WEIGHT_KDJ_BUDGET_SHARE", "0.22"),
            "--enable-ridge-kdj-advisor",
            "--enable-neural-kdj-advisor",
            "--neural-kdj-budget-share",
            os.getenv("DEHPS_NEURAL_KDJ_BUDGET_SHARE", "0.10"),
            "--target-weight-inversion-max-candidates",
            "4",
            "--target-weight-inversion-max-targets",
            "100",
            "--target-weight-inversion-max-deltas-per-target",
            "8",
            "--cpu-threads",
            "1",
        ]
        if as_of_issue:
            command.extend(["--as-of-issue", as_of_issue])
        handle = log_path.open("ab")
        process = subprocess.Popen(
            command,
            cwd=self.worker_dir,
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        handle.close()
        self.pid_path.parent.mkdir(parents=True, exist_ok=True)
        self.pid_path.write_text(f"{process.pid}\n", encoding="utf-8")
        return LaunchResult(True, run_id, process.pid, str(log_path), tuple(command))
