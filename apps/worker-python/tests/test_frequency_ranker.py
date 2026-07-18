from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest

from dehps.features.qian_kun import (
    qian_kun_distribution,
    qian_kun_icon,
    qian_kun_label,
    qian_kun_lines_from_pattern,
    qian_kun_pattern,
)
from dehps.input_contracts import InputContractViolation
from dehps.models.frequency_ranker import FrequencyRankerConfig, score_frequency_candidate, train_frequency_stats
from dehps.optimization import walk_forward
from dehps.optimization.walk_forward import (
    build_ranked_universe,
    deterministic_run_key,
    fingerprint_history,
    is_excluded_red_combination,
    normalize_worker_count,
    random_uniform_baseline,
    rank_target,
    rank_target_grid,
    rank_target_grid_with_red5,
    run_walk_forward,
)


def test_train_frequency_stats_uses_history_counts_and_omission():
    history = [
        ("001", (1, 2, 3, 4, 5, 6)),
        ("002", (1, 7, 8, 9, 10, 11)),
    ]

    stats = train_frequency_stats(history)

    assert stats.train_draws == 2
    assert stats.frequency_rate[1] == 2 / 12
    assert stats.frequency_rate[6] == 1 / 12
    assert stats.omission_rate[1] == 0
    assert stats.omission_rate[6] == 0.5
    assert stats.omission_rate[33] == 1.0


def test_score_frequency_candidate_is_configurable():
    history = [("001", (1, 2, 3, 4, 5, 6))]
    stats = train_frequency_stats(history)
    structural_only = score_frequency_candidate(
        (1, 8, 13, 18, 23, 31),
        stats,
        FrequencyRankerConfig(
            structural_weight=1,
            frequency_weight=0,
            omission_weight=0,
            previous_consecutive_weight=0,
        ),
    )
    omission_only = score_frequency_candidate(
        (7, 8, 9, 10, 11, 12),
        stats,
        FrequencyRankerConfig(
            structural_weight=0,
            frequency_weight=0,
            omission_weight=1,
            previous_consecutive_weight=0,
        ),
    )

    assert 0 <= structural_only["score"] <= 1
    assert omission_only["score"] == 1


def test_qian_kun_pattern_maps_odd_to_yang_and_even_to_yin():
    pattern = qian_kun_pattern((1, 2, 3, 4, 5, 6))
    distribution = qian_kun_distribution(
        [
            ("001", (1, 2, 3, 4, 5, 6)),
            ("002", (1, 3, 5, 7, 9, 11)),
        ],
    )

    assert pattern == "101010"
    assert qian_kun_lines_from_pattern(pattern) == ["—", "- -", "—", "- -", "—", "- -"]
    assert qian_kun_icon(pattern) == "䷾"
    assert qian_kun_label(pattern) == "既济卦"
    assert distribution["latest_label"] == "乾卦"
    assert distribution["latest_icon"] == "䷀"
    assert distribution["qian_count"] == 1


def test_qian_kun_pattern_weight_can_score_matching_pattern():
    history = [
        ("001", (1, 3, 5, 7, 9, 11)),
        ("002", (1, 3, 5, 13, 15, 17)),
        ("003", (2, 4, 6, 8, 10, 12)),
    ]
    config = FrequencyRankerConfig(
        structural_weight=0,
        frequency_weight=0,
        omission_weight=0,
        previous_consecutive_weight=0,
        qian_kun_pattern_weight=1,
    )

    matching = score_frequency_candidate((1, 5, 9, 13, 17, 21), train_frequency_stats(history), config)
    non_matching = score_frequency_candidate((1, 2, 3, 4, 5, 6), train_frequency_stats(history), config)

    assert matching["qian_kun_pattern_score"] > non_matching["qian_kun_pattern_score"]
    assert matching["score"] > non_matching["score"]


