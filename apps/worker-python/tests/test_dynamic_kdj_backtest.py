from __future__ import annotations

import pytest

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization import dynamic_kdj_backtest as dynamic
from dehps.optimization.dynamic_kdj_backtest import (
    DynamicKdjAcceptanceConfig,
    DynamicKdjThresholds,
    acceptance_summary,
    dynamic_config_for_target,
    evaluate_dynamic_kdj_backtest,
    kdj_layer_audit_summary,
    retention_audit_summary,
)
from dehps.optimization.walk_forward import TargetRank
from scripts.run_dynamic_kdj_backtest import load_base_config_json


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


def summary(
    *,
    top10000: int = 1,
    median_rank: int = 400_000,
    worst_rank: int = 800_000,
    p95_rank: int = 750_000,
    tail750: int = 1,
    tail900: int = 0,
    tail1000: int = 0,
    objective: float = 10.0,
) -> dict:
    return {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": top10000,
        "median_rank": median_rank,
        "best_rank": 1000,
        "worst_rank": worst_rank,
        "rank_quality": {
            "p95_rank": p95_rank,
            "tail_over_750000_count": tail750,
            "tail_over_900000_count": tail900,
            "tail_over_1000000_count": tail1000,
            "tail_risk_penalty": 1.0,
        },
        "reward": {"objectiveScore": objective},
    }


def passing_gate(**overrides) -> dict:
    static = summary(top10000=0, median_rank=500_000, worst_rank=900_000, p95_rank=850_000, tail750=2, objective=5.0)
    dynamic_summary = summary(top10000=1, median_rank=400_000, worst_rank=800_000, p95_rank=750_000, tail750=1, objective=10.0)
    null = summary(top10000=0, median_rank=450_000, worst_rank=850_000, p95_rank=800_000, tail750=1, objective=6.0)
    values = {
        "static_summary": static,
        "dynamic_summary": dynamic_summary,
        "null_summary": null,
        "movement": {"changed_target_count": 10, "median_abs_delta": 100.0},
        "leakage": {"passed": True},
        "offset_coverage": {"median_changed_weights": 3.0, "max_changed_weights": 5, "max_abs_offset": 0.04},
        "eval_window": 100,
        "acceptance_config": DynamicKdjAcceptanceConfig(min_eval_window_for_pass=50),
        "negative_controls": {"controls": {}},
    }
    values.update(overrides)
    return acceptance_summary(**values)


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


def test_dynamic_config_scales_offsets_without_leaking_target_issue():
    result = dynamic_config_for_target(
        base_config=FrequencyRankerConfig(frequency_weight=0.30),
        target_issue="2026068",
        signals=[
            signal("2026066", j_value=65.0, recommended_offset=0.02),
            signal("2026067", j_value=70.0, recommended_offset=0.02),
            signal("2026068", j_value=95.0, recommended_offset=0.20),
        ],
        thresholds=DynamicKdjThresholds(min_abs_offset=0.005, neutral_band=5.0, slope_window=3),
        offset_scale=0.5,
    )

    assert result.leakage_passed is True
    assert result.latest_signal_issue == "2026067"
    assert result.excluded_signal_count == 1
    assert result.applied_offsets == {"frequency_weight": 0.01}
    assert round(result.config.frequency_weight, 6) == 0.31


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


def test_strength_sweep_includes_zero_static_equivalent(monkeypatch):
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
        include_negative_controls=False,
        strength_sweep=(0.0, 0.25, 0.5, 1.0),
    )

    rows = {row["strength"]: row for row in payload["strength_sweep"]["rows"]}
    assert tuple(payload["strength_sweep"]["strengths"]) == (0.0, 0.25, 0.5, 1.0)
    assert rows[0.0]["median_rank"] == payload["static_baseline"]["median_rank"]
    assert rows[0.0]["changed_target_count"] == 0
    assert rows[1.0]["median_changed_weights"] == 1.0


