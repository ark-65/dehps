from __future__ import annotations

from dehps.forward_runtime.models import ForwardQueueAction, ForwardRuntimeState, ForwardRuntimeStatus
from dehps.forward_state.reconciler import ForwardStateReconciler


class ForwardValidationRuntime:
    """Forward validation remains allowed to WAIT; it never schedules research."""

    def __init__(self, reconciler: ForwardStateReconciler | None = None) -> None:
        self.reconciler = reconciler or ForwardStateReconciler()

    def status(self, *, event_key: str | None = None) -> ForwardRuntimeState:
        decision = self.reconciler.reconcile(event_key=event_key)
        if decision.resume_allowed:
            return ForwardRuntimeState(
                status=ForwardRuntimeStatus.FORWARD_READY,
                action=ForwardQueueAction.FORWARD_VALIDATION,
                pending_issue=decision.previous_pending_issue,
                observed_issue=decision.observed_issue,
                event_key=decision.event_key,
                reason_code=decision.reason_code,
                metadata={"decision": decision},
            )
        return ForwardRuntimeState(
            status=ForwardRuntimeStatus.FORWARD_WAITING,
            action=ForwardQueueAction.WAITING,
            pending_issue=decision.previous_pending_issue,
            observed_issue=decision.observed_issue,
            event_key=decision.event_key,
            reason_code=decision.reason_code,
            blockers=tuple(decision.blockers),
            metadata={"decision": decision},
        )