def test_temporal_features_track_neighbor_and_lagged_consecutive_chain():
    history = [
        ("001", (1, 11, 20, 23, 26, 33)),
        ("002", (4, 8, 12, 23, 29, 30)),
    ]
    stats = train_frequency_stats(history)

    lagged_candidate = score_frequency_candidate(
        (2, 5, 9, 13, 24, 31),
        stats,
        FrequencyRankerConfig(
            structural_weight=0,
            frequency_weight=0,
            omission_weight=0,
            previous_consecutive_weight=0,
            recent_neighbor_weight=1,
            lagged_consecutive_weight=1,
        ),
    )
    unrelated_candidate = score_frequency_candidate(
        (3, 6, 15, 18, 22, 32),
        stats,
        FrequencyRankerConfig(
            structural_weight=0,
            frequency_weight=0,
            omission_weight=0,
            previous_consecutive_weight=0,
            recent_neighbor_weight=1,
            lagged_consecutive_weight=1,
        ),
    )

    assert 13 in stats.lagged_consecutive_number_set
    assert lagged_candidate["lagged_consecutive_score"] > unrelated_candidate["lagged_consecutive_score"]
    assert lagged_candidate["recent_neighbor_score"] > 0


def test_dynamic_parity_transition_scores_conditioned_even_count():
    e2 = (1, 2, 3, 4, 5, 7)
    e3 = (1, 2, 3, 4, 5, 6)
    e4 = (1, 2, 3, 4, 6, 8)
    history = [
        ("001", e3),
        ("002", e3),
        ("003", e4),
        ("004", e3),
        ("005", e3),
        ("006", e4),
        ("007", e2),
        ("008", e3),
        ("009", e3),
    ]
    config = FrequencyRankerConfig(
        structural_weight=0,
        frequency_weight=0,
        omission_weight=0,
        previous_consecutive_weight=0,
        dynamic_parity_transition_weight=1,
    )
    stats = train_frequency_stats(history)

    four_even = score_frequency_candidate(e4, stats, config)
    three_even = score_frequency_candidate(e3, stats, config)

    assert stats.parity_transition_score_by_even_count[4] > stats.parity_transition_score_by_even_count[3]
    assert four_even["dynamic_parity_transition_score"] > three_even["dynamic_parity_transition_score"]
    assert four_even["score"] > three_even["score"]


def test_shape_trend_weights_score_red_ball_profiles():
    history = [
        ("001", (1, 2, 8, 14, 20, 26)),
        ("002", (2, 3, 9, 15, 21, 27)),
        ("003", (1, 4, 10, 16, 22, 28)),
        ("004", (2, 5, 11, 17, 23, 29)),
        ("005", (1, 6, 12, 18, 24, 30)),
    ]
    config = FrequencyRankerConfig(
        structural_weight=0,
        frequency_weight=0,
        omission_weight=0,
        previous_consecutive_weight=0,
        first_last_sum_weight=1,
        span_trend_weight=1,
        sum_trend_weight=1,
        ac_trend_weight=1,
        zone_ratio_weight=1,
        parity_ratio_weight=1,
        mod012_weight=1,
        tail_distribution_weight=1,
        sum_tail_weight=1,
        consecutive_trend_weight=1,
        repeat_trend_weight=1,
        stable_range_weight=1,
    )

    scored = score_frequency_candidate((2, 5, 11, 17, 23, 29), train_frequency_stats(history), config)

    assert scored["first_last_sum_score"] > 0
    assert scored["span_trend_score"] > 0
    assert scored["sum_trend_score"] > 0
    assert scored["ac_trend_score"] > 0
    assert scored["zone_ratio_score"] > 0
    assert scored["parity_ratio_score"] > 0
    assert scored["mod012_score"] > 0
    assert scored["tail_distribution_score"] > 0
    assert scored["sum_tail_score"] > 0
    assert scored["consecutive_trend_score"] > 0
    assert scored["repeat_trend_score"] > 0
    assert scored["stable_range_score"] > 0
    assert scored["score"] > 0


def test_weekday_trend_weight_uses_only_prior_same_draw_weekday():
    history = [
        ("001", date(2026, 1, 6), (1, 2, 8, 14, 20, 26)),
        ("002", date(2026, 1, 8), (3, 5, 9, 15, 21, 27)),
        ("003", date(2026, 1, 13), (1, 2, 8, 14, 20, 26)),
        ("004", date(2026, 1, 15), (4, 6, 10, 16, 22, 28)),
    ]
    config = FrequencyRankerConfig(
        structural_weight=0,
        frequency_weight=0,
        omission_weight=0,
        previous_consecutive_weight=0,
        weekday_trend_weight=1,
    )

    stats = train_frequency_stats(history, target_draw_date=date(2026, 1, 20))
    matching_tuesday = score_frequency_candidate((1, 2, 8, 14, 20, 26), stats, config)
    non_matching_tuesday = score_frequency_candidate((4, 6, 10, 16, 22, 28), stats, config)

    assert stats.target_weekday == 1
    assert matching_tuesday["weekday_trend_score"] > non_matching_tuesday["weekday_trend_score"]
    assert matching_tuesday["score"] > non_matching_tuesday["score"]


