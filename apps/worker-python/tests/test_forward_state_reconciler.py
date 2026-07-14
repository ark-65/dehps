from dehps.forward_state.models import WaitingSupervisorState
from dehps.forward_state.reconciler import ForwardStateReconciler


class Repository:
    def __init__(self, **overrides) -> None:
        self.event = {
            "event_key": "event-2026080",
            "status": "pending",
            "new_issue": "2026080",
            "history_fingerprint": "fp-after",
        }
        self.waiting = WaitingSupervisorState(
            status="waiting_for_forward_issue",
            old_run_id="old-run",
            history_latest_issue="2026079",
            pending_issue="2026080",
            pid=123,
            process_active=False,
            history_fingerprint=None,
            source={},
        )
        self.active_heavy = False
        self.main_allowed = True
        self.__dict__.update(overrides)

    def ensure_schema(self) -> None:
        return None

    def event_by_key(self, event_key):
        return self.event if self.event and self.event["event_key"] == event_key else None

    def latest_pending_event(self):
        return self.event

    def waiting_supervisor_state(self):
        return self.waiting

    def consumed_forward_count(self):
        return 2

    def heavy_job_active(self):
        return self.active_heavy

    def current_history_fingerprint(self):
        return "fp-after"

    def current_main_allowed(self):
        return self.main_allowed


def test_forward_reconciler_allows_audited_new_issue_at_pending_boundary() -> None:
    decision = ForwardStateReconciler(Repository()).reconcile()  # type: ignore[arg-type]

    assert decision.resume_allowed is True
    assert decision.reason_code == "new_forward_issue_available"
    assert decision.forward_count_after == 3


def test_forward_reconciler_blocks_without_waiting_supervisor() -> None:
    repository = Repository(
        waiting=WaitingSupervisorState(
            status="running",
            old_run_id="old-run",
            history_latest_issue="2026079",
            pending_issue="2026080",
            pid=123,
            process_active=False,
            history_fingerprint=None,
            source={},
        )
    )

    decision = ForwardStateReconciler(repository).reconcile()  # type: ignore[arg-type]

    assert decision.resume_allowed is False
    assert "supervisor_not_waiting_for_forward_issue" in decision.blockers


def test_forward_reconciler_blocks_on_unapproved_code_ref() -> None:
    decision = ForwardStateReconciler(Repository(main_allowed=False)).reconcile()  # type: ignore[arg-type]

    assert decision.resume_allowed is False
    assert "current_ref_not_allowed_for_training_resume" in decision.blockers
