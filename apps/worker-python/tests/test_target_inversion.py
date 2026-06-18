from __future__ import annotations

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.target_inversion import invert_target_weight_delta


def test_target_inversion_finds_small_delta_for_simplified_components():
    config = FrequencyRankerConfig(structural_weight=0.5, frequency_weight=0.5)
    universe = [
        {
            "numbers": (1, 2, 3, 4, 5, 6),
            "score": 0.35,
            "components": {"structural_score": 0.1, "frequency_score": 0.6},
        },
        {
            "numbers": (1, 2, 3, 4, 5, 7),
            "score": 0.50,
            "components": {"structural_score": 0.8, "frequency_score": 0.2},
        },
        {
            "numbers": (1, 2, 3, 4, 5, 8),
            "score": 0.45,
            "components": {"structural_score": 0.7, "frequency_score": 0.2},
        },
    ]

    result = invert_target_weight_delta(
        base_config=config,
        target_issue="2026068",
        red_numbers=(1, 2, 3, 4, 5, 6),
        current_rank=3,
        score=0.35,
        ranked_universe=universe,
        top_n=2,
    )

    assert result["success"] is True
    assert result["adjusted_hit_top10000"] is True
    assert result["adjusted_rank"] <= 2
    assert result["delta_norm"] > 0
    assert result["changed_fields"] == ["structural_weight", "frequency_weight"]
    assert result["required_delta_config"]["structural_weight"] < 0
    assert result["required_delta_config"]["frequency_weight"] > 0
    assert result["outlier_reason"] is None


def test_target_inversion_clamps_and_reports_failed_outlier():
    config = FrequencyRankerConfig(structural_weight=0.5, frequency_weight=0.5)
    universe = [
        {
            "numbers": (1, 2, 3, 4, 5, 6),
            "score": 0.10,
            "components": {"structural_score": 0.0, "frequency_score": 0.2},
        },
        {
            "numbers": (1, 2, 3, 4, 5, 7),
            "score": 0.90,
            "components": {"structural_score": 1.0, "frequency_score": 0.8},
        },
    ]

    result = invert_target_weight_delta(
        base_config=config,
        target_issue="2026068",
        red_numbers=(1, 2, 3, 4, 5, 6),
        current_rank=2,
        score=0.10,
        ranked_universe=universe,
        top_n=1,
        lower_bound=0.4,
        upper_bound=0.6,
    )

    assert result["success"] is False
    assert result["adjusted_hit_top10000"] is False
    assert result["outlier_reason"] == "clamp_limit"
    assert result["delta_norm"] > 0


def test_target_inversion_returns_zero_delta_when_target_already_hits_top_n():
    config = FrequencyRankerConfig()

    result = invert_target_weight_delta(
        base_config=config,
        target_issue="2026068",
        red_numbers=(1, 2, 3, 4, 5, 6),
        current_rank=1,
        score=0.9,
        ranked_universe=[],
        top_n=10_000,
    )

    assert result["success"] is True
    assert result["delta_norm"] == 0.0
    assert result["changed_fields"] == []
    assert all(value == 0.0 for value in result["required_delta_config"].values())


def test_target_inversion_requires_components_instead_of_fitting_history():
    config = FrequencyRankerConfig()

    result = invert_target_weight_delta(
        base_config=config,
        target_issue="2026068",
        red_numbers=(1, 2, 3, 4, 5, 6),
        current_rank=20_000,
        score=0.1,
        ranked_universe=[{"numbers": (1, 2, 3, 4, 5, 7), "score": 0.2}],
        top_n=10_000,
    )

    assert result["success"] is False
    assert result["outlier_reason"] == "missing_target_components"
    assert result["delta_norm"] == 0.0
