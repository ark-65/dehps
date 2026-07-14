from __future__ import annotations

from typing import Any

from dehps.forward_state.models import ForwardReconcileDecision
from dehps.forward_state.repository import ForwardStateRepository


def _issue_int(value: Any) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


class ForwardStateReconciler:
    def __init__(self, repository: ForwardStateRepository | None = None) -> None:
        self.repository = repository or ForwardStateRepository()

    def reconcile(self, *, event_key: str | None = None) -> ForwardReconcileDecision:
        self.repository.ensure_schema()
        event = self.repository.event_by_key(event_key) if event_key else self.repository.latest_pending_event()
        waiting = self.repository.waiting_supervisor_state()
        before = self.repository.consumed_forward_count()
        blockers: list[str] = []
        if event is None:
            return ForwardReconcileDecision(False, "no_pending_event", waiting.pending_issue, None, before, before, None)
        if event.get("status") not in {"pending", "failed"}:
            blockers.append(f"event_status_{event.get('status')}")
        observed_issue = str(event.get("new_issue") or "")
        pending_issue = waiting.pending_issue
        observed = _issue_int(observed_issue)
        pending = _issue_int(pending_issue)
        if observed is None or pending is None or observed < pending:
            blockers.append("observed_issue_before_pending_issue")
        if waiting.status != "waiting_for_forward_issue":
            blockers.append("supervisor_not_waiting_for_forward_issue")
        if waiting.process_active:
            blockers.append("old_supervisor_pid_active")
        if self.repository.heavy_job_active():
            blockers.append("active_heavy_job_lock")
        if not self.repository.current_main_allowed():
            blockers.append("current_ref_not_allowed_for_training_resume")
        if event.get("history_fingerprint") != self.repository.current_history_fingerprint():
            blockers.append("history_fingerprint_mismatch")
        if blockers:
            return ForwardReconcileDecision(
                False,
                blockers[0],
                pending_issue,
                observed_issue or None,
                before,
                before,
                str(event.get("event_key")),
                old_run_id=waiting.old_run_id,
                blockers=tuple(blockers),
            )
        return ForwardReconcileDecision(
            True,
            "new_forward_issue_available",
            pending_issue,
            observed_issue,
            before,
            before + 1,
            str(event.get("event_key")),
            old_run_id=waiting.old_run_id,
        )
