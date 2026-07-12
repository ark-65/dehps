from __future__ import annotations

from scripts.training_watch_forward_wait_guard import (
    ForwardWaitDecision,
    forward_wait_decision_from_watch_summary,
)


def wait_ready_summary() -> dict:
    return {
        "run_id": "run-1",
        "action": "await_new_forward_issue",
        "db_read_errors": [],
        "forward_wait": {
            "ready": True,
            "status": "awaiting_new_forward_issue",
            "action": "park_same_history_training",
            "history_latest_issue": "2026078",
            "next_pending_issue": "2026079",
            "adaptive_hypothesis_generation_counted": False,
            "sequential_search_multiplicity_counted": False,
            "selection_changed": False,
            "promotion_allowed": False,
        },
        "supervisor_round_boundary": {
            "status": "target_complete_round_recorded",
        },
        "supervisor_status": {
            "available": True,
            "pid": 12345,
            "latest_progress": {"fresh": True},
        },
        "heavy_job_supervisor_relation": {
            "status": "same_supervisor_pid",
            "supervisor_pid": 12345,
            "heavy_job_pid": 12345,
            "heavy_job_owner": "training-supervisor",
            "heavy_job_active": True,
            "same_pid": True,
        },
    }


def test_forward_wait_guard_accepts_future_issue_at_durable_boundary():
    decision = forward_wait_decision_from_watch_summary(
        wait_ready_summary(),
        expected_pid=12345,
    )

    assert decision == ForwardWaitDecision(
        True,
        "watch_forward_wait_ready:2026078->2026079",
    )


def test_forward_wait_guard_accepts_parked_process_without_pid_check():
    summary = wait_ready_summary()
    summary["supervisor_status"] = {"available": True, "pid": 99999}
    summary["heavy_job_supervisor_relation"] = {
        "status": "different_inactive_pid",
        "heavy_job_active": False,
    }

    decision = forward_wait_decision_from_watch_summary(summary)

    assert decision.should_wait is True


def test_forward_wait_guard_uses_pid_relation_not_owner_label():
    summary = wait_ready_summary()
    summary["heavy_job_supervisor_relation"]["heavy_job_owner"] = "legacy-label"

    decision = forward_wait_decision_from_watch_summary(
        summary,
        expected_pid=12345,
    )

    assert decision.should_wait is True


def test_forward_wait_guard_rejects_different_active_pid_relation():
    summary = wait_ready_summary()
    summary["heavy_job_supervisor_relation"].update(
        {
            "status": "different_active_pid",
            "heavy_job_pid": 54321,
            "same_pid": False,
        }
    )

    decision = forward_wait_decision_from_watch_summary(
        summary,
        expected_pid=12345,
    )

    assert decision.should_wait is False
    assert "heavy_job_relation" in decision.reason
    assert "heavy_job_same_pid" in decision.reason
    assert "heavy_job_pid" in decision.reason


def test_forward_wait_guard_rejects_missing_pid_relation():
    summary = wait_ready_summary()
    summary.pop("heavy_job_supervisor_relation")

    decision = forward_wait_decision_from_watch_summary(
        summary,
        expected_pid=12345,
    )

    assert decision.should_wait is False
    assert "heavy_job_relation" in decision.reason
    assert "heavy_job_active" in decision.reason


def test_forward_wait_guard_rejects_pending_issue_already_synced():
    summary = wait_ready_summary()
    summary["forward_wait"]["history_latest_issue"] = "2026079"

    decision = forward_wait_decision_from_watch_summary(summary)

    assert decision.should_wait is False
    assert "future_issue" in decision.reason


def test_forward_wait_guard_rejects_non_durable_round_boundary():
    summary = wait_ready_summary()
    summary["supervisor_round_boundary"]["status"] = (
        "target_complete_waiting_round_result"
    )

    decision = forward_wait_decision_from_watch_summary(
        summary,
        expected_pid=12345,
    )

    assert decision.should_wait is False
    assert "durable_round_boundary" in decision.reason


def test_forward_wait_guard_request_only_allows_boundary_polling():
    summary = wait_ready_summary()
    summary["supervisor_round_boundary"]["status"] = "target_in_progress"

    decision = forward_wait_decision_from_watch_summary(
        summary,
        expected_pid=12345,
        require_durable_boundary=False,
    )

    assert decision.should_wait is True


def test_forward_wait_guard_rejects_safety_state_change():
    summary = wait_ready_summary()
    summary["forward_wait"]["promotion_allowed"] = True
    summary["forward_wait"]["sequential_search_multiplicity_counted"] = True

    decision = forward_wait_decision_from_watch_summary(summary)

    assert decision.should_wait is False
    assert "promotion_disabled" in decision.reason
    assert "sequential_risk_explicit" in decision.reason