def test_ranked_universe_excludes_fixed_low_plausibility_patterns():
    universe = [
        (1, 2, 3, 4, 5, 9),
        (10, 11, 12, 13, 14, 30),
        (1, 3, 5, 7, 9, 11),
        (12, 14, 16, 18, 20, 22),
        (23, 25, 27, 29, 31, 33),
        (1, 8, 13, 18, 23, 31),
    ]

    ranked = build_ranked_universe(universe)

    assert is_excluded_red_combination((1, 2, 3, 4, 5, 9)) is True
    assert is_excluded_red_combination((1, 3, 5, 7, 9, 11)) is True
    assert is_excluded_red_combination((1, 8, 13, 18, 23, 31)) is False
    assert [entry.numbers for entry in ranked] == [(1, 8, 13, 18, 23, 31)]


def test_ranked_universe_matrix_cache_round_trips(tmp_path):
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
    ]

    first = build_ranked_universe(universe, cache_dir=tmp_path, use_cache=True)
    second = build_ranked_universe(universe, cache_dir=tmp_path, use_cache=True)

    assert first.cache_info["backend"] == "numpy_mmap_matrix"
    assert first.cache_info["cache_hit"] is False
    assert first.cache_info["cache_created"] is True
    assert isinstance(first.numbers, np.memmap)
    assert first.numbers.flags.writeable is False
    assert second.cache_info["cache_hit"] is True
    assert second.cache_info["storage"] == "npy_mmap_read_only"
    assert all(
        isinstance(getattr(second, field_name), np.memmap)
        for field_name in walk_forward.MATRIX_ARRAY_FIELDS
    )
    assert second.cache_info["filtered_count"] == len(first)
    assert [entry.numbers for entry in second] == [entry.numbers for entry in first]


def test_ranked_universe_matrix_cache_rebuilds_corrupt_manifest(tmp_path):
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
    ]
    first = build_ranked_universe(universe, cache_dir=tmp_path, use_cache=True)
    cache_path = Path(first.cache_info["cache_path"])
    (cache_path / "manifest.json").write_text("{not-json")

    rebuilt = build_ranked_universe(universe, cache_dir=tmp_path, use_cache=True)

    assert rebuilt.cache_info["cache_hit"] is False
    assert rebuilt.cache_info["cache_created"] is True
    assert isinstance(rebuilt.numbers, np.memmap)
    assert [entry.numbers for entry in rebuilt] == [entry.numbers for entry in first]


def test_ranked_universe_matrix_cache_replaces_corrupt_file(tmp_path):
    universe = [(1, 8, 13, 18, 23, 31)]
    first = build_ranked_universe(universe, cache_dir=tmp_path, use_cache=True)
    cache_path = Path(first.cache_info["cache_path"])
    walk_forward._remove_cache_artifact(cache_path)
    cache_path.write_text("partial-cache")

    rebuilt = build_ranked_universe(universe, cache_dir=tmp_path, use_cache=True)

    assert rebuilt.cache_info["cache_hit"] is False
    assert cache_path.is_dir()
    assert isinstance(rebuilt.numbers, np.memmap)


