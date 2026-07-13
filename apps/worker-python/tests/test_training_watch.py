from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import scripts.watch_training_progress as watch
from scripts.watch_training_progress import (
    add_supervisor_status_observation_ages,
    apply_guard_continuity_to_round_stats,
    advisor_signal_freshness_summary,
    advisor_summary,
    cli_evidence_context_summary,
    cli_summary,
    evidence_context_summary,
    forward_evidence_wait_summary,
    gate_summary,
    heavy_job_supervisor_relation_summary,
    load_supervisor_status,
    observed_age_minutes,
    operator_summary,
    parse_iso_datetime,
    recommendation_summary,
    render_candidate_source_survival_markdown,
    render_navigation_search_base_consumption_markdown,
    render_markdown,
    restart_readiness_summary,
    safe_float,
    safe_filename_component,
    safe_int,
    summarize_candidate_source_survival,
    summarize_navigation_search_base_consumption,
    summarize_round_repetition,
    supervisor_round_boundary_summary,
    supervisor_lifecycle_summary,
    supervisor_status_summary,
    summarize_watch,
)


def source_survival_round(round_index: int, source_survival: dict, **prefilter_fields) -> dict:
    holdout_isolation = prefilter_fields.get("holdout_isolation")
    if isinstance(holdout_isolation, dict) and (
        holdout_isolation.get("protocol") == watch.HOLDOUT_ISOLATION_PROTOCOL
    ):
        prefilter_fields["holdout_isolation"] = {
            "prefilter_isolation_status": "passed",
            "prefilter_frozen_issue_overlap_count": 0,
            "prefilter_uses_frozen_validation": False,
            **holdout_isolation,
        }
    return {
        "round_index": round_index,
        "prefilter": {"source_survival": source_survival, **prefilter_fields},
    }


def forward_evaluation_row(
    line_key: str,
    predicted_issue: str,
    *,
    as_of_issue: str,
    leakage_passed: bool = True,
    status: str = "evaluated",
    exact_top_10000: bool = False,
) -> dict[str, Any]:
    return {
        "evaluation_key": f"{line_key}:{predicted_issue}:snapshot",
        "line_key": line_key,
        "snapshot_key": f"{line_key}-{predicted_issue}",
        "run_id": "forward-run",
        "source_round_index": 1,
        "as_of_issue": as_of_issue,
        "predicted_issue": predicted_issue,
        "status": status,
        "summary": {"leakage_passed": leakage_passed},
        "hit_top_100": False,
        "hit_top_1000": False,
        "hit_top_10000": exact_top_10000,
        "hit_red5_top_100": False,
        "hit_red5_top_1000": False,
        "hit_red5_top_10000": False,
    }


def navigation_round(
    round_index: int,
    *,
    selected_hash: str | None = None,
    search_base_start_hash: str | None = None,
) -> dict[str, Any]:
    prefilter: dict[str, Any] = {}
    if search_base_start_hash is not None:
        prefilter["search_base_start"] = {"config_hash": search_base_start_hash}
    if selected_hash is not None:
        prefilter["search_base"] = {
            "source": "experimental_navigation",
            "config_hash": selected_hash,
            "exploration_navigation_config_hash": selected_hash,
            "exploration_navigation_selected": True,
            "exploration_navigation_eligibility_basis": "search_slice_rank_geometry",
            "exploration_navigation_selection_uses_frozen_validation": False,
        }
    return {"round_index": round_index, "prefilter": prefilter}


def test_navigation_search_base_consumption_verifies_next_durable_round():
    summary = summarize_navigation_search_base_consumption(
        [
            navigation_round(7, selected_hash="selected-hash"),
            navigation_round(8, search_base_start_hash="selected-hash"),
        ]
    )

    assert summary["status"] == "passed"
    assert summary["selected_count"] == 1
    assert summary["verified_count"] == 1
    assert summary["violation_count"] == 0
    assert summary["latest"]["matched"] is True
    assert summary["latest_verified"]["selection_round"] == 7
    assert (
        summary["latest_verified"]["selected_config_hash"]
        == summary["latest_verified"]["search_base_start_config_hash"]
    )
    assert summary["selection_changed"] is False
    assert summary["promotion_allowed"] is False


def test_navigation_search_base_consumption_waits_for_next_durable_round():
    summary = summarize_navigation_search_base_consumption(
        [navigation_round(7, selected_hash="selected-hash")]
    )

    assert summary["status"] == "pending_next_durable_round"
    assert summary["action"] == "observe_next_durable_round"
    assert summary["pending_count"] == 1
    assert summary["invariants_passed"] is True


def test_navigation_search_base_consumption_flags_hash_mismatch_in_markdown():
    summary = summarize_navigation_search_base_consumption(
        [
            navigation_round(7, selected_hash="selected-hash"),
            navigation_round(8, search_base_start_hash="different-hash"),
        ]
    )

    assert summary["status"] == "invalid"
    assert summary["action"] == "inspect_navigation_search_base_consumption"
    assert summary["violation_count"] == 1
    assert summary["invariants_passed"] is False
    markdown = render_navigation_search_base_consumption_markdown(summary)
    assert "Navigation Search-Base Consumption" in markdown
    assert "different-hash" in markdown
    assert "config_hash_mismatch" in markdown


def test_forward_evidence_excludes_pre_isolation_rows_and_surfaces_pending_pair():
    old_rows = [
        forward_evaluation_row(
            line_key,
            "2026078",
            as_of_issue="2026077",
        )
        for line_key in watch.FORWARD_EVIDENCE_LINE_KEYS
    ]
    snapshots = [
        {
            "line_key": line_key,
            "predicted_issue": "2026079",
            "as_of_issue": "2026078",
            "candidate_count": 10_000,
        }
        for line_key in watch.FORWARD_EVIDENCE_LINE_KEYS
    ]

    summary = watch.summarize_forward_evidence(
        activation_after_issue="2026078",
        activation_run_id="isolation-run",
        activation_round_index=1,
        evaluation_rows=old_rows,
        snapshot_rows=snapshots,
    )

    assert summary["status"] == "not_started"
    assert summary["pre_activation_evaluation_count"] == 3
    assert summary["paired_issue_count"] == 0
    assert summary["pending_snapshots"] == [
        {
            "predicted_issue": "2026079",
            "line_keys": ["dynamic_kdj", "dynamic_kdj_near", "static_100"],
            "complete_line_set": True,
            "candidate_counts": {
                "dynamic_kdj": 10_000,
                "dynamic_kdj_near": 10_000,
                "static_100": 10_000,
            },
        }
    ]
    assert summary["promotion_eligible"] is False
    assert summary["automatic_quarantine_release"] is False


def forward_wait_ready_payload(
    *,
    history_latest_issue: str = "2026078",
    selected_experiment_key: str = "null_model_forward_audit",
) -> dict:
    return forward_evidence_wait_summary(
        prefilter={
            "strategy_memory": {
                "selected_experiment": {"key": selected_experiment_key},
            },
            "sequential_null_ledger": {
                "observed_familywise_hypothesis_count": 1038,
                "legacy_uncounted_round_count": 294,
                "adaptive_hypothesis_generation_counted": False,
                "sequential_search_multiplicity_counted": False,
                "selection_changed": False,
                "promotion_allowed": False,
            },
        },
        forward_evidence={
            "status": "not_started",
            "paired_issue_count": 0,
            "min_paired_issues": 20,
            "pending_snapshots": [
                {
                    "predicted_issue": "2026079",
                    "complete_line_set": True,
                    "line_keys": list(watch.FORWARD_EVIDENCE_LINE_KEYS),
                }
            ],
        },
        round_repetition={
            "active": True,
            "latest_config_repeat_streak": 5,
            "latest_metric_repeat_streak": 5,
        },
        current_run_stagnation_rounds=5,
        history_latest_issue=history_latest_issue,
    )


def test_forward_wait_parks_repeated_same_history_with_future_snapshot():
    summary = forward_wait_ready_payload()

    assert summary["ready"] is True
    assert summary["status"] == "awaiting_new_forward_issue"
    assert summary["next_pending_issue"] == "2026079"
    assert summary["observed_familywise_hypothesis_count"] == 1038
    assert summary["selection_changed"] is False
    assert summary["promotion_allowed"] is False
    assert summary["blockers"] == []


def test_forward_wait_does_not_depend_on_strategy_memory_experiment_label():
    summary = forward_wait_ready_payload(
        selected_experiment_key="decision_surface_dominance_audit"
    )

    assert summary["ready"] is True
    assert summary["selected_experiment"] == "decision_surface_dominance_audit"
    assert summary["blockers"] == []


def test_forward_wait_releases_when_pending_issue_has_been_synced():
    summary = forward_wait_ready_payload(history_latest_issue="2026079")

    assert summary["ready"] is False
    assert summary["status"] == "continue_training"
    assert "no_complete_future_prediction_snapshot" in summary["blockers"]


def test_recommendation_waits_for_forward_issue_instead_of_restarting():
    now = datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc)
    forward_wait = forward_wait_ready_payload()
    recommendation = recommendation_summary(
        rows=[
            {
                "round_index": index,
                "improved": False,
                "updated_at": now - timedelta(minutes=1),
            }
            for index in range(1, 35)
        ],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        now=now,
        stale_minutes=30,
        round_repetition={
            "active": True,
            "latest_config_repeat_streak": 5,
            "latest_metric_repeat_streak": 5,
        },
        forward_wait=forward_wait,
    )
    payload = {
        "run_id": "run-1",
        "round_count": 34,
        "round_window_count": 5,
        "round_limit": 5,
        "latest_round": 34,
        "last_improved_round": None,
        "stagnation_rounds": 34,
        "latest_metrics": {},
        "advisor_summary": {},
        "advisor_signal_freshness": {},
        "forward_wait": forward_wait,
        "heavy_job_lock": {"active": True},
        "recommendation": recommendation,
        "guardrail": "No automatic promotion.",
    }

    assert recommendation["action"] == "await_new_forward_issue"
    assert "prepare_restart_with_more_exploration" not in recommendation["actions"]
    assert "Forward Evidence Wait Gate" in render_markdown(payload)
    assert operator_summary(payload)["forward_wait"]["ready"] is True


def test_recommendation_keeps_stale_parked_supervisor_waiting():
    now = datetime(2026, 7, 11, 6, 40, tzinfo=timezone.utc)
    forward_wait = forward_wait_ready_payload()
    recommendation = recommendation_summary(
        rows=[
            {
                "round_index": index,
                "improved": False,
                "updated_at": now - timedelta(minutes=40),
            }
            for index in range(1, 9)
        ],
        lock={
            "active": False,
            "owner": "training-supervisor",
            "pid": 12345,
            "status": "waiting_for_forward_issue",
        },
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        now=now,
        stale_minutes=30,
        supervisor_status={
            "available": True,
            "status": "waiting_for_forward_issue",
            "pid": 12345,
            "latest_progress": {
                "round": 8,
                "age_minutes": 40.0,
                "fresh": False,
            },
        },
        round_repetition={
            "active": True,
            "latest_config_repeat_streak": 5,
            "latest_metric_repeat_streak": 5,
        },
        forward_wait=forward_wait,
    )

    assert recommendation["action"] == "await_new_forward_issue"
    assert "inspect_training_log" not in recommendation["actions"]
    assert any("intentionally inactive" in note for note in recommendation["notes"])


def test_sequential_null_audit_exposes_coverage_and_incomplete_family_boundaries():
    prefilter = {
        "sequential_null_ledger": {
            "protocol": "dehps-sequential-null-ledger-v1",
            "mode": "same_history_durable_round_observed_family",
            "total_round_count": 317,
            "observed_diagnostic_round_count": 23,
            "legacy_uncounted_round_count": 294,
            "observed_candidate_hypothesis_count": 418,
            "tested_band_count": 3,
            "observed_familywise_hypothesis_count": 1254,
            "observed_round_family_complete": False,
            "adaptive_hypothesis_generation_counted": False,
            "sequential_search_multiplicity_counted": False,
        },
        "self_diagnostics": {
            "signal_vs_noise": {
                "status": "noise_risk",
                "familywise_method": "bonferroni_minimum_observed_family",
                "sequential_family_method": "bonferroni_observed_durable_round_lower_bound",
                "familywise_alpha": 0.01,
                "overfit_guard_active": True,
                "forward_evaluated_count": 0,
                "sequential_family": {
                    "protocol": "dehps-sequential-null-ledger-v1",
                    "mode": "same_history_durable_round_observed_family",
                },
                "strongest_band": {
                    "label": "top_100",
                    "hits": 3,
                    "trials": 80,
                    "binomial_tail_p_value": 0.0000000605,
                    "bonferroni_adjusted_p_value": 0.0000029037,
                    "sequential_observed_bonferroni_adjusted_p_value": 0.0000758589,
                },
            }
        },
    }

    summary = watch.sequential_null_audit_summary(prefilter)

    assert summary["status"] == "incomplete_observed_lower_bound"
    assert summary["observed_round_coverage_ratio"] == 0.072555
    assert summary["legacy_round_gap_ratio"] == 0.927445
    assert summary["round_partition_consistent"] is True
    assert summary["observed_family_consistent"] is True
    assert summary["invariants_passed"] is True
    assert summary["full_family_complete"] is False
    assert summary["candidate_signal_interpretable"] is False
    assert summary["automatic_promotion_allowed"] is False
    assert summary["sequential_family"] == {
        "protocol": "dehps-sequential-null-ledger-v1",
        "mode": "same_history_durable_round_observed_family",
        "total_round_count": 317,
        "observed_diagnostic_round_count": 23,
        "legacy_uncounted_round_count": 294,
        "observed_candidate_hypothesis_count": 418,
        "tested_band_count": 3,
        "observed_familywise_hypothesis_count": 1254,
        "observed_round_family_complete": False,
        "adaptive_hypothesis_generation_counted": False,
        "sequential_search_multiplicity_counted": False,
    }
    assert "legacy_rounds_unaccounted" in summary["blockers"]
    assert "adaptive_hypothesis_generation_unaccounted" in summary["blockers"]
    assert "sequential_search_multiplicity_incomplete" in summary["blockers"]
    assert "no_forward_evaluation" in summary["blockers"]
    assert (
        summary["strongest_band"][
            "sequential_observed_bonferroni_adjusted_p_value"
        ]
        == 0.0000758589
    )

    operator = operator_summary(
        {
            "recommendation": {"severity": "warn", "action": "await_new_forward_issue"},
            "sequential_null_audit": summary,
        }
    )
    assert operator["sequential_null_audit"]["observed_round_coverage_ratio"] == 0.072555
    assert operator["sequential_null_audit"]["sequential_family"] == summary[
        "sequential_family"
    ]
    markdown = watch.render_sequential_null_audit_markdown(summary)
    assert "Sequential Null Ledger Audit" in markdown
    assert "observed=23/317" in markdown
    assert "family=1254" in markdown
    assert "automatic_promotion=False" in markdown


