from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any


ROUND30_SCHEMA_VERSION = "continuous-research-runtime-v1"


class ResearchRuntimeStatus(str, Enum):
    RESEARCH_RUNNING = "research_running"
    RESEARCH_SLEEP = "research_sleep"
    RESEARCH_BUDGET_EXHAUSTED = "research_budget_exhausted"
    RESEARCH_WAITING_RESOURCES = "research_waiting_resources"


class ResearchCycleStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceSource(str, Enum):
    RESEARCH = "research"
    FORWARD = "forward"


@dataclass(frozen=True)
class HistorySnapshot:
    snapshot_key: str
    latest_issue: str | None
    issue_count: int
    history_fingerprint: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "ssq_history"


@dataclass(frozen=True)
class SnapshotRotationDecision:
    rotate: bool
    reason_code: str
    active_snapshot_key: str | None
    candidate_snapshot_key: str
    active_latest_issue: str | None
    candidate_latest_issue: str | None
    defer_until_cycle_complete: bool


@dataclass(frozen=True)
class ResearchRuntimeBudget:
    research_cpu: int = 12
    forward_cpu: int = 4
    total_memory_gb: int = 20
    research_memory_gb: int = 18
    forward_memory_gb: int = 2
    daily_cycle_limit: int = 100
    cycles_used: int = 0

    def validate(self) -> None:
        if self.research_cpu < 1:
            raise ValueError("research_cpu must be at least 1")
        if self.forward_cpu < 0:
            raise ValueError("forward_cpu must be non-negative")
        if self.research_memory_gb < 1:
            raise ValueError("research_memory_gb must be at least 1")
        if self.forward_memory_gb < 0:
            raise ValueError("forward_memory_gb must be non-negative")
        if self.research_memory_gb + self.forward_memory_gb > self.total_memory_gb:
            raise ValueError("research and forward memory budgets exceed total memory")
        if self.cycles_used < 0 or self.daily_cycle_limit < 0:
            raise ValueError("cycle counters must be non-negative")

    @property
    def research_available(self) -> bool:
        return self.research_cpu > 0 and self.research_memory_gb > 0 and self.cycles_used < self.daily_cycle_limit

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchRuntimeQueueItem:
    queue_key: str
    action: str
    status: str
    snapshot_key: str
    history_fingerprint: str
    evidence_source: EvidenceSource = EvidenceSource.RESEARCH
    priority_score: float = 0.5
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ResearchCycleResult:
    cycle_key: str
    status: ResearchCycleStatus
    runtime_status: ResearchRuntimeStatus
    snapshot: HistorySnapshot
    queue_item: ResearchRuntimeQueueItem | None
    scheduler_result: Any | None
    rotation: SnapshotRotationDecision
    budget: ResearchRuntimeBudget
    evidence_source: EvidenceSource = EvidenceSource.RESEARCH
    warnings: tuple[str, ...] = ()


def jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(item) for item in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return sha256(stable_json(value).encode("utf-8")).hexdigest()
