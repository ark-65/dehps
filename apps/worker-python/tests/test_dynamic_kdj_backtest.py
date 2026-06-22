from __future__ import annotations

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization import dynamic_kdj_backtest as dynamic
from dehps.optimization.dynamic_kdj_backtest import (
    DynamicKdjThresholds,
    dynamic_config_for_target,
    evaluate_dynamic_kdj_backtest,
)


def signal(
    issue: str,
    *,
    weight_name: str = "frequency_weight",
    recommended_offset: float = 0.02,
    j_value: float = 70.0,
    objective_delta: float = 1.0,
) -> dict:
    return {
        "signal_run_id": "weight-kdj-test",
        "issue": issue,
        "weight_name": weight_name,
        "recommended_offset": recommended_offset,
        "j_value": j_value,
        "objective_delta": objective_delta,
        "train_mode": "expanding",
        "train_window": 3,
        "top_n": 10000,
    }


def test_dynamic_config_uses_only_prior_issue_signals():
    result = dynamic_config_for_target(
        base_config=FrequencyRankerConfig(frequency_weight=0.30),
        target_issue="2026068",
        signals=[
            signal("2026065", j_value=60.0),
            signal("2026066", j_value=65.0),
            signal("2026067", j_value=70.0, recommended_offset=0.02),
            signal("2026068", j_value=95.0, recommended_offset=0.20),
        ],
        thresholds=DynamicKdjThresholds(min_abs_offset=0.005, neutral_band=5.0, slope_window=3),
    )

    assert result.leakage_passed is True
    assert result.latest_signal_issue == "2026067"
    assert result.excluded_signal_count == 1
    assert result.applied_offsets == {"frequency_weight": 0.02}
    assert round(result.config.frequency_weight, 6) == 0.32


def test_dynamic_config_rejects_neutral_opposite_slope_and_non_positive_delta():
    result = dynamic_config_for_target(
        base_config=FrequencyRankerConfig(frequency_weight=0.30, omission_weight=0.25, sum_tail_weight=0.0),
        target_issue="2026068",
        signals=[
            signal("2026065", weight_name="frequency_weight", recommended_offset=0.02, j_value=70.0),
            signal("2026066", weight_name="frequency_weight", recommended_offset=0.02, j_value=65.0),
            signal("2026067", weight_name="frequency_weight", recommended_offset=0.02, j_value=60.0),
            signal("2026067", weight_name="omission_weight", recommended_offset=0.02, j_value=53.0),
            signal("2026067", weight_name="sum_tail_weight", recommended_offset=0.02, j_value=75.0, objective_delta=0.0),
        ],
        thresholds=DynamicKdjThresholds(min_abs_offset=0.005, neutral_band=5.0, slope_window=3),
    )

    assert result.applied_offsets == {}
    assert round(result.config.frequency_weight, 6) == 0.30
    reasons = {item.weight_name: item.reason for item in result.advice}
    assert reasons["frequency_weight"] == "opposite_slope"
    assert reasons["omission_weight"] == "neutral_band"
    assert reasons["sum_tail_weight"] == "non_positive_objective_delta"


class FakeRankedUniverse:
    cache_info: dict = {}

    def __len__(self) -> int:
        return 1_107_568


def test_backtest_builds_per_target_dynamic_configs_without_mutating_static(monkeypatch):
    def fake_rank_target_grid_with_red5(**kwargs):
        return [
            (int(10_000 - getattr(config, "frequency_weight") * 1_000), 0.0, None)
            for config in kwargs["configs"]
        ]

    monkeypatch.setattr(dynamic, "rank_target_grid_with_red5", fake_rank_target_grid_with_red5)
    history = [
        ("0000", None, (1, 2, 3, 8, 13, 21)),
        ("0001", None, (2, 4, 6, 11, 19, 31)),
        ("0002", None, (3, 5, 9, 14, 22, 30)),
        ("0003", None, (4, 7, 12, 18, 23, 32)),
        ("0004", None, (5, 10, 15, 20, 25, 33)),
    ]
    payload = evaluate_dynamic_kdj_backtest(
        history=history,
        ranked_universe=FakeRankedUniverse(),
        base_config=FrequencyRankerConfig(frequency_weight=0.30),
        signals=[
            signal("0000", j_value=60.0, recommended_offset=0.02),
            signal("0001", j_value=65.0, recommended_offset=0.02),
            signal("0002", j_value=70.0, recommended_offset=0.02),
            signal("0003", j_value=80.0, recommended_offset=0.04),
        ],
        train_window=3,
        train_mode="expanding",
        eval_window=2,
        top_n=10000,
        thresholds=DynamicKdjThresholds(min_abs_offset=0.005, neutral_band=5.0, slope_window=3),
    )

    dynamic_configs = payload["dynamic"]["dynamic_configs"]
    assert payload["static_baseline"]["config"]["frequency_weight"] == 0.30
    assert dynamic_configs[0]["target_issue"] == "0003"
    assert dynamic_configs[0]["applied_offsets"] == {"frequency_weight": 0.02}
    assert dynamic_configs[1]["target_issue"] == "0004"
    assert dynamic_configs[1]["applied_offsets"] == {"frequency_weight": 0.04}
    assert payload["rank_movement"]["changed_target_count"] == 2
    assert payload["leakage_audit"]["passed"] is True