def test_sequential_null_audit_rejects_inconsistent_family_arithmetic():
    summary = watch.sequential_null_audit_summary(
        {
            "sequential_null_ledger": {
                "total_round_count": 10,
                "observed_diagnostic_round_count": 4,
                "legacy_uncounted_round_count": 5,
                "observed_candidate_hypothesis_count": 12,
                "tested_band_count": 3,
                "observed_familywise_hypothesis_count": 35,
                "observed_round_family_complete": False,
                "adaptive_hypothesis_generation_counted": False,
                "sequential_search_multiplicity_counted": False,
            }
        }
    )

    assert summary["status"] == "invalid"
    assert summary["invariants_passed"] is False
    assert "round_partition_inconsistent" in summary["blockers"]
    assert "observed_family_product_inconsistent" in summary["blockers"]
    assert summary["candidate_signal_interpretable"] is False


def test_sequential_null_audit_never_turns_complete_family_into_automatic_promotion():
    summary = watch.sequential_null_audit_summary(
        {
            "sequential_null_ledger": {
                "total_round_count": 2,
                "observed_diagnostic_round_count": 2,
                "legacy_uncounted_round_count": 0,
                "observed_candidate_hypothesis_count": 10,
                "tested_band_count": 3,
                "observed_familywise_hypothesis_count": 30,
                "observed_round_family_complete": True,
                "adaptive_hypothesis_generation_counted": True,
                "sequential_search_multiplicity_counted": True,
            },
            "self_diagnostics": {
                "signal_vs_noise": {
                    "status": "candidate_signal",
                    "overfit_guard_active": False,
                    "forward_evaluated_count": 20,
                }
            },
        }
    )

    assert summary["status"] == "complete_registered_family"
    assert summary["full_family_complete"] is True
    assert summary["candidate_signal_interpretable"] is True
    assert summary["automatic_promotion_allowed"] is False


def test_compute_capability_is_visible_in_operator_and_markdown():
    compute_capability = {
        "status": "cpu_parallel_gpu_backend_unvalidated",
        "action": "keep_cpu_parallel_require_pinned_gpu_equivalence_probe",
        "cpu": {
            "logical_count": 22,
            "configured_workers": 16,
            "matrix_backend": "NumPy feature matrix",
            "numpy_version": "2.4.6",
            "parallel_protocol": "ordered_target_parallel_v1",
            "equivalence_requirement": "serial_parallel_exact_summary_match",
        },
        "accelerator": {
            "gpu_device_visible": True,
            "dri_render_node_visible": True,
            "intel_arc_visible": True,
            "nvidia_tool_visible": False,
            "installed_accelerator_modules": [],
            "opencl_runtime_visible": True,
            "probe_status": "completed",
            "probe_protocol": "dehps-opencl-score-equivalence-v1",
            "probe_generated_at": "2026-07-11T08:00:00Z",
            "probe_accepted_for_training": False,
            "probe_blockers": [
                "rounded_score_matrix_not_exact",
                "insufficient_full_end_to_end_speedup",
            ],
            "probe_full_end_to_end_speedup": 0.851,
            "probe_rounded_score_matrix_exact": False,
            "probe_rounded_changed_cell_count": 9,
            "probe_top_set_match_count": 28,
            "probe_top_set_config_count": 28,
            "probe_target_ranks_equal": True,
            "probed_gpu_backend": "pyopencl",
            "probed_gpu_device": "Intel(R) Arc(TM) Graphics",
            "probed_gpu_driver": "26.05.037020",
            "validated_gpu_backend": None,
            "gpu_backend_validated": False,
            "gpu_training_enabled": False,
        },
        "selection_changed": False,
        "promotion_allowed": False,
        "interpretation": "GPU remains disabled pending an equivalence probe.",
    }
    payload = {
        "run_id": "run-1",
        "round_count": 8,
        "round_window_count": 5,
        "round_limit": 5,
        "latest_round": 8,
        "last_improved_round": None,
        "stagnation_rounds": 8,
        "latest_metrics": {},
        "advisor_summary": {},
        "advisor_signal_freshness": {},
        "compute_capability": compute_capability,
        "heavy_job_lock": {"active": False},
        "recommendation": {"severity": "warn", "action": "continue_current_run"},
        "guardrail": "No automatic promotion.",
    }

    markdown = render_markdown(payload)
    operator = operator_summary(payload)

    assert "## Compute Capability" in markdown
    assert "gpu_training=False" in markdown
    assert "accepted=False speedup=0.851 rounded_exact=False changed_cells=9" in markdown
    assert "top_sets=28/28 target_ranks_equal=True" in markdown
    assert operator["compute_capability"]["cpu"]["configured_workers"] == 16
    assert (
        operator["compute_capability"]["accelerator"]["probe_accepted_for_training"]
        is False
    )
    assert operator["compute_capability"]["accelerator"]["probe_blockers"] == [
        "rounded_score_matrix_not_exact",
        "insufficient_full_end_to_end_speedup",
    ]
    assert (
        operator["compute_capability"]["accelerator"]["gpu_backend_validated"]
        is False
    )


def test_forward_evidence_threshold_only_enables_human_review():
    rows = []
    for offset in range(1, 21):
        predicted_issue = str(2026078 + offset)
        as_of_issue = str(2026077 + offset)
        rows.extend(
            forward_evaluation_row(
                line_key,
                predicted_issue,
                as_of_issue=as_of_issue,
                exact_top_10000=(line_key == "dynamic_kdj" and offset == 1),
            )
            for line_key in watch.FORWARD_EVIDENCE_LINE_KEYS
        )

    summary = watch.summarize_forward_evidence(
        activation_after_issue="2026078",
        evaluation_rows=rows,
        snapshot_rows=[],
        min_paired_issues=20,
    )

    assert summary["status"] == "review_ready"
    assert summary["paired_issue_count"] == 20
    assert summary["review_ready"] is True
    assert summary["review_only"] is True
    assert summary["promotion_eligible"] is False
    assert summary["automatic_quarantine_release"] is False
    assert summary["line_totals"]["dynamic_kdj"]["exact_top_100_1000_10000"] == [0, 0, 1]
    assert summary["comparison"]["exact_delta_dynamic_minus_static"] == [0, 0, 1]
    assert summary["exact_random_null"]["expected_hits"]["top_10000"] == 0.180576
    assert summary["exact_random_null"]["red5_null_status"] == "not_estimated"


def test_forward_evidence_fails_closed_for_leakage_duplicates_and_incomplete_pairs():
    rows = [
        forward_evaluation_row(
            "static_100",
            "2026079",
            as_of_issue="2026078",
            leakage_passed=False,
        ),
        forward_evaluation_row("dynamic_kdj", "2026079", as_of_issue="2026078"),
    ]
    rows.append({**rows[-1], "evaluation_key": "duplicate"})

    summary = watch.summarize_forward_evidence(
        activation_after_issue="2026078",
        evaluation_rows=rows,
        snapshot_rows=[],
    )

    assert summary["status"] == "invalid"
    blockers = " ".join(summary["blockers"])
    assert "invalid_evaluation_boundary:2026079:static_100" in blockers
    assert "duplicate_line_issue_rows:2026079:dynamic_kdj" in blockers
    assert "incomplete_paired_issue:2026079:dynamic_kdj_near" in blockers
    assert summary["automatic_quarantine_release"] is False


def test_forward_evidence_is_visible_in_recommendation_markdown_and_operator_summary():
    forward_evidence = {
        **watch.default_forward_evidence(),
        "status": "invalid",
        "activation_after_issue": "2026078",
        "blockers": ["duplicate_line_issue_rows:2026079:dynamic_kdj"],
    }
    now = datetime.now(timezone.utc)
    recommendation = recommendation_summary(
        rows=[{"round_index": 1, "improved": False, "updated_at": now}],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        now=now,
        stale_minutes=30,
        forward_evidence=forward_evidence,
    )
    payload = {
        "generated_at": "2026-07-11T00:00:00Z",
        "run_id": "run-1",
        "round_count": 1,
        "latest_round": 1,
        "last_improved_round": None,
        "stagnation_rounds": 1,
        "latest_metrics": {},
        "advisor_summary": {},
        "forward_evidence": forward_evidence,
        "heavy_job_lock": {"active": True},
        "recommendation": recommendation,
        "guardrail": "No automatic promotion.",
    }

    markdown = render_markdown(payload)
    operator = operator_summary(payload)

    assert recommendation["severity"] == "alert"
    assert recommendation["action"] == "inspect_forward_evidence"
    assert "## Forward Evidence Ledger" in markdown
    assert "automatic_quarantine_release=False" in markdown
    assert operator["forward_evidence"]["status"] == "invalid"
    assert operator["forward_evidence"]["promotion_eligible"] is False


def test_guard_continuity_promotes_effective_stagnation_without_changing_round_count():
    round_stats, continuity = apply_guard_continuity_to_round_stats(
        {
            "round_count": 1,
            "latest_round": 1,
            "last_improved_round": None,
            "stagnation_rounds": 1,
            "improvement_count": 0,
            "best_objective_seen": 10.0,
        },
        {
            "stagnation_rounds": 20,
            "guard_continuity": {
                "active": True,
                "source_run_ids": ["run-old"],
                "effective_stagnation_rounds": 20,
            },
        },
    )

    assert round_stats["round_count"] == 1
    assert round_stats["current_run_stagnation_rounds"] == 1
    assert round_stats["stagnation_rounds"] == 20
    assert continuity["applied"] is True
    assert continuity["source_run_ids"] == ["run-old"]
    assert continuity["current_run_stagnation_rounds"] == 1
    assert continuity["effective_stagnation_rounds"] == 20


def test_guard_continuity_never_reduces_current_run_stagnation():
    round_stats, continuity = apply_guard_continuity_to_round_stats(
        {"round_count": 5, "stagnation_rounds": 5},
        {"guard_continuity": {"effective_stagnation_rounds": 2}},
    )

    assert round_stats["stagnation_rounds"] == 5
    assert continuity["applied"] is False
    assert continuity["effective_stagnation_rounds"] == 5


def test_candidate_source_survival_waits_for_a_minimum_round_window():
    rows = [
        source_survival_round(
            index,
            {
                "normal": {
                    "generated": 7,
                    "prefilter_selected": 7,
                    "full_eval_top5": 5,
                    "round_best": True,
                },
                "weight_kdj": {
                    "generated": 7,
                    "prefilter_selected": 0,
                    "full_eval_top5": 0,
                    "round_best": False,
                },
            },
        )
        for index in range(1, 3)
    ]

    summary = summarize_candidate_source_survival(rows)

    assert summary["status"] == "insufficient_window"
    assert summary["action"] == "observe_more_rounds"
    assert summary["evidence_ready"] is False
    assert summary["budget_review_ready"] is False
    assert summary["budget_review_sources"] == []
    assert summary["starved_sources"] == []


def test_candidate_source_survival_separates_productive_starved_and_zero_top5_sources():
    rows = []
    for index in range(1, 5):
        rows.append(
            source_survival_round(
                index,
                {
                    "normal": {
                        "generated": 7,
                        "prefilter_selected": 6,
                        "full_eval_top5": 3,
                        "round_best": index == 1,
                    },
                    "neural_kdj": {
                        "generated": 3,
                        "prefilter_selected": 1 if index >= 2 else 0,
                        "full_eval_top5": 1 if index == 4 else 0,
                        "round_best": index == 4,
                    },
                    "ridge_kdj": {
                        "generated": 3,
                        "prefilter_selected": 1,
                        "full_eval_top5": 0,
                        "round_best": False,
                    },
                    "weight_kdj": {
                        "generated": 7,
                        "prefilter_selected": 0,
                        "full_eval_top5": 0,
                        "round_best": False,
                    },
                },
            )
        )

    summary = summarize_candidate_source_survival(rows)

    assert summary["status"] == "diverse"
    assert summary["action"] == "continue_current_run"
    assert summary["evidence_ready"] is True
    assert summary["budget_review_min_rounds"] == 8
    assert summary["budget_review_ready"] is False
    assert summary["budget_review_action"] == "observe_until_budget_review_window"
    assert summary["budget_review_sources"] == []
    assert summary["productive_sources"] == ["neural_kdj", "normal"]
    assert summary["starved_sources"] == ["weight_kdj"]
    assert summary["zero_top5_sources"] == ["ridge_kdj"]
    assert summary["sources"]["weight_kdj"]["prefilter_selection_rate"] == 0.0
    assert summary["sources"]["neural_kdj"]["round_best_rounds"] == 1

    markdown = render_candidate_source_survival_markdown(summary)
    assert "Candidate Source Survival Window" in markdown
    assert "weight_kdj" in markdown
    operator = operator_summary(
        {
            "recommendation": {"severity": "ok", "action": "continue_current_run"},
            "candidate_source_survival": summary,
        }
    )
    assert operator["candidate_source_survival"]["starved_sources"] == ["weight_kdj"]
    assert operator["candidate_source_survival"]["budget_review_ready"] is False


