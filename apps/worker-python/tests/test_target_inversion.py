from __future__ import annotations

from itertools import combinations

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.target_inversion import TargetWeightInversion
from dehps.optimization.target_inversion import aggregate_target_inversions
from dehps.optimization.target_inversion import invert_targets_for_summary
from dehps.optimization.target_inversion import invert_target_weight_delta
import dehps.optimization.target_inversion as target_inversion
from dehps.optimization.walk_forward import build_ranked_universe


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


def test_parallel_target_inversion_preserves_serial_order_and_payload(monkeypatch):
    history = [
        ("2026001", (1, 2, 3, 4, 5, 6)),
        ("2026002", (1, 2, 3, 4, 5, 7)),
        ("2026003", (1, 2, 3, 4, 5, 8)),
        ("2026004", (1, 2, 3, 4, 5, 9)),
    ]
    target_results = [
        {"issue": issue, "red_numbers": list(numbers)}
        for issue, numbers in history[1:]
    ]

    def fake_invert_target_weight(**kwargs):
        rank = int(kwargs["target_issue"][-1])
        return TargetWeightInversion(
            target_issue=kwargs["target_issue"],
            red_numbers=kwargs["red_numbers"],
            current_rank=rank,
            hit_top10000=True,
            score=float(rank),
            rank_margin=0,
            base_config_hash="base",
            required_delta_config={},
            adjusted_config={},
            adjusted_rank=rank,
            adjusted_hit_top10000=True,
            delta_norm=0.0,
            changed_fields=(),
            success=True,
        )

    class FakePool:
        def __init__(self, *, initializer, initargs, **_kwargs):
            initializer(*initargs)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def imap_unordered(self, function, tasks):
            return iter(function(task) for task in reversed(tasks))

    class FakeContext:
        Pool = FakePool

    monkeypatch.setattr(target_inversion, "invert_target_weight", fake_invert_target_weight)
    monkeypatch.setattr(target_inversion, "_target_inversion_pool_context", lambda: FakeContext())
    progress = []
    kwargs = {
        "history": history,
        "ranked_universe": object(),
        "base_config": FrequencyRankerConfig(),
        "target_results": target_results,
        "train_window": 3,
        "train_mode": "expanding",
        "top_n": 10_000,
    }

    serial = invert_targets_for_summary(**kwargs, workers=1)
    parallel = invert_targets_for_summary(
        **kwargs,
        workers=3,
        progress_callback=lambda completed, total: progress.append((completed, total)),
    )

    assert parallel == serial
    assert [item.target_issue for item in parallel] == ["2026002", "2026003", "2026004"]
    assert progress == [(1, 3), (2, 3), (3, 3)]


def test_real_parallel_target_inversion_is_bitwise_equal_to_serial():
    universe = list(combinations(range(1, 11), 6))
    ranked_universe = build_ranked_universe(universe, use_cache=False)
    history = [
        (f"202600{index}", numbers)
        for index, numbers in enumerate(universe[:8], start=1)
    ]
    target_results = [
        {"issue": issue, "red_numbers": list(numbers)}
        for issue, numbers in history[-4:]
    ]
    kwargs = {
        "history": history,
        "ranked_universe": ranked_universe,
        "base_config": FrequencyRankerConfig(),
        "target_results": target_results,
        "train_window": 4,
        "train_mode": "expanding",
        "top_n": 10,
        "max_delta_candidates": 3,
    }

    serial = invert_targets_for_summary(**kwargs, workers=1)
    parallel = invert_targets_for_summary(**kwargs, workers=2)

    assert parallel == serial


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
