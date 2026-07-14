from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any


ROUND29_SCHEMA_VERSION = "draw-sync-training-resume-v1"


class DrawSyncStatus(str, Enum):
    NO_CHANGE = "no_change"
    NEW_ISSUE = "new_issue"
    CORRECTED_ISSUE = "corrected_issue"
    SOURCE_UNAVAILABLE = "source_unavailable"
    AUDIT_FAILED = "audit_failed"
    INVALID_RESPONSE = "invalid_response"
    LOCKED = "locked"


class DrawIssueEventStatus(str, Enum):
    PENDING = "pending"
    CONSUMING = "consuming"
    CONSUMED = "consumed"
    FAILED = "failed"
    INVALIDATED = "invalidated"


@dataclass(frozen=True)
class DrawAuditReport:
    passed: bool
    latest_issue: str | None
    history_fingerprint: str | None
    draw_count: int
    duplicate_issue_count: int
    invalid_red_length_count: int
    red_out_of_range_count: int
    duplicate_red_numbers_count: int
    blue_out_of_range_count: int
    issue_order_ok: bool
    warnings: tuple[str, ...] = ()

    @property
    def report_hash(self) -> str:
        return stable_hash(self)


@dataclass(frozen=True)
class DrawSyncResult:
    status: DrawSyncStatus
    previous_latest_issue: str | None
    current_latest_issue: str | None
    inserted_issues: tuple[str, ...]
    updated_issues: tuple[str, ...]
    audit_passed: bool
    history_fingerprint_before: str | None
    history_fingerprint_after: str | None
    event_key: str | None
    warnings: tuple[str, ...] = ()
    run_key: str | None = None
    source: str = "zhcw"
    error: dict[str, Any] | None = None
    audit_report_hash: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class NewIssueAvailableEvent:
    event_key: str
    previous_issue: str
    new_issue: str
    history_fingerprint: str
    synced_at: datetime
    source: str
    audit_report_hash: str
    status: DrawIssueEventStatus = DrawIssueEventStatus.PENDING
    consumed_at: datetime | None = None
    consumer_run_id: str | None = None


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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_issue_event_key(
    *,
    previous_issue: str,
    new_issue: str,
    history_fingerprint: str,
    audit_report_hash: str,
    source: str,
) -> str:
    digest = stable_hash(
        {
            "schema": ROUND29_SCHEMA_VERSION,
            "previous_issue": previous_issue,
            "new_issue": new_issue,
            "history_fingerprint": history_fingerprint,
            "audit_report_hash": audit_report_hash,
            "source": source,
        }
    )[:20]
    return f"draw-issue-{new_issue}-{digest}"
