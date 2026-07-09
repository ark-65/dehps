from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import scripts.watch_training_progress as watch
from scripts.watch_training_progress import (
    add_supervisor_status_observation_ages,
    advisor_summary,
    cli_evidence_context_summary,
    cli_summary,
    evidence_context_summary,
    gate_summary,
    load_supervisor_status,
    observed_age_minutes,
    operator_summary,
    parse_iso_datetime,
    recommendation_summary,
    render_markdown,
    restart_readiness_summary,
    safe_float,
    safe_filename_component,
    safe_int,
    supervisor_round_boundary_summary,
    summarize_watch,
)


def test_recommendation_continues_healthy_active_training_run():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    rows = [
        {
            "round_index": 1,
            "improved": True,
            "updated_at": now - timedelta(minutes=5),
        },
        {
            "round_index": 2,
            "improved": False,
            "updated_at": now - timedelta(minutes=1),
        },
    ]
    lock = {"active": True, "owner": "training-supervisor"}
    advisors = {
        "neural_kdj_advisor": {
            "candidate_count": 1,
            "top_advice": [{"confidence": 0.02}],
        },
        "ridge_kdj_advisor": {"candidate_count": 1},
    }

    recommendation = recommendation_summary(
        rows=rows,
        lock=lock,
        advisors=advisors,
        now=now,
        stale_minutes=30,
    )

    assert recommendation["severity"] == "ok"
    assert recommendation["action"] == "continue_current_run"
    assert any("confidence is low" in note for note in recommendation["notes"])
    assert any("Ridge advisor remains" in note for note in recommendation["notes"])


def test_recommendation_flags_high_stagnation_for_restart_preparation():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    rows = [
        {
            "round_index": index,
            "improved": index == 1,
            "updated_at": now - timedelta(minutes=2),
        }
        for index in range(1, 35)
    ]

    recommendation = recommendation_summary(
        rows=rows,
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        now=now,
        stale_minutes=30,
    )

    assert recommendation["severity"] == "alert"
    assert recommendation["action"] == "prepare_restart_with_more_exploration"
    assert "prepare_restart_with_more_exploration" in recommendation["actions"]
    assert any("not launch-ready" in note for note in recommendation["notes"])


def test_restart_readiness_blocks_parallel_supervisor_while_lock_is_active():
    recommendation = {
        "action": "prepare_restart_with_more_exploration",
        "actions": ["prepare_restart_with_more_exploration"],
    }
    lock = {
        "active": True,
        "owner": "training-supervisor",
        "pid": 12345,
        "pid_active": True,
        "heartbeat_at": "2026-07-01T00:00:00Z",
        "lock_age_hours": 2.0,
        "heartbeat_age_minutes": 1.5,
    }

    readiness = restart_readiness_summary(recommendation=recommendation, lock=lock)

    assert readiness["requested"] is True
    assert readiness["ready"] is False
    assert readiness["status"] == "blocked_by_active_training_supervisor_lock"
    assert readiness["blockers"] == ["active_training_supervisor_lock"]
    assert readiness["blocker_stage"] == "active_training_supervisor_progress_unknown_or_stale"
    assert (
        readiness["operator_action"]
        == "stop_or_transfer_active_training_supervisor_before_restart"
    )
    assert readiness["pid"] == 12345
    assert readiness["lock_age_hours"] == 2.0
    assert readiness["heartbeat_age_minutes"] == 1.5


def test_restart_readiness_surfaces_fresh_supervisor_progress(tmp_path):
    recommendation = {
        "action": "prepare_restart_with_more_exploration",
        "actions": ["prepare_restart_with_more_exploration"],
    }
    lock = {
        "active": True,
        "owner": "training-supervisor",
        "pid": 12345,
        "pid_active": True,
        "heartbeat_at": "2026-07-01T00:09:30Z",
        "lock_age_hours": 2.0,
        "heartbeat_age_minutes": 0.5,
    }
    supervisor_status = {
        "available": True,
        "status": "running",
        "updated_at": "2026-07-01T00:09:00Z",
        "updated_at_age_minutes": 1.0,
        "latest_progress": {
            "logged_at": "2026-07-01T00:08:30Z",
            "round": 42,
            "target_index": 17,
            "target_total": 100,
            "target_complete": False,
            "age_minutes": 1.5,
            "fresh": True,
            "freshness_threshold_minutes": 30,
        },
    }

    readiness = restart_readiness_summary(
        recommendation=recommendation,
        lock=lock,
        supervisor_status=supervisor_status,
    )
    payload = {
        "generated_at": "2026-07-01T00:10:00Z",
        "run_id": "run-1",
        "round_count": 42,
        "latest_round": 42,
        "last_improved_round": None,
        "stagnation_rounds": 42,
        "latest_metrics": {
            "phase": "large",
            "step": 0.15,
            "improved": False,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": 0,
            "red5_top_10000_hits": 0,
            "best_rank": None,
            "median_rank": None,
            "worst_rank": None,
            "objective_score": None,
            "best_objective_seen": None,
        },
        "advisor_summary": {},
        "heavy_job_lock": lock,
        "recommendation": {
            "severity": "alert",
            "action": "prepare_restart_with_more_exploration",
            "notes": [],
        },
        "restart_readiness": readiness,
        "guardrail": "Historical response-surface monitoring only.",
    }

    summary = cli_summary(payload, tmp_path / "watch.json", tmp_path / "watch.md")
    markdown = render_markdown(payload)

    assert readiness["ready"] is False
    assert readiness["blockers"] == ["active_training_supervisor_lock"]
    assert readiness["blocker_stage"] == "active_training_supervisor_fresh_progress"
    assert (
        readiness["operator_action"]
        == "wait_for_active_training_supervisor_to_finish_or_stop_before_restart"
    )
    assert readiness["supervisor_progress_fresh"] is True
    assert readiness["supervisor_progress_age_minutes"] == 1.5
    assert readiness["supervisor_updated_age_minutes"] == 1.0
    assert readiness["supervisor_progress_round"] == 42
    assert readiness["supervisor_target_index"] == 17
    assert summary["restart_readiness"]["supervisor_progress_fresh"] is True
    assert summary["restart_readiness"]["supervisor_progress_age_minutes"] == 1.5
    assert summary["restart_readiness"]["supervisor_progress_round"] == 42
    assert summary["restart_readiness"]["supervisor_target_index"] == 17
    assert summary["restart_readiness"]["supervisor_target_total"] == 100
    assert summary["restart_readiness"]["supervisor_target_complete"] is False
    assert "Supervisor progress fresh: True (threshold 30 minutes)" in markdown
    assert "Supervisor progress round: 42" in markdown
    assert "Supervisor target progress: 17 / 100 complete=False" in markdown
    assert "Supervisor progress age: 1.5 minutes" in markdown


def test_restart_readiness_marks_continuous_supervisor_for_operator_review(tmp_path):
    recommendation = {
        "action": "prepare_restart_with_more_exploration",
        "actions": ["prepare_restart_with_more_exploration"],
    }
    lock = {
        "active": True,
        "owner": "training-supervisor",
        "pid": 12345,
        "pid_active": True,
    }
    supervisor_status = {
        "available": True,
        "status": "running",
        "run_mode": "continuous",
        "deadline": None,
        "latest_progress": {
            "round": 60,
            "target_index": 100,
            "target_total": 100,
            "target_complete": True,
            "age_minutes": 0.9,
            "fresh": True,
            "freshness_threshold_minutes": 30,
        },
    }

    readiness = restart_readiness_summary(
        recommendation=recommendation,
        lock=lock,
        supervisor_status=supervisor_status,
    )
    payload = {
        "generated_at": "2026-07-01T00:10:00Z",
        "run_id": "run-1",
        "round_count": 60,
        "latest_round": 60,
        "last_improved_round": None,
        "stagnation_rounds": 60,
        "latest_metrics": {},
        "advisor_summary": {},
        "heavy_job_lock": lock,
        "recommendation": {
            "severity": "alert",
            "action": "prepare_restart_with_more_exploration",
            "notes": [],
        },
        "restart_readiness": readiness,
        "guardrail": "Historical response-surface monitoring only.",
    }

    summary = cli_summary(payload, tmp_path / "watch.json", tmp_path / "watch.md")
    markdown = render_markdown(payload)

    assert (
        readiness["operator_action"]
        == "operator_review_then_stop_continuous_training_supervisor_before_restart"
    )
    assert readiness["blocker_stage"] == "active_continuous_supervisor_target_complete"
    assert readiness["supervisor_run_mode"] == "continuous"
    assert readiness["supervisor_deadline"] is None
    assert (
        summary["restart_readiness"]["blocker_stage"]
        == "active_continuous_supervisor_target_complete"
    )
    assert summary["restart_readiness"]["supervisor_run_mode"] == "continuous"
    assert summary["restart_readiness"]["supervisor_target_index"] == 100
    assert summary["restart_readiness"]["supervisor_target_total"] == 100
    assert summary["restart_readiness"]["supervisor_target_complete"] is True
    assert (
        summary["restart_readiness"]["operator_action"]
        == "operator_review_then_stop_continuous_training_supervisor_before_restart"
    )
    assert "Supervisor run mode: continuous" in markdown
    assert "Blocker stage: active_continuous_supervisor_target_complete" in markdown
    assert (
        "Operator action: operator_review_then_stop_continuous_training_supervisor_before_restart"
        in markdown
    )