def test_ranked_universe_matrix_cache_preserves_all_arrays_and_ranks(tmp_path):
    universe = [
        (1, 4, 9, 14, 22, 31),
        (1, 4, 9, 14, 22, 32),
        (2, 7, 12, 17, 24, 29),
        (3, 8, 13, 18, 25, 30),
    ]
    uncached = build_ranked_universe(universe, use_cache=False)
    cached = build_ranked_universe(universe, cache_dir=tmp_path, use_cache=True)

    for field_name in walk_forward.MATRIX_ARRAY_FIELDS:
        assert np.array_equal(getattr(cached, field_name), getattr(uncached, field_name))

    history = [
        ("2025001", universe[2]),
        ("2025002", universe[3]),
    ]
    configs = (
        FrequencyRankerConfig(),
        FrequencyRankerConfig(
            structural_weight=0,
            frequency_weight=1,
            omission_weight=0,
            previous_consecutive_weight=0,
        ),
    )
    expected = rank_target_grid_with_red5(
        target_numbers=universe[0],
        train_history=history,
        configs=configs,
        ranked_universe=uncached,
    )
    actual = rank_target_grid_with_red5(
        target_numbers=universe[0],
        train_history=history,
        configs=configs,
        ranked_universe=cached,
    )

    assert actual == expected


def test_default_legal_universe_cache_hit_skips_enumeration(tmp_path, monkeypatch):
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
    ]
    monkeypatch.setattr(walk_forward, "TOTAL_LOCAL_LEGAL_COMBINATIONS", len(universe))
    monkeypatch.setattr(walk_forward, "iter_ssq_red_combinations", lambda: iter(universe))
    created = build_ranked_universe(cache_dir=tmp_path)

    def fail_if_enumerated():
        raise AssertionError("cache hit must not enumerate the legal universe")

    monkeypatch.setattr(walk_forward, "iter_ssq_red_combinations", fail_if_enumerated)
    loaded = build_ranked_universe(cache_dir=tmp_path)

    assert created.cache_info["cache_hit"] is False
    assert loaded.cache_info["cache_hit"] is True
    assert isinstance(loaded.numbers, np.memmap)
    assert np.array_equal(loaded.numbers, created.numbers)


def test_walk_forward_reports_target_ranks_on_small_universe():
    universe = [
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (2, 7, 12, 17, 22, 27),
        (3, 8, 13, 18, 23, 28),
    ]
    history = [
        ("2025001", universe[0]),
        ("2025002", universe[1]),
        ("2025003", universe[2]),
        ("2025004", universe[3]),
    ]

    result = run_walk_forward(
        history=history,
        train_window=2,
        eval_window=2,
        top_n=3,
        config=FrequencyRankerConfig(),
        universe=universe,
    )

    assert result.evaluated_draws == 2
    assert result.as_of_issue == "2025004"
    assert result.train_mode == "expanding"
    assert result.history_fingerprint == fingerprint_history(history)
    assert len(result.target_ranks) == 2
    assert len(result.zero_model_target_ranks) == 2
    assert result.universe_size == 2
    assert all(1 <= rank.rank <= result.universe_size for rank in result.target_ranks)
    assert len(result.top_candidates) == 2


def test_walk_forward_rejects_nonpositive_top_n():
    universe = [
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (2, 7, 12, 17, 22, 27),
    ]

    with pytest.raises(ValueError, match="top_n must be at least 1"):
        run_walk_forward(
            history=[
                ("2025001", universe[0]),
                ("2025002", universe[1]),
                ("2025003", universe[2]),
            ],
            train_window=1,
            eval_window=1,
            top_n=0,
            config=FrequencyRankerConfig(),
            universe=universe,
        )


def test_walk_forward_parallel_matches_single_worker_on_small_universe():
    universe = [
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (2, 7, 12, 17, 22, 27),
        (3, 8, 13, 18, 23, 28),
        (4, 9, 14, 19, 24, 29),
    ]
    history = [
        ("2025001", universe[0]),
        ("2025002", universe[1]),
        ("2025003", universe[2]),
        ("2025004", universe[3]),
    ]

    single = run_walk_forward(
        history=history,
        train_window=2,
        eval_window=2,
        top_n=3,
        config=FrequencyRankerConfig(),
        universe=universe,
        workers=1,
    )
    parallel = run_walk_forward(
        history=history,
        train_window=2,
        eval_window=2,
        top_n=3,
        config=FrequencyRankerConfig(),
        universe=universe,
        workers=2,
    )

    assert parallel.workers == 2
    assert parallel.target_ranks == single.target_ranks
    assert parallel.top_candidates == single.top_candidates
    assert parallel.history_fingerprint == single.history_fingerprint


