from __future__ import annotations

from dehps.draw_sync.models import DrawSyncStatus


def issue_int(value: str | None) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


class NewIssueDetector:
    def classify(
        self,
        *,
        previous_latest_issue: str | None,
        current_latest_issue: str | None,
        inserted_issues: tuple[str, ...],
        updated_issues: tuple[str, ...],
        fingerprint_before: str | None,
        fingerprint_after: str | None,
    ) -> DrawSyncStatus:
        if fingerprint_before and fingerprint_after and fingerprint_before == fingerprint_after:
            return DrawSyncStatus.NO_CHANGE
        previous = issue_int(previous_latest_issue)
        current = issue_int(current_latest_issue)
        if previous is not None and current is not None and current > previous and inserted_issues:
            return DrawSyncStatus.NEW_ISSUE
        if updated_issues:
            return DrawSyncStatus.CORRECTED_ISSUE
        return DrawSyncStatus.NO_CHANGE