def test_restart_readiness_blocks_target_boundary_stop_when_evidence_gate_fails(tmp_path):
    recommendation = {
        "action": "prepare_restart_with_more_exploration",
        "actions": ["prepare_restart_with_more_exploration"],
    }
    lock = {
        "active": True,
        "owner": "training-supervisor",
        "pid": 12345,
        "pid_active": True,
    }
    supervisor_status = {
        "available": True,
        "status": "running",
        "run_mode": "continuous",
        "latest_progress": {
            "round": 35,
            "target_index": 100,
            "target_total": 100,
            "target_complete": True,
            "age_minutes": 0.6,
            "fresh": True,
            "freshness_threshold_minutes": 30,
        },
    }
    gates = {
        "rank_homogeneity_restart_champion": {
            "active": True,
            "source": "stagnation_restart",
            "reason": "rank_homogeneity_restart_changed_rank_vector",
            "rank_vector_changed": True,
            "changed_target_count": 100,
            "full_eval_rank": 14,
            "frozen_primary_score": [0, 0, 0],
            "baseline_frozen_primary_score": [0, 0, 0],
            "source_frontier_primary_score_improved": False,
            "source_frontier_secondary_score_improved": False,
            "source_frontier_improvement_basis": "none",
            "tail_over_1000000_delta": -2,
        },
        "experimental_navigation_candidate": {
            "eligible": True,
            "eligibility_reason": "eligible",
            "quality_reason": "passed",
            "rank_vector_changed": True,
            "config_distance": 3.60011,
            "min_config_distance": 0.08,
        },
    }

    readiness = restart_readiness_summary(
        recommendation=recommendation,
        lock=lock,
        supervisor_status=supervisor_status,
        gates=gates,
    )
    payload = {
        "generated_at": "2026-07-01T00:10:00Z",
        "run_id": "run-1",
        "round_count": 35,
        "latest_round": 34,
        "last_improved_round": None,
        "stagnation_rounds": 33,
        "latest_metrics": {},
        "advisor_summary": {},
        "heavy_job_lock": lock,
        "recommendation": {
            "severity": "alert",
            "action": "prepare_restart_with_more_exploration",
            "notes": [],
        },
        "restart_readiness": readiness,
        "guardrail": "Historical response-surface monitoring only.",
    }

    summary = cli_summary(payload, tmp_path / "watch.json", tmp_path / "watch.md")
    markdown = render_markdown(payload)

    assert readiness["ready"] is False
    assert readiness["status"] == "blocked_by_restart_candidate_evidence"
    assert readiness["blockers"] == [
        "active_training_supervisor_lock",
        "restart_candidate_evidence",
    ]
    assert readiness["blocker_stage"] == "restart_candidate_evidence_incomplete"
    assert (
        readiness["operator_action"]
        == "continue_current_training_supervisor_until_restart_candidate_evidence_improves"
    )
    assert readiness["restart_candidate_evidence_ready"] is False
    assert readiness["restart_candidate_evidence_blockers"] == [
        "restart_frontier_improved",
        "restart_improvement_basis",
    ]
    assert summary["restart_readiness"]["status"] == "blocked_by_restart_candidate_evidence"
    assert (
        summary["restart_readiness"]["operator_action"]
        == "continue_current_training_supervisor_until_restart_candidate_evidence_improves"
    )
    assert (
        summary["restart_readiness"]["restart_candidate_evidence_blockers"]
        == ["restart_frontier_improved", "restart_improvement_basis"]
    )
    assert "Restart candidate evidence gate: ready=False" in markdown
    assert "restart_frontier_improved" in markdown
    assert "restart_improvement_basis" in markdown


def test_restart_readiness_waits_for_continuous_supervisor_target_boundary():
    recommendation = {
        "action": "prepare_restart_with_more_exploration",
        "actions": ["prepare_restart_with_more_exploration"],
    }
    lock = {
        "active": True,
        "owner": "training-supervisor",
        "pid": 12345,
        "pid_active": True,
    }
    supervisor_status = {
        "available": True,
        "status": "running",
        "run_mode": "continuous",
        "latest_progress": {
            "round": 98,
            "target_index": 30,
            "target_total": 100,
            "target_complete": False,
            "age_minutes": 0.1,
            "fresh": True,
            "freshness_threshold_minutes": 30,
        },
    }

    readiness = restart_readiness_summary(
        recommendation=recommendation,
        lock=lock,
        supervisor_status=supervisor_status,
    )

    assert readiness["ready"] is False
    assert readiness["status"] == "blocked_by_active_training_supervisor_lock"
    assert readiness["blocker_stage"] == "active_continuous_supervisor_target_incomplete"
    assert (
        readiness["operator_action"]
        == "wait_for_continuous_training_supervisor_target_boundary_before_restart"
    )
    assert readiness["supervisor_run_mode"] == "continuous"
    assert readiness["supervisor_target_index"] == 30
    assert readiness["supervisor_target_total"] == 100
    assert readiness["supervisor_target_complete"] is False


def test_cli_summary_includes_restart_readiness_when_restart_is_requested(tmp_path):
    payload = {
        "run_id": "run-1",
        "round_count": 34,
        "round_window_count": 5,
        "recommendation": {
            "severity": "alert",
            "action": "prepare_restart_with_more_exploration",
        },
        "gate_summary": {
            "rank_homogeneity_guardrail": {
                "active": True,
                "reason": "stale_rank_signature_cycle",
                "stagnation_rounds": 34,
                "stagnation_threshold": 16,
                "window": 12,
                "observed": 12,
                "unique_signature_count": 1,
                "max_unique_signatures": 4,
                "signature_hashes": ["sig-a", "sig-b"],
            },
        },
        "restart_readiness": {
            "requested": True,
            "ready": False,
            "status": "blocked_by_active_heavy_job_lock",
            "blockers": ["active_training_supervisor_lock"],
            "operator_action": "stop_or_transfer_active_training_supervisor_before_restart",
            "owner": "training-supervisor",
            "pid": 12345,
            "heartbeat_age_minutes": 1.5,
            "supervisor_target_index": 100,
            "supervisor_target_total": 100,
            "supervisor_target_complete": True,
        },
    }

    summary = cli_summary(payload, tmp_path / "watch.json", tmp_path / "watch.md")

    assert summary["severity"] == "alert"
    assert summary["action"] == "prepare_restart_with_more_exploration"
    assert summary["rank_homogeneity"] == {
        "reason": "stale_rank_signature_cycle",
        "stagnation_rounds": 34,
        "stagnation_threshold": 16,
        "window": 12,
        "observed": 12,
        "unique_signature_count": 1,
        "max_unique_signatures": 4,
        "signature_hashes": ["sig-a", "sig-b"],
    }
    assert summary["restart_readiness"] == {
        "ready": False,
        "status": "blocked_by_active_heavy_job_lock",
        "blockers": ["active_training_supervisor_lock"],
        "operator_action": "stop_or_transfer_active_training_supervisor_before_restart",
        "owner": "training-supervisor",
        "pid": 12345,
        "heartbeat_age_minutes": 1.5,
        "supervisor_target_index": 100,
        "supervisor_target_total": 100,
        "supervisor_target_complete": True,
    }


def test_cli_summary_includes_restart_candidate_readiness_context(tmp_path):
    payload = {
        "run_id": "run-1",
        "round_count": 67,
        "round_window_count": 5,
        "recommendation": {
            "severity": "alert",
            "action": "prepare_restart_with_more_exploration",
        },
        "restart_readiness": {
            "requested": True,
            "ready": False,
            "status": "blocked_by_active_training_supervisor_lock",
            "blockers": ["active_training_supervisor_lock"],
            "operator_action": "operator_review_then_stop_continuous_training_supervisor_before_restart",
            "owner": "training-supervisor",
            "pid": 12345,
            "heartbeat_age_minutes": 0.5,
            "restart_candidate_active": True,
            "restart_candidate_source": "stagnation_restart",
            "restart_candidate_reason": "rank_homogeneity_restart_changed_rank_vector",
            "restart_candidate_rank_vector_changed": True,
            "restart_candidate_changed_target_count": 100,
            "restart_candidate_full_eval_rank": 13,
            "restart_candidate_frozen_primary_score": [0, 0, 0],
            "restart_candidate_baseline_frozen_primary_score": [0, 0, 0],
            "restart_candidate_primary_score_improved": False,
            "restart_candidate_secondary_score_improved": True,
            "restart_candidate_improvement_basis": "secondary",
            "restart_candidate_tail_over_1000000_delta": -2,
            "restart_candidate_evidence_ready": True,
            "restart_candidate_evidence_blockers": [],
            "experimental_navigation_eligible": True,
            "experimental_navigation_eligibility_reason": "eligible",
            "experimental_navigation_quality_reason": "passed",
            "experimental_navigation_rank_vector_changed": True,
            "experimental_navigation_config_distance": 3.62905,
            "experimental_navigation_min_config_distance": 0.08,
        },
    }

    summary = cli_summary(payload, tmp_path / "watch.json", tmp_path / "watch.md")

    readiness = summary["restart_readiness"]
    assert readiness["restart_candidate_frozen_primary_score"] == [0, 0, 0]
    assert readiness["restart_candidate_primary_score_improved"] is False
    assert readiness["restart_candidate_secondary_score_improved"] is True
    assert readiness["restart_candidate_improvement_basis"] == "secondary"
    assert readiness["restart_candidate_evidence_ready"] is True
    assert readiness["restart_candidate_evidence_blockers"] == []
    assert readiness["experimental_navigation_eligible"] is True
    assert readiness["experimental_navigation_eligibility_reason"] == "eligible"
    assert readiness["experimental_navigation_config_distance"] == 3.62905


def test_operator_summary_matches_cli_summary_without_paths(tmp_path):
    payload = {
        "run_id": "run-1",
        "round_count": 34,
        "round_window_count": 5,
        "recommendation": {
            "severity": "alert",
            "action": "prepare_restart_with_more_exploration",
        },
        "gate_summary": {
            "rank_homogeneity_guardrail": {
                "active": True,
                "reason": "stale_rank_signature_cycle",
                "unique_signature_count": 1,
                "signature_hashes": ["sig-a"],
            },
        },
    }

    summary = operator_summary(payload)
    cli = cli_summary(payload, tmp_path / "watch.json", tmp_path / "watch.md")
    cli_without_paths = {
        key: value
        for key, value in cli.items()
        if key not in {"json_path", "report_path"}
    }

    assert summary == cli_without_paths