def test_candidate_source_survival_flags_mature_single_productive_source_window():
    rows = [
        source_survival_round(
            index,
            {
                "normal": {
                    "generated": 7,
                    "prefilter_selected": 7,
                    "full_eval_top5": 5,
                    "round_best": True,
                },
                "neural_kdj": {
                    "generated": 3,
                    "prefilter_selected": 1,
                    "full_eval_top5": 0,
                    "round_best": False,
                },
            },
        )
        for index in range(1, 5)
    ]

    summary = summarize_candidate_source_survival(rows)

    assert summary["status"] == "narrow"
    assert summary["action"] == "inspect_candidate_diversity"
    assert summary["productive_sources"] == ["normal"]


def test_candidate_source_survival_opens_budget_review_only_after_eight_same_run_rounds():
    rows = [
        source_survival_round(
            index,
            {
                "normal": {
                    "generated": 7,
                    "prefilter_selected": 6,
                    "full_eval_top5": 3,
                    "round_best": index == 1,
                },
                "recency_canary": {
                    "generated": 4,
                    "prefilter_selected": 1,
                    "full_eval_top5": 0,
                    "round_best": False,
                },
                "weight_kdj": {
                    "generated": 7,
                    "prefilter_selected": 0,
                    "full_eval_top5": 0,
                    "round_best": False,
                },
            },
        )
        for index in range(1, 9)
    ]

    summary = summarize_candidate_source_survival(rows)

    assert summary["evidence_ready"] is True
    assert summary["budget_review_ready"] is True
    assert summary["budget_review_action"] == "review_persistently_unproductive_source_budgets"
    assert summary["budget_review_sources"] == ["recency_canary", "weight_kdj"]
    assert summary["budget_experiment_candidate_ready"] is True
    assert summary["automatic_budget_change_allowed"] is False
    assert summary["history_surface_signature_count"] == 1
    assert summary["performance_signature_count"] == 1
    assert summary["same_history_performance_repetition"] is True
    assert "same_history_performance_repetition" in summary["budget_review_limitations"]

    markdown = render_candidate_source_survival_markdown(summary)
    assert "observed=8/8 ready=True" in markdown
    assert "review_persistently_unproductive_source_budgets" in markdown
    assert "automatic_change=False" in markdown


def test_candidate_source_survival_separates_conversion_variety_from_repeated_performance():
    rows = []
    for index, selected in ((1, 0), (2, 2), (3, 1)):
        row = source_survival_round(
            index,
            {
                "normal": {
                    "generated": 7,
                    "prefilter_selected": 6,
                    "full_eval_top5": 3,
                    "round_best": True,
                },
                "weight_kdj": {
                    "generated": 7,
                    "prefilter_selected": selected,
                    "full_eval_top5": 0,
                    "round_best": False,
                },
            },
        )
        row.update(
            {
                "best_config": {"frequency": 1.0},
                "top_100_hits": 3,
                "top_1000_hits": 3,
                "top_10000_hits": 3,
                "objective_score": 1.0,
            }
        )
        rows.append(row)

    summary = summarize_candidate_source_survival(
        rows,
        min_rounds=3,
        min_generated=1,
        budget_review_min_rounds=3,
    )

    assert summary["source_conversion_signature_count"] == 3
    assert summary["history_surface_signature_count"] == 1
    assert summary["performance_signature_count"] == 1
    assert summary["evidence_geometry"] == "distinct_source_conversion_same_performance"
    assert summary["budget_experiment_candidate_ready"] is True
    assert summary["automatic_budget_change_allowed"] is False

    operator = operator_summary(
        {
            "recommendation": {"severity": "warn", "action": "await_new_forward_issue"},
            "candidate_source_survival": summary,
        }
    )
    candidate = operator["candidate_source_survival"]
    assert candidate["source_conversion_signature_count"] == 3
    assert candidate["history_surface_signature_count"] == 1
    assert candidate["performance_signature_count"] == 1
    assert candidate["automatic_budget_change_allowed"] is False


def test_candidate_source_survival_does_not_call_different_histories_same_surface():
    rows = []
    for index, issue in enumerate(("2026077", "2026078", "2026079"), start=1):
        row = source_survival_round(
            index,
            {
                "weight_kdj": {
                    "generated": 7,
                    "prefilter_selected": 1,
                    "full_eval_top5": 0,
                    "round_best": False,
                }
            },
        )
        row.update(
            {
                "as_of_issue": issue,
                "history_fingerprint": f"history-{issue}",
                "best_config": {"frequency": 1.0},
                "top_100_hits": 0,
                "objective_score": 0.0,
            }
        )
        rows.append(row)

    summary = summarize_candidate_source_survival(
        rows,
        min_rounds=3,
        min_generated=1,
        budget_review_min_rounds=3,
    )

    assert summary["history_surface_signature_count"] == 3
    assert summary["performance_signature_count"] == 3
    assert summary["same_history_performance_repetition"] is False
    assert "same_history_performance_repetition" not in summary["budget_review_limitations"]


def test_candidate_source_survival_preserves_guarded_recovery_source_budget():
    rows = []
    for index in range(1, 9):
        prefilter_fields = {}
        if index == 8:
            prefilter_fields = {
                "source_frontier_champion": {
                    "active": True,
                    "source": "stagnation_restart",
                    "config_hash": "restart-frontier",
                    "candidate_primary_score": [0, 0, 1],
                    "baseline_primary_score": [0, 0, 0],
                },
                "decision_round_best": {
                    "source": "source_frontier",
                    "config_hash": "restart-frontier",
                },
                "search_base": {
                    "source": "round_best",
                    "config_hash": "restart-frontier",
                },
            }
        rows.append(
            source_survival_round(
                index,
                {
                    "normal": {
                        "generated": 7,
                        "prefilter_selected": 6,
                        "full_eval_top5": 3,
                        "round_best": index == 1,
                    },
                    "stagnation_restart": {
                        "generated": 5,
                        "prefilter_selected": 1,
                        "full_eval_top5": 0,
                        "round_best": False,
                    },
                    "weight_kdj": {
                        "generated": 7,
                        "prefilter_selected": 1,
                        "full_eval_top5": 0,
                        "round_best": False,
                    },
                },
                **prefilter_fields,
            )
        )

    summary = summarize_candidate_source_survival(rows)

    assert summary["budget_review_ready"] is True
    assert summary["budget_review_sources"] == ["weight_kdj"]
    assert summary["productive_sources"] == ["normal", "stagnation_restart"]
    assert summary["recovery_productive_sources"] == ["stagnation_restart"]
    assert summary["zero_top5_sources"] == ["weight_kdj"]
    restart = summary["sources"]["stagnation_restart"]
    assert restart["state"] == "productive_recovery"
    assert restart["frozen_frontier_rounds"] == 1
    assert restart["guarded_navigation_rounds"] == 1
    assert restart["frozen_frontier_per_generated_round_rate"] == 0.125

    markdown = render_candidate_source_survival_markdown(summary)
    assert "Frozen frontier" in markdown
    assert "Guarded navigation" in markdown
    assert "productive_recovery" in markdown

    operator = operator_summary(
        {
            "recommendation": {"severity": "ok", "action": "continue_current_run"},
            "candidate_source_survival": summary,
        }
    )
    assert operator["candidate_source_survival"]["recovery_productive_sources"] == [
        "stagnation_restart"
    ]


def test_candidate_source_survival_requires_verified_primary_lift_for_recovery_value():
    rows = [
        source_survival_round(
            1,
            {
                "stagnation_restart": {
                    "generated": 5,
                    "prefilter_selected": 1,
                    "full_eval_top5": 0,
                    "round_best": False,
                }
            },
            source_frontier_champion={
                "active": True,
                "source": "stagnation_restart",
                "config_hash": "no-primary-lift",
                "candidate_primary_score": [0, 0, 0],
                "baseline_primary_score": [0, 0, 0],
            },
            decision_round_best={
                "source": "source_frontier",
                "config_hash": "no-primary-lift",
            },
            search_base={"config_hash": "no-primary-lift"},
        )
    ]

    summary = summarize_candidate_source_survival(
        rows,
        min_rounds=1,
        min_generated=1,
        budget_review_min_rounds=1,
    )

    restart = summary["sources"]["stagnation_restart"]
    assert restart["frozen_frontier_rounds"] == 0
    assert restart["guarded_navigation_rounds"] == 0
    assert restart["state"] == "evaluated_without_top5"
    assert summary["recovery_productive_sources"] == []
    assert summary["budget_review_sources"] == ["stagnation_restart"]


def test_candidate_source_survival_preserves_selected_search_navigation_source_budget():
    rows = []
    for index in range(1, 9):
        selected_hash = f"restart-{index}"
        rows.append(
            source_survival_round(
                index,
                {
                    "normal": {
                        "generated": 5,
                        "prefilter_selected": 4,
                        "full_eval_top5": 2,
                        "round_best": index == 1,
                    },
                    "stagnation_restart": {
                        "generated": 5,
                        "prefilter_selected": 1,
                        "full_eval_top5": 0,
                        "round_best": False,
                    },
                },
                holdout_isolation={
                    "protocol": "search_slice_frozen_promotion_v1",
                    "frozen_validation_role": "promotion_only",
                    "search_uses_frozen_validation": False,
                },
                search_base={
                    "source": "experimental_navigation",
                    "config_hash": selected_hash,
                    "selection_uses_frozen_validation": False,
                    "exploration_navigation_source": "rank_homogeneity_restart_champion",
                    "exploration_navigation_config_hash": selected_hash,
                    "exploration_navigation_selected": True,
                },
                rank_homogeneity_restart_champion={
                    "active": True,
                    "source": "stagnation_restart",
                    "config_hash": selected_hash,
                },
            )
        )

    summary = summarize_candidate_source_survival(rows)

    assert summary["budget_review_ready"] is True
    assert summary["budget_review_sources"] == []
    assert summary["search_navigation_sources"] == ["stagnation_restart"]
    assert summary["productive_sources"] == ["normal", "stagnation_restart"]
    restart = summary["sources"]["stagnation_restart"]
    assert restart["search_navigation_rounds"] == 8
    assert restart["state"] == "productive_search_navigation"

    markdown = render_candidate_source_survival_markdown(summary)
    assert "Promotion-only selected search navigation: [stagnation_restart]" in markdown
    assert "productive_search_navigation" in markdown

    operator = operator_summary(
        {
            "recommendation": {"severity": "ok", "action": "continue_current_run"},
            "candidate_source_survival": summary,
        }
    )
    assert operator["candidate_source_survival"]["search_navigation_sources"] == [
        "stagnation_restart"
    ]


def test_candidate_source_survival_excludes_unverified_prefilter_isolation_rounds():
    rows = [
        source_survival_round(
            1,
            {
                "normal": {
                    "generated": 7,
                    "prefilter_selected": 6,
                    "full_eval_top5": 5,
                    "round_best": True,
                }
            },
            holdout_isolation={
                "protocol": "search_slice_frozen_promotion_v1",
                "frozen_validation_role": "promotion_only",
                "search_uses_frozen_validation": False,
                "prefilter_isolation_status": "failed",
                "prefilter_frozen_issue_overlap_count": 1,
                "prefilter_uses_frozen_validation": True,
            },
        )
    ]

    summary = summarize_candidate_source_survival(
        rows,
        min_rounds=1,
        min_generated=1,
        budget_review_min_rounds=1,
    )

    assert summary["observed_round_count"] == 0
    assert summary["unverified_prefilter_round_count"] == 1
    assert summary["evidence_ready"] is False
    assert summary["status"] == "invalidated"
    assert summary["action"] == "restart_with_verified_prefilter_isolation"
    assert summary["sources"] == {}


def test_candidate_source_survival_rejects_preempted_navigation_credit():
    unsafe_rows = []
    for index in range(1, 9):
        unsafe_rows.append(
            source_survival_round(
                index,
                {
                    "stagnation_restart": {
                        "generated": 5,
                        "prefilter_selected": 1,
                        "full_eval_top5": 0,
                        "round_best": False,
                    }
                },
                holdout_isolation={
                    "protocol": "search_slice_frozen_promotion_v1",
                    "frozen_validation_role": "promotion_only",
                    "search_uses_frozen_validation": False,
                },
                search_base={
                    "source": "probability_focus",
                    "config_hash": f"focus-{index}",
                    "selection_uses_frozen_validation": False,
                    "exploration_navigation_source": "rank_homogeneity_restart_champion",
                    "exploration_navigation_config_hash": f"restart-{index}",
                    "exploration_navigation_selected": False,
                    "exploration_navigation_preempted_by": "probability_focus",
                },
                rank_homogeneity_restart_champion={
                    "active": True,
                    "source": "stagnation_restart",
                    "config_hash": f"restart-{index}",
                },
            )
        )

    summary = summarize_candidate_source_survival(unsafe_rows)

    assert summary["search_navigation_sources"] == []
    assert summary["sources"]["stagnation_restart"]["search_navigation_rounds"] == 0
    assert summary["sources"]["stagnation_restart"]["state"] == "evaluated_without_top5"
    assert summary["budget_review_sources"] == ["stagnation_restart"]


