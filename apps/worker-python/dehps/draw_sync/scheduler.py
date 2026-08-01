from __future__ import annotations

import argparse
import json
import math
import os
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import time as day_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.draw_sync.launch_contract import (
    build_draw_sync_watch_launch_contract,
    write_draw_sync_watch_launch_contract,
)
from dehps.draw_sync.models import jsonable
from dehps.draw_sync.service import DrawSyncService
from dehps.forward_runtime.shadow_attestation import (
    ForwardShadowAttestationService,
    forward_shadow_attestation_enabled,
)
from dehps.notifications.post_draw_evaluation import (
    deliver_post_draw_evaluation_report,
)
from dehps.prediction.v2.retirement import legacy_retirement_status
from dehps.scoring_kernel import seal_shadow_watch_cycle
from dehps.source_version import resolve_git_commit

DEFAULT_STATE_PATH = ROOT_DIR / "runtime" / "logs" / "draw-sync-watch.json"
DEFAULT_PID_PATH = ROOT_DIR / "runtime" / "logs" / "draw-sync-watch.pid"
DEFAULT_VERSION_PATH = ROOT_DIR / "runtime" / "logs" / "draw-sync-watch.version"
DEFAULT_LAUNCH_CONTRACT_PATH = (
    ROOT_DIR / "runtime" / "logs" / "draw-sync-watch.launch.json"
)


