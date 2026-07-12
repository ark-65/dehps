from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
SSQ_DRAW_WEEKDAYS = frozenset({1, 3, 6})  # Tuesday, Thursday, Sunday
SSQ_RECOVERY_WEEKDAYS = frozenset({0, 2, 4})  # Monday, Wednesday, Friday
DEFAULT_COLD_POLL_MINUTES = 60
DEFAULT_RUNNING_GRACE_MINUTES = 30
COLD_POLL_BOUNDARY_TOLERANCE_SECONDS = 60


def ssq_remote_sync_poll_plan(
    *,
    now: datetime,
    last_attempt_at: datetime | None,
    last_status: str | None,
    cold_poll_minutes: int = DEFAULT_COLD_POLL_MINUTES,
    running_grace_minutes: int = DEFAULT_RUNNING_GRACE_MINUTES,
) -> dict[str, Any]:
    local_now = now.astimezone(SHANGHAI)
    safe_cold_minutes = max(10, int(cold_poll_minutes))
    safe_running_grace_minutes = max(10, int(running_grace_minutes))
    in_draw_hot_window = (
        local_now.weekday() in SSQ_DRAW_WEEKDAYS
        and 20 <= local_now.hour <= 23
    )
    in_recovery_window = (
        local_now.weekday() in SSQ_RECOVERY_WEEKDAYS
        and 0 <= local_now.hour < 2
    )
    hot_window = in_draw_hot_window or in_recovery_window
    normalized_status = str(last_status or "").strip().lower() or None

    elapsed_minutes: float | None = None
    if last_attempt_at is not None:
        elapsed_minutes = (now - last_attempt_at.astimezone(now.tzinfo)).total_seconds() / 60

    if (
        normalized_status == "running"
        and elapsed_minutes is not None
        and 0 <= elapsed_minutes < safe_running_grace_minutes
    ):
        due = False
        reason = "recent_sync_attempt_still_running"
    elif normalized_status not in {None, "success"}:
        due = True
        reason = "retry_non_successful_sync"
    elif hot_window:
        due = True
        reason = "official_draw_hot_window"
    elif last_attempt_at is None:
        due = True
        reason = "no_prior_sync_attempt"
    elif elapsed_minutes is None or elapsed_minutes < 0:
        due = True
        reason = "sync_clock_invariant_failed"
    elif (
        elapsed_minutes * 60 + COLD_POLL_BOUNDARY_TOLERANCE_SECONDS
        >= safe_cold_minutes * 60
    ):
        due = True
        reason = "cold_poll_interval_elapsed"
    else:
        due = False
        reason = "cold_poll_interval_not_elapsed"

    retry_after_minutes = (
        0.0
        if due or elapsed_minutes is None
        else max(0.0, safe_cold_minutes - elapsed_minutes)
    )
    return {
        "protocol": "dehps-ssq-remote-sync-cadence-v1",
        "due": due,
        "reason": reason,
        "local_now": local_now.isoformat(),
        "official_draw_schedule": "Tuesday, Thursday, Sunday at 21:15 Asia/Shanghai",
        "draw_hot_window": in_draw_hot_window,
        "recovery_window": in_recovery_window,
        "cold_poll_minutes": safe_cold_minutes,
        "cold_poll_boundary_tolerance_seconds": COLD_POLL_BOUNDARY_TOLERANCE_SECONDS,
        "running_grace_minutes": safe_running_grace_minutes,
        "last_attempt_at": last_attempt_at.isoformat() if last_attempt_at else None,
        "last_status": normalized_status,
        "elapsed_minutes": round(elapsed_minutes, 3) if elapsed_minutes is not None else None,
        "retry_after_minutes": round(retry_after_minutes, 3),
        "local_health_check_cadence_minutes": 10,
        "selection_changed": False,
        "promotion_allowed": False,
        "interpretation": (
            "Remote polling cadence only. The watchdog still runs local capacity, forward-ledger, "
            "advisor, lifecycle, and supervisor checks every ten minutes. A non-successful prior "
            "sync retries immediately after a short running grace period; cold windows retain an "
            "hourly fallback for schedule changes with a small scheduler-boundary tolerance."
        ),
    }