def test_candidate_source_survival_rejects_frozen_or_mismatched_navigation_credit():
    rows = []
    for index in range(1, 9):
        selected_hash = f"restart-{index}"
        rows.append(
            source_survival_round(
                index,
                {
                    "stagnation_restart": {
                        "generated": 5,
                        "prefilter_selected": 1,
                        "full_eval_top5": 0,
                        "round_best": False,
                    }
                },
                holdout_isolation={
                    "protocol": "search_slice_frozen_promotion_v1",
                    "frozen_validation_role": "promotion_only",
                    "search_uses_frozen_validation": False,
                },
                search_base={
                    "source": "experimental_navigation",
                    "config_hash": selected_hash,
                    "selection_uses_frozen_validation": index % 2 == 1,
                    "exploration_navigation_source": "rank_homogeneity_restart_champion",
                    "exploration_navigation_config_hash": (
                        selected_hash if index % 2 == 1 else f"mismatch-{index}"
                    ),
                    "exploration_navigation_selected": True,
                },
                rank_homogeneity_restart_champion={
                    "active": True,
                    "source": "stagnation_restart",
                    "config_hash": selected_hash,
                },
            )
        )

    summary = summarize_candidate_source_survival(rows)

    assert summary["search_navigation_sources"] == []
    assert summary["sources"]["stagnation_restart"]["search_navigation_rounds"] == 0
    assert summary["sources"]["stagnation_restart"]["state"] == "evaluated_without_top5"
    assert summary["budget_review_sources"] == ["stagnation_restart"]


def test_candidate_source_survival_reports_recovery_for_top5_productive_source():
    rows = [
        source_survival_round(
            1,
            {
                "normal": {
                    "generated": 7,
                    "prefilter_selected": 6,
                    "full_eval_top5": 1,
                    "round_best": True,
                }
            },
            source_frontier_champion={
                "active": True,
                "source": "normal",
                "config_hash": "normal-frontier",
                "candidate_primary_score": [0, 0, 1],
                "baseline_primary_score": [0, 0, 0],
            },
        )
    ]

    summary = summarize_candidate_source_survival(
        rows,
        min_rounds=1,
        min_generated=1,
        budget_review_min_rounds=1,
    )

    assert summary["sources"]["normal"]["state"] == "productive"
    assert summary["sources"]["normal"]["frozen_frontier_rounds"] == 1
    assert summary["recovery_productive_sources"] == ["normal"]


def test_promotion_only_frozen_frontier_is_diagnostic_not_budget_evidence():
    rows = [
        source_survival_round(
            1,
            {
                "stagnation_restart": {
                    "generated": 5,
                    "prefilter_selected": 1,
                    "full_eval_top5": 0,
                    "round_best": False,
                }
            },
            holdout_isolation={
                "frozen_validation_role": "promotion_only",
                "search_uses_frozen_validation": False,
            },
            source_frontier_champion={
                "active": True,
                "source": "stagnation_restart",
                "config_hash": "diagnostic-frontier",
                "candidate_primary_score": [0, 0, 1],
                "baseline_primary_score": [0, 0, 0],
            },
            decision_round_best={
                "source": "source_frontier",
                "config_hash": "diagnostic-frontier",
            },
            search_base={"config_hash": "diagnostic-frontier"},
        )
    ]

    summary = summarize_candidate_source_survival(
        rows,
        min_rounds=1,
        min_generated=1,
        budget_review_min_rounds=1,
    )

    restart = summary["sources"]["stagnation_restart"]
    assert restart["frozen_frontier_rounds"] == 1
    assert restart["frozen_frontier_diagnostic_only_rounds"] == 1
    assert restart["budget_eligible_frozen_frontier_rounds"] == 0
    assert restart["guarded_navigation_rounds"] == 0
    assert restart["state"] == "evaluated_without_top5"
    assert summary["recovery_productive_sources"] == []
    assert summary["frozen_diagnostic_sources"] == ["stagnation_restart"]
    assert summary["budget_review_sources"] == ["stagnation_restart"]


def test_gate_summary_distinguishes_missing_frozen_validation_bypass_from_navigation_gate():
    gates = gate_summary(
        {
            "promotion_gate": {
                "passed": True,
                "reason": "missing_frozen_validation",
            },
            "decision_round_best": {
                "frozen_primary_lift_required": False,
            },
        }
    )

    assert gates["promotion_gate"]["frozen_validation_evaluated"] is False
    assert gates["promotion_gate"]["frozen_validation_bypassed"] is True
    assert gates["decision_round_best"]["frozen_primary_lift_required"] is False


def test_advisor_signal_freshness_flags_lagging_and_future_signals():
    freshness = advisor_signal_freshness_summary(
        {
            "weight_kdj_advisor": {
                "enabled": True,
                "latest_signal_issue": "2026068",
            },
            "ridge_kdj_advisor": {
                "enabled": True,
                "latest_signal_issue": "2026078",
            },
            "neural_kdj_advisor": {
                "enabled": True,
                "latest_signal_issue": "2026079",
            },
        },
        history_latest_issue="2026078",
    )

    assert freshness["status"] == "signal_issue_ahead_of_history"
    assert freshness["stale_advisors"] == ["weight_kdj_advisor"]
    assert freshness["future_advisors"] == ["neural_kdj_advisor"]
    assert freshness["advisors"]["weight_kdj_advisor"]["issue_lag"] == 10
    assert freshness["advisors"]["ridge_kdj_advisor"]["status"] == "current"


def test_advisor_signal_freshness_uses_history_order_across_year_boundary():
    freshness = advisor_signal_freshness_summary(
        {
            "weight_kdj_advisor": {
                "enabled": True,
                "latest_signal_issue": "2025151",
            }
        },
        history_latest_issue="2026001",
        history_issues=["2025150", "2025151", "2026001"],
    )

    assert freshness["status"] == "current"
    assert freshness["advisors"]["weight_kdj_advisor"]["issue_lag"] == 1


def test_advisor_signal_freshness_accepts_declared_search_slice_cutoff():
    freshness = advisor_signal_freshness_summary(
        {
            "target_weight_inversion_advisor": {
                "enabled": True,
                "latest_signal_issue": "2026058",
                "signal_scope": "search_slice",
                "expected_cutoff_issue": "2026058",
            }
        },
        history_latest_issue="2026078",
    )

    advisor = freshness["advisors"]["target_weight_inversion_advisor"]
    assert freshness["status"] == "current"
    assert freshness["stale_advisors"] == []
    assert advisor["status"] == "current_search_slice"
    assert advisor["issue_lag"] == 20
    assert advisor["signal_scope"] == "search_slice"


def test_recommendation_warns_when_advisor_signals_are_stale():
    now = datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc)
    recommendation = recommendation_summary(
        rows=[
            {
                "round_index": 1,
                "updated_at": now - timedelta(minutes=1),
                "improved": False,
            }
        ],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={},
        now=now,
        stale_minutes=30,
        advisor_signal_freshness={
            "status": "stale",
            "history_latest_issue": "2026078",
            "max_allowed_issue_lag": 1,
            "stale_advisors": ["weight_kdj_advisor"],
        },
    )

    assert recommendation["severity"] == "warn"
    assert recommendation["action"] == "refresh_advisor_signals"
    assert any("lag the latest history" in note for note in recommendation["notes"])


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


def test_recommendation_observes_guard_continuity_before_another_restart():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    rows = [
        {
            "round_index": 1,
            "improved": False,
            "updated_at": now - timedelta(minutes=1),
        }
    ]

    recommendation = recommendation_summary(
        rows=rows,
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        now=now,
        stale_minutes=30,
        round_stats={
            "round_count": 1,
            "latest_round": 1,
            "last_improved_round": None,
            "stagnation_rounds": 80,
            "current_run_stagnation_rounds": 1,
            "improvement_count": 0,
        },
    )

    assert recommendation["severity"] == "warn"
    assert recommendation["action"] == "watch_stagnation_recovery"
    assert "prepare_restart_with_more_exploration" not in recommendation["actions"]
    assert any(
        "Guard continuity restored high same-history stagnation" in note
        and "current=1" in note
        for note in recommendation["notes"]
    )


def test_round_repetition_diagnostic_surfaces_repeated_config_and_metrics(tmp_path):
    rows = [
        {
            "round_index": index,
            "best_config": {"frequency_weight": 0.7, "structural_weight": 0.7},
            "top_100_hits": 3,
            "top_1000_hits": 3,
            "top_10000_hits": 3,
            "red5_top_100_hits": 3,
            "red5_top_1000_hits": 13,
            "red5_top_10000_hits": 29,
            "median_rank": 556718.5,
            "best_rank": 39,
            "worst_rank": 1091300,
            "objective_score": 5083.928984,
        }
        for index in range(1, 5)
    ]

    diagnostic = summarize_round_repetition(rows)
    recommendation = recommendation_summary(
        rows=rows,
        lock={"active": True, "owner": "training-supervisor"},
        advisors={},
        now=datetime(2026, 7, 10, 2, 0, tzinfo=timezone.utc),
        stale_minutes=30,
        round_repetition=diagnostic,
    )
    evidence = evidence_context_summary(
        supervisor_status={"status": "running", "run_id": "run-1", "pid": 12345},
        gates={},
        parser_sync_duplicate_checks={"status": "checked", "ok": True},
        round_repetition=diagnostic,
    )
    payload = {
        "generated_at": "2026-07-10T02:00:00Z",
        "run_id": "run-1",
        "round_count": 4,
        "latest_round": 4,
        "last_improved_round": 1,
        "stagnation_rounds": 3,
        "latest_metrics": {},
        "advisor_summary": {},
        "round_repetition": diagnostic,
        "heavy_job_lock": {},
        "recommendation": recommendation,
        "guardrail": "Historical response-surface monitoring only.",
    }

    summary = cli_summary(payload, tmp_path / "watch.json", tmp_path / "watch.md")
    markdown = render_markdown(payload)

    assert diagnostic["status"] == "ready"
    assert diagnostic["active"] is True
    assert diagnostic["reason"] == "same_config_and_metrics_repeated"
    assert diagnostic["window_count"] == 4
    assert diagnostic["unique_config_count"] == 1
    assert diagnostic["observed_config_count"] == 4
    assert diagnostic["dominant_config_repeat_count"] == 4
    assert diagnostic["latest_config_repeat_streak"] == 4
    assert diagnostic["unique_metric_signature_count"] == 1
    assert diagnostic["dominant_metric_repeat_count"] == 4
    assert diagnostic["latest_metric_repeat_streak"] == 4
    assert summary["round_repetition"]["reason"] == "same_config_and_metrics_repeated"
    assert summary["round_repetition"]["latest_config_repeat_streak"] == 4
    assert summary["round_repetition"]["dominant_config_hash"]
    assert summary["round_repetition"]["dominant_metric_signature_hash"]
    assert "not predictive evidence" in summary["round_repetition"]["interpretation"]
    assert recommendation["severity"] == "ok"
    assert any("Round repetition diagnostic is active" in note for note in recommendation["notes"])
    assert any("not predictive evidence or a restart decision" in note for note in recommendation["notes"])
    assert (
        "round_repetition:same_config_and_metrics_repeated:window=4"
        in evidence["failure_modes"]
    )
    assert evidence["search_diagnostics"]["round_repetition"]["latest_metric_repeat_streak"] == 4
    assert "## Round Repetition Diagnostic" in markdown
    assert "reason=same_config_and_metrics_repeated" in markdown
    assert "Config repeats: unique=1/4" in markdown
    assert "Metric repeats: unique=1/4" in markdown
    assert "not predictive evidence or a restart decision" in markdown


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
                "trigger_mode": "low_diversity_cycle",
                "stagnation_rounds": 34,
                "stagnation_threshold": 16,
                "window": 12,
                "observed": 12,
                "unique_signature_count": 1,
                "max_unique_signatures": 4,
                "restart_batch_index": 3,
                "restart_catalog_offset": 15,
                "fallback_stagnation_threshold": 16,
                "fallback_window": 12,
                "fallback_observed": 12,
                "fallback_unique_signature_count": 1,
                "fallback_max_unique_signatures": 4,
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
        "trigger_mode": "low_diversity_cycle",
        "stagnation_rounds": 34,
        "stagnation_threshold": 16,
        "window": 12,
        "observed": 12,
        "unique_signature_count": 1,
        "max_unique_signatures": 4,
        "restart_batch_index": 3,
        "restart_catalog_offset": 15,
        "fallback_stagnation_threshold": 16,
        "fallback_window": 12,
        "fallback_observed": 12,
        "fallback_unique_signature_count": 1,
        "fallback_max_unique_signatures": 4,
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