@dataclass(frozen=True)
class DrawSyncSchedulePolicy:
    interval_seconds: int = 900
    hot_interval_seconds: int = 300
    cold_interval_seconds: int = 3600
    timezone: str = "Asia/Shanghai"

    def deferred_until(self, moment: datetime | None = None) -> datetime | None:
        tz = ZoneInfo(self.timezone)
        local = (moment or datetime.now(tz)).astimezone(tz)
        is_draw_day = local.weekday() in {1, 3, 6}
        draw_time = day_time(21, 15)
        update_time = day_time(21, 45)
        if is_draw_day and draw_time <= local.time() < update_time:
            return local.replace(
                hour=update_time.hour,
                minute=update_time.minute,
                second=0,
                microsecond=0,
            )
        return None

    def next_interval(self, moment: datetime | None = None) -> int:
        tz = ZoneInfo(self.timezone)
        local = (moment or datetime.now(tz)).astimezone(tz)
        deferred_until = self.deferred_until(local)
        if deferred_until is not None:
            return max(1, math.ceil((deferred_until - local).total_seconds()))
        # Draws are scheduled at 21:15; remote update polling accelerates at 21:45.
        is_draw_day = local.weekday() in {1, 3, 6}
        hot_start = day_time(21, 45)
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
        forward_evaluator: Any | None = None,
        policy: DrawSyncSchedulePolicy | None = None,
        resume_on_event: bool = False,
        state_path: Path = DEFAULT_STATE_PATH,
        pid_path: Path = DEFAULT_PID_PATH,
        version_path: Path | None = None,
        launch_contract_path: Path | None = None,
        code_commit: str | None = None,
        clock: Callable[[], datetime] | None = None,
        shadow_attestor: Any | None = None,
        shadow_attestation_enabled: bool | None = None,
        post_draw_report_notifier: Callable[[str], dict[str, Any]] | None = None,
        prediction_v2_shadow_notifier: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.service = service or DrawSyncService()
        if forward_evaluator is None:
            from dehps.forward_runtime.evaluation_service import (
                ForwardEvaluationService,
            )

            forward_evaluator = ForwardEvaluationService()
        self.forward_evaluator = forward_evaluator
        self.policy = policy or DrawSyncSchedulePolicy()
        self.resume_on_event = resume_on_event
        self.state_path = state_path
        self.pid_path = pid_path
        if version_path is not None:
            self.version_path = version_path
        elif pid_path == DEFAULT_PID_PATH:
            self.version_path = DEFAULT_VERSION_PATH
        else:
            self.version_path = pid_path.with_suffix(".version")
        if launch_contract_path is not None:
            self.launch_contract_path = launch_contract_path
        elif pid_path == DEFAULT_PID_PATH:
            self.launch_contract_path = DEFAULT_LAUNCH_CONTRACT_PATH
        else:
            self.launch_contract_path = pid_path.with_suffix(".launch.json")
        self.code_commit = code_commit or resolve_git_commit()
        self._clock = clock or (lambda: datetime.now(ZoneInfo(self.policy.timezone)))
        self.started_at = self._clock().isoformat()
        self.shadow_attestation_enabled = (
            forward_shadow_attestation_enabled()
            if shadow_attestation_enabled is None
            else bool(shadow_attestation_enabled)
        )
        self.shadow_attestor = (
            shadow_attestor
            if shadow_attestor is not None
            else (
                ForwardShadowAttestationService()
                if self.shadow_attestation_enabled
                else None
            )
        )
        self.post_draw_report_notifier = post_draw_report_notifier
        self.prediction_v2_shadow_notifier = prediction_v2_shadow_notifier
        self.launch_contract = build_draw_sync_watch_launch_contract(
            code_commit=self.code_commit,
            interval_seconds=self.policy.interval_seconds,
            hot_interval_seconds=self.policy.hot_interval_seconds,
            cold_interval_seconds=self.policy.cold_interval_seconds,
            timezone=self.policy.timezone,
            resume_on_event=self.resume_on_event,
            shadow_attestation_enabled=self.shadow_attestation_enabled,
        )
        self._stopping = False

    def run(self, *, once: bool = False) -> None:
        self.pid_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.pid_path, f"{os.getpid()}\n")
        atomic_write_text(self.version_path, f"{self.code_commit}\n")
        write_draw_sync_watch_launch_contract(
            self.launch_contract_path,
            self.launch_contract,
        )
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        while not self._stopping:
            started = self._clock()
            try:
                deferred_until = self.policy.deferred_until(started)
                if deferred_until is None:
                    result = self.service.once()
                    event_key = result.event_key
                else:
                    result = {
                        "status": "deferred_until_update_window",
                        "deferred_until": deferred_until.isoformat(),
                    }
                    event_key = None
                legacy_retired = legacy_retirement_status()["status"] == "ACTIVE"
                evaluation_result = (
                    {
                        "status": "skipped",
                        "failed_count": 0,
                        "reason": "legacy_prediction_lines_frozen",
                    }
                    if legacy_retired
                    else self.forward_evaluator.evaluate_pending()
                )
                evaluation_failed = int(evaluation_result.get("failed_count") or 0) > 0
                result_payload = jsonable(result)
                result_payload = result_payload if isinstance(result_payload, dict) else {}
                current_issue = str(result_payload.get("current_latest_issue") or "").strip()
                post_draw_evaluation_mail = (
                    {
                        "status": "skipped",
                        "issue": current_issue or None,
                        "reason": "legacy_prediction_lines_frozen",
                    }
                    if legacy_retired
                    else self._notify_post_draw_report(
                        current_issue=current_issue or None,
                        evaluation_failed=evaluation_failed,
                    )
                )
                prediction_v2_shadow_report = (
                    self._notify_prediction_v2_shadow(current_issue=current_issue or None)
                    if legacy_retired
                    else {
                        "status": "inactive",
                        "issue": current_issue or None,
                        "reason": "legacy retirement activation not published",
                    }
                )
                shadow_watch_cycle = None
                shadow_attestation = {
                    "protocol": "forward-shadow-attestation-closure.v1",
                    "status": "disabled",
                    "automatic_promotion_allowed": False,
                }
                if (
                    not legacy_retired
                    and self.shadow_attestation_enabled
                    and self.shadow_attestor is not None
                ):
                    shadow_watch_cycle = seal_shadow_watch_cycle(
                        watch_code_commit=self.code_commit,
                        watch_started_at=self.started_at,
                        observed_at=self._clock().isoformat(),
                        sync_status=str(result_payload.get("status") or "unknown"),
                        sync_audit_passed=result_payload.get("audit_passed") is True,
                        current_latest_issue=result_payload.get("current_latest_issue"),
                        evaluation_batch_status=str(
                            evaluation_result.get("status") or "unknown"
                        ),
                        evaluation_failed_count=int(
                            evaluation_result.get("failed_count") or 0
                        ),
                    )
                    try:
                        shadow_attestation = self.shadow_attestor.close_cycle(
                            shadow_watch_cycle
                        )
                    except Exception as exc:  # shadow evidence cannot replace official evaluation.
                        details = getattr(exc, "as_dict", None)
                        shadow_attestation = {
                            "protocol": "forward-shadow-attestation-closure.v1",
                            "status": "failed",
                            "failed_count": 1,
                            "error": (
                                details()
                                if callable(details)
                                else {"type": type(exc).__name__, "message": str(exc)}
                            ),
                            "automatic_promotion_allowed": False,
                        }
                resume_result = (
                    None
                    if evaluation_failed or legacy_retired
                    else self._resume_if_event(event_key)
                )
                payload = {
                    "status": "error" if evaluation_failed else "ok",
                    "pid": os.getpid(),
                    "watch_code_commit": self.code_commit,
                    "watch_started_at": self.started_at,
                    "launch_contract": self.launch_contract,
                    "heartbeat_at": self._clock().isoformat(),
                    "last_result": result,
                    "sync_deferred": deferred_until is not None,
                    "forward_evaluation": evaluation_result,
                    "legacy_prediction_lines": {
                        "status": "LEGACY_FROZEN" if legacy_retired else "ACTIVE",
                        "compute_scheduled": not legacy_retired,
                    },
                    "post_draw_evaluation_mail": post_draw_evaluation_mail,
                    "prediction_v2_shadow_report": prediction_v2_shadow_report,
                    "shadow_watch_cycle": shadow_watch_cycle,
                    "shadow_attestation": shadow_attestation,
                    "resume_on_event": self.resume_on_event,
                    "resume_result": resume_result,
                    "error": (
                        {
                            "type": "ForwardEvaluationBatchFailed",
                            "message": "pending forward evaluation failed; training resume withheld",
                        }
                        if evaluation_failed
                        else None
                    ),
                    "next_interval_seconds": self.policy.next_interval(self._clock()),
                }
            except Exception as exc:  # fail closed: record but keep the watch process alive.
                payload = {
                    "status": "error",
                    "pid": os.getpid(),
                    "watch_code_commit": self.code_commit,
                    "watch_started_at": self.started_at,
                    "heartbeat_at": self._clock().isoformat(),
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                    "next_interval_seconds": self.policy.next_interval(self._clock()),
                }
            atomic_write_text(self.state_path, json.dumps(jsonable(payload), ensure_ascii=False, indent=2))
            if once:
                return
            current = self._clock()
            elapsed = (current - started).total_seconds()
            sleep_seconds = max(1.0, self.policy.next_interval(current) - elapsed)
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

    def _notify_post_draw_report(
        self,
        *,
        current_issue: str | None,
        evaluation_failed: bool,
    ) -> dict[str, Any]:
        if self.post_draw_report_notifier is None:
            return {"status": "disabled"}
        if evaluation_failed:
            return {
                "status": "withheld",
                "issue": current_issue,
                "reason": "forward evaluation batch failed",
            }
        if current_issue is None:
            return {
                "status": "not_ready",
                "reason": "draw sync did not identify a current latest issue",
            }
        try:
            return self.post_draw_report_notifier(current_issue)
        except Exception as exc:  # noqa: BLE001 - failure is isolated from durable sync.
            return {
                "status": "failed",
                "issue": current_issue,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }

    def _notify_prediction_v2_shadow(
        self,
        *,
        current_issue: str | None,
    ) -> dict[str, Any]:
        if self.prediction_v2_shadow_notifier is None:
            return {"status": "disabled", "issue": current_issue}
        if current_issue is None:
            return {"status": "not_ready", "reason": "draw sync has no current issue"}
        try:
            return self.prediction_v2_shadow_notifier(current_issue)
        except Exception as exc:  # noqa: BLE001 - failure is isolated from durable sync.
            # Notification/mainline failure must never replace a successful draw sync.
            return {
                "status": "failed",
                "issue": current_issue,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the independent DEHPS draw-sync watch.")
    parser.add_argument("--interval-seconds", type=int, default=900)
    parser.add_argument("--hot-interval-seconds", type=int, default=300)
    parser.add_argument("--cold-interval-seconds", type=int, default=3600)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--resume-on-event", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--post-draw-report-notifications",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--prediction-v2-shadow-notifications",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    args = parser.parse_args(argv)
    prediction_v2_notifier = None
    if args.prediction_v2_shadow_notifications:
        from scripts.run_prediction_v2_shadow_issue import settle_synchronized_issue

        prediction_v2_notifier = settle_synchronized_issue
    DrawSyncWatch(
        policy=DrawSyncSchedulePolicy(
            interval_seconds=args.interval_seconds,
            hot_interval_seconds=args.hot_interval_seconds,
            cold_interval_seconds=args.cold_interval_seconds,
            timezone=args.timezone,
        ),
        resume_on_event=bool(args.resume_on_event),
        post_draw_report_notifier=(
            deliver_post_draw_evaluation_report
            if args.post_draw_report_notifications
            else None
        ),
        prediction_v2_shadow_notifier=prediction_v2_notifier,
    ).run(once=args.once)