def test_rank_target_uses_only_supplied_train_history():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
    ]
    config = FrequencyRankerConfig(
        structural_weight=0,
        frequency_weight=1,
        omission_weight=0,
        previous_consecutive_weight=0,
    )

    rank, score = rank_target(
        target_numbers=(1, 8, 13, 18, 23, 31),
        train_history=[("2025001", (2, 9, 14, 19, 24, 32))],
        config=config,
        universe=universe,
    )

    assert rank == 2
    assert score == 0


def test_rank_target_grid_matches_individual_rank_target():
    universe = [
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (2, 7, 12, 17, 22, 27),
        (3, 8, 13, 18, 23, 28),
    ]
    train_history = [
        ("2025001", universe[0]),
        ("2025002", universe[1]),
    ]
    configs = (
        FrequencyRankerConfig(),
        FrequencyRankerConfig(structural_weight=0, frequency_weight=0, omission_weight=1, previous_consecutive_weight=0),
    )
    ranked_universe = build_ranked_universe(universe)

    grid = rank_target_grid(
        target_numbers=universe[2],
        train_history=train_history,
        configs=configs,
        ranked_universe=ranked_universe,
    )
    individual = [
        rank_target(
            target_numbers=universe[2],
            train_history=train_history,
            config=config,
            universe=universe,
        )
        for config in configs
    ]

    assert grid == individual


def test_rank_target_grid_with_red5_reports_nearest_difference_number():
    target = (1, 4, 9, 14, 22, 31)
    near_match = (1, 4, 9, 14, 22, 32)
    universe = [
        target,
        near_match,
        (2, 7, 12, 17, 24, 29),
        (3, 8, 13, 18, 25, 30),
    ]
    train_history = [
        ("2025001", (2, 7, 12, 17, 24, 29)),
        ("2025002", (3, 8, 13, 18, 25, 30)),
    ]
    configs = (FrequencyRankerConfig(),)

    grid = rank_target_grid_with_red5(
        target_numbers=target,
        train_history=train_history,
        configs=configs,
        ranked_universe=build_ranked_universe(universe),
    )

    rank, score, red5 = grid[0]
    assert isinstance(rank, int)
    assert isinstance(score, float)
    assert red5 is not None
    assert red5.numbers == near_match
    assert red5.missing_number == 31
    assert red5.extra_number == 32
    assert 1 <= red5.rank <= len(universe)


def test_excluded_target_ranks_after_filtered_universe():
    universe = [
        (1, 2, 3, 4, 5, 9),
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
    ]
    config = FrequencyRankerConfig()

    rank, _ = rank_target(
        target_numbers=(1, 2, 3, 4, 5, 9),
        train_history=[("2025001", (1, 8, 13, 18, 23, 31))],
        config=config,
        universe=universe,
    )

    assert rank == len(build_ranked_universe(universe)) + 1


def test_core_scoring_runtime_rejects_noncanonical_issue_identity():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
    ]

    with pytest.raises(InputContractViolation, match="invalid_issue_encoding"):
        rank_target(
            target_numbers=universe[0],
            train_history=[("001", universe[1])],
            config=FrequencyRankerConfig(),
            universe=universe,
        )


def test_random_uniform_baseline_is_analytical_only():
    baseline = random_uniform_baseline(evaluated_draws=100, universe_size=1107568)

    assert baseline["top_100"]["expected_hits"] == 100 * 100 / 1107568
    assert baseline["top_10000"]["hit_rate"] == 10000 / 1107568


def test_deterministic_run_key_is_stable_for_same_protocol():
    kwargs = {
        "strategy_key": "frequency_v1",
        "as_of_issue": "2026067",
        "train_window": 100,
        "train_mode": "expanding",
        "eval_window": 5,
        "top_n": 10000,
        "history_fingerprint_value": "abc",
        "config_hash_value": "def",
    }

    assert deterministic_run_key(**kwargs) == deterministic_run_key(**kwargs)
    assert "2026067" in deterministic_run_key(**kwargs)
    assert deterministic_run_key(**kwargs) != deterministic_run_key(**{**kwargs, "train_mode": "rolling"})


def test_default_worker_count_leaves_spare_cpu_on_large_machine():
    default_workers = normalize_worker_count(None)

    assert default_workers >= 1
    assert default_workers <= 16
    assert normalize_worker_count(2) == 2
