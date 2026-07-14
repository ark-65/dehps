from __future__ import annotations

from pathlib import Path
from typing import Any

from dehps.config import ROOT_DIR
from dehps.runtime.heavy_job import HeavyJobLock, HeavyJobLockTimeout


DEFAULT_DRAW_SYNC_LOCK_PATH = ROOT_DIR / "runtime" / "logs" / "dehps-draw-sync.lock"


def draw_sync_lock(*, timeout_seconds: float = 0, context: dict[str, Any] | None = None) -> HeavyJobLock:
    return HeavyJobLock(
        owner="draw-sync",
        lock_path=DEFAULT_DRAW_SYNC_LOCK_PATH,
        timeout_seconds=timeout_seconds,
        cleanup_metadata_on_release=False,
        status="running",
        context=context or {},
    )


def is_locked_error(exc: BaseException) -> bool:
    return isinstance(exc, HeavyJobLockTimeout)