def test_cli_summary_surfaces_recovery_gate_decision(tmp_path):
    payload = {
        "run_id": "run-1",
        "round_count": 29,
        "round_window_count": 5,
        "recommendation": {
            "severity": "warn",
            "action": "watch_stagnation_recovery",
        },
        "gate_summary": {
            "rank_homogeneity_guardrail": {
                "active": True,
                "reason": "stale_rank_signature_cycle",
                "unique_signature_count": 1,
                "signature_hashes": ["sig-a"],
            },
            "rank_homogeneity_restart_champion": {
                "active": True,
                "source": "stagnation_restart",
                "reason": "rank_homogeneity_restart_changed_rank_vector",
                "rank_vector_changed": True,
                "changed_target_count": 100,
                "full_eval_rank": 14,
                "frozen_primary_score": [0, 0, 0],
                "tail_over_1000000_delta": -2,
                "source_frontier_score_improved": False,
                "source_frontier_improvement_basis": "none",
            },
            "experimental_navigation_candidate": {
                "source": "rank_homogeneity_restart_champion",
                "reason": "rank_homogeneity_restart_changed_rank_vector",
                "config_hash": "nav-hash",
                "eligible": False,
                "eligibility_reason": "below_min_config_distance",
                "quality_reason": "passed",
                "rank_vector_changed": True,
                "config_distance": 0.006,
                "min_config_distance": 0.08,
            },
            "decision_round_best": {
                "source": "source_frontier",
                "reason": "selected_candidate",
                "selected_frozen_primary_score": [0, 0, 1],
                "blocked_candidate_count": 0,
                "blocked_candidate_sources": [],
            },
        },
    }

    summary = cli_summary(payload, tmp_path / "watch.json", tmp_path / "watch.md")

    assert summary["rank_homogeneity_restart_champion"] == {
        "source": "stagnation_restart",
        "reason": "rank_homogeneity_restart_changed_rank_vector",
        "rank_vector_changed": True,
        "changed_target_count": 100,
        "full_eval_rank": 14,
        "frozen_primary_score": [0, 0, 0],
        "tail_over_1000000_delta": -2,
        "source_frontier_score_improved": False,
        "source_frontier_improvement_basis": "none",
    }
    assert summary["experimental_navigation_candidate"] == {
        "source": "rank_homogeneity_restart_champion",
        "reason": "rank_homogeneity_restart_changed_rank_vector",
        "candidate_present": True,
        "eligible": False,
        "eligibility_reason": "below_min_config_distance",
        "quality_reason": "passed",
        "rank_vector_changed": True,
        "config_distance": 0.006,
        "min_config_distance": 0.08,
    }
    assert summary["decision_round_best"] == {
        "source": "source_frontier",
        "reason": "selected_candidate",
        "selected_frozen_primary_score": [0, 0, 1],
        "blocked_candidate_count": 0,
        "blocked_candidate_sources": [],
    }


def test_recommendation_surfaces_recovery_decision_note():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    gates = {
        "rank_homogeneity_restart_champion": {
            "active": True,
            "source": "stagnation_restart",
            "reason": "rank_homogeneity_restart_changed_rank_vector",
            "frozen_primary_score": [0, 0, 0],
            "source_frontier_improvement_basis": "none",
        },
        "experimental_navigation_candidate": {
            "source": "rank_homogeneity_restart_champion",
            "reason": "rank_homogeneity_restart_changed_rank_vector",
            "eligible": True,
            "eligibility_reason": "eligible",
        },
        "decision_round_best": {
            "source": "source_frontier",
            "reason": "selected_candidate",
            "selected_frozen_primary_score": [0, 0, 1],
            "blocked_candidate_count": 0,
            "blocked_candidate_sources": [],
        },
    }

    recommendation = recommendation_summary(
        rows=[{"round_index": 29, "improved": False, "updated_at": now}],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        gates=gates,
        now=now,
        stale_minutes=30,
        round_stats={"stagnation_rounds": 29},
    )
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 29,
        "latest_round": 29,
        "last_improved_round": None,
        "stagnation_rounds": 29,
        "latest_metrics": {},
        "advisor_summary": {},
        "gate_summary": gates,
        "heavy_job_lock": {"active": True},
        "recommendation": recommendation,
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)
    note = next(
        note
        for note in recommendation["notes"]
        if note.startswith("Recovery decision:")
    )

    assert "selected_source=source_frontier" in note
    assert "selected_frozen_primary=[0, 0, 1]" in note
    assert "navigation_source=rank_homogeneity_restart_champion" in note
    assert "navigation_eligible=True" in note
    assert "restart_frozen_primary=[0, 0, 0]" in note
    assert "- Recovery decision:" in markdown


def test_gate_summary_surfaces_ineligible_navigation_distance():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    prefilter = {
        "experimental_navigation_candidate": {
            "source": "rank_homogeneity_restart_champion",
            "reason": "rank_homogeneity_restart_changed_rank_vector",
            "config_hash": "restart-hash",
        },
        "search_base": {
            "exploration_navigation_config_hash": "restart-hash",
            "exploration_navigation_eligible": False,
            "exploration_navigation_quality_reason": "passed",
            "exploration_navigation_config_distance": 0.006042,
            "min_config_distance": 0.08,
            "exploration_navigation_rank_vector_changed": True,
            "exploration_navigation_frozen_primary_score": [0, 0, 1],
            "exploration_navigation_baseline_frozen_primary_score": [0, 0, 1],
            "exploration_navigation_tail_over_1000000_delta": 0,
            "exploration_navigation_source_frontier_score_improved": False,
        },
    }

    gates = gate_summary(prefilter)
    navigation = gates["experimental_navigation_candidate"]

    assert navigation == {
        "source": "rank_homogeneity_restart_champion",
        "reason": "rank_homogeneity_restart_changed_rank_vector",
        "config_hash": "restart-hash",
        "candidate_present": True,
        "eligible": False,
        "eligibility_reason": "below_min_config_distance",
        "config_distance": 0.006042,
        "min_config_distance": 0.08,
        "rank_vector_changed": True,
        "tail_over_1000000_delta": 0,
        "source_frontier_score_improved": False,
        "quality_reason": "passed",
        "frozen_primary_score": [0, 0, 1],
        "baseline_frozen_primary_score": [0, 0, 1],
    }

    recommendation = recommendation_summary(
        rows=[{"round_index": 34, "improved": False, "updated_at": now}],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        gates=gates,
        now=now,
        stale_minutes=30,
        round_stats={"stagnation_rounds": 34},
    )
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 34,
        "latest_round": 34,
        "last_improved_round": None,
        "stagnation_rounds": 34,
        "latest_metrics": {},
        "advisor_summary": {},
        "gate_summary": gates,
        "heavy_job_lock": {"active": True},
        "recommendation": recommendation,
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert any(
        "reason=below_min_config_distance" in note
        and "config_distance=0.006042" in note
        and "min_config_distance=0.08" in note
        for note in recommendation["notes"]
    )
    assert "eligibility_reason=below_min_config_distance" in markdown
    assert "config_distance=0.006042 min_config_distance=0.08" in markdown


def test_gate_summary_labels_primary_lift_navigation_as_standard_search_path():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    prefilter = {
        "experimental_navigation_candidate": {
            "source": "rank_homogeneity_restart_champion",
            "reason": "rank_homogeneity_restart_changed_rank_vector",
            "config_hash": "restart-hash",
        },
        "search_base": {
            "exploration_navigation_config_hash": "restart-hash",
            "exploration_navigation_eligible": False,
            "exploration_navigation_quality_reason": "passed",
            "exploration_navigation_config_distance": 2.354982,
            "min_config_distance": 0.08,
            "exploration_navigation_rank_vector_changed": True,
            "exploration_navigation_frozen_primary_score": [0, 0, 1],
            "exploration_navigation_baseline_frozen_primary_score": [0, 0, 0],
            "exploration_navigation_tail_over_1000000_delta": 0,
            "exploration_navigation_source_frontier_score_improved": True,
        },
    }

    gates = gate_summary(prefilter)
    navigation = gates["experimental_navigation_candidate"]

    assert navigation["eligibility_reason"] == "primary_lift_candidate_uses_standard_search_path"
    assert navigation["frozen_primary_score"] == [0, 0, 1]
    assert navigation["baseline_frozen_primary_score"] == [0, 0, 0]

    recommendation = recommendation_summary(
        rows=[{"round_index": 17, "improved": False, "updated_at": now}],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        gates=gates,
        now=now,
        stale_minutes=30,
        round_stats={"stagnation_rounds": 17},
    )
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 17,
        "latest_round": 17,
        "last_improved_round": None,
        "stagnation_rounds": 17,
        "latest_metrics": {},
        "advisor_summary": {},
        "gate_summary": gates,
        "heavy_job_lock": {"active": True},
        "recommendation": recommendation,
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert any(
        "reason=primary_lift_candidate_uses_standard_search_path" in note
        and "quality=passed" in note
        and "rank_vector_changed=True" in note
        for note in recommendation["notes"]
    )
    assert "eligibility_reason=primary_lift_candidate_uses_standard_search_path" in markdown