def test_cli_summary_uses_safe_action_during_navigation_arbitration(tmp_path):
    payload = {
        "run_id": "run-1",
        "round_count": 74,
        "round_window_count": 12,
        "recommendation": {
            "severity": "alert",
            "action": "prepare_restart_with_more_exploration",
        },
        "restart_readiness": {
            "requested": True,
            "ready": False,
            "status": "blocked_by_current_run_navigation_arbitration",
            "blockers": [
                "active_training_supervisor_lock",
                "current_run_navigation_arbitration",
                "durable_round_boundary",
            ],
            "operator_action": (
                "continue_current_training_supervisor_through_navigation_arbitration"
            ),
            "current_run_navigation_arbitration_active": True,
            "experimental_navigation_selected": True,
            "durable_round_boundary_status": "target_complete_waiting_round_result",
        },
    }

    summary = cli_summary(payload, tmp_path / "watch.json", tmp_path / "watch.md")

    assert summary["action"] == (
        "continue_current_training_supervisor_through_navigation_arbitration"
    )
    assert summary["recommendation_action"] == (
        "prepare_restart_with_more_exploration"
    )
    assert summary["restart_readiness"]["ready"] is False
    assert (
        summary["restart_readiness"]["durable_round_boundary_status"]
        == "target_complete_waiting_round_result"
    )


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
                "eligibility_basis": "ineligible",
                "selection_uses_frozen_validation": False,
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
        "eligibility_basis": "ineligible",
        "selection_uses_frozen_validation": False,
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


def test_gate_summary_surfaces_eligible_navigation_preempted_by_probability_focus():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    prefilter = {
        "experimental_navigation_candidate": {
            "source": "rank_homogeneity_restart_champion",
            "reason": "rank_homogeneity_restart_changed_rank_vector",
            "config_hash": "restart-hash",
        },
        "search_base": {
            "source": "probability_focus",
            "config_hash": "focus-hash",
            "exploration_navigation_config_hash": "restart-hash",
            "exploration_navigation_eligible": True,
            "exploration_navigation_eligibility_basis": "search_slice_rank_geometry",
            "exploration_navigation_selection_uses_frozen_validation": False,
            "exploration_navigation_selected": False,
            "exploration_navigation_preempted_by": "probability_focus",
            "exploration_navigation_quality_reason": "zero_frozen_primary_without_tail_or_frontier_lift",
            "exploration_navigation_rank_vector_changed": True,
            "exploration_navigation_config_distance": 1.25,
            "min_config_distance": 0.08,
        },
    }

    gates = gate_summary(prefilter)
    navigation = gates["experimental_navigation_candidate"]
    recommendation = recommendation_summary(
        rows=[{"round_index": 40, "improved": False, "updated_at": now}],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        gates=gates,
        now=now,
        stale_minutes=30,
        round_stats={"stagnation_rounds": 40},
    )
    operator = operator_summary(
        {
            "run_id": "run-1",
            "gate_summary": gates,
            "recommendation": recommendation,
        }
    )

    assert navigation["eligible"] is True
    assert navigation["eligibility_reason"] == "eligible"
    assert navigation["eligibility_basis"] == "search_slice_rank_geometry"
    assert navigation["selection_uses_frozen_validation"] is False
    assert navigation["selected"] is False
    assert navigation["preempted_by"] == "probability_focus"
    assert operator["experimental_navigation_candidate"]["selected"] is False
    assert operator["experimental_navigation_candidate"]["preempted_by"] == "probability_focus"
    assert any(
        "search-slice eligible but not selected" in note
        and "preempted_by=probability_focus" in note
        and "uses_frozen=False" in note
        for note in recommendation["notes"]
    )


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
            "exploration_navigation_eligibility_basis": "ineligible",
            "exploration_navigation_selection_uses_frozen_validation": False,
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
        "eligibility_basis": "ineligible",
        "selection_uses_frozen_validation": False,
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


def test_gate_summary_surfaces_navigation_quality_block_from_standard_path():
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
            "exploration_navigation_eligibility_basis": "ineligible",
            "exploration_navigation_selection_uses_frozen_validation": False,
            "exploration_navigation_quality_reason": "zero_frozen_primary_without_tail_or_frontier_lift",
            "exploration_navigation_quality_blocked": True,
            "round_best_quality_blocked": True,
            "exploration_navigation_rank_vector_changed": True,
            "exploration_navigation_frozen_primary_score": [0, 0, 0],
            "exploration_navigation_baseline_frozen_primary_score": [0, 0, 0],
            "exploration_navigation_tail_over_1000000_delta": 2,
            "exploration_navigation_source_frontier_score_improved": False,
        },
    }

    gates = gate_summary(prefilter)
    navigation = gates["experimental_navigation_candidate"]

    assert navigation["eligible"] is False
    assert navigation["eligibility_reason"] == "zero_frozen_primary_without_tail_or_frontier_lift"
    assert navigation["eligibility_basis"] == "ineligible"
    assert navigation["selection_uses_frozen_validation"] is False
    assert navigation["quality_blocked_from_search_base"] is True
    assert navigation["round_best_quality_blocked"] is True

    operator = operator_summary(
        {
            "run_id": "run-1",
            "gate_summary": gates,
            "recommendation": {"severity": "ok", "action": "continue_current_run"},
        }
    )
    assert operator["experimental_navigation_candidate"]["quality_blocked_from_search_base"] is True
    assert operator["experimental_navigation_candidate"]["round_best_quality_blocked"] is True
    assert operator["experimental_navigation_candidate"]["eligibility_basis"] == "ineligible"
    assert operator["experimental_navigation_candidate"]["selection_uses_frozen_validation"] is False

    recommendation = recommendation_summary(
        rows=[{"round_index": 7, "improved": False, "updated_at": now}],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        gates=gates,
        now=now,
        stale_minutes=30,
        round_stats={"stagnation_rounds": 7},
    )

    assert any(
        "quality_blocked=True" in note
        and "reason=zero_frozen_primary_without_tail_or_frontier_lift" in note
        for note in recommendation["notes"]
    )


def test_gate_summary_surfaces_strict_primary_navigation_block_despite_tail_lift():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    prefilter = {
        "experimental_navigation_candidate": {
            "source": "rank_homogeneity_restart_champion",
            "reason": "rank_homogeneity_restart_changed_rank_vector",
            "config_hash": "restart-hash",
        },
        "search_base": {
            "frozen_primary_lift_required": True,
            "exploration_navigation_config_hash": "restart-hash",
            "exploration_navigation_eligible": False,
            "exploration_navigation_primary_lift_passed": False,
            "exploration_navigation_primary_lift_blocked": True,
            "exploration_navigation_quality_reason": "passed",
            "exploration_navigation_quality_blocked": False,
            "exploration_navigation_rank_vector_changed": True,
            "exploration_navigation_frozen_primary_score": [0, 0, 0],
            "exploration_navigation_baseline_frozen_primary_score": [0, 0, 0],
            "exploration_navigation_tail_over_1000000_delta": -2,
            "exploration_navigation_source_frontier_score_improved": False,
            "exploration_navigation_config_distance": 3.4,
            "min_config_distance": 0.08,
        },
    }

    gates = gate_summary(prefilter)
    navigation = gates["experimental_navigation_candidate"]

    assert navigation["eligible"] is False
    assert navigation["eligibility_reason"] == "frozen_primary_lift_required"
    assert navigation["quality_reason"] == "passed"
    assert navigation["primary_lift_passed"] is False
    assert navigation["primary_lift_blocked"] is True
    assert navigation["tail_over_1000000_delta"] == -2

    operator = operator_summary(
        {
            "run_id": "run-1",
            "gate_summary": gates,
            "recommendation": {"severity": "warn", "action": "watch_stagnation_recovery"},
        }
    )
    assert operator["experimental_navigation_candidate"]["primary_lift_passed"] is False
    assert operator["experimental_navigation_candidate"]["primary_lift_blocked"] is True

    recommendation = recommendation_summary(
        rows=[{"round_index": 17, "improved": False, "updated_at": now}],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        gates=gates,
        now=now,
        stale_minutes=30,
        round_stats={"stagnation_rounds": 17},
    )

    assert any(
        "reason=frozen_primary_lift_required" in note
        and "quality=passed" in note
        and "primary_lift_blocked=True" in note
        for note in recommendation["notes"]
    )


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


def test_restart_readiness_keeps_selected_navigation_in_current_supervisor():
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
            "round": 5,
            "target_index": 10,
            "target_total": 100,
            "target_complete": False,
            "age_minutes": 0.1,
            "fresh": True,
            "freshness_threshold_minutes": 30,
        },
    }
    gates = {
        "rank_homogeneity_restart_champion": {
            "active": True,
            "rank_vector_changed": True,
            "changed_target_count": 80,
            "full_eval_rank": 6,
            "source_frontier_primary_score_improved": True,
            "source_frontier_secondary_score_improved": False,
            "source_frontier_improvement_basis": "primary",
        },
        "experimental_navigation_candidate": {
            "eligible": True,
            "eligibility_reason": "eligible",
            "eligibility_basis": "search_slice_rank_geometry",
            "selection_uses_frozen_validation": False,
            "selected": True,
            "quality_reason": "passed",
            "rank_vector_changed": True,
            "config_distance": 1.45,
            "min_config_distance": 0.08,
        },
    }

    readiness = restart_readiness_summary(
        recommendation=recommendation,
        lock=lock,
        supervisor_status=supervisor_status,
        gates=gates,
        round_boundary={"status": "target_in_progress"},
    )

    assert readiness["status"] == "blocked_by_current_run_navigation_arbitration"
    assert readiness["blockers"] == [
        "active_training_supervisor_lock",
        "current_run_navigation_arbitration",
        "durable_round_boundary",
    ]
    assert readiness["blocker_stage"] == "current_run_navigation_arbitration_active"
    assert (
        readiness["operator_action"]
        == "continue_current_training_supervisor_through_navigation_arbitration"
    )
    assert readiness["current_run_navigation_arbitration_active"] is True
    assert readiness["durable_round_boundary_status"] == "target_in_progress"
    assert readiness["experimental_navigation_selected"] is True
    assert readiness["restart_candidate_evidence_ready"] is True


def test_restart_readiness_requires_durable_round_record_before_stop_review():
    readiness = restart_readiness_summary(
        recommendation={
            "action": "prepare_restart_with_more_exploration",
            "actions": ["prepare_restart_with_more_exploration"],
        },
        lock={"active": True, "owner": "training-supervisor", "pid": 12345},
        supervisor_status={
            "available": True,
            "status": "running",
            "run_mode": "continuous",
            "latest_progress": {
                "round": 10,
                "target_index": 100,
                "target_total": 100,
                "target_complete": True,
                "fresh": True,
            },
        },
        round_boundary={"status": "target_complete_waiting_round_result"},
    )

    assert readiness["status"] == "blocked_by_durable_round_boundary"
    assert readiness["blockers"] == [
        "active_training_supervisor_lock",
        "durable_round_boundary",
    ]
    assert readiness["blocker_stage"] == "durable_round_boundary_not_recorded"
    assert readiness["operator_action"] == "wait_for_durable_round_record_before_restart_review"


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
          "prediction_input_boundary": {
            "protocol": "dehps-draw-outcome-input-boundary-v1",
            "status": "passed",
            "action": "continue_draw_outcome_training",
            "training_fields": ["issue", "draw_date", "red_numbers"],
            "required_draw_fields": ["issue", "draw_date", "red_numbers"],
            "selected_market_aggregate_fields": [],
            "available_market_aggregate_fields_excluded": ["prize_tier_counts"],
            "ticket_distribution_observed": false,
            "ticket_distribution_identifiability": "aggregate_prize_counts_do_not_identify_ticket_level_number_selection",
            "market_data_role": "separate_observation_only_not_draw_probability",
            "draw_probability_effect": "none",
            "selection_changed": false,
            "promotion_allowed": false,
            "reasons": []
          },
          "forward_wait": {
            "process_active": true
          },
          "continuity_seed": {
            "mode": "same_history_validated_navigation_replay",
            "eligible": true,
            "reason": "strict_frozen_primary_lift_revalidated",
            "record_count": 17,
            "recovered_count": 1,
            "evaluated_count": 1,
            "eligible_count": 1,
            "selected_config_hash": "continuity-hash",
            "selected_frozen_primary_score": [0, 0, 1],
            "baseline_frozen_primary_score": [0, 0, 0]
          },
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
    assert status["status_reported_process_active"] is True
    assert status["deadline"] == "2026-07-01T06:00:00"
    assert status["latest_progress"]["round"] == 9
    assert status["latest_progress"]["target_complete"] is True
    assert status["latest_progress"]["elapsed_seconds"] == 53.3
    assert status["legal_universe_size"] == 1107568
    assert status["history_scope"] == "current_regime_default"
    assert status["train_window"] == 900
    assert status["eval_window"] == 100
    assert status["prediction_input_boundary"] == {
        "protocol": "dehps-draw-outcome-input-boundary-v1",
        "source_status": "passed",
        "status": "passed",
        "action": "continue_draw_outcome_training",
        "training_fields": ["issue", "draw_date", "red_numbers"],
        "required_draw_fields": ["issue", "draw_date", "red_numbers"],
        "selected_market_aggregate_fields": [],
        "available_market_aggregate_fields_excluded": ["prize_tier_counts"],
        "ticket_distribution_observed": False,
        "ticket_distribution_identifiability": (
            "aggregate_prize_counts_do_not_identify_ticket_level_number_selection"
        ),
        "market_data_role": "separate_observation_only_not_draw_probability",
        "draw_probability_effect": "none",
        "selection_changed": False,
        "promotion_allowed": False,
        "watcher_invariants_passed": True,
        "reasons": [],
    }
    assert status["continuity_seed"] == {
        "mode": "same_history_validated_navigation_replay",
        "eligible": True,
        "reason": "strict_frozen_primary_lift_revalidated",
        "record_count": 17,
        "recovered_count": 1,
        "evaluated_count": 1,
        "eligible_count": 1,
        "selected_config_hash": "continuity-hash",
        "selected_frozen_primary_score": [0, 0, 1],
        "baseline_frozen_primary_score": [0, 0, 0],
    }


