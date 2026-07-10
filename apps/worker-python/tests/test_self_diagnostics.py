from __future__ import annotations

from dehps.optimization.self_diagnostics import (
    build_prediction_self_diagnostics,
    candidate_space_diagnostic,
    signal_vs_noise_diagnostic,
    weight_trust_diagnostic,
)


def test_weight_trust_blocks_leakage_and_missing_dynamic_offset():
    diagnostic = weight_trust_diagnostic(
        {
            "eval_window": 9,
            "changed_target_count": 9,
            "fallback_target_count": 0,
            "leakage_passed": False,
        },
        dynamic_metadata={"leakage_passed": False, "applied_offsets": {}},
    )

    assert diagnostic["status"] == "blocked"
    assert diagnostic["action"] == "do_not_trust_dynamic_weight"
    assert "leakage_guard_failed" in diagnostic["reasons"]
    assert "no_current_dynamic_offset_applied" in diagnostic["reasons"]


def test_candidate_space_diagnostic_detects_collapsed_top_window():
    candidates = [
        (index + 1, (1, 2, 3, 4, 5, 6 + index % 2), 1.0)
        for index in range(30)
    ]

    diagnostic = candidate_space_diagnostic(candidates)

    assert diagnostic["status"] == "collapsed"
    assert diagnostic["unique_red_number_count"] <= 7
    assert "top_candidates_use_too_few_red_numbers" in diagnostic["reasons"]


def test_signal_vs_noise_marks_small_window_as_noise_risk():
    diagnostic = signal_vs_noise_diagnostic(
        {"eval_window": 9, "top_100_hits": 3, "top_1000_hits": 3, "top_10000_hits": 3},
        legal_sample_space=1_107_568,
    )

    assert diagnostic["status"] == "noise_risk"
    assert "small_regression_window" in diagnostic["reasons"]
    assert diagnostic["strongest_band"]["label"] in {"top_100", "top_1000", "top_10000"}


def test_prediction_self_diagnostics_synthesizes_weakest_status():
    payload = build_prediction_self_diagnostics(
        regression_summary={
            "eval_window": 9,
            "changed_target_count": 9,
            "fallback_target_count": 0,
            "leakage_passed": True,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": 0,
        },
        candidates=[(index + 1, (1, 2, 3, 4, 5, 6 + index % 2), 1.0) for index in range(30)],
        legal_sample_space=1_107_568,
        dynamic_metadata={
            "leakage_passed": True,
            "applied_offsets": {"frequency_weight": 0.01},
            "strength_state": {"confidence": 0.5},
        },
    )

    assert payload["synthesis"]["status"] == "collapsed"
    assert payload["candidate_space"]["status"] == "collapsed"
    assert payload["signal_vs_noise"]["status"] == "noise_risk"
