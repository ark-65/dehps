from __future__ import annotations

from scripts.training_watch_restart_guard import (
    RestartDecision,
    restart_decision_from_watch_summary,
)


def restart_ready_summary(**overrides):
    summary = {
        "run_id": "run-1",
        "action": "prepare_restart_with_more_exploration",
        "restart_readiness": {
            "supervisor_run_id": "run-1",
            "status": "blocked_by_active_training_supervisor_lock",
            "operator_action": "operator_review_then_stop_continuous_training_supervisor_before_restart",
            "owner": "training-supervisor",
            "pid": 12345,
            "supervisor_pid": 12345,
            "supervisor_run_mode": "continuous",
            "supervisor_progress_fresh": True,
            "supervisor_target_complete": True,
            "restart_candidate_active": True,
            "restart_candidate_rank_vector_changed": True,
            "restart_candidate_changed_target_count": 100,
            "restart_candidate_full_eval_rank": 14,
            "restart_candidate_primary_score_improved": False,
            "restart_candidate_secondary_score_improved": True,
            "restart_candidate_improvement_basis": "secondary",
            "experimental_navigation_eligible": True,
            "experimental_navigation_quality_reason": "passed",
            "experimental_navigation_rank_vector_changed": True,
            "experimental_navigation_config_distance": 2.0982626296634663,
            "experimental_navigation_min_config_distance": 0.08,
        },
    }
    readiness_overrides = overrides.pop("restart_readiness", None)
    summary.update(overrides)
    if readiness_overrides:
        summary["restart_readiness"].update(readiness_overrides)
    return summary


def test_restart_decision_accepts_target_boundary_stop_action():
    decision = restart_decision_from_watch_summary(
        restart_ready_summary(),
        expected_pid=12345,
    )

    assert decision == RestartDecision(True, "watch_restart_ready_target_boundary")


def test_restart_decision_rejects_incomplete_target_boundary():
    decision = restart_decision_from_watch_summary(
        restart_ready_summary(
            restart_readiness={
                "operator_action": "wait_for_continuous_training_supervisor_target_boundary_before_restart",
                "supervisor_target_complete": False,
            }
        ),
        expected_pid=12345,
    )

    assert decision.should_restart is False
    assert "operator_action" in decision.reason
    assert "target_complete" in decision.reason


def test_restart_decision_rejects_mismatched_pid():
    decision = restart_decision_from_watch_summary(
        restart_ready_summary(),
        expected_pid=54321,
    )

    assert decision.should_restart is False
    assert "pid" in decision.reason


def test_restart_decision_rejects_mismatched_supervisor_status_pid():
    decision = restart_decision_from_watch_summary(
        restart_ready_summary(
            restart_readiness={
                "supervisor_pid": 99999,
            }
        ),
        expected_pid=12345,
    )

    assert decision.should_restart is False
    assert "supervisor_pid" in decision.reason


def test_restart_decision_rejects_mismatched_supervisor_status_run_id():
    decision = restart_decision_from_watch_summary(
        restart_ready_summary(
            restart_readiness={
                "supervisor_run_id": "old-run",
            }
        ),
        expected_pid=12345,
    )

    assert decision.should_restart is False
    assert "supervisor_run_id" in decision.reason


def test_restart_decision_rejects_stale_progress():
    decision = restart_decision_from_watch_summary(
        restart_ready_summary(
            restart_readiness={
                "supervisor_progress_fresh": False,
            }
        ),
        expected_pid=12345,
    )

    assert decision.should_restart is False
    assert "progress_fresh" in decision.reason


def test_restart_decision_rejects_missing_restart_candidate():
    decision = restart_decision_from_watch_summary(
        restart_ready_summary(
            restart_readiness={
                "restart_candidate_active": False,
            }
        ),
        expected_pid=12345,
    )

    assert decision.should_restart is False
    assert "restart_candidate" in decision.reason


def test_restart_decision_rejects_unchanged_restart_candidate_rank_vector():
    decision = restart_decision_from_watch_summary(
        restart_ready_summary(
            restart_readiness={
                "restart_candidate_rank_vector_changed": False,
                "experimental_navigation_rank_vector_changed": False,
            }
        ),
        expected_pid=12345,
    )

    assert decision.should_restart is False
    assert "restart_rank_vector_changed" in decision.reason
    assert "navigation_rank_vector_changed" in decision.reason


def test_restart_decision_rejects_restart_candidate_without_frontier_improvement():
    decision = restart_decision_from_watch_summary(
        restart_ready_summary(
            restart_readiness={
                "restart_candidate_primary_score_improved": False,
                "restart_candidate_secondary_score_improved": False,
                "restart_candidate_improvement_basis": "none",
            }
        ),
        expected_pid=12345,
    )

    assert decision.should_restart is False
    assert "restart_frontier_improved" in decision.reason
    assert "restart_improvement_basis" in decision.reason


def test_restart_decision_rejects_navigation_quality_failure():
    decision = restart_decision_from_watch_summary(
        restart_ready_summary(
            restart_readiness={
                "experimental_navigation_eligible": False,
                "experimental_navigation_quality_reason": "below_min_config_distance",
                "experimental_navigation_config_distance": 0.01,
            }
        ),
        expected_pid=12345,
    )

    assert decision.should_restart is False
    assert "navigation_eligible" in decision.reason
    assert "navigation_quality" in decision.reason
    assert "navigation_distance" in decision.reason