def test_prediction_input_boundary_is_fail_closed_and_visible_to_operator():
    missing = watch.prediction_input_boundary_summary(None)
    assert missing["status"] == "missing"
    assert missing["promotion_allowed"] is False
    assert missing["draw_probability_effect"] == "unverified"

    boundary = watch.prediction_input_boundary_summary(
        {
            "protocol": "dehps-draw-outcome-input-boundary-v1",
            "status": "passed",
            "action": "continue_draw_outcome_training",
            "training_fields": ["issue", "draw_date", "red_numbers"],
            "required_draw_fields": ["issue", "draw_date", "red_numbers"],
            "selected_market_aggregate_fields": [],
            "available_market_aggregate_fields_excluded": [
                "prize_tier_counts",
                "sales_amount",
            ],
            "ticket_distribution_observed": False,
            "ticket_distribution_identifiability": (
                "aggregate_prize_counts_do_not_identify_ticket_level_number_selection"
            ),
            "market_data_role": "separate_observation_only_not_draw_probability",
            "draw_probability_effect": "none",
            "selection_changed": False,
            "promotion_allowed": False,
            "reasons": [],
        }
    )
    evidence = evidence_context_summary(
        supervisor_status={"status": "waiting_for_forward_issue", "run_id": "run-1"},
        gates={},
        parser_sync_duplicate_checks={"status": "checked", "ok": True},
        prediction_input_boundary=boundary,
    )
    payload = {
        "generated_at": "2026-07-11T07:00:00Z",
        "run_id": "run-1",
        "latest_metrics": {},
        "advisor_summary": {},
        "prediction_input_boundary": boundary,
        "evidence_context": evidence,
        "recommendation": {"severity": "warn", "action": "await_new_forward_issue"},
        "guardrail": "Historical response-surface monitoring only.",
    }

    operator = operator_summary(payload)
    markdown = render_markdown(payload)

    assert operator["prediction_input_boundary"]["status"] == "passed"
    assert operator["prediction_input_boundary"]["training_fields"] == [
        "issue",
        "draw_date",
        "red_numbers",
    ]
    assert operator["prediction_input_boundary"]["selected_market_aggregate_fields"] == []
    assert operator["prediction_input_boundary"]["ticket_distribution_observed"] is False
    assert operator["prediction_input_boundary"]["promotion_allowed"] is False
    assert operator["prediction_input_boundary"]["watcher_invariants_passed"] is True
    leakage = operator["evidence_context"]["leakage_checks"]
    assert leakage["prediction_input_boundary_status"] == "passed"
    assert leakage["prediction_input_boundary_invariants_passed"] is True
    assert leakage["draw_probability_effect"] == "none"
    assert "## Prediction Input Boundary" in markdown
    assert "aggregate_prize_counts_do_not_identify_ticket_level_number_selection" in markdown

    contradictory = watch.prediction_input_boundary_summary(
        {
            **boundary,
            "status": "passed",
            "selected_market_aggregate_fields": ["prize_tier_counts"],
            "draw_probability_effect": "candidate_score",
            "promotion_allowed": True,
        }
    )
    assert contradictory["status"] == "invalid"
    assert contradictory["action"] == "stop_supervisor_and_fix_prediction_input_boundary"
    assert contradictory["watcher_invariants_passed"] is False
    assert contradictory["promotion_allowed"] is True
    assert "market_aggregate_selected_for_draw_prediction" in contradictory["reasons"]
    assert "market_data_draw_probability_effect_not_none" in contradictory["reasons"]
    assert "prediction_boundary_promotion_not_disabled" in contradictory["reasons"]


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


def test_supervisor_lifecycle_identifies_intentionally_parked_status(monkeypatch):
    monkeypatch.setattr(watch, "is_pid_active", lambda pid: False)

    lifecycle = supervisor_lifecycle_summary(
        {
            "available": True,
            "status": "waiting_for_forward_issue",
            "pid": 3579268,
            "status_reported_process_active": False,
        }
    )

    assert lifecycle == {
        "protocol": "dehps-supervisor-lifecycle-observation-v1",
        "status": "parked_waiting_for_forward_issue",
        "status_file_available": True,
        "status_file_state": "waiting_for_forward_issue",
        "pid": 3579268,
        "status_reported_process_active": False,
        "expected_process_active": False,
        "observed_pid_active": False,
        "pid_activity_scope": "os_pid_exists_not_command_identity",
        "lifecycle_consistent": True,
        "requires_attention": False,
        "selection_changed": False,
        "promotion_allowed": False,
        "interpretation": (
            "The status artifact is available while its supervisor PID is inactive, matching "
            "the intentional forward-evidence parked state."
        ),
    }


def test_supervisor_lifecycle_flags_running_status_with_inactive_pid(monkeypatch):
    monkeypatch.setattr(watch, "is_pid_active", lambda pid: False)

    lifecycle = supervisor_lifecycle_summary(
        {"available": True, "status": "running", "pid": 12345}
    )

    assert lifecycle["status"] == "running_pid_inactive"
    assert lifecycle["expected_process_active"] is True
    assert lifecycle["observed_pid_active"] is False
    assert lifecycle["lifecycle_consistent"] is False
    assert lifecycle["requires_attention"] is True
    assert "inspect the supervisor log" in lifecycle["interpretation"]


def test_supervisor_lifecycle_reports_pid_scope_for_active_process(monkeypatch):
    monkeypatch.setattr(watch, "is_pid_active", lambda pid: True)

    lifecycle = supervisor_lifecycle_summary(
        {"available": True, "status": "running", "pid": 12345}
    )

    assert lifecycle["status"] == "running_pid_active"
    assert lifecycle["lifecycle_consistent"] is True
    assert lifecycle["requires_attention"] is False
    assert "does not verify" in lifecycle["interpretation"]


def test_supervisor_lifecycle_flags_waiting_status_with_unexpected_pid(monkeypatch):
    monkeypatch.setattr(watch, "is_pid_active", lambda pid: True)

    lifecycle = supervisor_lifecycle_summary(
        {
            "available": True,
            "status": "waiting_for_forward_issue",
            "pid": 12345,
            "status_reported_process_active": False,
        }
    )

    assert lifecycle["status"] == "waiting_status_pid_active"
    assert lifecycle["lifecycle_consistent"] is False
    assert lifecycle["requires_attention"] is True
    assert "PID reuse" in lifecycle["interpretation"]


def test_supervisor_lifecycle_does_not_probe_without_status_artifact(monkeypatch):
    def unexpected_probe(pid):
        raise AssertionError(f"unexpected PID probe: {pid}")

    monkeypatch.setattr(watch, "is_pid_active", unexpected_probe)

    lifecycle = supervisor_lifecycle_summary(
        {"available": False, "reason": "status_file_missing"}
    )

    assert lifecycle["status"] == "status_file_unavailable"
    assert lifecycle["observed_pid_active"] is None
    assert lifecycle["lifecycle_consistent"] is None
    assert lifecycle["requires_attention"] is True


def test_supervisor_lifecycle_is_visible_to_operator_and_markdown():
    lifecycle = {
        "protocol": "dehps-supervisor-lifecycle-observation-v1",
        "status": "parked_waiting_for_forward_issue",
        "status_file_available": True,
        "status_file_state": "waiting_for_forward_issue",
        "pid": 3579268,
        "status_reported_process_active": False,
        "expected_process_active": False,
        "observed_pid_active": False,
        "pid_activity_scope": "os_pid_exists_not_command_identity",
        "lifecycle_consistent": True,
        "requires_attention": False,
        "selection_changed": False,
        "promotion_allowed": False,
        "interpretation": "The supervisor is intentionally parked.",
    }
    payload = {
        "generated_at": "2026-07-11T08:30:00Z",
        "run_id": "run-1",
        "round_count": 8,
        "latest_metrics": {},
        "advisor_summary": {},
        "supervisor_lifecycle": lifecycle,
        "heavy_job_lock": {},
        "recommendation": {
            "severity": "warn",
            "action": "await_new_forward_issue",
            "notes": [],
        },
        "guardrail": "Historical response-surface monitoring only.",
    }

    summary = operator_summary(payload)
    markdown = render_markdown(payload)

    assert summary["supervisor_lifecycle"]["status"] == (
        "parked_waiting_for_forward_issue"
    )
    assert summary["supervisor_lifecycle"]["observed_pid_active"] is False
    assert "## Supervisor Lifecycle" in markdown
    assert "parked_waiting_for_forward_issue" in markdown


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


def test_recommendation_fails_closed_on_sync_conflicts():
    now = datetime(2026, 7, 11, 9, 10, tzinfo=timezone.utc)
    recommendation = recommendation_summary(
        rows=[
            {
                "round_index": 1,
                "improved": False,
                "updated_at": now,
                "prefilter": {},
            }
        ],
        lock={"active": False},
        advisors={},
        now=now,
        stale_minutes=30,
        supervisor_status={"status": "waiting_for_forward_issue"},
        parser_sync_duplicate_checks={
            "status": "checked",
            "ok": False,
            "latest_sync": {"conflict_count": 1},
            "recorded_data_conflict_count": 2,
            "unresolved_data_conflict_count": 2,
        },
    )

    assert recommendation["severity"] == "alert"
    assert recommendation["action"] == "inspect_parser_sync_conflicts"
    assert "latest_sync_conflicts=1 unresolved_conflicts=2 recorded_conflicts=2" in " ".join(
        recommendation["notes"]
    )


def test_recommendation_allows_preserved_resolved_conflict_evidence():
    now = datetime(2026, 7, 11, 9, 10, tzinfo=timezone.utc)
    recommendation = recommendation_summary(
        rows=[],
        lock={"active": False},
        advisors={},
        now=now,
        stale_minutes=30,
        supervisor_status={"status": "waiting_for_forward_issue"},
        parser_sync_duplicate_checks={
            "status": "checked",
            "ok": True,
            "latest_sync": {"conflict_count": 0},
            "recorded_data_conflict_count": 3,
            "unresolved_data_conflict_count": 0,
        },
    )

    assert recommendation["action"] != "inspect_parser_sync_conflicts"


def test_recommendation_prioritizes_critical_runtime_storage():
    now = datetime(2026, 7, 11, 10, 10, tzinfo=timezone.utc)
    recommendation = recommendation_summary(
        rows=[
            {
                "round_index": 1,
                "improved": False,
                "updated_at": now,
                "prefilter": {},
            }
        ],
        lock={"active": False},
        advisors={},
        now=now,
        stale_minutes=30,
        supervisor_status={"status": "waiting_for_forward_issue"},
        forward_wait={"ready": True},
        runtime_storage_capacity={
            "status": "critical",
            "action": "stop_new_heavy_jobs_and_recover_storage",
            "free_bytes": 4,
            "critical_threshold_bytes": 5,
            "blockers": ["disk_free_below_critical_threshold"],
        },
    )

    assert recommendation["severity"] == "alert"
    assert recommendation["action"] == "stop_new_heavy_jobs_and_recover_storage"
    assert recommendation["actions"][:2] == [
        "stop_new_heavy_jobs_and_recover_storage",
        watch.FORWARD_WAIT_ACTION,
    ]
    assert any("Runtime storage is not safe" in note for note in recommendation["notes"])


def test_runtime_storage_capacity_is_visible_to_operator_and_markdown():
    storage = {
        "protocol": "dehps-runtime-storage-capacity-v1",
        "status": "healthy",
        "action": "continue_storage_monitoring",
        "root_path": "/repo",
        "total_bytes": 1000,
        "used_bytes": 100,
        "free_bytes": 900,
        "free_ratio": 0.9,
        "warning_threshold_bytes": 50,
        "critical_threshold_bytes": 10,
        "observed_append_log_bytes": 18,
        "observed_append_logs": [
            {"path": "/repo/runtime/logs/hourly_self_iterate.log", "size_bytes": 18}
        ],
        "blockers": [],
        "automatic_cleanup_allowed": False,
        "selection_changed": False,
        "promotion_allowed": False,
        "interpretation": "Read-only capacity evidence.",
    }
    payload = {
        "runtime_storage_capacity": storage,
        "recommendation": {"severity": "ok", "action": "continue_current_run"},
    }

    operator = watch.operator_summary(payload)
    markdown = watch.render_runtime_storage_capacity_markdown(storage)

    assert operator["runtime_storage_capacity"]["status"] == "healthy"
    assert operator["runtime_storage_capacity"]["automatic_cleanup_allowed"] is False
    assert "## Runtime Storage Capacity" in markdown
    assert "hourly_self_iterate.log=18" in markdown


