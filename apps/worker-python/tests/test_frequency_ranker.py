from __future__ import annotations

from dehps.models.frequency_ranker import FrequencyRankerConfig, score_frequency_candidate, train_frequency_stats
from dehps.optimization.walk_forward import (
    deterministic_run_key,
    fingerprint_history,
    normalize_worker_count,
    random_uniform_baseline,
    rank_target,
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


def test_walk_forward_reports_target_ranks_on_small_universe():
    universe = [
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (2, 7, 12, 17, 22, 27),
        (3, 8, 13, 18, 23, 28),
    ]
    history = [
        ("001", universe[0]),
        ("002", universe[1]),
        ("003", universe[2]),
        ("004", universe[3]),
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
    assert result.as_of_issue == "004"
    assert result.train_mode == "expanding"
    assert result.history_fingerprint == fingerprint_history(history)
    assert len(result.target_ranks) == 2
    assert len(result.zero_model_target_ranks) == 2
    assert result.universe_size == len(universe)
    assert all(1 <= rank.rank <= len(universe) for rank in result.target_ranks)
    assert len(result.top_candidates) == 3


def test_walk_forward_parallel_matches_single_worker_on_small_universe():
    universe = [
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (2, 7, 12, 17, 22, 27),
        (3, 8, 13, 18, 23, 28),
        (4, 9, 14, 19, 24, 29),
    ]
    history = [
        ("001", universe[0]),
        ("002", universe[1]),
        ("003", universe[2]),
        ("004", universe[3]),
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
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
    ]
    config = FrequencyRankerConfig(
        structural_weight=0,
        frequency_weight=1,
        omission_weight=0,
        previous_consecutive_weight=0,
    )

    rank, score = rank_target(
        target_numbers=(1, 2, 3, 4, 5, 6),
        train_history=[("001", (7, 8, 9, 10, 11, 12))],
        config=config,
        universe=universe,
    )

    assert rank == 2
    assert score == 0


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
