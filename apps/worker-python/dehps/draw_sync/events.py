from __future__ import annotations

from dehps.draw_sync.models import (
    DrawAuditReport,
    NewIssueAvailableEvent,
    new_issue_event_key,
    utc_now,
)


class NewIssueEventBuilder:
    def build(
        self,
        *,
        previous_issue: str,
        new_issue: str,
        history_fingerprint: str,
        source: str,
        audit_report: DrawAuditReport,
    ) -> NewIssueAvailableEvent:
        key = new_issue_event_key(
            previous_issue=previous_issue,
            new_issue=new_issue,
            history_fingerprint=history_fingerprint,
            audit_report_hash=audit_report.report_hash,
            source=source,
        )
        return NewIssueAvailableEvent(
            event_key=key,
            previous_issue=previous_issue,
            new_issue=new_issue,
            history_fingerprint=history_fingerprint,
            synced_at=utc_now(),
            source=source,
            audit_report_hash=audit_report.report_hash,
        )
