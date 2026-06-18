from __future__ import annotations

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.target_inversion import TargetWeightInversion
from dehps.optimization.target_inversion import aggregate_target_inversions
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


def test_target_inversion_aggregate_uses_partial_improvements_as_micro_candidates():
    base = FrequencyRankerConfig(frequency_weight=0.30, omission_weight=0.20)
    inversions = [
        TargetWeightInversion(
            target_issue="2026067",
            red_numbers=(1, 2, 3, 4, 5, 6),
            current_rank=80_000,
            hit_top10000=False,
            score=0.1,
            rank_margin=70_000,
            base_config_hash="base",
            required_delta_config={"frequency_weight": 0.04, "omission_weight": -0.02},
            adjusted_config={"frequency_weight": 0.34, "omission_weight": 0.18},
            adjusted_rank=24_000,
            adjusted_hit_top10000=False,
            delta_norm=0.0447,
            changed_fields=("frequency_weight", "omission_weight"),
            success=False,
            outlier_reason="not_enough_shift",
        ),
        TargetWeightInversion(
            target_issue="2026068",
            red_numbers=(1, 2, 3, 4, 5, 7),
            current_rank=120_000,
            hit_top10000=False,
            score=0.1,
            rank_margin=110_000,
            base_config_hash="base",
            required_delta_config={"frequency_weight": 0.03, "omission_weight": -0.01},
            adjusted_config={"frequency_weight": 0.33, "omission_weight": 0.19},
            adjusted_rank=60_000,
            adjusted_hit_top10000=False,
            delta_norm=0.0316,
            changed_fields=("frequency_weight", "omission_weight"),
            success=False,
            outlier_reason="not_enough_shift",
        ),
    ]

    aggregate = aggregate_target_inversions(inversions, base_config=base)

    assert aggregate["success_count"] == 0
    assert aggregate["partial_improvement_count"] == 2
    assert aggregate["partial_weighted_delta"]["frequency_weight"] > 0
    labels = {candidate["label"] for candidate in aggregate["candidates"]}
    assert aggregate["candidate_count"] >= 2
    assert "current_plus_0_25_partial_weighted_delta" in labels
    assert "current_plus_0_50_partial_weighted_delta" in labels
