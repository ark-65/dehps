from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


ROUND30_FORWARD_SCHEMA_VERSION = "forward-validation-runtime-v1"


class ForwardRuntimeStatus(str, Enum):
    FORWARD_WAITING = "forward_waiting"
    FORWARD_READY = "forward_ready"
    FORWARD_RUNNING = "forward_running"


class ForwardQueueAction(str, Enum):
    PENDING_FORWARD = "pending_forward"
    WAITING = "waiting"
    FORWARD_VALIDATION = "forward_validation"
    PROMOTION = "promotion"


@dataclass(frozen=True)
class ForwardRuntimeState:
    status: ForwardRuntimeStatus
    action: ForwardQueueAction
    pending_issue: str | None
    observed_issue: str | None
    event_key: str | None
    reason_code: str
    blockers: tuple[str, ...] = ()
    forward_evidence_source: str = "forward"
    promotion_allowed_from_research: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
