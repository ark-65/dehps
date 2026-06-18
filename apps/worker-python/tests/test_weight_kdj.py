from __future__ import annotations

from dehps.optimization.weight_kdj import (
    WeightKdjState,
    WeightProbeResult,
    next_kdj_state,
    rsv_from_interval,
    signal_from_probe_results,
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
