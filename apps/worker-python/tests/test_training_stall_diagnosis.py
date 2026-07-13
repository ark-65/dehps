from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/diagnose_training_stall.py"
SPEC = importlib.util.spec_from_file_location("stall_diagnosis", SCRIPT_PATH)
assert SPEC and SPEC.loader
stall_diagnosis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stall_diagnosis)


def stalled_watch() -> dict:
    return {
        "run_id": "run-1",
        "current_run_stagnation_rounds": 137,
        "forward_wait": {
            "history_latest_issue": "2026079",
            "next_pending_issue": "2026080",
            "observed_familywise_hypothesis_count": 8163,
        },
        "forward_evidence": {"paired_issue_count": 1, "min_paired_issues": 20},
        "round_repetition": {
            "active": True,
            "latest_config_repeat_streak": 5,
            "latest_metric_repeat_streak": 5,
        },
        "compute_capability": {
            "cpu": {"logical_count": 22, "configured_workers": 16},
            "accelerator": {
                "gpu_training_enabled": False,
                "probe_status": "completed",
                "probe_full_end_to_end_speedup": 0.85,
                "probe_rounded_changed_cell_count": 9,
            },
        },
        "supervisor_status": {
            "prediction_input_boundary": {
                "status": "passed",
                "training_fields": ["issue", "draw_date", "red_numbers"],
                "ticket_distribution_observed": False,
            }
        },
    }


def test_diagnosis_identifies_the_distinct_stall_dimensions(monkeypatch) -> None:
    monkeypatch.setattr(
        stall_diagnosis,
        "_dynamic_acceptance",
        lambda _: {
            "passed": False,
            "status": "FAIL",
            "failures": ["dynamic_did_not_beat_static"],
            "static_objective": 4.0,
            "dynamic_objective": 1.0,
            "null_objective": 0.0,
        },
    )
    diagnosis = stall_diagnosis.build_diagnosis(
        stalled_watch(),
        {"status": "completed", "runs": [{"name": "dynamic_kdj_frozen_backtest", "elapsed_seconds": 714.0}]},
    )

    assert diagnosis["critical_dimensions"] == [
        "forward_evidence",
        "search_geometry",
        "dynamic_kdj_model",
    ]
    assert diagnosis["selection_changed"] is False
    assert diagnosis["promotion_allowed"] is False
    assert "data_and_leakage" in {row["key"] for row in diagnosis["dimensions"]}


def test_diagnosis_fingerprint_changes_only_with_diagnostic_state(monkeypatch) -> None:
    monkeypatch.setattr(stall_diagnosis, "_dynamic_acceptance", lambda _: {})
    first = stall_diagnosis.build_diagnosis(stalled_watch(), {})
    second = stall_diagnosis.build_diagnosis(stalled_watch(), {})
    assert stall_diagnosis.fingerprint(first) == stall_diagnosis.fingerprint(second)
    changed = stalled_watch()
    changed["forward_evidence"]["paired_issue_count"] = 2
    assert stall_diagnosis.fingerprint(first) != stall_diagnosis.fingerprint(
        stall_diagnosis.build_diagnosis(changed, {})
    )
