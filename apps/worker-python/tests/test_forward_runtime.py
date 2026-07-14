from dehps.forward_runtime.models import ForwardQueueAction, ForwardRuntimeStatus
from dehps.forward_runtime.runtime import ForwardValidationRuntime
from dehps.forward_state.models import ForwardReconcileDecision


class Reconciler:
    def __init__(self, decision: ForwardReconcileDecision) -> None:
        self.decision = decision

    def reconcile(self, *, event_key=None):
        return self.decision


def test_forward_runtime_waits_without_blocking_research() -> None:
    runtime = ForwardValidationRuntime(
        Reconciler(ForwardReconcileDecision(False, "no_pending_event", "2026080", None, 1, 1, None))
    )

    state = runtime.status()

    assert state.status == ForwardRuntimeStatus.FORWARD_WAITING
    assert state.action == ForwardQueueAction.WAITING
    assert state.forward_evidence_source == "forward"
    assert state.promotion_allowed_from_research is False


def test_forward_runtime_becomes_ready_for_forward_validation_event() -> None:
    runtime = ForwardValidationRuntime(
        Reconciler(
            ForwardReconcileDecision(True, "new_forward_issue_available", "2026080", "2026080", 1, 2, "event")
        )
    )

    state = runtime.status()

    assert state.status == ForwardRuntimeStatus.FORWARD_READY
    assert state.action == ForwardQueueAction.FORWARD_VALIDATION
    assert state.event_key == "event"
