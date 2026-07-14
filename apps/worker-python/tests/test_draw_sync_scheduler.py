from datetime import datetime
from zoneinfo import ZoneInfo

from dehps.draw_sync.scheduler import DrawSyncSchedulePolicy


def test_draw_sync_scheduler_uses_hot_interval_on_draw_evening() -> None:
    policy = DrawSyncSchedulePolicy(interval_seconds=900, hot_interval_seconds=300, timezone="Asia/Shanghai")

    interval = policy.next_interval(datetime(2026, 7, 14, 21, 30, tzinfo=ZoneInfo("Asia/Shanghai")))

    assert interval == 300


def test_draw_sync_scheduler_defaults_to_cold_safe_interval() -> None:
    policy = DrawSyncSchedulePolicy(interval_seconds=900, hot_interval_seconds=300, timezone="Asia/Shanghai")

    interval = policy.next_interval(datetime(2026, 7, 15, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")))

    assert interval == 900