def test_retention_audit_tracks_lost_top10000_and_acceptance_failure():
    static_ranks = [
        TargetRank(
            issue="2026068",
            rank=9_500,
            score=0.0,
            hit_top_100=False,
            hit_top_1000=False,
            hit_top_10000=True,
        )
    ]
    dynamic_ranks = [
        TargetRank(
            issue="2026068",
            rank=12_000,
            score=0.0,
            hit_top_100=False,
            hit_top_1000=False,
            hit_top_10000=False,
        )
    ]

    retention = retention_audit_summary(static_ranks=static_ranks, dynamic_ranks=dynamic_ranks, bands=(10000,))
    result = passing_gate(retention_audit=retention)

    assert retention["bands"]["10000"]["lost_count"] == 1
    assert retention["lost_top10000_count"] == 1
    assert result["status"] == "FAIL"
    assert result["retention_passed"] is False
    assert "retention_lost_top10000" in result["failures"]


def test_kdj_layer_audit_groups_structural_weights_and_warns_on_concentration():
    result = dynamic_config_for_target(
        base_config=FrequencyRankerConfig(parity_ratio_weight=0.0, sum_tail_weight=0.0),
        target_issue="2026068",
        signals=[
            signal("2026067", weight_name="parity_ratio_weight", recommended_offset=0.02, j_value=70.0),
            signal("2026067", weight_name="sum_tail_weight", recommended_offset=0.02, j_value=53.0),
        ],
        thresholds=DynamicKdjThresholds(min_abs_offset=0.005, neutral_band=5.0, slope_window=3),
    )

    audit = kdj_layer_audit_summary([result], concentration_threshold=0.5)

    assert audit["layers"]["parity"]["selected"] == 1
    assert audit["layers"]["sum"]["rejected"] == 1
    assert audit["top_layer"]["name"] == "parity"
    assert audit["warnings"] == ["layer_contribution_concentration:parity:1.000"]


def test_acceptance_marks_short_windows_research_only():
    result = passing_gate(eval_window=5)

    assert result["status"] == "RESEARCH_ONLY"
    assert result["passed"] is False
    assert "eval_window_below_min_for_pass" in result["failures"]


def test_acceptance_requires_beating_null_baseline():
    result = passing_gate(null_summary=summary(top10000=0, median_rank=350_000, worst_rank=700_000, objective=20.0))

    assert result["status"] == "FAIL"
    assert result["beats_null"] is False
    assert "dynamic_did_not_beat_null" in result["failures"]


def test_acceptance_rejects_worse_tail_buckets():
    dynamic_summary = summary(top10000=1, median_rank=400_000, worst_rank=950_000, p95_rank=900_000, tail750=3, tail900=1, objective=20.0)
    result = passing_gate(dynamic_summary=dynamic_summary)

    assert result["status"] == "FAIL"
    assert result["tail_not_worse"] is False
    assert "tail_risk_worse_than_static_or_null" in result["failures"]


def test_acceptance_rejects_overwide_offset_coverage():
    result = passing_gate(offset_coverage={"median_changed_weights": 19.0, "max_changed_weights": 20, "max_abs_offset": 0.04})

    assert result["status"] == "FAIL"
    assert result["offset_within_limit"] is False
    assert "offset_coverage_too_wide" in result["failures"]


def test_acceptance_rejects_when_negative_control_passes():
    result = passing_gate(
        negative_controls={
            "controls": {
                "weight_name_shuffle": {
                    "acceptance": {"status": "PASS"},
                }
            }
        }
    )

    assert result["status"] == "FAIL"
    assert result["negative_controls_passed"] is False
    assert "negative_control_passed" in result["failures"]


def test_base_config_json_rejects_nonfinite_values(tmp_path):
    path = tmp_path / "base-config.json"
    path.write_text('{"config": {"frequency_weight": "Infinity"}}')

    with pytest.raises(ValueError, match="--base-config-json field frequency_weight must be a finite number"):
        load_base_config_json(path)