def test_recommendation_omits_missing_navigation_distance_when_no_candidate():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    prefilter = {
        "experimental_navigation_candidate": {
            "source": "",
            "reason": "no_experimental_navigation_candidate",
            "config_hash": "",
        },
        "search_base": {
            "exploration_navigation_eligible": False,
            "exploration_navigation_quality_reason": "missing_candidate_or_baseline",
            "exploration_navigation_rank_vector_changed": False,
            "min_config_distance": 0.08,
        },
    }

    gates = gate_summary(prefilter)
    recommendation = recommendation_summary(
        rows=[{"round_index": 7, "improved": False, "updated_at": now}],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        gates=gates,
        now=now,
        stale_minutes=30,
        round_stats={"stagnation_rounds": 7},
    )
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 7,
        "latest_round": 7,
        "last_improved_round": None,
        "stagnation_rounds": 7,
        "latest_metrics": {},
        "advisor_summary": {},
        "gate_summary": gates,
        "heavy_job_lock": {"active": True},
        "recommendation": recommendation,
        "guardrail": "Historical response-surface monitoring only.",
    }

    note = next(
        note
        for note in recommendation["notes"]
        if note.startswith("No experimental navigation candidate is available:")
    )
    markdown = render_markdown(payload)

    assert gates["experimental_navigation_candidate"]["candidate_present"] is False
    assert "reason=no_experimental_navigation_candidate" in note
    assert "quality=missing_candidate_or_baseline" in note
    assert "rank_vector_changed=False" in note
    assert "source=" not in note
    assert "config_distance" not in note
    assert "min_config_distance" not in note
    assert "Experimental navigation: reason=no_experimental_navigation_candidate" in markdown
    assert "source=" not in markdown
    assert "config_distance" not in markdown
    assert "min_config_distance" not in markdown


def test_restart_readiness_reports_operator_action_for_non_training_lock():
    recommendation = {
        "action": "prepare_restart_with_more_exploration",
        "actions": ["prepare_restart_with_more_exploration"],
    }
    lock = {
        "active": True,
        "owner": "history-sync",
        "pid": 23456,
    }

    readiness = restart_readiness_summary(recommendation=recommendation, lock=lock)

    assert readiness["ready"] is False
    assert readiness["status"] == "blocked_by_active_heavy_job_lock"
    assert readiness["blockers"] == ["active_heavy_job_lock"]
    assert readiness["blocker_stage"] == "active_heavy_job_lock"
    assert (
        readiness["operator_action"]
        == "wait_for_or_clear_active_heavy_job_lock_before_restart"
    )


def test_restart_readiness_reports_operator_action_when_ready():
    recommendation = {
        "action": "prepare_restart_with_more_exploration",
        "actions": ["prepare_restart_with_more_exploration"],
    }

    readiness = restart_readiness_summary(
        recommendation=recommendation,
        lock={"active": False},
    )

    assert readiness["ready"] is True
    assert readiness["blockers"] == []
    assert readiness["blocker_stage"] == "clear"
    assert readiness["operator_action"] == "operator_review_then_start_fresh_supervisor"


def test_restart_readiness_includes_supervisor_progress_freshness():
    recommendation = {
        "action": "prepare_restart_with_more_exploration",
        "actions": ["prepare_restart_with_more_exploration"],
    }

    readiness = restart_readiness_summary(
        recommendation=recommendation,
        lock={"active": True, "owner": "training-supervisor"},
        supervisor_status={
            "available": True,
            "latest_progress": {
                "round": 42,
                "age_minutes": 1.5,
                "fresh": True,
            },
        },
    )

    assert readiness["supervisor_progress_round"] == 42
    assert readiness["supervisor_progress_age_minutes"] == 1.5
    assert readiness["supervisor_progress_fresh"] is True


def test_restart_readiness_includes_restart_candidate_evidence():
    recommendation = {
        "action": "prepare_restart_with_more_exploration",
        "actions": ["prepare_restart_with_more_exploration"],
    }
    gates = {
        "rank_homogeneity_restart_champion": {
            "active": True,
            "source": "stagnation_restart",
            "reason": "rank_homogeneity_restart_changed_rank_vector",
            "rank_vector_changed": True,
            "changed_target_count": 100,
            "full_eval_rank": 13,
            "frozen_primary_score": [0, 0, 0],
            "baseline_frozen_primary_score": [0, 0, 0],
            "source_frontier_primary_score_improved": False,
            "source_frontier_secondary_score_improved": True,
            "source_frontier_improvement_basis": "secondary",
            "tail_over_1000000_delta": -2,
        },
        "experimental_navigation_candidate": {
            "eligible": True,
            "eligibility_reason": "eligible",
            "quality_reason": "passed",
            "rank_vector_changed": True,
            "config_distance": 3.62905,
            "min_config_distance": 0.08,
        },
    }

    readiness = restart_readiness_summary(
        recommendation=recommendation,
        lock={"active": False},
        gates=gates,
    )

    assert readiness["ready"] is True
    assert readiness["restart_candidate_active"] is True
    assert readiness["restart_candidate_source"] == "stagnation_restart"
    assert readiness["restart_candidate_frozen_primary_score"] == [0, 0, 0]
    assert readiness["restart_candidate_baseline_frozen_primary_score"] == [0, 0, 0]
    assert readiness["restart_candidate_primary_score_improved"] is False
    assert readiness["restart_candidate_secondary_score_improved"] is True
    assert readiness["restart_candidate_improvement_basis"] == "secondary"
    assert readiness["experimental_navigation_candidate_present"] is True
    assert readiness["experimental_navigation_eligible"] is True
    assert readiness["experimental_navigation_eligibility_reason"] == "eligible"
    assert readiness["experimental_navigation_config_distance"] == 3.62905
    assert readiness["experimental_navigation_min_config_distance"] == 0.08


def test_load_supervisor_status_reads_current_progress(tmp_path):
    status_path = tmp_path / "training-supervisor-run-1.json"
    status_path.write_text(
        """
        {
          "run_id": "run-1",
          "status": "running",
          "pid": 12345,
          "started_at": "2026-07-01T00:00:00",
          "updated_at": "2026-07-01T00:03:00",
          "deadline": "2026-07-01T06:00:00",
          "run_mode": "timed",
          "report_path": "/tmp/training-supervisor-run-1.md",
          "legal_universe_size": 1107568,
          "ranked_universe_size": 1107568,
          "excluded_universe_count": 0,
          "history_scope": "current_regime_default",
          "train_mode": "expanding",
          "train_window": 900,
          "eval_window": 100,
          "top_n": 10000,
          "regime_start_date": "2016-01-01",
          "regime_years": 10,
          "latest_progress": {
            "logged_at": "2026-07-01T00:03:00",
            "round": 9,
            "target_index": 100,
            "target_total": 100,
            "issue": "2026074",
            "train_draws": 1494,
            "elapsed_seconds": 53.3
          }
        }
        """,
        encoding="utf-8",
    )

    status = load_supervisor_status("run-1", output_dir=tmp_path)

    assert status["available"] is True
    assert status["status"] == "running"
    assert status["pid"] == 12345
    assert status["run_mode"] == "timed"
    assert status["deadline"] == "2026-07-01T06:00:00"
    assert status["latest_progress"]["round"] == 9
    assert status["latest_progress"]["target_complete"] is True
    assert status["latest_progress"]["elapsed_seconds"] == 53.3
    assert status["legal_universe_size"] == 1107568
    assert status["history_scope"] == "current_regime_default"
    assert status["train_window"] == 900
    assert status["eval_window"] == 100


def test_load_supervisor_status_infers_continuous_run_mode_from_null_deadline(tmp_path):
    status_path = tmp_path / "training-supervisor-run-1.json"
    status_path.write_text(
        """
        {
          "run_id": "run-1",
          "status": "running",
          "pid": 12345,
          "updated_at": "2026-07-01T00:03:00",
          "deadline": null,
          "latest_progress": {
            "logged_at": "2026-07-01T00:03:00",
            "round": 9
          }
        }
        """,
        encoding="utf-8",
    )

    status = load_supervisor_status("run-1", output_dir=tmp_path)

    assert status["run_mode"] == "continuous"
    assert status["deadline"] is None


def test_supervisor_status_progress_age_uses_local_timezone_for_naive_timestamps():
    now = datetime(2026, 7, 1, 18, 5, tzinfo=timezone.utc)
    local_tz = timezone(timedelta(hours=8))
    status = {
        "available": True,
        "updated_at": "2026-07-02T02:03:00",
        "latest_progress": {
            "logged_at": "2026-07-02T02:03:30",
            "round": 9,
        },
    }

    enriched = add_supervisor_status_observation_ages(
        status,
        now=now,
        stale_minutes=30,
        default_timezone=local_tz,
    )

    assert enriched["updated_at_age_minutes"] == 2.0
    assert enriched["latest_progress"]["age_minutes"] == 1.5
    assert enriched["latest_progress"]["fresh"] is True
    assert enriched["latest_progress"]["freshness_threshold_minutes"] == 30


def test_recommendation_flags_stale_supervisor_progress():
    now = datetime(2026, 7, 1, 18, 5, tzinfo=timezone.utc)
    rows = [
        {
            "round_index": 1,
            "improved": True,
            "updated_at": now - timedelta(minutes=1),
        }
    ]
    supervisor_status = {
        "available": True,
        "status": "running",
        "pid": 12345,
        "latest_progress": {
            "logged_at": "2026-07-01T17:20:00Z",
            "round": 1,
            "age_minutes": 45.0,
            "fresh": False,
        },
    }

    recommendation = recommendation_summary(
        rows=rows,
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        now=now,
        stale_minutes=30,
        supervisor_status=supervisor_status,
    )

    assert recommendation["severity"] == "warn"
    assert recommendation["action"] == "inspect_training_log"
    assert any("Supervisor progress is stale" in note for note in recommendation["notes"])


