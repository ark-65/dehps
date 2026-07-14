from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WaitingSupervisorState:
    status: str
    old_run_id: str | None
    history_latest_issue: str | None
    pending_issue: str | None
    pid: int | None
    process_active: bool
    history_fingerprint: str | None
    source: dict[str, Any]


@dataclass(frozen=True)
class ForwardReconcileDecision:
    resume_allowed: bool
    reason_code: str
    previous_pending_issue: str | None
    observed_issue: str | None
    forward_count_before: int
    forward_count_after: int
    event_key: str | None
    old_run_id: str | None = None
    blockers: tuple[str, ...] = ()
