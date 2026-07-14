from __future__ import annotations

import argparse
import json
import os
import signal
import time
from dataclasses import dataclass
from datetime import datetime, time as day_time
from pathlib import Path
from zoneinfo import ZoneInfo

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.draw_sync.models import jsonable
from dehps.draw_sync.service import DrawSyncService


DEFAULT_STATE_PATH = ROOT_DIR / "runtime" / "logs" / "draw-sync-watch.json"
DEFAULT_PID_PATH = ROOT_DIR / "runtime" / "logs" / "draw-sync-watch.pid"


@dataclass(frozen=True)
class DrawSyncSchedulePolicy:
    interval_seconds: int = 900
    hot_interval_seconds: int = 300
    cold_interval_seconds: int = 3600
    timezone: str = "Asia/Shanghai"

    def next_interval(self, moment: datetime | None = None) -> int:
        tz = ZoneInfo(self.timezone)
        local = (moment or datetime.now(tz)).astimezone(tz)
        # 双色球 official draw days: Tuesday, Thursday, Sunday around 21:15.
        is_draw_day = local.weekday() in {1, 3, 6}
        hot_start = day_time(20, 45)
        hot_end = day_time(23, 59, 59)
        recovery_end = day_time(2, 0)
        if is_draw_day and hot_start <= local.time() <= hot_end:
            return max(300, int(self.hot_interval_seconds))
        if local.time() <= recovery_end:
            return max(300, int(self.hot_interval_seconds))
        return max(900, int(self.interval_seconds or self.cold_interval_seconds))


class DrawSyncWatch:
    def __init__(
        self,
        *,
        service: DrawSyncService | None = None,
        policy: DrawSyncSchedulePolicy | None = None,
        resume_on_event: bool = False,
        state_path: Path = DEFAULT_STATE_PATH,
        pid_path: Path = DEFAULT_PID_PATH,
    ) -> None:
        self.service = service or DrawSyncService()
        self.policy = policy or DrawSyncSchedulePolicy()
        self.resume_on_event = resume_on_event
        self.state_path = state_path
        self.pid_path = pid_path
        self._stopping = False

    def run(self, *, once: bool = False) -> None:
        self.pid_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.pid_path, f"{os.getpid()}\n")
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        while not self._stopping:
            started = datetime.now(ZoneInfo(self.policy.timezone))
            try:
                result = self.service.once()
                resume_result = self._resume_if_event(result.event_key)
                payload = {
                    "status": "ok",
                    "pid": os.getpid(),
                    "heartbeat_at": datetime.now(ZoneInfo(self.policy.timezone)).isoformat(),
                    "last_result": result,
                    "resume_on_event": self.resume_on_event,
                    "resume_result": resume_result,
                    "next_interval_seconds": self.policy.next_interval(),
                }
            except Exception as exc:  # fail closed: record but keep the watch process alive.
                payload = {
                    "status": "error",
                    "pid": os.getpid(),
                    "heartbeat_at": datetime.now(ZoneInfo(self.policy.timezone)).isoformat(),
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                    "next_interval_seconds": self.policy.next_interval(),
                }
            atomic_write_text(self.state_path, json.dumps(jsonable(payload), ensure_ascii=False, indent=2))
            if once:
                return
            elapsed = (datetime.now(ZoneInfo(self.policy.timezone)) - started).total_seconds()
            sleep_seconds = max(1.0, self.policy.next_interval() - elapsed)
            self._sleep(sleep_seconds)

    def _stop(self, *_args: object) -> None:
        self._stopping = True

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not self._stopping and time.monotonic() < deadline:
            time.sleep(min(1.0, deadline - time.monotonic()))

    def _resume_if_event(self, event_key: str | None) -> dict[str, object] | None:
        if not self.resume_on_event or not event_key:
            return None
        from dehps.training_resume.service import TrainingResumeService

        return TrainingResumeService().execute(event_key=event_key)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the independent DEHPS draw-sync watch.")
    parser.add_argument("--interval-seconds", type=int, default=900)
    parser.add_argument("--hot-interval-seconds", type=int, default=300)
    parser.add_argument("--cold-interval-seconds", type=int, default=3600)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--resume-on-event", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args(argv)
    DrawSyncWatch(
        policy=DrawSyncSchedulePolicy(
            interval_seconds=args.interval_seconds,
            hot_interval_seconds=args.hot_interval_seconds,
            cold_interval_seconds=args.cold_interval_seconds,
            timezone=args.timezone,
        ),
        resume_on_event=bool(args.resume_on_event),
    ).run(once=args.once)