def test_recommendation_and_markdown_include_supervisor_progress():
    now = datetime(2026, 7, 1, 0, 5, tzinfo=timezone.utc)
    supervisor_status = {
        "available": True,
        "path": "/tmp/training-supervisor-run-1.json",
        "status": "running",
        "pid": 12345,
        "updated_at": "2026-07-01T00:03:00",
        "updated_at_age_minutes": 2.0,
        "latest_progress": {
            "logged_at": "2026-07-01T00:03:00",
            "round": 9,
            "target_index": 42,
            "target_total": 100,
            "target_complete": False,
            "issue": "2026074",
            "train_draws": 1494,
            "elapsed_seconds": 12.5,
            "age_minutes": 2.0,
            "fresh": True,
            "freshness_threshold_minutes": 30,
        },
    }
    recommendation = recommendation_summary(
        rows=[
            {
                "round_index": 8,
                "improved": False,
                "updated_at": now - timedelta(minutes=1),
            }
        ],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        now=now,
        stale_minutes=30,
        supervisor_status=supervisor_status,
    )
    payload = {
        "generated_at": "2026-07-01T00:05:00Z",
        "run_id": "run-1",
        "round_count": 8,
        "latest_round": 8,
        "last_improved_round": None,
        "stagnation_rounds": 8,
        "latest_metrics": {
            "phase": "large",
            "step": 0.15,
            "improved": False,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": 0,
            "red5_top_10000_hits": 0,
            "best_rank": 100,
            "median_rank": 1000,
            "worst_rank": 9000,
            "objective_score": 1.0,
            "best_objective_seen": 1.0,
        },
        "advisor_summary": {},
        "gate_summary": {},
        "supervisor_status": supervisor_status,
        "heavy_job_lock": {"active": True},
        "recommendation": recommendation,
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert any("Supervisor status file reports current progress" in note for note in recommendation["notes"])
    assert any("round=9" in note and "target=42/100" in note for note in recommendation["notes"])
    assert "## Supervisor Progress" in markdown
    assert "Status/PID: running / 12345" in markdown
    assert "Updated age: 2.0 minutes" in markdown
    assert "Progress round: 9" in markdown
    assert "Target progress: 42 / 100" in markdown
    assert "Progress age: 2.0 minutes" in markdown
    assert "Progress fresh: True (threshold 30 minutes)" in markdown
    assert "Issue: 2026074" in markdown


def test_supervisor_round_boundary_waits_for_completed_round_result():
    now = datetime(2026, 7, 1, 0, 5, tzinfo=timezone.utc)
    round_stats = {
        "latest_round": 23,
        "last_improved_round": None,
        "stagnation_rounds": 23,
        "improvement_count": 0,
    }
    supervisor_status = {
        "available": True,
        "path": "/tmp/training-supervisor-run-1.json",
        "status": "running",
        "pid": 12345,
        "run_mode": "continuous",
        "updated_at": "2026-07-01T00:04:30Z",
        "updated_at_age_minutes": 0.5,
        "latest_progress": {
            "logged_at": "2026-07-01T00:04:20Z",
            "round": 24,
            "target_index": 100,
            "target_total": 100,
            "target_complete": True,
            "issue": "2026077",
            "elapsed_seconds": 55.0,
            "age_minutes": 0.666667,
            "fresh": True,
            "freshness_threshold_minutes": 30,
        },
    }

    round_boundary = supervisor_round_boundary_summary(
        supervisor_status=supervisor_status,
        round_stats=round_stats,
    )
    recommendation = recommendation_summary(
        rows=[
            {
                "round_index": 23,
                "improved": False,
                "updated_at": now - timedelta(minutes=1),
            }
        ],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        now=now,
        stale_minutes=30,
        round_stats=round_stats,
        supervisor_status=supervisor_status,
    )
    payload = {
        "generated_at": "2026-07-01T00:05:00Z",
        "run_id": "run-1",
        "round_count": 23,
        "round_window_count": 5,
        "latest_round": 23,
        "last_improved_round": None,
        "stagnation_rounds": 23,
        "latest_metrics": {
            "phase": "large",
            "step": 0.15,
            "improved": False,
            "top_100_hits": 3,
            "top_1000_hits": 3,
            "top_10000_hits": 3,
            "red5_top_10000_hits": 29,
            "best_rank": 39,
            "median_rank": 580674,
            "worst_rank": 1091258,
            "objective_score": 5083.69366,
            "best_objective_seen": 5083.69366,
        },
        "advisor_summary": {},
        "gate_summary": {},
        "supervisor_status": supervisor_status,
        "supervisor_round_boundary": round_boundary,
        "heavy_job_lock": {"active": True},
        "recommendation": recommendation,
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)
    summary = operator_summary(payload)

    assert round_boundary == {
        "status": "target_complete_waiting_round_result",
        "supervisor_progress_round": 24,
        "latest_db_round": 23,
        "round_lag": 1,
        "target_index": 100,
        "target_total": 100,
        "target_complete": True,
        "progress_fresh": True,
        "progress_age_minutes": 0.666667,
    }
    assert any(
        "Supervisor target boundary reached but round results are not visible yet" in note
        for note in recommendation["notes"]
    )
    assert "Round boundary: status=target_complete_waiting_round_result" in markdown
    assert "progress_round=24 latest_db_round=23 round_lag=1 target_complete=True" in markdown
    assert summary["supervisor_round_boundary"] == {
        "status": "target_complete_waiting_round_result",
        "supervisor_progress_round": 24,
        "latest_db_round": 23,
        "round_lag": 1,
        "target_index": 100,
        "target_total": 100,
        "target_complete": True,
        "progress_fresh": True,
        "progress_age_minutes": 0.666667,
    }


def test_render_markdown_includes_restart_readiness_when_restart_is_requested():
    payload = {
        "generated_at": "2026-07-01T00:00:00Z",
        "run_id": "run-1",
        "round_count": 34,
        "latest_round": 34,
        "last_improved_round": None,
        "stagnation_rounds": 34,
        "latest_metrics": {
            "phase": "large",
            "step": 0.15,
            "improved": False,
            "top_100_hits": 3,
            "top_1000_hits": 3,
            "top_10000_hits": 3,
            "red5_top_10000_hits": 27,
            "best_rank": 39,
            "median_rank": 555738,
            "worst_rank": 1091255,
            "objective_score": 5082.552393,
            "best_objective_seen": 5082.552393,
        },
        "advisor_summary": {},
        "gate_summary": {},
        "heavy_job_lock": {"active": True, "owner": "training-supervisor", "pid": 12345},
        "recommendation": {
            "severity": "alert",
            "action": "prepare_restart_with_more_exploration",
            "notes": [],
        },
        "restart_readiness": {
            "requested": True,
            "ready": False,
            "status": "blocked_by_active_training_supervisor_lock",
            "blockers": ["active_training_supervisor_lock"],
            "owner": "training-supervisor",
            "pid": 12345,
            "heartbeat_at": "2026-07-01T00:00:00Z",
            "lock_age_hours": 2.0,
            "heartbeat_age_minutes": 1.5,
            "supervisor_progress_fresh": True,
            "supervisor_progress_age_minutes": 2.0,
            "supervisor_progress_round": 34,
            "operator_action": "wait_for_active_training_supervisor_to_finish_or_stop_before_restart",
            "restart_candidate_active": True,
            "restart_candidate_source": "stagnation_restart",
            "restart_candidate_reason": "rank_homogeneity_restart_changed_rank_vector",
            "restart_candidate_rank_vector_changed": True,
            "restart_candidate_changed_target_count": 100,
            "restart_candidate_full_eval_rank": 13,
            "restart_candidate_frozen_primary_score": [0, 0, 0],
            "restart_candidate_baseline_frozen_primary_score": [0, 0, 0],
            "restart_candidate_primary_score_improved": False,
            "restart_candidate_secondary_score_improved": True,
            "restart_candidate_improvement_basis": "secondary",
            "restart_candidate_tail_over_1000000_delta": -2,
            "experimental_navigation_eligible": True,
            "experimental_navigation_eligibility_reason": "eligible",
            "experimental_navigation_quality_reason": "passed",
            "experimental_navigation_rank_vector_changed": True,
            "experimental_navigation_config_distance": 3.62905,
            "experimental_navigation_min_config_distance": 0.08,
        },
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert "## Restart Readiness" in markdown
    assert "Ready for fresh supervisor: False" in markdown
    assert "Blockers: [active_training_supervisor_lock]" in markdown
    assert (
        "Operator action: wait_for_active_training_supervisor_to_finish_or_stop_before_restart"
        in markdown
    )
    assert "Lock owner/PID: training-supervisor / 12345" in markdown
    assert "Restart candidate: active=True source=stagnation_restart" in markdown
    assert "frozen_primary=[0, 0, 0] baseline_frozen_primary=[0, 0, 0]" in markdown
    assert "primary_improved=False secondary_improved=True frontier_basis=secondary" in markdown
    assert "Experimental navigation readiness: eligible=True reason=eligible quality=passed" in markdown
    assert "Lock age: 2.0 hours" in markdown
    assert "Heartbeat age: 1.5 minutes" in markdown
    assert "Supervisor progress fresh: True (age=2.0 minutes, round=34)" in markdown


def test_advisor_summary_and_markdown_include_guardrails():
    prefilter = {
        "candidate_budget": {"neural_kdj": 1},
        "neural_kdj_advisor": {
            "enabled": True,
            "budget": 1,
            "candidate_count": 1,
            "selected_count": 1,
            "rejected_count": 2,
            "latest_signal_issue": "2026068",
            "selected_fields": ["consecutive_trend_weight"],
            "advice": [
                {
                    "weight_name": "consecutive_trend_weight",
                    "decision": "selected",
                    "suggested_offset": 0.02,
                    "confidence": 0.03,
                    "validation_metric": 0.01,
                    "baseline_metric": 0.02,
                }
            ],
        },
    }

    advisors = advisor_summary(prefilter)
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 2,
        "latest_round": 2,
        "last_improved_round": 1,
        "stagnation_rounds": 1,
        "latest_metrics": {
            "phase": "micro",
            "step": 0.01,
            "improved": False,
            "top_100_hits": 0,
            "top_1000_hits": 1,
            "top_10000_hits": 3,
            "red5_top_10000_hits": 12,
            "best_rank": 100,
            "median_rank": 1000,
            "worst_rank": 9000,
            "objective_score": 1.0,
            "best_objective_seen": 2.0,
        },
        "advisor_summary": advisors,
        "heavy_job_lock": {"active": True},
        "recommendation": {
            "severity": "ok",
            "action": "continue_current_run",
            "notes": ["Training process is active under the heavy-job lock."],
        },
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert advisors["neural_kdj_advisor"]["candidate_count"] == 1
    assert advisors["neural_kdj_advisor"]["top_advice"][0]["confidence"] == 0.03
    assert "Neural" not in markdown  # Machine-readable key is used in the table.
    assert "Historical response-surface monitoring only" in markdown


def test_gate_summary_surfaces_frozen_primary_blockers_in_recommendation_and_markdown():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    prefilter = {
        "promotion_gate": {
            "passed": False,
            "reason": "frozen_validation_not_better",
            "tail_passed": True,
            "objective_passed": False,
            "primary_hit_passed": False,
            "candidate_primary_score": [0, 0, 0],
            "incumbent_primary_score": [0, 0, 0],
        },
        "eval_slice_overfit_guardrail": {
            "active": True,
            "reason": "eval_slice_overfit_no_frozen_primary_lift",
            "force_primary_gate": True,
            "rank_homogeneity_active": True,
            "rank_homogeneity_unique_signature_count": 1,
            "round_best_eval_primary_score": [3, 3, 3],
            "round_best_frozen_primary_score": [0, 0, 0],
            "incumbent_frozen_primary_score": [0, 0, 0],
            "suspicious_candidate_count": 4,
            "issue_counts": {"2026025": 4},
            "source_counts": {"unknown": 3, "stagnation_restart": 1},
        },
        "stale_round_best_search_base_gate": {
            "active": True,
            "reason": "eval_slice_overfit_no_frozen_primary_lift",
            "require_frozen_primary_challenger": True,
            "allow_unpromoted_round_best": False,
            "threshold": 64,
        },
        "rank_homogeneity_guardrail": {
            "active": True,
            "reason": "stale_rank_signature_cycle",
            "stagnation_rounds": 34,
            "stagnation_threshold": 16,
            "window": 12,
            "observed": 12,
            "unique_signature_count": 1,
            "max_unique_signatures": 4,
            "signatures": [
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
                "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            ],
        },
        "rank_homogeneity_restart_champion": {
            "active": True,
            "reason": "rank_homogeneity_restart_changed_rank_vector",
            "source": "stagnation_restart",
            "config_hash": "restart-hash",
            "full_eval_rank": 12,
            "rank_vector_changed": True,
            "changed_target_count": 99,
            "max_abs_delta": 904798,
            "primary_weight_pattern": "structural=0.05/frequency=0.70/omission=0.70",
            "context_field_movement_count": 5,
            "frozen_primary_score": [0, 0, 0],
            "baseline_frozen_primary_score": [0, 0, 0],
            "source_frontier_secondary_score": [0, 0, 0, -1, -700000.0, 0.0],
            "baseline_source_frontier_secondary_score": [0, 0, 0, -2, -700000.0, 0.0],
            "tail_over_1000000_delta": -1,
            "source_frontier_score_improved": True,
            "source_frontier_primary_score_improved": False,
            "source_frontier_secondary_score_improved": True,
            "source_frontier_improvement_basis": "secondary",
            "unique_rank_signature_count": 3,
        },
        "experimental_navigation_candidate": {
            "source": "exploration_champion",
            "reason": "stagnation_top_eval_exploration",
            "config_hash": "nav-hash",
        },
        "decision_round_best": {
            "source": "incumbent",
            "reason": "incumbent_due_to_required_frozen_primary_lift",
            "frozen_primary_lift_required": True,
            "selected_frozen_primary_score": [0, 0, 0],
            "frozen_primary_lift_baseline_score": [0, 0, 0],
            "blocked_candidates": [{"source": "rank_homogeneity_restart"}],
        },
    }

    gates = gate_summary(prefilter)
    recommendation = recommendation_summary(
        rows=[
            {
                "round_index": index,
                "improved": False,
                "updated_at": now - timedelta(minutes=2),
            }
            for index in range(1, 35)
        ],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        gates=gates,
        now=now,
        stale_minutes=30,
    )
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 34,
        "latest_round": 34,
        "last_improved_round": None,
        "stagnation_rounds": 34,
        "latest_metrics": {
            "phase": "large",
            "step": 0.15,
            "improved": False,
            "top_100_hits": 3,
            "top_1000_hits": 3,
            "top_10000_hits": 3,
            "red5_top_10000_hits": 28,
            "best_rank": 39,
            "median_rank": 557702,
            "worst_rank": 1079121,
            "objective_score": 5085.35383,
            "best_objective_seen": 5085.35383,
        },
        "advisor_summary": {},
        "gate_summary": gates,
        "heavy_job_lock": {"active": True},
        "recommendation": recommendation,
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert gates["promotion_gate"]["reason"] == "frozen_validation_not_better"
    assert gates["eval_slice_overfit_guardrail"]["round_best_eval_primary_score"] == [3, 3, 3]
    assert gates["rank_homogeneity_restart_champion"]["rank_vector_changed"] is True
    assert gates["rank_homogeneity_restart_champion"]["changed_target_count"] == 99
    assert gates["rank_homogeneity_restart_champion"]["primary_weight_pattern"] == (
        "structural=0.05/frequency=0.70/omission=0.70"
    )
    assert gates["rank_homogeneity_restart_champion"]["context_field_movement_count"] == 5
    assert gates["rank_homogeneity_restart_champion"]["frozen_primary_score"] == [0, 0, 0]
    assert gates["rank_homogeneity_restart_champion"]["baseline_frozen_primary_score"] == [0, 0, 0]
    assert gates["rank_homogeneity_restart_champion"]["tail_over_1000000_delta"] == -1
    assert gates["rank_homogeneity_restart_champion"]["source_frontier_score_improved"] is True
    assert gates["rank_homogeneity_restart_champion"]["source_frontier_primary_score_improved"] is False
    assert gates["rank_homogeneity_restart_champion"]["source_frontier_secondary_score_improved"] is True
    assert gates["rank_homogeneity_restart_champion"]["source_frontier_improvement_basis"] == "secondary"
    assert gates["rank_homogeneity_restart_champion"]["unique_rank_signature_count"] == 3
    assert gates["rank_homogeneity_guardrail"]["stagnation_rounds"] == 34
    assert gates["rank_homogeneity_guardrail"]["stagnation_threshold"] == 16
    assert gates["rank_homogeneity_guardrail"]["window"] == 12
    assert gates["rank_homogeneity_guardrail"]["observed"] == 12
    assert gates["rank_homogeneity_guardrail"]["max_unique_signatures"] == 4
    assert gates["rank_homogeneity_guardrail"]["signature_hashes"] == [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    ]
    assert gates["experimental_navigation_candidate"]["source"] == "exploration_champion"
    assert gates["decision_round_best"]["blocked_candidate_count"] == 1
    assert any("Promotion gate blocked" in note for note in recommendation["notes"])
    assert any("Eval-slice overfit guardrail is active" in note for note in recommendation["notes"])
    assert any("sources=unknown=3, stagnation_restart=1" in note for note in recommendation["notes"])
    assert any("issues=2026025=4" in note for note in recommendation["notes"])
    assert any(
        "window=12 observed=12 unique_signatures=1/4 stagnation=34/16" in note
        for note in recommendation["notes"]
    )
    assert any(
        "signature_hashes=[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, "
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, "
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc, +1 more]"
        in note
        for note in recommendation["notes"]
    )
    assert any("Rank-homogeneity restart champion observed" in note for note in recommendation["notes"])
    assert "## Gate Snapshot" in markdown
    assert "frozen_primary=[0, 0, 0]" in markdown
    assert "sources=unknown=3, stagnation_restart=1" in markdown
    assert "issues=2026025=4" in markdown
    assert "Restart champion: active=True" in markdown
    assert "window=12 observed=12 unique_signatures=1/4 stagnation=34/16" in markdown
    assert (
        "signature_hashes=[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, "
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, "
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc, +1 more]"
    ) in markdown
    assert "rank_vector_changed=True changed_targets=99 full_eval_rank=12 max_abs_delta=904798" in markdown
    assert "context_moves=5 frozen_primary=[0, 0, 0] tail1000000_delta=-1" in markdown
    assert (
        "source_frontier_improved=True frontier_basis=secondary "
        "primary_improved=False secondary_improved=True unique_signatures=3"
    ) in markdown
    assert "Experimental navigation: source=exploration_champion reason=stagnation_top_eval_exploration" in markdown
    assert "blocked_sources=[rank_homogeneity_restart]" in markdown


def test_evidence_context_surfaces_sample_space_baseline_and_leakage_guardrails():
    gates = {
        "promotion_gate": {
            "passed": False,
            "reason": "frozen_validation_not_better",
        },
        "eval_slice_overfit_guardrail": {
            "active": True,
            "reason": "eval_slice_overfit_no_frozen_primary_lift",
            "suspicious_candidate_count": 8,
        },
        "rank_homogeneity_guardrail": {
            "active": True,
            "reason": "stale_rank_signature_cycle",
        },
        "decision_round_best": {
            "frozen_primary_lift_required": True,
            "frozen_primary_lift_baseline_score": [0, 0, 0],
            "blocked_candidate_count": 2,
            "blocked_candidate_sources": ["rank_homogeneity_restart", "exploration"],
        },
    }
    supervisor_status = {
        "available": True,
        "run_id": "run-1",
        "status": "running",
        "pid": 12345,
        "legal_universe_size": 1107568,
        "ranked_universe_size": 1107568,
        "excluded_universe_count": 0,
        "history_scope": "current_regime_default",
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "regime_start_date": "2016-01-01",
        "regime_years": 10.0,
        "top_n": 10000,
    }
    parser_sync_duplicate_checks = {
        "status": "checked",
        "ok": True,
        "history_ok": True,
        "history_draw_count": 1494,
        "history_first_issue": "2003001",
        "history_latest_issue": "2026074",
        "history_duplicate_issue_count": 0,
        "history_invalid_red_length_count": 0,
        "history_red_out_of_range_count": 0,
        "history_duplicate_red_numbers_count": 0,
        "history_blue_out_of_range_count": 0,
        "universe_ok": True,
        "red_combination_universe_count": 1107568,
        "expected_red_combination_universe_count": 1107568,
        "red_combination_universe_complete": True,
        "red_combination_duplicate_count": 0,
        "red_combination_invalid_shape_count": 0,
        "latest_sync_ok": True,
        "latest_sync": {"status": "success", "conflict_count": 0},
        "recorded_data_conflict_count": 0,
    }

    evidence = evidence_context_summary(
        supervisor_status=supervisor_status,
        gates=gates,
        parser_sync_duplicate_checks=parser_sync_duplicate_checks,
    )
    payload = {
        "generated_at": "2026-07-01T00:00:00Z",
        "run_id": "run-1",
        "round_count": 34,
        "latest_round": 34,
        "last_improved_round": None,
        "stagnation_rounds": 34,
        "latest_metrics": {
            "phase": "large",
            "step": 0.15,
            "improved": False,
            "top_100_hits": 3,
            "top_1000_hits": 3,
            "top_10000_hits": 3,
            "red5_top_10000_hits": 27,
            "best_rank": 39,
            "median_rank": 555738,
            "worst_rank": 1091255,
            "objective_score": 5082.552393,
            "best_objective_seen": 5082.552393,
        },
        "advisor_summary": {},
        "gate_summary": {},
        "supervisor_status": supervisor_status,
        "evidence_context": evidence,
        "heavy_job_lock": {"active": True},
        "recommendation": {
            "severity": "alert",
            "action": "prepare_restart_with_more_exploration",
            "notes": [],
        },
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert evidence["legal_sample_space"]["legal_universe_size"] == 1107568
    assert evidence["baseline_or_null_model"]["random_null_model"] == "ranked_uniform_per_draw"
    null_expectation = evidence["baseline_or_null_model"]["random_null_expectation"]
    assert null_expectation["status"] == "estimated"
    assert null_expectation["bands"]["top_100"]["expected_eval_hits"] == 0.009029
    assert null_expectation["bands"]["top_1000"]["expected_eval_hits"] == 0.090288
    assert null_expectation["bands"]["top_10000"]["expected_eval_hits"] == 0.902879
    assert evidence["leakage_checks"]["eval_slice_overfit_guardrail_active"] is True
    assert evidence["leakage_checks"]["parser_sync_duplicate_checks"]["status"] == "checked"
    assert evidence["leakage_checks"]["parser_sync_duplicate_checks"]["history_draw_count"] == 1494
    assert "## Evidence Context" in markdown
    assert "Legal sample space: domain=ssq_red_ball_combinations legal_universe=1107568" in markdown
    assert "Historical window: scope=current_regime_default mode=expanding train_window=900 eval_window=100" in markdown
    assert "random_null=ranked_uniform_per_draw" in markdown
    assert "top_100:p=0.00009029,eval_expected=0.009029" in markdown
    assert "top_10000:p=0.00902879,eval_expected=0.902879" in markdown
    assert "eval_overfit_active=True" in markdown
    assert "parser_sync_duplicates=status=checked ok=True history_ok=True draws=1494" in markdown
    assert "universe=1107568/1107568" in markdown
    assert "guaranteed hits or low-risk betting" in markdown


def test_cli_summary_includes_evidence_context_guardrails(tmp_path):
    payload = {
        "run_id": "run-1",
        "round_count": 34,
        "round_window_count": 5,
        "recommendation": {"severity": "warn", "action": "inspect_training_log"},
        "evidence_context": {
            "legal_sample_space": {
                "domain": "ssq_red_ball_combinations",
                "legal_universe_size": 1107568,
                "ranked_universe_size": 1105506,
                "excluded_universe_count": 2062,
            },
            "historical_window": {
                "history_scope": "current_regime_default",
                "train_mode": "expanding",
                "train_window": 900,
                "eval_window": 100,
                "regime_start_date": "2016-06-30",
                "top_n": 10000,
            },
            "baseline_or_null_model": {
                "operational_baseline": "incumbent_config_frozen_primary_baseline",
                "random_null_model": "ranked_uniform_per_draw",
                "random_null_expectation": {"status": "estimated"},
                "baseline_score": [0, 0, 0],
            },
            "leakage_checks": {
                "promotion_gate_reason": "frozen_validation_not_better",
                "eval_slice_overfit_guardrail_active": True,
                "suspicious_candidate_count": 8,
                "frozen_primary_lift_required": True,
                "parser_sync_duplicate_checks": {"status": "checked", "ok": True},
            },
            "evidence_level": "operational_training_diagnostic_no_predictive_claim",
            "risk": "Historical response-surface behavior is hypothesis evidence only.",
            "uncertainty": "Frozen validation can remain at baseline.",
            "failure_modes": ["promotion_gate:frozen_validation_not_better"],
        },
    }

    summary = cli_summary(payload, tmp_path / "watch.json", tmp_path / "watch.md")
    evidence = summary["evidence_context"]

    assert cli_evidence_context_summary({}) == {}
    assert evidence["evidence_level"] == "operational_training_diagnostic_no_predictive_claim"
    assert evidence["risk"] == "Historical response-surface behavior is hypothesis evidence only."
    assert evidence["uncertainty"] == "Frozen validation can remain at baseline."
    assert evidence["failure_modes"] == ["promotion_gate:frozen_validation_not_better"]
    assert evidence["legal_sample_space"] == {
        "domain": "ssq_red_ball_combinations",
        "legal_universe_size": 1107568,
        "ranked_universe_size": 1105506,
        "excluded_universe_count": 2062,
    }
    assert evidence["historical_window"]["train_window"] == 900
    assert evidence["historical_window"]["eval_window"] == 100
    assert evidence["baseline_or_null_model"] == {
        "operational_baseline": "incumbent_config_frozen_primary_baseline",
        "random_null_model": "ranked_uniform_per_draw",
        "random_null_expectation_status": "estimated",
        "baseline_score": [0, 0, 0],
    }
    assert evidence["leakage_checks"] == {
        "promotion_gate_reason": "frozen_validation_not_better",
        "eval_slice_overfit_guardrail_active": True,
        "suspicious_candidate_count": 8,
        "frozen_primary_lift_required": True,
        "parser_sync_duplicate_status": "checked",
        "parser_sync_duplicate_ok": True,
    }


def test_render_markdown_escapes_untrusted_inline_text():
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run`id\nwith-line",
        "round_count": 1,
        "latest_round": 1,
        "last_improved_round": None,
        "stagnation_rounds": 1,
        "latest_metrics": {
            "phase": "micro|phase\nretry",
            "step": 0.01,
            "improved": False,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": 0,
            "red5_top_10000_hits": 0,
            "best_rank": None,
            "median_rank": None,
            "worst_rank": None,
            "objective_score": None,
            "best_objective_seen": None,
        },
        "advisor_summary": {
            "custom|advisor": {
                "candidate_count": 1,
                "selected_count": 1,
                "rejected_count": 0,
                "selected_fields": ["weight|field", "line\nfield"],
            }
        },
        "heavy_job_lock": {},
        "recommendation": {
            "severity": "warn",
            "action": "inspect|log",
            "notes": ["first line\nsecond line | detail"],
        },
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert "- Run id: ``run`id with-line``" in markdown
    assert "- Phase/step: micro\\|phase retry / 0.01" in markdown
    assert "| custom\\|advisor | 1 | 1 | 0 | weight\\|field, line field |" in markdown
    assert "- first line second line \\| detail" in markdown
    assert "first line\nsecond line" not in markdown


def test_write_outputs_sanitizes_run_id_filename(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "utc_stamp", lambda: "20260618-100000")
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": " ../run:bad/..//escape ",
        "round_count": 0,
        "latest_round": None,
        "last_improved_round": None,
        "stagnation_rounds": 0,
        "latest_metrics": {},
        "advisor_summary": {},
        "heavy_job_lock": {},
        "recommendation": {"severity": "ok", "action": "continue_current_run", "notes": []},
        "guardrail": "Historical response-surface monitoring only.",
    }

    json_path, md_path = watch.write_outputs(payload, tmp_path)

    assert safe_filename_component(payload["run_id"]) == "run_bad_escape"
    assert safe_filename_component(None) == "none"
    assert safe_filename_component(" / ") == "none"
    assert safe_filename_component(0) == "0"
    assert json_path == tmp_path / "training-watch-run_bad_escape-20260618-100000.json"
    assert md_path == tmp_path / "training-watch-run_bad_escape-20260618-100000.md"
    assert (tmp_path / "training-watch-latest.json").exists()
    assert (tmp_path / "training-watch-latest.md").exists()


def test_write_outputs_embeds_operator_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "utc_stamp", lambda: "20260618-100000")
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 34,
        "latest_round": 34,
        "last_improved_round": None,
        "stagnation_rounds": 34,
        "latest_metrics": {},
        "advisor_summary": {},
        "heavy_job_lock": {},
        "recommendation": {
            "severity": "alert",
            "action": "prepare_restart_with_more_exploration",
            "notes": [],
        },
        "gate_summary": {
            "rank_homogeneity_guardrail": {
                "active": True,
                "reason": "stale_rank_signature_cycle",
                "unique_signature_count": 1,
                "signature_hashes": ["sig-a"],
            },
        },
        "guardrail": "Historical response-surface monitoring only.",
    }

    json_path, _ = watch.write_outputs(payload, tmp_path)
    artifact = json.loads(json_path.read_text())

    assert artifact["severity"] == "alert"
    assert artifact["action"] == "prepare_restart_with_more_exploration"
    assert artifact["operator_summary"]["severity"] == artifact["severity"]
    assert artifact["operator_summary"]["rank_homogeneity"] == {
        "reason": "stale_rank_signature_cycle",
        "unique_signature_count": 1,
        "signature_hashes": ["sig-a"],
    }