def test_remote_sync_cadence_is_visible_to_operator_and_markdown():
    cadence = {
        "protocol": "dehps-ssq-remote-sync-cadence-v1",
        "due": False,
        "reason": "cold_poll_interval_not_elapsed",
        "local_now": "2026-07-11T18:20:00+08:00",
        "draw_hot_window": False,
        "recovery_window": False,
        "cold_poll_minutes": 60,
        "cold_poll_boundary_tolerance_seconds": 60,
        "running_grace_minutes": 30,
        "last_attempt_at": "2026-07-11T18:10:00+08:00",
        "last_status": "success",
        "elapsed_minutes": 10.0,
        "retry_after_minutes": 50.0,
        "local_health_check_cadence_minutes": 10,
        "selection_changed": False,
        "promotion_allowed": False,
        "interpretation": "Remote cadence only.",
    }
    payload = {
        "remote_sync_cadence": cadence,
        "recommendation": {"severity": "ok", "action": "continue_current_run"},
    }

    operator = watch.operator_summary(payload)
    markdown = watch.render_remote_sync_cadence_markdown(cadence)

    assert operator["remote_sync_cadence"]["due"] is False
    assert operator["remote_sync_cadence"]["local_health_check_cadence_minutes"] == 10
    assert operator["remote_sync_cadence"]["cold_poll_boundary_tolerance_seconds"] == 60
    assert "## Remote Sync Cadence" in markdown
    assert "cold_poll_interval_not_elapsed" in markdown
    assert "boundary_tolerance=60s" in markdown


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
            "trigger_mode": "low_diversity_cycle",
            "stagnation_rounds": 34,
            "stagnation_threshold": 16,
            "window": 12,
            "observed": 12,
            "unique_signature_count": 1,
            "max_unique_signatures": 4,
            "restart_batch_index": 3,
            "restart_catalog_offset": 15,
            "fallback_stagnation_threshold": 16,
            "fallback_window": 12,
            "fallback_observed": 12,
            "fallback_unique_signature_count": 1,
            "fallback_max_unique_signatures": 4,
            "restart_candidate_novelty": {
                "history_hash_count": 75,
                "baseline_candidate_count": 5,
                "baseline_reused_count": 2,
                "baseline_reused_hashes": ["repeat-a", "repeat-b"],
                "generated_candidate_count": 5,
                "generated_reused_count": 0,
                "replacement_count": 2,
                "novelty_enforced": True,
            },
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
    assert gates["rank_homogeneity_guardrail"]["trigger_mode"] == "low_diversity_cycle"
    assert gates["rank_homogeneity_guardrail"]["stagnation_threshold"] == 16
    assert gates["rank_homogeneity_guardrail"]["window"] == 12
    assert gates["rank_homogeneity_guardrail"]["observed"] == 12
    assert gates["rank_homogeneity_guardrail"]["max_unique_signatures"] == 4
    assert gates["rank_homogeneity_guardrail"]["restart_batch_index"] == 3
    assert gates["rank_homogeneity_guardrail"]["restart_catalog_offset"] == 15
    assert gates["rank_homogeneity_guardrail"]["fallback_stagnation_threshold"] == 16
    assert gates["rank_homogeneity_guardrail"]["fallback_window"] == 12
    assert gates["rank_homogeneity_guardrail"]["restart_candidate_novelty"] == {
        "history_hash_count": 75,
        "baseline_candidate_count": 5,
        "baseline_reused_count": 2,
        "baseline_reused_hashes": ["repeat-a", "repeat-b"],
        "generated_candidate_count": 5,
        "generated_reused_count": 0,
        "replacement_count": 2,
        "novelty_enforced": True,
    }
    assert gates["rank_homogeneity_guardrail"]["signature_hashes"] == [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    ]
    assert gates["experimental_navigation_candidate"]["source"] == "exploration_champion"
    assert gates["decision_round_best"]["blocked_candidate_count"] == 1
    assert any("Promotion gate blocked" in note for note in recommendation["notes"])
    assert any("restart_batch=3 catalog_offset=15" in note for note in recommendation["notes"])
    assert any(
        "Restart exact-repeat filter applied" in note
        and "filtered=2 replacements=2 generated_reused=0" in note
        for note in recommendation["notes"]
    )
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
    assert "restart_novelty=2filtered/2replaced/0reused" in markdown
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
    operator = operator_summary(payload)
    assert operator["rank_homogeneity"]["restart_candidate_novelty"] == {
        "history_hash_count": 75,
        "baseline_candidate_count": 5,
        "baseline_reused_count": 2,
        "baseline_reused_hashes": ["repeat-a", "repeat-b"],
        "generated_candidate_count": 5,
        "generated_reused_count": 0,
        "replacement_count": 2,
        "novelty_enforced": True,
    }


def test_holdout_isolation_is_visible_in_gate_recommendation_markdown_and_evidence():
    now = datetime(2026, 7, 11, 1, 30, tzinfo=timezone.utc)
    prefilter = {
        "promotion_gate": {
            "passed": False,
            "reason": "historical_frozen_holdout_quarantined",
            "pre_quarantine_passed": True,
            "pre_quarantine_reason": "passed",
            "historical_holdout_quarantined": True,
            "promotion_holdout_status": "requires_forward_unseen_evidence",
            "objective_passed": True,
            "tail_passed": True,
            "primary_hit_passed": True,
            "candidate_primary_score": [0, 0, 1],
            "incumbent_primary_score": [0, 0, 0],
        },
        "holdout_isolation": {
            "protocol": "search_slice_frozen_promotion_v1",
            "total_window": 100,
            "search_window": 80,
            "frozen_window": 20,
            "issue_overlap_count": 0,
            "search_uses_frozen_validation": False,
            "prefilter_isolation_status": "passed",
            "prefilter_target_count": 20,
            "prefilter_search_issue_overlap_count": 20,
            "prefilter_frozen_issue_overlap_count": 0,
            "prefilter_outside_split_issue_count": 0,
            "prefilter_uses_frozen_validation": False,
            "frozen_validation_role": "promotion_only",
            "source_frontier_used_for_navigation": False,
            "historical_holdout_quarantined": True,
            "promotion_holdout_status": "requires_forward_unseen_evidence",
            "forward_unseen_evidence_required": True,
        },
        "stale_round_best_search_base_gate": {
            "active": True,
            "reason": "eval_slice_overfit_no_frozen_primary_lift",
            "require_frozen_primary_challenger": False,
            "allow_unpromoted_round_best": False,
            "threshold": 64,
            "navigation_evidence": "search_slice_only",
            "frozen_validation_role": "promotion_only",
        },
    }

    gates = gate_summary(prefilter)
    recommendation = recommendation_summary(
        rows=[{"round_index": 1, "improved": False, "updated_at": now}],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        gates=gates,
        now=now,
        stale_minutes=30,
    )
    evidence = evidence_context_summary(
        supervisor_status={
            "run_id": "isolated-run",
            "status": "running",
            "eval_window": 100,
            "ranked_universe_size": 1_105_506,
            "top_n": 10_000,
        },
        gates=gates,
        parser_sync_duplicate_checks={"status": "checked", "ok": True},
    )
    markdown = render_markdown(
        {
            "generated_at": "2026-07-11T01:30:00Z",
            "run_id": "isolated-run",
            "round_count": 1,
            "latest_round": 1,
            "last_improved_round": None,
            "stagnation_rounds": 1,
            "latest_metrics": {},
            "advisor_summary": {},
            "gate_summary": gates,
            "heavy_job_lock": {"active": True},
            "recommendation": recommendation,
            "guardrail": "No predictive claim.",
        }
    )

    assert gates["holdout_isolation"]["search_window"] == 80
    assert gates["holdout_isolation"]["search_uses_frozen_validation"] is False
    assert gates["holdout_isolation"]["prefilter_isolation_status"] == "passed"
    assert gates["holdout_isolation"]["prefilter_frozen_issue_overlap_count"] == 0
    assert gates["promotion_gate"]["historical_holdout_quarantined"] is True
    assert gates["stale_round_best_search_base_gate"]["navigation_evidence"] == "search_slice_only"
    assert any("Holdout isolation is active" in note for note in recommendation["notes"])
    assert any("forward unseen evidence" in note for note in recommendation["notes"])
    assert any("search-slice evidence only" in note for note in recommendation["notes"])
    assert evidence["historical_window"]["search_window"] == 80
    assert evidence["baseline_or_null_model"]["random_null_scope"] == "search_slice"
    assert evidence["baseline_or_null_model"]["random_null_expectation"]["eval_window"] == 80
    assert evidence["leakage_checks"]["search_uses_frozen_validation"] is False
    assert evidence["leakage_checks"]["prefilter_isolation_status"] == "passed"
    assert evidence["leakage_checks"]["prefilter_frozen_issue_overlap_count"] == 0
    assert evidence["leakage_checks"]["historical_holdout_quarantined"] is True
    assert "Holdout isolation:" in markdown
    assert "search/frozen=80/20" in markdown
    assert "prefilter=passed" in markdown
    assert "navigation_evidence=search_slice_only" in markdown


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
        "unresolved_data_conflict_count": 0,
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
    assert evidence["leakage_checks"]["decision_navigation_frozen_primary_lift_required"] is True
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
                "promotion_frozen_validation_evaluated": True,
                "promotion_frozen_validation_passed": False,
                "promotion_frozen_validation_bypassed": False,
                "eval_slice_overfit_guardrail_active": True,
                "suspicious_candidate_count": 8,
                "decision_navigation_frozen_primary_lift_required": True,
                "parser_sync_duplicate_checks": {
                    "status": "checked",
                    "ok": True,
                    "history_latest_issue": "2026074",
                    "history_draw_count": 1494,
                    "history_duplicate_issue_count": 0,
                    "history_invalid_red_length_count": 0,
                    "history_red_out_of_range_count": 0,
                    "history_duplicate_red_numbers_count": 0,
                    "history_blue_out_of_range_count": 0,
                    "universe_ok": True,
                    "red_combination_universe_count": 1107568,
                    "recorded_data_conflict_count": 3,
                    "unresolved_data_conflict_count": 0,
                    "latest_sync": {"status": "success", "conflict_count": 1},
                },
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
        "promotion_frozen_validation_evaluated": True,
        "promotion_frozen_validation_passed": False,
        "promotion_frozen_validation_bypassed": False,
        "eval_slice_overfit_guardrail_active": True,
        "suspicious_candidate_count": 8,
        "decision_navigation_frozen_primary_lift_required": True,
        "parser_sync_duplicate_status": "checked",
        "parser_sync_duplicate_ok": True,
    }
    assert summary["parser_sync"] == {
        "status": "checked",
        "ok": True,
        "history_latest_issue": "2026074",
        "history_draw_count": 1494,
        "history_duplicate_issue_count": 0,
        "history_invalid_red_length_count": 0,
        "history_red_out_of_range_count": 0,
        "history_duplicate_red_numbers_count": 0,
        "history_blue_out_of_range_count": 0,
        "universe_ok": True,
        "red_combination_universe_count": 1107568,
        "recorded_data_conflict_count": 3,
        "unresolved_data_conflict_count": 0,
        "latest_sync_status": "success",
        "latest_sync_conflict_count": 1,
    }


def test_operator_summary_preserves_unknown_parser_conflict_counts():
    payload = {
        "evidence_context": {
            "leakage_checks": {
                "parser_sync_duplicate_checks": {
                    "status": "unavailable",
                    "ok": False,
                    "recorded_data_conflict_count": "not-an-integer",
                    "latest_sync": {
                        "status": "error",
                        "conflict_count": "unknown",
                    },
                }
            }
        }
    }

    parser_sync = operator_summary(payload)["parser_sync"]

    assert parser_sync["recorded_data_conflict_count"] is None
    assert parser_sync["unresolved_data_conflict_count"] is None
    assert parser_sync["latest_sync_conflict_count"] is None


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


def artifact_persistence_payload(*, severity="ok", action="await_new_forward_issue"):
    return {
        "generated_at": "2026-07-11T09:30:00Z",
        "run_id": "run-1",
        "round_count": 8,
        "latest_round": 8,
        "last_improved_round": None,
        "stagnation_rounds": 204,
        "latest_metrics": {},
        "advisor_summary": {},
        "advisor_signal_freshness": {
            "status": "current",
            "history_latest_issue": "2026078",
            "stale_advisors": [],
            "missing_advisors": [],
            "future_advisors": [],
        },
        "forward_evidence": {
            "status": "not_started",
            "paired_issue_count": 0,
            "review_ready": False,
            "pending_snapshots": [{"predicted_issue": "2026079"}],
        },
        "forward_wait": {
            "status": "awaiting_new_forward_issue",
            "history_latest_issue": "2026078",
            "next_pending_issue": "2026079",
            "ready": True,
        },
        "supervisor_lifecycle": {
            "status": "parked_waiting_for_forward_issue",
            "lifecycle_consistent": True,
            "requires_attention": False,
        },
        "heavy_job_lock": {},
        "recommendation": {"severity": severity, "action": action, "notes": []},
        "guardrail": "Historical response-surface monitoring only.",
    }


def test_write_outputs_skips_stable_versioned_snapshot_inside_interval(
    monkeypatch, tmp_path
):
    stamps = iter(("20260711-093000", "20260711-094000"))
    monkeypatch.setattr(watch, "utc_stamp", lambda: next(stamps))
    now = datetime(2026, 7, 11, 9, 30, tzinfo=timezone.utc)

    first_json, _ = watch.write_outputs(
        artifact_persistence_payload(),
        tmp_path,
        min_snapshot_interval_minutes=120,
        now=now,
    )
    os.utime(first_json, (now.timestamp(), now.timestamp()))

    def fail_unbounded_snapshot_scan(*_args, **_kwargs):
        raise AssertionError("stable marker path must not scan all versioned artifacts")

    second_payload = artifact_persistence_payload()
    second_payload["generated_at"] = "2026-07-11T09:40:00Z"
    with monkeypatch.context() as marker_context:
        marker_context.setattr(
            type(tmp_path), "glob", fail_unbounded_snapshot_scan
        )
        second_json, second_md = watch.write_outputs(
            second_payload,
            tmp_path,
            min_snapshot_interval_minutes=120,
            now=now + timedelta(minutes=10),
        )

    versioned_json = [
        path for path in tmp_path.glob("training-watch-*.json")
        if path.name != "training-watch-latest.json"
    ]
    assert versioned_json == [first_json]
    assert second_json == tmp_path / "training-watch-latest.json"
    assert second_md == tmp_path / "training-watch-latest.md"
    latest = json.loads(second_json.read_text())
    assert "material_change_or_heartbeat_v1" in second_md.read_text()
    assert latest["generated_at"] == "2026-07-11T09:40:00Z"
    assert latest["artifact_persistence"] == {
        "protocol": "material_change_or_heartbeat_v1",
        "versioned_snapshot_created": False,
        "reason": "stable_within_interval",
        "min_snapshot_interval_minutes": 120,
        "previous_versioned_snapshot_age_seconds": 600.0,
        "latest_artifacts_updated": True,
        "existing_versioned_artifacts_deleted": False,
        "last_versioned_snapshot_at": now.isoformat(),
        "last_versioned_json_path": str(first_json),
        "last_versioned_report_path": str(first_json.with_suffix(".md")),
    }


