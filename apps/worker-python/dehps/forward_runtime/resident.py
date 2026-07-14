from __future__ import annotations

import fcntl
import json
import os
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.forward_runtime.service import ForwardRuntimeService
from dehps.research_runtime.models import jsonable


@dataclass(frozen=True)
class ResidentForwardRuntimeConfig:
    interval_seconds: float = 10.0
    max_checks: int | None = None
    lock_path: str = "runtime/logs/forward-runtime.lock"
    pid_path: str = "runtime/logs/forward-runtime.pid"
    state_path: str = "runtime/logs/forward-runtime-state.json"

    def validate(self) -> None:
        if self.interval_seconds < 0:
            raise ValueError("interval_seconds must be non-negative")
        if self.max_checks is not None and self.max_checks < 1:
            raise ValueError("max_checks must be positive when provided")


class ResidentForwardRuntime:
    """Long-running heartbeat wrapper for forward validation status."""

    def __init__(
        self,
        *,
        service: ForwardRuntimeService | None = None,
        config: ResidentForwardRuntimeConfig | None = None,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.service = service or ForwardRuntimeService()
        self.config = config or ResidentForwardRuntimeConfig()
        self.config.validate()
        self.root_dir = root_dir
        self.checks_completed = 0
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

    def run(self) -> dict[str, Any]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_handle:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                state = self._state(status="already_running", reason_code="forward_runtime_lock_busy")
                self._write_state(state)
                return state
            self._install_signal_handlers()
            atomic_write_text(self.pid_path, f"{os.getpid()}\n")
            last_status: dict[str, Any] | None = None
            while not self._stopping:
                if self.config.max_checks is not None and self.checks_completed >= self.config.max_checks:
                    break
                last_status = self.service.status()
                self.checks_completed += 1
                self._write_state(
                    self._state(status=last_status["state"].status.value, reason_code="status_checked", extra=last_status)
                )
                self._sleep(self.config.interval_seconds)
            final = self._state(status="stopped", reason_code="max_checks" if self.config.max_checks else "signal", extra=last_status)
            self._write_state(final)
            return final

    def _state(self, *, status: str, reason_code: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "runtime": "forward_validation",
            "pid": os.getpid(),
            "active": status not in {"stopped", "already_running"},
            "status": status,
            "reason_code": reason_code,
            "checks_completed": self.checks_completed,
            "heartbeat_at": datetime.now(timezone.utc).isoformat(),
            "research_runtime_blocked": False,
            "promotion_allowed_from_research": False,
            "config": self.config,
        }
        if extra:
            payload["last_status"] = extra
        return payload

    def _write_state(self, payload: dict[str, Any]) -> None:
        atomic_write_text(self.state_path, json.dumps(jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True))

    def _install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, *_args: object) -> None:
        self._stopping = True

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not self._stopping and time.monotonic() < deadline:
            time.sleep(min(0.25, deadline - time.monotonic()))