def test_write_outputs_uses_atomic_writer(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "utc_stamp", lambda: "20260618-100000")
    writes = []

    def fake_atomic_write_text(path, text):
        writes.append((path.name, text))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    monkeypatch.setattr(watch, "atomic_write_text", fake_atomic_write_text)
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 0,
        "latest_round": None,
        "last_improved_round": None,
        "stagnation_rounds": 0,
        "latest_metrics": {},
        "advisor_summary": {},
        "heavy_job_lock": {},
        "recommendation": {"severity": "ok", "action": "continue_current_run", "notes": []},
        "guardrail": "Historical response-surface monitoring only.",
    }

    watch.write_outputs(payload, tmp_path)

    assert [name for name, _ in writes] == [
        "training-watch-run-1-20260618-100000.json",
        "training-watch-run-1-20260618-100000.md",
        "training-watch-latest.json",
        "training-watch-latest.md",
    ]


def test_safe_filename_component_bounds_long_run_ids():
    first = safe_filename_component("run-" + ("a" * 240), max_length=48)
    second = safe_filename_component("run-" + ("b" * 240), max_length=48)

    assert len(first) == 48
    assert len(second) == 48
    assert first.startswith("run")
    assert second.startswith("run")
    assert first != second


def test_heavy_lock_summary_reports_unreadable_metadata_error(monkeypatch):
    monkeypatch.setattr(
        watch,
        "describe_heavy_job_owner",
        lambda: SimpleNamespace(
            active=False,
            pid_active=None,
            reason="metadata_unreadable",
            error="Unable to read heavy-job metadata",
            metadata=None,
        ),
    )

    summary = watch.heavy_lock_summary()

    assert summary["active"] is False
    assert summary["reason"] == "metadata_unreadable"
    assert summary["error"] == "Unable to read heavy-job metadata"


