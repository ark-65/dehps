from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from dehps.agents.roles import AgentRole


@dataclass(frozen=True)
class AgentRequestDecision:
    id: int
    request_id: int
    previous_status: str
    new_status: str
    decision_code: str
    summary: str
    reason: dict[str, Any]
    decided_by_role: AgentRole
    decided_by: str
    decided_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason_code: str
    summary: str
    constraints: tuple[str, ...] = field(default_factory=tuple)
