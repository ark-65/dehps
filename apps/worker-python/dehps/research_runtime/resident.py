from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_runtime.executor import PatternDiscoveryActionExecutor
from dehps.research_runtime.models import (
    ResidentResearchRuntimeConfig,
    ResearchCycleResult,
    ResearchRuntimeBudget,
    jsonable,
)
from dehps.research_runtime.runtime import ContinuousResearchRuntime


class LegacySupervisorActiveError(RuntimeError):
    pass


class ResidentResearchRuntime:
    """Long-running process wrapper for ContinuousResearchRuntime.

    The resident worker owns only research cycles.  It fails closed when a legacy
    training supervisor is active so both runtimes cannot consume research work
    concurrently.
    """

    def __init__(
        self,
        *,
        runtime: ContinuousResearchRuntime | None = None,
        budget: ResearchRuntimeBudget | None = None,
        config: ResidentResearchRuntimeConfig | None = None,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.root_dir = root_dir
        self.config = config or ResidentResearchRuntimeConfig()
        self.config.validate()
        self.budget = budget or ResearchRuntimeBudget()
        self.runtime = runtime or ContinuousResearchRuntime(
            budget=self.budget,
            executor=PatternDiscoveryActionExecutor(),
        )
        self.cycles_completed = 0
        self._stopping = False

    @property
    def lock_path(self) -> Path:
        return self.root_dir / self.config.lock_path

    @property
    def pid_path(self) -> Path:
        return self.root_dir / self.config.pid_path

    @property
    def state_path(self) -> Path:
        return self.root_dir / self.config.state_path

    @property
    def cycle_log_path(self) -> Path:
        return self.root_dir / self.config.cycle_log_path

    def run(self) -> dict[str, Any]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_handle:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                state = self._state(status="already_running", reason_code="research_runtime_lock_busy")
                self._write_state(state)
                return state

            self._install_signal_handlers()
            atomic_write_text(self.pid_path, f"{os.getpid()}\n")
            self._write_state(self._state(status="research_running", reason_code="started"))
            try:
                self._assert_no_legacy_supervisor()
                while not self._stopping:
                    if self.config.max_cycles is not None and self.cycles_completed >= self.config.max_cycles:
                        break
                    self._run_cycle()
                    self._sleep(self.config.interval_seconds)
                final = self._state(status="stopped", reason_code="max_cycles" if self.config.max_cycles else "signal")
                self._write_state(final)
                return final
            except LegacySupervisorActiveError as exc:
                blocked = self._state(status="blocked", reason_code=str(exc))
                self._write_state(blocked)
                raise

    def _run_cycle(self) -> ResearchCycleResult:
        self.runtime.budget = replace(self.budget, cycles_used=self.cycles_completed)
        cycle_started_at = datetime.now(timezone.utc)
        start_snapshot = self.runtime.active_snapshot or self.runtime.snapshot_manager.current()
        result = self.runtime.once(cycle_running=False)
        end_snapshot = self.runtime.active_snapshot or result.snapshot
        self.cycles_completed += 1
        record = {
            "runtime": "continuous_research",
            "cycle_number": self.cycles_completed,
            "started_at": cycle_started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "cycle_key": result.cycle_key,
            "status": result.status.value,
            "runtime_status": result.runtime_status.value,
            "queue_item": result.queue_item,
            "snapshot_start": start_snapshot,
            "snapshot_end": end_snapshot,
            "snapshot_stable_within_cycle": start_snapshot.snapshot_key == end_snapshot.snapshot_key,
            "rotation": result.rotation,
            "budget": result.budget,
            "execution_result": result.execution_result,
            "evidence_source": result.evidence_source.value,
            "forward_wait_blocks_research": False,
        }
        self._append_cycle(record)
        self._write_state(self._state(status=result.runtime_status.value, reason_code="cycle_completed", extra=record))
        return result

    def _assert_no_legacy_supervisor(self) -> None:
        matches = legacy_supervisor_processes(patterns=self.config.legacy_supervisor_patterns)
        if matches:
            raise LegacySupervisorActiveError("legacy_supervisor_active")

    def _state(self, *, status: str, reason_code: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        active_snapshot = self.runtime.active_snapshot
        payload: dict[str, Any] = {
            "runtime": "continuous_research",
            "pid": os.getpid(),
            "active": status not in {"stopped", "blocked", "already_running"},
            "status": status,
            "reason_code": reason_code,
            "cycles_completed": self.cycles_completed,
            "heartbeat_at": datetime.now(timezone.utc).isoformat(),
            "active_snapshot": active_snapshot,
            "forward_wait_blocks_research": False,
            "promotion_allowed_from_research": False,
            "budget": replace(self.budget, cycles_used=self.cycles_completed),
            "config": self.config,
        }
        if extra:
            payload["last_cycle"] = extra
        return payload

    def _write_state(self, payload: dict[str, Any]) -> None:
        atomic_write_text(self.state_path, json.dumps(jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True))

    def _append_cycle(self, payload: dict[str, Any]) -> None:
        self.cycle_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cycle_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(jsonable(payload), ensure_ascii=False, sort_keys=True) + "\n")

    def _install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, *_args: object) -> None:
        self._stopping = True

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not self._stopping and time.monotonic() < deadline:
            time.sleep(min(0.25, deadline - time.monotonic()))


def legacy_supervisor_processes(*, patterns: tuple[str, ...] = ("run_training_supervisor", "training_supervisor")) -> tuple[str, ...]:
    completed = subprocess.run(
        ["pgrep", "-af", "|".join(patterns)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode not in {0, 1}:
        return ()
    own_pid = os.getpid()
    rows: list[str] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        first = stripped.split(maxsplit=1)[0]
        try:
            pid = int(first)
        except ValueError:
            continue
        if pid == own_pid:
            continue
        command = stripped.split(maxsplit=1)[1] if " " in stripped else ""
        if "pgrep" in command:
            continue
        if any(pattern in command for pattern in patterns):
            rows.append(stripped)
    return tuple(rows)