def test_summarize_watch_normalizes_non_positive_windows(monkeypatch):
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    captured = {}

    def fake_load_rounds(run_id, *, limit):
        captured["rounds_run_id"] = run_id
        captured["limit"] = limit
        return [
            {
                "round_index": 1,
                "improved": False,
                "updated_at": now,
                "objective_score": 1.0,
                "prefilter": {},
            }
        ]

    def fake_load_round_stats(run_id):
        captured["stats_run_id"] = run_id
        return {
            "round_count": 1,
            "latest_round": 1,
            "last_improved_round": None,
            "stagnation_rounds": 1,
            "improvement_count": 0,
            "best_objective_seen": 1.0,
        }

    monkeypatch.setattr(watch, "utc_now", lambda: now)
    monkeypatch.setattr(watch, "resolve_run_id", lambda run_id: "run-1")
    monkeypatch.setattr(watch, "load_rounds", fake_load_rounds)
    monkeypatch.setattr(watch, "load_round_stats", fake_load_round_stats)
    monkeypatch.setattr(watch, "heavy_lock_summary", lambda: {"active": True, "owner": "training-supervisor"})

    payload = summarize_watch(None, limit=0, stale_minutes=-10)

    assert captured == {
        "rounds_run_id": "run-1",
        "stats_run_id": "run-1",
        "limit": watch.DEFAULT_ROUND_LIMIT,
    }
    assert payload["round_limit"] == watch.DEFAULT_ROUND_LIMIT
    assert payload["stale_minutes"] == watch.DEFAULT_STALE_MINUTES
    assert payload["recommendation"]["severity"] == "ok"


