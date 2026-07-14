from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dehps.draw_sync.audit import DrawDatabaseAuditor
from dehps.draw_sync.events import NewIssueEventBuilder
from dehps.draw_sync.issue_detector import NewIssueDetector
from dehps.draw_sync.lock import draw_sync_lock, is_locked_error
from dehps.draw_sync.models import DrawSyncResult, DrawSyncStatus, utc_now
from dehps.draw_sync.repository import DrawSyncRepository
from dehps.draw_sync.synchronizer import DrawSynchronizer, SsqDrawSynchronizer


class DrawSyncService:
    def __init__(
        self,
        *,
        repository: DrawSyncRepository | None = None,
        synchronizer: DrawSynchronizer | None = None,
        auditor: DrawDatabaseAuditor | None = None,
        detector: NewIssueDetector | None = None,
        event_builder: NewIssueEventBuilder | None = None,
    ) -> None:
        self.repository = repository or DrawSyncRepository()
        self.synchronizer = synchronizer or SsqDrawSynchronizer()
        self.auditor = auditor or DrawDatabaseAuditor()
        self.detector = detector or NewIssueDetector()
        self.event_builder = event_builder or NewIssueEventBuilder()

    def ensure_schema(self) -> None:
        self.repository.ensure_schema()

    def once(
        self,
        *,
        source: str = "zhcw",
        history: bool = True,
        csv_file: str | None = None,
        lock_timeout_seconds: float = 0,
        run_key: str | None = None,
    ) -> DrawSyncResult:
        self.ensure_schema()
        started = utc_now()
        run_key = run_key or f"draw-sync-{started.strftime('%Y%m%d-%H%M%S-%f')}"
        try:
            with draw_sync_lock(timeout_seconds=lock_timeout_seconds, context={"run_key": run_key}):
                return self._once_locked(
                    source=source,
                    history=history,
                    csv_file=csv_file,
                    run_key=run_key,
                    started=started,
                )
        except Exception as exc:
            if is_locked_error(exc):
                result = DrawSyncResult(
                    status=DrawSyncStatus.LOCKED,
                    previous_latest_issue=None,
                    current_latest_issue=None,
                    inserted_issues=(),
                    updated_issues=(),
                    audit_passed=False,
                    history_fingerprint_before=None,
                    history_fingerprint_after=None,
                    event_key=None,
                    warnings=("draw_sync_lock_held",),
                    run_key=run_key,
                    source=source,
                    error={"type": type(exc).__name__, "message": str(exc)},
                    started_at=started,
                    completed_at=utc_now(),
                )
                return self.repository.record_run(result)
            raise

    def _once_locked(
        self,
        *,
        source: str,
        history: bool,
        csv_file: str | None,
        run_key: str,
        started: datetime,
    ) -> DrawSyncResult:
        previous_issue = self.repository.latest_issue()
        before_audit = self.auditor.audit(self.repository.load_audit_draws())
        try:
            summary = self.synchronizer.sync(
                source=source,
                history=history,
                from_issue=previous_issue,
                to_issue=None,
                csv_file=csv_file,
                dry_run=False,
                run_key=run_key,
            )
        except ValueError as exc:
            return self._record_error(
                status=DrawSyncStatus.INVALID_RESPONSE,
                started=started,
                run_key=run_key,
                source=source,
                previous_issue=previous_issue,
                before_fingerprint=before_audit.history_fingerprint,
                exc=exc,
            )
        except Exception as exc:
            return self._record_error(
                status=DrawSyncStatus.SOURCE_UNAVAILABLE,
                started=started,
                run_key=run_key,
                source=source,
                previous_issue=previous_issue,
                before_fingerprint=before_audit.history_fingerprint,
                exc=exc,
            )
        current_issue = self.repository.latest_issue()
        after_audit = self.auditor.audit(self.repository.load_audit_draws())
        inserted = tuple(self._issues_from_summary(summary, "inserted_issues"))
        updated = tuple(self._issues_from_summary(summary, "updated_issues"))
        if not inserted and int(summary.get("inserted_count") or 0) > 0 and current_issue:
            inserted = (current_issue,)
        if not updated and int(summary.get("updated_count") or 0) > 0:
            updated = tuple()
        if not after_audit.passed:
            result = DrawSyncResult(
                status=DrawSyncStatus.AUDIT_FAILED,
                previous_latest_issue=previous_issue,
                current_latest_issue=current_issue,
                inserted_issues=inserted,
                updated_issues=updated,
                audit_passed=False,
                history_fingerprint_before=before_audit.history_fingerprint,
                history_fingerprint_after=after_audit.history_fingerprint,
                event_key=None,
                warnings=after_audit.warnings,
                run_key=run_key,
                source=source,
                audit_report_hash=after_audit.report_hash,
                started_at=started,
                completed_at=utc_now(),
            )
            return self.repository.record_run(result)
        status = self.detector.classify(
            previous_latest_issue=previous_issue,
            current_latest_issue=current_issue,
            inserted_issues=inserted,
            updated_issues=updated,
            fingerprint_before=before_audit.history_fingerprint,
            fingerprint_after=after_audit.history_fingerprint,
        )
        event_key = None
        if (
            status == DrawSyncStatus.NEW_ISSUE
            and previous_issue
            and current_issue
            and after_audit.history_fingerprint
            and before_audit.history_fingerprint != after_audit.history_fingerprint
        ):
            event = self.event_builder.build(
                previous_issue=previous_issue,
                new_issue=current_issue,
                history_fingerprint=after_audit.history_fingerprint,
                source=source,
                audit_report=after_audit,
            )
            self.repository.upsert_event(event)
            event_key = event.event_key
        result = DrawSyncResult(
            status=status,
            previous_latest_issue=previous_issue,
            current_latest_issue=current_issue,
            inserted_issues=inserted,
            updated_issues=updated,
            audit_passed=True,
            history_fingerprint_before=before_audit.history_fingerprint,
            history_fingerprint_after=after_audit.history_fingerprint,
            event_key=event_key,
            warnings=after_audit.warnings,
            run_key=run_key,
            source=source,
            audit_report_hash=after_audit.report_hash,
            started_at=started,
            completed_at=utc_now(),
        )
        return self.repository.record_run(result)

    def _record_error(
        self,
        *,
        status: DrawSyncStatus,
        started: datetime,
        run_key: str,
        source: str,
        previous_issue: str | None,
        before_fingerprint: str | None,
        exc: Exception,
    ) -> DrawSyncResult:
        result = DrawSyncResult(
            status=status,
            previous_latest_issue=previous_issue,
            current_latest_issue=previous_issue,
            inserted_issues=(),
            updated_issues=(),
            audit_passed=False,
            history_fingerprint_before=before_fingerprint,
            history_fingerprint_after=before_fingerprint,
            event_key=None,
            warnings=(status.value,),
            run_key=run_key,
            source=source,
            error={"type": type(exc).__name__, "message": str(exc)},
            started_at=started,
            completed_at=utc_now(),
        )
        return self.repository.record_run(result)

    def status(self) -> dict[str, Any]:
        self.ensure_schema()
        return self.repository.status()

    def events(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        self.ensure_schema()
        return {"events": self.repository.list_events(limit=limit, offset=offset), "limit": limit, "offset": offset}

    def runs(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        self.ensure_schema()
        return {"runs": self.repository.list_runs(limit=limit, offset=offset), "limit": limit, "offset": offset}

    @staticmethod
    def _issues_from_summary(summary: dict[str, Any], key: str) -> list[str]:
        value = summary.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
        return []
