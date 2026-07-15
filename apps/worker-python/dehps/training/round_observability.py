from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any


StatusPublisher = Callable[[], None]
LogWriter = Callable[[str], None]


class RoundStageTracker:
    """Publish non-destructive stage telemetry for one training round at a time."""

    def __init__(
        self,
        *,
        status: dict[str, Any],
        publish: StatusPublisher,
        log: LogWriter,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._status = status
        self._publish = publish
        self._log = log
        self._monotonic = monotonic
        self._now = now
        self._stage_started_monotonic: float | None = None

    def transition(
        self,
        stage: str,
        *,
        round_index: int,
        active_workers: int,
        generated_config_count: int | None = None,
        selected_config_count: int | None = None,
        target_completed: int | None = None,
        target_total: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = self._now().isoformat(timespec="seconds")
        current = self._status.get("round_execution")
        completed_stages: list[dict[str, Any]] = []
        if isinstance(current, dict) and int(current.get("round") or 0) == round_index:
            completed_stages = list(current.get("completed_stages") or [])
            prior_stage = current.get("stage")
            if prior_stage and self._stage_started_monotonic is not None:
                completed_stages.append(
                    {
                        "stage": prior_stage,
                        "elapsed_seconds": round(
                            max(0.0, self._monotonic() - self._stage_started_monotonic),
                            3,
                        ),
                        "completed_at": now,
                        "active_workers": current.get("active_workers"),
                        "generated_config_count": current.get("generated_config_count"),
                        "selected_config_count": current.get("selected_config_count"),
                        "target_progress": current.get("target_progress"),
                    }
                )
        self._stage_started_monotonic = self._monotonic()
        payload: dict[str, Any] = {
            "round": round_index,
            "stage": stage,
            "status": "running",
            "active_workers": max(0, int(active_workers)),
            "generated_config_count": generated_config_count,
            "selected_config_count": selected_config_count,
            "target_progress": {
                "completed": target_completed,
                "total": target_total,
            },
            "stage_started_at": now,
            "updated_at": now,
            "completed_stages": completed_stages,
            "details": details or {},
        }
        self._status["round_execution"] = payload
        self._log(
            "training_stage "
            f"round={round_index} stage={stage} active_workers={payload['active_workers']} "
            f"configs={generated_config_count}->{selected_config_count} "
            f"targets={target_completed}/{target_total}"
        )
        self._publish()
        return payload

    def update_target_progress(
        self,
        *,
        completed: int,
        total: int,
        publish: bool = True,
    ) -> None:
        current = self._status.get("round_execution")
        if not isinstance(current, dict):
            return
        current["target_progress"] = {
            "completed": max(0, int(completed)),
            "total": max(0, int(total)),
        }
        current["updated_at"] = self._now().isoformat(timespec="seconds")
        if publish:
            self._publish()

    def complete(self, *, round_index: int) -> dict[str, Any]:
        current = self._status.get("round_execution")
        current = current if isinstance(current, dict) else {}
        target_progress = current.get("target_progress")
        target_progress = target_progress if isinstance(target_progress, dict) else {}
        payload = self.transition(
            "round_completed",
            round_index=round_index,
            active_workers=0,
            generated_config_count=current.get("generated_config_count"),
            selected_config_count=current.get("selected_config_count"),
            target_completed=target_progress.get("completed"),
            target_total=target_progress.get("total"),
        )
        payload["status"] = "completed"
        payload["completed_at"] = self._now().isoformat(timespec="seconds")
        payload["stage_elapsed_seconds"] = 0.0
        self._publish()
        return payload

    def fail(self, *, error: Exception) -> None:
        current = self._status.get("round_execution")
        if not isinstance(current, dict):
            return
        current["status"] = "failed"
        current["active_workers"] = 0
        current["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }
        current["updated_at"] = self._now().isoformat(timespec="seconds")
        self._publish()