def test_summarize_watch_uses_full_stats_beyond_recent_limit(monkeypatch):
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    captured = {}

    def fake_load_rounds(run_id, *, limit):
        captured["rounds"] = (run_id, limit)
        return [
            {
                "round_index": 11,
                "improved": False,
                "updated_at": now - timedelta(minutes=2),
                "objective_score": 1.0,
                "prefilter": {},
            },
            {
                "round_index": 12,
                "improved": False,
                "updated_at": now - timedelta(minutes=1),
                "objective_score": 2.0,
                "prefilter": {},
            },
        ]

    def fake_load_round_stats(run_id):
        captured["stats"] = run_id
        return {
            "round_count": 12,
            "latest_round": 12,
            "last_improved_round": 10,
            "stagnation_rounds": 2,
            "improvement_count": 4,
            "best_objective_seen": 99.0,
        }

    monkeypatch.setattr(watch, "utc_now", lambda: now)
    monkeypatch.setattr(watch, "resolve_run_id", lambda run_id: "run-1")
    monkeypatch.setattr(watch, "load_rounds", fake_load_rounds)
    monkeypatch.setattr(watch, "load_round_stats", fake_load_round_stats)
    monkeypatch.setattr(watch, "heavy_lock_summary", lambda: {"active": True, "owner": "training-supervisor"})

    payload = summarize_watch("input-run", limit=2, stale_minutes=30)

    assert captured == {"rounds": ("run-1", 2), "stats": "run-1"}
    assert payload["round_count"] == 12
    assert payload["round_window_count"] == 2
    assert payload["last_improved_round"] == 10
    assert payload["stagnation_rounds"] == 2
    assert payload["latest_metrics"]["best_objective_seen"] == 99.0
    assert payload["recommendation"]["severity"] == "ok"


def test_summarize_watch_reports_db_read_errors_with_status_fallback(monkeypatch):
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)

    def raise_db_unavailable(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(watch, "utc_now", lambda: now)
    monkeypatch.setattr(watch, "resolve_run_id", raise_db_unavailable)
    monkeypatch.setattr(watch, "latest_supervisor_run_id_from_status_file", lambda: "run-1")
    monkeypatch.setattr(watch, "load_rounds", raise_db_unavailable)
    monkeypatch.setattr(watch, "load_round_stats", raise_db_unavailable)
    monkeypatch.setattr(
        watch,
        "load_supervisor_status",
        lambda run_id: {
            "available": True,
            "path": "/tmp/training-supervisor-run-1.json",
            "run_id": run_id,
            "status": "running",
            "pid": 123,
            "updated_at": "2026-06-18T09:59:00Z",
            "latest_progress": {
                "logged_at": "2026-06-18T09:59:30Z",
                "round": 7,
                "target_index": 12,
                "target_total": 100,
                "target_complete": False,
            },
        },
    )
    monkeypatch.setattr(watch, "heavy_lock_summary", lambda: {"active": True, "owner": "training-supervisor"})
    monkeypatch.setattr(watch, "load_parser_sync_duplicate_checks", lambda: {"status": "checked", "ok": True})

    payload = summarize_watch(None, limit=2, stale_minutes=30)

    assert payload["run_id"] == "run-1"
    assert payload["round_count"] == 0
    assert payload["recommendation"]["severity"] == "alert"
    assert payload["recommendation"]["action"] == "inspect_training_db"
    assert payload["recommendation"]["actions"][0] == "inspect_training_db"
    assert [
        error["stage"] for error in payload["db_read_errors"]
    ] == ["resolve_run_id", "load_rounds", "load_round_stats"]
    assert all(error["error_type"] == "RuntimeError" for error in payload["db_read_errors"])
    assert "diagnostic-only until DB reads recover" in payload["recommendation"]["notes"][0]

    summary = operator_summary(payload)
    assert summary["db_read_errors"][0]["stage"] == "resolve_run_id"
    assert summary["action"] == "inspect_training_db"

    markdown = render_markdown(payload)
    assert "## Database Read Errors" in markdown
    assert "stage=resolve_run_id" in markdown


def test_latest_supervisor_run_id_from_status_file_skips_invalid_newest(tmp_path):
    invalid = tmp_path / "training-supervisor-invalid.json"
    older = tmp_path / "training-supervisor-old.json"
    newer = tmp_path / "training-supervisor-new.json"
    invalid.write_text("{", encoding="utf-8")
    older.write_text(json.dumps({"run_id": "run-old"}), encoding="utf-8")
    newer.write_text(json.dumps({"run_id": "run-new"}), encoding="utf-8")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    os.utime(invalid, (3, 3))

    assert watch.latest_supervisor_run_id_from_status_file(output_dir=tmp_path) == "run-new"


def test_safe_numeric_helpers_reject_bool_and_non_finite_values():
    assert safe_float("3.5") == 3.5
    assert safe_float(True) is None
    assert safe_float("nan") is None
    assert safe_float(float("inf")) is None

    assert safe_int("3") == 3
    assert safe_int(" 003 ") == 3
    assert safe_int(3.0) == 3
    assert safe_int(3.5) is None
    assert safe_int(False) is None
    assert safe_int(float("inf")) is None


def test_observed_age_minutes_parses_utc_lock_timestamps():
    now = datetime(2026, 7, 1, 2, 0, tzinfo=timezone.utc)

    assert parse_iso_datetime("2026-07-01T00:00:00Z") == datetime(
        2026,
        7,
        1,
        0,
        0,
        tzinfo=timezone.utc,
    )
    assert observed_age_minutes("2026-07-01T01:58:30Z", now=now) == 1.5
    assert observed_age_minutes("not-a-date", now=now) is None


def test_safe_int_rejects_non_decimal_string_forms():
    for value in ("+3", "-1", "1_000", "0x10", "1e3", "3.0", "", "\uff13"):
        assert safe_int(value) is None


def test_load_rounds_queries_recent_window_before_chronological_sort(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.sql = ""
            self.params = ()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params):
            self.sql = " ".join(sql.split())
            self.params = params
            return self

        def fetchall(self):
            return [{"round_index": 12}, {"round_index": 13}]

    class FakeConnection:
        def __init__(self, cursor):
            self.cursor_instance = cursor

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self, **_kwargs):
            return self.cursor_instance

    cursor = FakeCursor()
    monkeypatch.setattr(watch, "get_connection", lambda: FakeConnection(cursor))

    rows = watch.load_rounds("run-1", limit=2)

    assert rows == [{"round_index": 12}, {"round_index": 13}]
    assert cursor.params == ("run-1", 2)
    assert "ORDER BY round_index DESC LIMIT %s ) recent_rounds ORDER BY round_index ASC" in cursor.sql
