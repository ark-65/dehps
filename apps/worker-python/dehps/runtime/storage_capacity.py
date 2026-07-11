from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from dehps.config import ROOT_DIR


GIB = 1024**3
DEFAULT_WARNING_FREE_RATIO = 0.05
DEFAULT_WARNING_FREE_BYTES = 20 * GIB
DEFAULT_CRITICAL_FREE_RATIO = 0.01
DEFAULT_CRITICAL_FREE_BYTES = 5 * GIB
OBSERVED_APPEND_LOGS = (
    "runtime/logs/hourly_self_iterate.log",
    "runtime/logs/training-supervisor-watchdog.log",
    "runtime/logs/ssq_draw_sync.log",
)


def _observed_file(root_dir: Path, relative_path: str) -> dict[str, Any]:
    path = root_dir / relative_path
    try:
        size_bytes = path.stat().st_size
    except FileNotFoundError:
        return {
            "path": str(path),
            "exists": False,
            "size_bytes": 0,
        }
    except OSError as exc:
        return {
            "path": str(path),
            "exists": None,
            "size_bytes": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": int(size_bytes),
    }


def runtime_storage_capacity_summary(
    root_dir: Path = ROOT_DIR,
    *,
    warning_free_ratio: float = DEFAULT_WARNING_FREE_RATIO,
    warning_free_bytes: int = DEFAULT_WARNING_FREE_BYTES,
    critical_free_ratio: float = DEFAULT_CRITICAL_FREE_RATIO,
    critical_free_bytes: int = DEFAULT_CRITICAL_FREE_BYTES,
) -> dict[str, Any]:
    root_dir = Path(root_dir)
    try:
        usage = shutil.disk_usage(root_dir)
    except OSError as exc:
        return {
            "protocol": "dehps-runtime-storage-capacity-v1",
            "status": "unavailable",
            "action": "inspect_runtime_storage",
            "root_path": str(root_dir),
            "error": f"{type(exc).__name__}: {exc}",
            "selection_changed": False,
            "promotion_allowed": False,
            "automatic_cleanup_allowed": False,
        }

    total_bytes = max(0, int(usage.total))
    used_bytes = max(0, int(usage.used))
    free_bytes = max(0, int(usage.free))
    free_ratio = free_bytes / total_bytes if total_bytes > 0 else 0.0
    warning_threshold_bytes = max(
        max(0, int(warning_free_bytes)),
        int(total_bytes * max(0.0, float(warning_free_ratio))),
    )
    critical_threshold_bytes = max(
        max(0, int(critical_free_bytes)),
        int(total_bytes * max(0.0, float(critical_free_ratio))),
    )
    critical_threshold_bytes = min(
        critical_threshold_bytes,
        warning_threshold_bytes,
    )

    if total_bytes <= 0:
        status = "unavailable"
        action = "inspect_runtime_storage"
        blockers = ["disk_total_bytes_invalid"]
    elif free_bytes <= critical_threshold_bytes:
        status = "critical"
        action = "stop_new_heavy_jobs_and_recover_storage"
        blockers = ["disk_free_below_critical_threshold"]
    elif free_bytes <= warning_threshold_bytes:
        status = "warning"
        action = "review_runtime_evidence_retention"
        blockers = ["disk_free_below_warning_threshold"]
    else:
        status = "healthy"
        action = "continue_storage_monitoring"
        blockers = []

    observed_logs = [
        _observed_file(root_dir, relative_path)
        for relative_path in OBSERVED_APPEND_LOGS
    ]
    observed_log_bytes = sum(
        int(row["size_bytes"])
        for row in observed_logs
        if isinstance(row.get("size_bytes"), int)
    )
    return {
        "protocol": "dehps-runtime-storage-capacity-v1",
        "status": status,
        "action": action,
        "root_path": str(root_dir),
        "total_bytes": total_bytes,
        "used_bytes": used_bytes,
        "free_bytes": free_bytes,
        "free_ratio": round(free_ratio, 6),
        "warning_threshold_bytes": warning_threshold_bytes,
        "critical_threshold_bytes": critical_threshold_bytes,
        "observed_append_log_bytes": observed_log_bytes,
        "observed_append_logs": observed_logs,
        "blockers": blockers,
        "selection_changed": False,
        "promotion_allowed": False,
        "automatic_cleanup_allowed": False,
        "interpretation": (
            "Read-only capacity evidence for long-running training operations. It never deletes, "
            "compresses, rotates, or rewrites runtime evidence. Capacity status does not change "
            "model selection or promotion."
        ),
    }
