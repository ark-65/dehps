from __future__ import annotations

from typing import Any

from dehps.draw_sync.models import DrawSyncStatus
from dehps.draw_sync.service import DrawSyncService


class Repository:
    def __init__(self) -> None:
        self.draws = [("2026079", (1, 2, 3, 4, 5, 6), 7)]
        self.runs = []
        self.events = []

    def ensure_schema(self) -> None:
        return None

    def latest_issue(self) -> str | None:
        return max((issue for issue, _, _ in self.draws), default=None)

    def load_audit_draws(self):
        return tuple(self.draws)

    def record_run(self, result):
        self.runs.append(result)
        return result

    def upsert_event(self, event):
        self.events.append(event)
        return event


class Synchronizer:
    def __init__(self, repository: Repository, *, append_new_issue: bool) -> None:
        self.repository = repository
        self.append_new_issue = append_new_issue
        self.calls: list[dict[str, Any]] = []

    def sync(self, **kwargs):
        self.calls.append(kwargs)
        if self.append_new_issue:
            self.repository.draws.append(("2026080", (3, 8, 12, 18, 25, 33), 16))
            return {"inserted_count": 1, "updated_count": 0, "inserted_issues": ["2026080"]}
        return {"inserted_count": 0, "updated_count": 0}


def test_draw_sync_builds_audited_event_for_new_issue() -> None:
    repository = Repository()
    synchronizer = Synchronizer(repository, append_new_issue=True)
    service = DrawSyncService(repository=repository, synchronizer=synchronizer)  # type: ignore[arg-type]

    result = service.once(run_key="test-run")

    assert result.status == DrawSyncStatus.NEW_ISSUE
    assert result.previous_latest_issue == "2026079"
    assert result.current_latest_issue == "2026080"
    assert result.audit_passed is True
    assert result.event_key == repository.events[0].event_key
    assert synchronizer.calls[0]["from_issue"] == "2026079"


def test_draw_sync_records_no_change_without_event() -> None:
    repository = Repository()
    synchronizer = Synchronizer(repository, append_new_issue=False)
    service = DrawSyncService(repository=repository, synchronizer=synchronizer)  # type: ignore[arg-type]

    result = service.once(run_key="test-run")

    assert result.status == DrawSyncStatus.NO_CHANGE
    assert result.event_key is None
    assert repository.events == []
