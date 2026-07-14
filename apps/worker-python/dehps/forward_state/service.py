from __future__ import annotations

from typing import Any

from dehps.forward_state.reconciler import ForwardStateReconciler


class ForwardStateService:
    def __init__(self, reconciler: ForwardStateReconciler | None = None) -> None:
        self.reconciler = reconciler or ForwardStateReconciler()

    def reconcile(self, *, event_key: str | None = None) -> dict[str, Any]:
        decision = self.reconciler.reconcile(event_key=event_key)
        return {"decision": decision}

    def status(self) -> dict[str, Any]:
        repo = self.reconciler.repository
        repo.ensure_schema()
        return {
            "waiting_supervisor": repo.waiting_supervisor_state(),
            "latest_issue": repo.latest_issue(),
            "pending_event": repo.latest_pending_event(),
            "consumed_forward_count": repo.consumed_forward_count(),
            "heavy_job_active": repo.heavy_job_active(),
        }
