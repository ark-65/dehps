from datetime import datetime, timedelta, timezone

from dehps.runtime.remote_sync_schedule import SHANGHAI, ssq_remote_sync_poll_plan


def local_time(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=SHANGHAI)


def test_remote_sync_poll_is_due_during_official_draw_hot_window():
    now = local_time(2026, 7, 12, 21, 20)  # Sunday
    plan = ssq_remote_sync_poll_plan(
        now=now,
        last_attempt_at=now - timedelta(minutes=5),
        last_status="success",
    )

    assert plan["due"] is True
    assert plan["reason"] == "official_draw_hot_window"
    assert plan["draw_hot_window"] is True
    assert plan["local_health_check_cadence_minutes"] == 10


def test_remote_sync_poll_is_due_in_post_draw_recovery_window():
    now = local_time(2026, 7, 13, 0, 30)  # Monday after Sunday draw
    plan = ssq_remote_sync_poll_plan(
        now=now,
        last_attempt_at=now - timedelta(minutes=5),
        last_status="success",
    )

    assert plan["due"] is True
    assert plan["recovery_window"] is True


def test_remote_sync_poll_skips_recent_success_in_cold_window():
    now = local_time(2026, 7, 11, 18, 20)  # Saturday
    plan = ssq_remote_sync_poll_plan(
        now=now,
        last_attempt_at=now - timedelta(minutes=10),
        last_status="success",
    )

    assert plan["due"] is False
    assert plan["reason"] == "cold_poll_interval_not_elapsed"
    assert plan["retry_after_minutes"] == 50.0


def test_remote_sync_poll_keeps_hourly_cold_fallback():
    now = local_time(2026, 7, 11, 18, 20)
    plan = ssq_remote_sync_poll_plan(
        now=now,
        last_attempt_at=now - timedelta(minutes=60),
        last_status="success",
    )

    assert plan["due"] is True
    assert plan["reason"] == "cold_poll_interval_elapsed"


def test_remote_sync_poll_accepts_subsecond_hourly_scheduler_drift():
    now = local_time(2026, 7, 12, 8).replace(second=1)  # Sunday, outside hot window
    plan = ssq_remote_sync_poll_plan(
        now=now,
        last_attempt_at=local_time(2026, 7, 12, 7).replace(second=2),
        last_status="success",
    )

    assert plan["elapsed_minutes"] == 59.983
    assert plan["due"] is True
    assert plan["reason"] == "cold_poll_interval_elapsed"
    assert plan["cold_poll_boundary_tolerance_seconds"] == 60


def test_remote_sync_poll_does_not_apply_boundary_tolerance_too_early():
    now = local_time(2026, 7, 11, 18, 20)
    plan = ssq_remote_sync_poll_plan(
        now=now,
        last_attempt_at=now - timedelta(minutes=58, seconds=59),
        last_status="success",
    )

    assert plan["due"] is False
    assert plan["reason"] == "cold_poll_interval_not_elapsed"
    assert plan["retry_after_minutes"] == 1.017


def test_remote_sync_poll_retries_failed_attempt_without_backoff():
    now = local_time(2026, 7, 11, 18, 20)
    plan = ssq_remote_sync_poll_plan(
        now=now,
        last_attempt_at=now - timedelta(minutes=1),
        last_status="failed",
    )

    assert plan["due"] is True
    assert plan["reason"] == "retry_non_successful_sync"


def test_remote_sync_poll_does_not_compete_with_recent_running_attempt():
    now = local_time(2026, 7, 12, 21, 20)
    plan = ssq_remote_sync_poll_plan(
        now=now,
        last_attempt_at=now - timedelta(minutes=5),
        last_status="running",
    )

    assert plan["due"] is False
    assert plan["reason"] == "recent_sync_attempt_still_running"
    assert plan["running_grace_minutes"] == 30


def test_remote_sync_poll_fails_open_to_due_on_clock_invariant_error():
    now = datetime(2026, 7, 11, 10, 20, tzinfo=timezone.utc)
    plan = ssq_remote_sync_poll_plan(
        now=now,
        last_attempt_at=now + timedelta(minutes=1),
        last_status="success",
    )

    assert plan["due"] is True
    assert plan["reason"] == "sync_clock_invariant_failed"