def test_write_outputs_snapshots_material_state_change_inside_interval(
    monkeypatch, tmp_path
):
    stamps = iter(("20260711-093000", "20260711-094000"))
    monkeypatch.setattr(watch, "utc_stamp", lambda: next(stamps))
    now = datetime(2026, 7, 11, 9, 30, tzinfo=timezone.utc)
    first_json, _ = watch.write_outputs(
        artifact_persistence_payload(),
        tmp_path,
        min_snapshot_interval_minutes=120,
        now=now,
    )
    os.utime(first_json, (now.timestamp(), now.timestamp()))

    changed_json, _ = watch.write_outputs(
        artifact_persistence_payload(
            severity="alert",
            action="inspect_parser_sync_conflicts",
        ),
        tmp_path,
        min_snapshot_interval_minutes=120,
        now=now + timedelta(minutes=10),
    )

    assert changed_json.name == "training-watch-run-1-20260711-094000.json"
    changed = json.loads(changed_json.read_text())
    assert changed["artifact_persistence"]["versioned_snapshot_created"] is True
    assert changed["artifact_persistence"]["reason"] == "material_state_changed"


def test_write_outputs_snapshots_integrity_count_change_without_action_change(
    monkeypatch, tmp_path
):
    stamps = iter(("20260711-093000", "20260711-094000"))
    monkeypatch.setattr(watch, "utc_stamp", lambda: next(stamps))
    now = datetime(2026, 7, 11, 9, 30, tzinfo=timezone.utc)
    first = artifact_persistence_payload(
        severity="alert",
        action="inspect_parser_sync_conflicts",
    )
    first["evidence_context"] = {
        "leakage_checks": {
            "parser_sync_duplicate_checks": {
                "status": "checked",
                "ok": False,
                "unresolved_data_conflict_count": 1,
                "latest_sync": {"status": "success", "conflict_count": 1},
            }
        }
    }
    first_json, _ = watch.write_outputs(
        first,
        tmp_path,
        min_snapshot_interval_minutes=120,
        now=now,
    )
    os.utime(first_json, (now.timestamp(), now.timestamp()))
    changed = artifact_persistence_payload(
        severity="alert",
        action="inspect_parser_sync_conflicts",
    )
    changed["evidence_context"] = {
        "leakage_checks": {
            "parser_sync_duplicate_checks": {
                "status": "checked",
                "ok": False,
                "unresolved_data_conflict_count": 2,
                "latest_sync": {"status": "success", "conflict_count": 1},
            }
        }
    }

    changed_json, _ = watch.write_outputs(
        changed,
        tmp_path,
        min_snapshot_interval_minutes=120,
        now=now + timedelta(minutes=10),
    )

    assert changed_json.name == "training-watch-run-1-20260711-094000.json"
    artifact = json.loads(changed_json.read_text())
    assert artifact["artifact_persistence"]["reason"] == "material_state_changed"


def test_write_outputs_creates_stable_heartbeat_after_interval(
    monkeypatch, tmp_path
):
    stamps = iter(("20260711-093000", "20260711-113100"))
    monkeypatch.setattr(watch, "utc_stamp", lambda: next(stamps))
    now = datetime(2026, 7, 11, 9, 30, tzinfo=timezone.utc)
    first_json, _ = watch.write_outputs(
        artifact_persistence_payload(),
        tmp_path,
        min_snapshot_interval_minutes=120,
        now=now,
    )
    os.utime(first_json, (now.timestamp(), now.timestamp()))

    heartbeat_json, _ = watch.write_outputs(
        artifact_persistence_payload(),
        tmp_path,
        min_snapshot_interval_minutes=120,
        now=now + timedelta(minutes=121),
    )

    assert heartbeat_json.name == "training-watch-run-1-20260711-113100.json"
    heartbeat = json.loads(heartbeat_json.read_text())
    assert heartbeat["artifact_persistence"]["versioned_snapshot_created"] is True
    assert heartbeat["artifact_persistence"]["reason"] == "heartbeat_due"
    assert heartbeat["artifact_persistence"][
        "previous_versioned_snapshot_age_seconds"
    ] == 7260.0


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


def test_heavy_job_supervisor_relation_distinguishes_inactive_other_pid():
    relation = heavy_job_supervisor_relation_summary(
        supervisor_status={
            "available": True,
            "pid": 3579268,
            "status": "waiting_for_forward_issue",
        },
        lock={
            "active": False,
            "owner": "training-supervisor",
            "pid": 3647004,
            "status": "interrupted",
        },
    )

    assert relation == {
        "protocol": "dehps-heavy-job-supervisor-owner-relation-v1",
        "status": "different_inactive_pid",
        "supervisor_available": True,
        "supervisor_pid": 3579268,
        "heavy_job_pid": 3647004,
        "heavy_job_owner": "training-supervisor",
        "heavy_job_status": "interrupted",
        "heavy_job_active": False,
        "same_pid": False,
        "different_active_owner": False,
        "selection_changed": False,
        "promotion_allowed": False,
        "interpretation": (
            "Heavy-job metadata belongs to a different inactive PID. Preserve it as audit "
            "history; it does not describe the current supervisor process."
        ),
    }


def test_heavy_job_supervisor_relation_flags_different_active_pid():
    relation = heavy_job_supervisor_relation_summary(
        supervisor_status={"available": True, "pid": 101},
        lock={"active": True, "owner": "training-supervisor", "pid": 202},
    )

    assert relation["status"] == "different_active_pid"
    assert relation["same_pid"] is False
    assert relation["different_active_owner"] is True
    assert "do not overwrite" in relation["interpretation"]


def test_heavy_job_supervisor_relation_covers_same_and_unknown_pid_states():
    cases = [
        (
            {"available": True, "pid": 101},
            {"active": True, "pid": 101},
            "same_supervisor_pid",
            True,
        ),
        (
            {"available": True, "pid": 101},
            {"active": False},
            "heavy_job_pid_missing",
            None,
        ),
        (
            {"available": False, "pid": 101},
            {"active": False, "pid": 202},
            "supervisor_unavailable",
            False,
        ),
    ]

    for supervisor_status, lock, expected_status, expected_same_pid in cases:
        relation = heavy_job_supervisor_relation_summary(
            supervisor_status=supervisor_status,
            lock=lock,
        )

        assert relation["status"] == expected_status
        assert relation["same_pid"] is expected_same_pid


def test_heavy_job_supervisor_relation_is_visible_to_operator_and_markdown():
    relation = heavy_job_supervisor_relation_summary(
        supervisor_status={"available": True, "pid": 101},
        lock={
            "active": False,
            "owner": "training-supervisor",
            "pid": 202,
            "status": "interrupted",
        },
    )
    payload = {
        "generated_at": "2026-07-11T08:20:00Z",
        "run_id": "run-1",
        "round_count": 8,
        "latest_metrics": {},
        "advisor_summary": {},
        "heavy_job_lock": {"active": False, "pid": 202},
        "heavy_job_supervisor_relation": relation,
        "recommendation": {
            "severity": "warn",
            "action": "await_new_forward_issue",
            "notes": [],
        },
        "guardrail": "Historical response-surface monitoring only.",
    }

    summary = operator_summary(payload)
    markdown = render_markdown(payload)

    assert summary["heavy_job_supervisor_relation"]["status"] == (
        "different_inactive_pid"
    )
    assert summary["heavy_job_supervisor_relation"]["same_pid"] is False
    assert "## Heavy Job / Supervisor Relation" in markdown
    assert '"status": "different_inactive_pid"' in markdown


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
    monkeypatch.setattr(watch, "load_line_progress", lambda *_args, **_kwargs: watch.default_line_progress())
    monkeypatch.setattr(
        watch,
        "load_forward_evidence_rows",
        lambda: {"activation_after_issue": None, "evaluation_rows": [], "snapshot_rows": []},
    )
    monkeypatch.setattr(
        watch,
        "load_parser_sync_duplicate_checks",
        lambda: {"status": "checked", "ok": True},
    )
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
    monkeypatch.setattr(watch, "load_line_progress", lambda *_args, **_kwargs: watch.default_line_progress())
    monkeypatch.setattr(
        watch,
        "load_forward_evidence_rows",
        lambda: {"activation_after_issue": None, "evaluation_rows": [], "snapshot_rows": []},
    )
    monkeypatch.setattr(
        watch,
        "load_parser_sync_duplicate_checks",
        lambda: {"status": "checked", "ok": True},
    )
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
    monkeypatch.setattr(watch, "load_line_progress", lambda *_args, **_kwargs: watch.default_line_progress())
    monkeypatch.setattr(
        watch,
        "load_forward_evidence_rows",
        lambda: {"activation_after_issue": None, "evaluation_rows": [], "snapshot_rows": []},
    )
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


def test_operator_summary_exposes_self_diagnostics_and_strategy_memory_boundaries():
    payload = {
        "run_id": "run-1",
        "self_diagnostics": {
            "candidate_space": {
                "status": "diverse",
                "unique_top_rank_signature_count": 10,
                "round_best_path_status": "stale",
            },
            "decision_surface": {
                "status": "objective_tiebreak_tradeoff",
                "first_difference_counts": {"objective_score": 4},
                "pareto_tradeoff_count": 4,
                "objective_gap_min": 0.001,
                "objective_gap_max": 0.68,
                "selection_scope": "search_slice_only",
                "selection_uses_frozen_validation": False,
                "objective_component_control": {
                    "status": "measured",
                    "max_abs_reconstruction_residual": 0.0,
                    "selection_changed": False,
                    "selection_uses_frozen_validation": False,
                },
                "objective_component_counterfactual": {
                    "status": "measured",
                    "component": "tail_risk_penalty",
                    "counterfactual_top_changed": True,
                    "selection_changed": False,
                    "selection_uses_frozen_validation": False,
                },
            },
        },
        "strategy_memory": {
            "mode": "observe_only_strategy_memory",
            "memory_window": 8,
            "state": {
                "current_candidate_space": "diverse",
                "current_round_best_path": "stale",
                "objective_component_counterfactual_observation_window": {
                    "status": "mature",
                    "measured_round_count": 8,
                    "guard_violation_count": 0,
                    "promotion_allowed": False,
                },
            },
            "selected_experiment": {
                "key": "null_model_forward_audit",
                "promotion_allowed": False,
            },
        },
        "supervisor_status": {
            "available": True,
            "continuity_seed": {
                "mode": "holdout_isolated_search_replay",
                "eligible": True,
                "selected_config_hash": "seed-hash",
            },
            "strategy_memory_continuity": {
                "mode": "same_history_persisted_self_diagnostics",
                "record_count": 8,
                "selection_changed": False,
                "selection_uses_frozen_validation": False,
            },
        },
        "recommendation": {"severity": "warn", "action": "await_new_forward_issue"},
    }

    summary = operator_summary(payload)

    candidate_space = summary["self_diagnostics"]["candidate_space"]
    assert candidate_space["status"] == "diverse"
    assert candidate_space["unique_top_rank_signature_count"] == 10
    assert candidate_space["round_best_path_status"] == "stale"
    decision_surface = summary["self_diagnostics"]["decision_surface"]
    assert decision_surface["status"] == "objective_tiebreak_tradeoff"
    assert decision_surface["objective_component_control"]["selection_changed"] is False
    assert decision_surface["objective_component_counterfactual"]["selection_uses_frozen_validation"] is False
    observation = summary["strategy_memory"]["state"][
        "objective_component_counterfactual_observation_window"
    ]
    assert observation["status"] == "mature"
    assert observation["promotion_allowed"] is False
    assert summary["continuity_seed"]["selected_config_hash"] == "seed-hash"
    assert summary["strategy_memory_continuity"]["record_count"] == 8


def test_supervisor_status_summary_preserves_strategy_memory_continuity(tmp_path):
    status = supervisor_status_summary(
        {
            "run_id": "run-1",
            "strategy_memory_continuity": {
                "mode": "same_history_persisted_self_diagnostics",
                "record_count": 8,
                "limit": 8,
                "source_run_ids": ["run-a", "run-b"],
                "oldest_round": {"run_id": "run-a", "round_index": 1},
                "latest_round": {"run_id": "run-b", "round_index": 8},
                "current_run_excluded": "run-1",
                "selection_changed": False,
                "selection_uses_frozen_validation": False,
                "interpretation": "Read-only continuity.",
            },
        },
        path=tmp_path / "training-supervisor-run-1.json",
    )

    continuity = status["strategy_memory_continuity"]
    assert continuity["record_count"] == 8
    assert continuity["source_run_ids"] == ["run-a", "run-b"]
    assert continuity["selection_changed"] is False
    assert continuity["selection_uses_frozen_validation"] is False


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
