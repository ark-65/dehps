from __future__ import annotations

from dehps.optimization.weight_kdj import (
    WeightKdjState,
    WeightProbeResult,
    next_kdj_state,
    rsv_from_interval,
    signal_from_probe_results,
    weight_kdj_advice_from_signals,
)


def test_rsv_uses_midpoint_when_interval_is_flat():
    assert rsv_from_interval(close_value=0.3, low_value=0.3, high_value=0.3) == 50.0


def test_next_kdj_state_matches_stock_style_smoothing():
    state = next_kdj_state(close_value=0.75, rolling_low_value=0.0, rolling_high_value=1.0)

    assert round(state.rsv, 6) == 75
    assert round(state.k_value, 6) == 58.333333
    assert round(state.d_value, 6) == 52.777778
    assert round(state.j_value, 6) == 69.444444


def test_signal_from_probe_results_uses_best_objective_as_close():
    signal, state = signal_from_probe_results(
        signal_run_id="weight-kdj-test",
        issue="2026068",
        draw_date="2026-06-16",
        weight_name="frequency_weight",
        train_mode="expanding",
        train_window=900,
        eval_window=1,
        top_n=10000,
        history_fingerprint="history-1",
        source="weight_response_probe_v0",
        base_value=0.30,
        step=0.03,
        probe_results=[
            WeightProbeResult("frequency_weight", 0.27, 8.0, "a", 500000),
            WeightProbeResult("frequency_weight", 0.30, 9.0, "b", 400000),
            WeightProbeResult("frequency_weight", 0.33, 11.0, "c", 1000),
        ],
        rolling_issue_bounds=[(0.24, 0.36)],
        previous_state=WeightKdjState(rsv=50, k_value=50, d_value=50, j_value=50),
    )

    assert signal.close_value == 0.33
    assert signal.rolling_low_value == 0.24
    assert signal.rolling_high_value == 0.36
    assert round(signal.objective_delta, 6) == 2.0
    assert signal.recommended_offset > 0
    assert round(state.k_value, 6) == round(signal.k_value, 6)


def test_weight_kdj_advice_rejects_neutral_and_opposite_slope_and_downweights_noise():
    signals = [
        {
            "signal_run_id": "run-1",
            "issue": "2026066",
            "weight_name": "frequency_weight",
            "recommended_offset": 0.04,
            "objective_delta": 2.0,
            "j_value": 45.0,
        },
        {
            "signal_run_id": "run-1",
            "issue": "2026067",
            "weight_name": "frequency_weight",
            "recommended_offset": 0.04,
            "objective_delta": 2.0,
            "j_value": 75.0,
        },
        {
            "signal_run_id": "run-1",
            "issue": "2026068",
            "weight_name": "frequency_weight",
            "recommended_offset": 0.04,
            "objective_delta": 2.0,
            "j_value": 65.0,
        },
        {
            "signal_run_id": "run-1",
            "issue": "2026068",
            "weight_name": "sum_tail_weight",
            "recommended_offset": -0.03,
            "objective_delta": 2.0,
            "j_value": 47.0,
        },
        {
            "signal_run_id": "run-1",
            "issue": "2026067",
            "weight_name": "weekday_trend_weight",
            "recommended_offset": 0.02,
            "objective_delta": 1.0,
            "j_value": 70.0,
        },
        {
            "signal_run_id": "run-1",
            "issue": "2026068",
            "weight_name": "weekday_trend_weight",
            "recommended_offset": 0.02,
            "objective_delta": 1.0,
            "j_value": 60.0,
        },
    ]

    advice = {
        item.weight_name: item
        for item in weight_kdj_advice_from_signals(
            signals,
            allowed_fields=("frequency_weight", "sum_tail_weight", "weekday_trend_weight"),
            min_objective_delta=0.5,
            min_abs_offset=0.01,
            slope_window=3,
            neutral_band=5.0,
        )
    }

    assert advice["frequency_weight"].decision == "downweighted"
    assert advice["frequency_weight"].reason == "noisy_slope"
    assert advice["frequency_weight"].applied_offset == 0.02
    assert advice["sum_tail_weight"].decision == "rejected"
    assert advice["sum_tail_weight"].reason == "neutral_band"
    assert advice["weekday_trend_weight"].decision == "rejected"
    assert advice["weekday_trend_weight"].reason == "opposite_slope"
