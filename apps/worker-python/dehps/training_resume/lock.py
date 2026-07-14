from __future__ import annotations

from typing import Any

from dehps.config import ROOT_DIR
from dehps.runtime.heavy_job import HeavyJobLock


DEFAULT_TRAINING_RESUME_LOCK_PATH = ROOT_DIR / "runtime" / "logs" / "dehps-training-resume.lock"


def training_resume_lock(*, timeout_seconds: float = 0, context: dict[str, Any] | None = None) -> HeavyJobLock:
    return HeavyJobLock(
        owner="training-resume",
        lock_path=DEFAULT_TRAINING_RESUME_LOCK_PATH,
        timeout_seconds=timeout_seconds,
        cleanup_metadata_on_release=False,
        status="running",
        context=context or {},
    )
