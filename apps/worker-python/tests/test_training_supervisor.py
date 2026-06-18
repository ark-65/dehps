from __future__ import annotations

import json

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.walk_forward import TargetRank, build_ranked_universe
from scripts.run_training_supervisor import (
    calculate_tail_risk_penalty,
    candidate_budget,
    attach_frozen_validation,
    config_hash,
    control_experiment_configs,
    control_experiment_summaries,
    evaluate_configs,
    frozen_validation_window,
    generate_configs,
    low_coverage_fields_from_summaries,
    load_prior_supervisor_candidates,
    post_training_event,
    prefilter_configs,
    reward_summary,
    sort_key,
    stagnation_round_count,
    training_event_payload,
    summarize_target_ranks,
    training_progress_payload,
    weight_kdj_advisor_candidate_configs,
    weight_kdj_advisor_metadata,
)


def test_generate_configs_keeps_base_and_clamps_weight_range():
    base = FrequencyRankerConfig(
        structural_weight=0.40,
        frequency_weight=0.30,
        omission_weight=0.25,
        previous_consecutive_weight=0.05,
    )

    configs = generate_configs(base, phase="large", step=1.0, max_configs=32)

    assert configs[0] == base
    assert len({tuple(config.__dict__.items()) for config in configs}) == len(configs)
    assert all(0 <= config.structural_weight <= 1.25 for config in configs)
    assert all(-0.30 <= config.previous_overlap_weight <= 0.30 for config in configs)


def test_candidate_budget_uses_search_intelligence_mix():
    budget = candidate_budget(20)

    assert budget == {"exploitation": 8, "exploration": 6, "replay": 4, "baseline": 2}
    assert sum(budget.values()) == 20


def test_generate_configs_reuses_elite_configs_for_local_search():
    base = FrequencyRankerConfig()
    elite = FrequencyRankerConfig(
        structural_weight=0.35,
        frequency_weight=0.45,
        omission_weight=0.20,
        previous_consecutive_weight=0.12,
        previous_zone_shape_weight=0.18,
    )

    configs = generate_configs(base, phase="micro", step=0.02, max_configs=12, elite_configs=(elite,))

    assert elite in configs
    assert any(config.frequency_weight > elite.frequency_weight for config in configs)
    assert any(config.frequency_weight < elite.frequency_weight for config in configs)


def test_generate_configs_includes_late_shape_fields_under_round_limit():
    configs = generate_configs(FrequencyRankerConfig(), phase="micro", step=0.01, max_configs=28)

    assert any(config.weekday_trend_weight > 0 for config in configs)
    assert any(config.stable_range_weight > 0 for config in configs)
    assert any(config.tail_distribution_weight > 0 for config in configs)


def test_generate_configs_large_phase_keeps_themed_seed_candidates():
    configs = generate_configs(FrequencyRankerConfig(), phase="large", step=0.15, max_configs=28)

    assert any(config.weekday_trend_weight >= 0.10 for config in configs)
    assert any(config.mod012_weight > 0 and config.tail_distribution_weight > 0 for config in configs)
    assert any(config.first_last_sum_weight > 0 and config.stable_range_weight > 0 for config in configs)


def test_generate_configs_uses_history_and_stagnation_exploration():
    base = FrequencyRankerConfig()
    historical = [
        {
            "config": {
                **base.__dict__,
                "frequency_weight": 0.55,
                "tail_distribution_weight": 0.12,
            },
            "reward": {"objectiveScore": 120.0},
        },
        {
            "config": {
                **base.__dict__,
                "frequency_weight": 0.20,
                "tail_distribution_weight": -0.08,
            },
            "reward": {"objectiveScore": 20.0},
        },
        {
            "config": {**base.__dict__, "weekday_trend_weight": 0.10},
            "reward": {"objectiveScore": 80.0},
        },
        {
            "config": {**base.__dict__, "previous_overlap_weight": -0.10},
            "reward": {"objectiveScore": 40.0},
        },
        {
            "config": {**base.__dict__, "mod012_weight": 0.08},
            "reward": {"objectiveScore": 60.0},
        },
        {
            "config": {**base.__dict__, "red_omission_shape_weight": 0.08},
            "reward": {"objectiveScore": 70.0},
        },
    ]

    configs = generate_configs(
        base,
        phase="medium",
        step=0.07,
        max_configs=24,
        historical_summaries=historical,
        low_coverage_fields=("sum_tail_weight", "stable_range_weight"),
        stagnation_rounds=20,
        round_index=33,
    )

    assert len(configs) == len({config_hash(config) for config in configs}) <= 24
    assert any(abs(config.sum_tail_weight) >= 0.07 for config in configs)
    assert any(config.frequency_weight > 0.50 for config in configs)
    assert any(all(value == 0 for value in config.__dict__.values()) for config in configs)


def test_weight_kdj_advisor_generates_bounded_candidate_offsets():
    base = FrequencyRankerConfig(frequency_weight=0.30, sum_tail_weight=0.0)
    signals = [
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026067",
            "weight_name": "frequency_weight",
            "recommended_offset": 0.04,
            "objective_delta": 2.0,
            "j_value": 70.0,
        },
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026068",
            "weight_name": "sum_tail_weight",
            "recommended_offset": -0.02,
            "objective_delta": 1.0,
            "j_value": 30.0,
        },
    ]

    configs = weight_kdj_advisor_candidate_configs(base, signals, max_configs=4)
    metadata = weight_kdj_advisor_metadata(signals, configs)

    assert any(round(config.frequency_weight, 6) == 0.34 for config in configs)
    assert any(round(config.sum_tail_weight, 6) == -0.02 for config in configs)
    assert metadata["mode"] == "advisor_only"
    assert metadata["candidate_count"] == len(configs)


def test_prefilter_configs_keeps_base_and_elite_before_full_refine():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
        (4, 11, 16, 21, 26, 30),
        (5, 12, 17, 22, 27, 29),
    ]
    history = [
        ("001", universe[0]),
        ("002", universe[1]),
        ("003", universe[2]),
        ("004", universe[3]),
        ("005", universe[4]),
        ("006", universe[0]),
        ("007", universe[1]),
    ]
    base = FrequencyRankerConfig()
    elite = FrequencyRankerConfig(structural_weight=0.35, frequency_weight=0.40, omission_weight=0.20)
    configs = (
        base,
        elite,
        FrequencyRankerConfig(structural_weight=0.10, frequency_weight=0.80, omission_weight=0.05),
        FrequencyRankerConfig(structural_weight=0.80, frequency_weight=0.10, omission_weight=0.05),
    )

    refined, metadata = prefilter_configs(
        history=history,
        ranked_universe=build_ranked_universe(universe),
        configs=configs,
        keep_configs=(base, elite),
        train_window=2,
        train_mode="expanding",
        eval_window=4,
        top_n=10000,
        workers=1,
        pool=None,
        round_index=1,
        stride=4,
        promote_limit=1,
    )

    assert base in refined
    assert elite in refined
    assert len(refined) <= 4
    assert metadata["generated_config_count"] == len(configs)
    assert metadata["refined_config_count"] == len(refined)
    assert metadata["target_count"] == 1
    assert metadata["diversity_added_count"] >= 0


def test_prefilter_configs_keeps_diversity_quota():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
        (4, 11, 16, 21, 26, 30),
        (5, 12, 17, 22, 27, 29),
    ]
    history = [
        ("001", universe[0]),
        ("002", universe[1]),
        ("003", universe[2]),
        ("004", universe[3]),
        ("005", universe[4]),
        ("006", universe[0]),
        ("007", universe[1]),
    ]
    base = FrequencyRankerConfig()
    far = FrequencyRankerConfig(structural_weight=1.25, frequency_weight=0.0, omission_weight=0.0)
    configs = (
        base,
        FrequencyRankerConfig(structural_weight=0.41, frequency_weight=0.30, omission_weight=0.25),
        FrequencyRankerConfig(structural_weight=0.42, frequency_weight=0.30, omission_weight=0.25),
        far,
    )

    refined, metadata = prefilter_configs(
        history=history,
        ranked_universe=build_ranked_universe(universe),
        configs=configs,
        keep_configs=(base,),
        train_window=2,
        train_mode="expanding",
        eval_window=4,
        top_n=10000,
        workers=1,
        pool=None,
        round_index=1,
        stride=4,
        promote_limit=1,
        diversity_quota=1,
    )

    assert far in refined
    assert metadata["diversity_added_count"] == 1


def test_stagnation_and_low_coverage_fields_are_deterministic():
    rounds = [{"improved": True}, {"improved": False}, {"improved": False}]
    summaries = [
        {"config": {"frequency_weight": 0.4, "tail_distribution_weight": 0.1}},
        {"config": {"frequency_weight": 0.5}},
    ]

    assert stagnation_round_count(rounds) == 2
    assert low_coverage_fields_from_summaries(summaries, limit=2) == ("tail_distribution_weight", "frequency_weight")


def test_control_experiments_and_frozen_validation_are_recorded():
    base = FrequencyRankerConfig()
    controls = control_experiment_configs(base)
    summary_by_hash = {}
    for index, (_label, config) in enumerate(controls, start=1):
        summary = {
            "config": config.__dict__,
            "as_of_issue": "2026067",
            "history_fingerprint": "history-1",
            "config_hash": config_hash(config),
            "evaluated_draws": 3,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": index,
            "median_rank": 20000 + index,
            "best_rank": 100 + index,
            "worst_rank": 900000 - index,
            "red5": {"top_100_hits": 0, "top_1000_hits": 1, "top_10000_hits": 2},
            "rank_quality": {},
            "target_results": [
                {
                    "issue": "2026001",
                    "rank": 50000,
                    "hit_top_100": False,
                    "hit_top_1000": False,
                    "hit_top_10000": False,
                    "hit_red5_top_100": False,
                    "hit_red5_top_1000": False,
                    "hit_red5_top_10000": True,
                },
                {
                    "issue": "2026002",
                    "rank": 900,
                    "hit_top_100": False,
                    "hit_top_1000": True,
                    "hit_top_10000": True,
                    "red5_rank": 80,
                    "hit_red5_top_100": True,
                    "hit_red5_top_1000": True,
                    "hit_red5_top_10000": True,
                },
            ],
            "reward": {"objectiveScore": float(index)},
        }
        summary_by_hash[summary["config_hash"]] = summary

    summaries = list(summary_by_hash.values())
    attach_frozen_validation(summaries, validation_window=frozen_validation_window(10), universe_size=1107568)
    rows = control_experiment_summaries(summaries, controls)

    assert frozen_validation_window(100) == 20
    assert {label for label, _config in controls} == {
        "current_best_frozen_baseline",
        "structural_baseline",
        "frequency_baseline",
        "omission_baseline",
        "null_baseline",
    }
    assert all(config.previous_consecutive_weight == 0 for label, config in controls if label != "current_best_frozen_baseline")
    assert len(rows) == len(controls)
    assert rows[0]["frozen_validation"]["window"] == 2
    assert rows[0]["frozen_validation"]["top_1000_hits"] == 1
    assert rows[0]["frozen_validation"]["red5"]["top_100_hits"] == 1


def test_prefilter_configs_target_parallel_matches_single_worker():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
        (4, 11, 16, 21, 26, 30),
        (5, 12, 17, 22, 27, 29),
    ]
    history = [
        ("001", universe[0]),
        ("002", universe[1]),
        ("003", universe[2]),
        ("004", universe[3]),
        ("005", universe[4]),
        ("006", universe[0]),
        ("007", universe[1]),
    ]
    base = FrequencyRankerConfig()
    elite = FrequencyRankerConfig(structural_weight=0.35, frequency_weight=0.40, omission_weight=0.20)
    configs = (
        base,
        elite,
        FrequencyRankerConfig(structural_weight=0.10, frequency_weight=0.80, omission_weight=0.05),
        FrequencyRankerConfig(structural_weight=0.80, frequency_weight=0.10, omission_weight=0.05),
    )
    matrix = build_ranked_universe(universe)

    serial, serial_metadata = prefilter_configs(
        history=history,
        ranked_universe=matrix,
        configs=configs,
        keep_configs=(base, elite),
        train_window=2,
        train_mode="expanding",
        eval_window=5,
        top_n=10000,
        workers=1,
        pool=None,
        round_index=1,
        stride=1,
        promote_limit=2,
    )
    parallel, parallel_metadata = prefilter_configs(
        history=history,
        ranked_universe=matrix,
        configs=configs,
        keep_configs=(base, elite),
        train_window=2,
        train_mode="expanding",
        eval_window=5,
        top_n=10000,
        workers=2,
        pool=None,
        round_index=1,
        stride=1,
        promote_limit=2,
    )

    assert [config_hash(config) for config in parallel] == [config_hash(config) for config in serial]
    assert parallel_metadata["target_count"] == serial_metadata["target_count"] == 5
    assert parallel_metadata["target_worker_count"] == 2
    assert [item["config_hash"] for item in parallel_metadata["top_preview"]] == [
        item["config_hash"] for item in serial_metadata["top_preview"]
    ]


def test_evaluate_configs_target_parallel_matches_single_worker():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
        (4, 11, 16, 21, 26, 30),
        (5, 12, 17, 22, 27, 29),
    ]
    history = [
        ("001", universe[0]),
        ("002", universe[1]),
        ("003", universe[2]),
        ("004", universe[3]),
        ("005", universe[4]),
        ("006", universe[0]),
    ]
    configs = (
        FrequencyRankerConfig(),
        FrequencyRankerConfig(structural_weight=0.2, frequency_weight=0.6, omission_weight=0.1),
    )
    matrix = build_ranked_universe(universe)

    single = evaluate_configs(
        history=history,
        ranked_universe=matrix,
        configs=configs,
        train_window=2,
        train_mode="expanding",
        eval_window=3,
        top_n=10000,
        workers=1,
        pool=None,
        progress_interval=0,
        round_index=1,
    )
    parallel = evaluate_configs(
        history=history,
        ranked_universe=matrix,
        configs=configs,
        train_window=2,
        train_mode="expanding",
        eval_window=3,
        top_n=10000,
        workers=2,
        pool=None,
        progress_interval=0,
        round_index=1,
    )

    assert parallel == single


def test_training_event_post_failure_is_non_fatal():
    sent = post_training_event({"run_id": "event-test"}, event_url="http://127.0.0.1:9/training-events/status", timeout=0.05)

    assert sent is False


def test_training_event_payload_is_compact_signal_only():
    payload = training_event_payload(
        {
            "run_id": "run-1",
            "status": "running",
            "updated_at": "2026-06-17T12:00:00",
            "latest_progress": {"round": 1},
            "status_path": "/tmp/status.json",
            "report_path": "/tmp/status.md",
            "rounds": [{"large": "payload"}],
            "best": {"large": "payload"},
        }
    )

    assert payload == {
        "run_id": "run-1",
        "status": "running",
        "updated_at": "2026-06-17T12:00:00",
        "latest_progress": {"round": 1},
        "status_path": "/tmp/status.json",
        "report_path": "/tmp/status.md",
    }


def test_training_progress_payload_is_json_status_compatible():
    payload = training_progress_payload(
        round_index=2,
        target_index=7,
        target_total=100,
        issue="2026068",
        train_draws=1400,
        elapsed_seconds=12.34,
        logged_at="2026-06-17T12:00:00",
    )

    assert payload == {
        "logged_at": "2026-06-17T12:00:00",
        "round": 2,
        "target_index": 7,
        "target_total": 100,
        "issue": "2026068",
        "train_draws": 1400,
        "elapsed_seconds": 12.3,
    }


def test_training_sort_key_prefers_higher_coverage_then_lower_rank():
    weaker = {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 3, "median_rank": 600000, "best_rank": 4000}
    stronger = {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 4, "median_rank": 900000, "best_rank": 8000}
    tie_better_rank = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 3,
        "median_rank": 500000,
        "best_rank": 5000,
    }

    assert sort_key(stronger) > sort_key(weaker)
    assert sort_key(tie_better_rank) > sort_key(weaker)


def test_training_sort_key_prefers_top1000_over_extra_top10000_hit():
    top1000_hit = {
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 650000,
        "best_rank": 864,
        "worst_rank": 1_096_000,
    }
    extra_top10000_hit = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 4,
        "median_rank": 590000,
        "best_rank": 3238,
        "worst_rank": 1_090_000,
    }

    assert reward_summary(top1000_hit)["hitReward"] > reward_summary(extra_top10000_hit)["hitReward"]
    assert sort_key(top1000_hit) > sort_key(extra_top10000_hit)


def test_reward_summary_penalizes_worse_rank_inside_same_hit_counts():
    better_rank = {
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 400000,
        "best_rank": 500,
        "worst_rank": 900000,
    }
    worse_rank = {
        **better_rank,
        "median_rank": 700000,
        "worst_rank": 1_000_000,
    }

    assert reward_summary(better_rank)["objectiveScore"] > reward_summary(worse_rank)["objectiveScore"]
    assert sort_key(better_rank) > sort_key(worse_rank)


def test_rank_quality_reward_keeps_tail_improvements_visible():
    better_tail = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 3,
        "median_rank": 400000,
        "best_rank": 3000,
        "worst_rank": 700000,
        "rank_quality": {
            "top_50000_hits": 8,
            "top_100000_hits": 12,
            "top_250000_hits": 30,
            "top_500000_hits": 60,
            "reward": 4.0,
        },
    }
    worse_tail = {
        **better_tail,
        "median_rank": 600000,
        "worst_rank": 1_050_000,
        "rank_quality": {
            "top_50000_hits": 4,
            "top_100000_hits": 8,
            "top_250000_hits": 20,
            "top_500000_hits": 45,
            "reward": 1.0,
        },
    }

    assert reward_summary(better_tail)["rankQualityReward"] > reward_summary(worse_tail)["rankQualityReward"]
    assert reward_summary(better_tail)["objectiveScore"] > reward_summary(worse_tail)["objectiveScore"]
    assert sort_key(better_tail) > sort_key(worse_tail)


def test_tail_risk_penalty_strongly_punishes_million_rank_outliers():
    stable_tail = {
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 520000,
        "best_rank": 864,
        "worst_rank": 820000,
        "rank_quality": {
            "top_50000_hits": 5,
            "top_100000_hits": 8,
            "top_250000_hits": 24,
            "top_500000_hits": 41,
            "p95_rank": 780000,
            "tail_over_750000_count": 3,
            "tail_over_900000_count": 0,
            "tail_over_1000000_count": 0,
            "reward": 1.7,
        },
    }
    million_tail = {
        **stable_tail,
        "median_rank": 590000,
        "worst_rank": 1_097_823,
        "rank_quality": {
            **stable_tail["rank_quality"],
            "p95_rank": 1_030_000,
            "tail_over_750000_count": 12,
            "tail_over_900000_count": 7,
            "tail_over_1000000_count": 3,
        },
    }

    stable_reward = reward_summary(stable_tail)
    million_reward = reward_summary(million_tail)

    assert million_reward["tailRiskPenalty"] > stable_reward["tailRiskPenalty"] + 10
    assert stable_reward["objectiveScore"] > million_reward["objectiveScore"]
    assert sort_key(stable_tail) > sort_key(million_tail)


def test_calculate_tail_risk_penalty_is_threshold_and_shape_sensitive():
    low_tail = calculate_tail_risk_penalty(
        median_rank=400000,
        worst_rank=700000,
        p95_rank=650000,
        tail_over_750000_count=0,
        tail_over_900000_count=0,
        tail_over_1000000_count=0,
        universe_size=1_107_568,
    )
    high_tail = calculate_tail_risk_penalty(
        median_rank=600000,
        worst_rank=1_080_000,
        p95_rank=1_010_000,
        tail_over_750000_count=15,
        tail_over_900000_count=8,
        tail_over_1000000_count=4,
        universe_size=1_107_568,
    )

    assert high_tail > low_tail
    assert high_tail - low_tail > 20


def test_red5_reward_is_low_weight_and_cannot_override_exact_top1000():
    red5_top100_heavy = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 3,
        "median_rank": 400000,
        "best_rank": 3000,
        "worst_rank": 900000,
        "red5": {"top_100_hits": 20, "top_1000_hits": 35, "top_10000_hits": 80},
    }
    exact_top1000 = {
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 650000,
        "best_rank": 864,
        "worst_rank": 1_096_000,
        "red5": {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 0},
    }

    assert reward_summary(red5_top100_heavy)["red5Reward"] > 0
    assert reward_summary(red5_top100_heavy)["hitReward"] == 30
    assert sort_key(exact_top1000) > sort_key(red5_top100_heavy)


def test_summarize_target_ranks_counts_red5_difference_numbers():
    config = FrequencyRankerConfig()
    target_ranks = [
        TargetRank(
            issue="2026001",
            rank=12000,
            score=0.5,
            hit_top_100=False,
            hit_top_1000=False,
            hit_top_10000=False,
            red5_rank=88,
            red5_score=0.6,
            red5_numbers=(1, 2, 3, 4, 5, 7),
            red5_missing_number=6,
            red5_extra_number=7,
            hit_red5_top_100=True,
            hit_red5_top_1000=True,
            hit_red5_top_10000=True,
        )
    ]

    summary = summarize_target_ranks(
        target_ranks=target_ranks,
        config=config,
        as_of_issue="2026001",
        history_fingerprint_value="history-1",
        train_window=900,
        train_mode="expanding",
        top_n=10000,
        universe_size=1_107_568,
    )

    assert summary["red5"]["top_100_hits"] == 1
    assert summary["red5"]["missing_counts"] == {"06": 1}
    assert summary["red5"]["extra_counts"] == {"07": 1}
    assert summary["red5"]["pairs"] == [{"missing_number": 6, "extra_number": 7, "count": 1}]
    assert summary["red5"]["examples"][0]["issue"] == "2026001"
    assert summary["target_results"] == [
        {
            "issue": "2026001",
            "draw_date": None,
            "red_numbers": [],
            "rank": 12000,
            "score": 0.5,
            "hit_top_100": False,
            "hit_top_1000": False,
            "hit_top_10000": False,
            "red5_rank": 88,
            "red5_score": 0.6,
            "red5_numbers": [1, 2, 3, 4, 5, 7],
            "red5_missing_number": 6,
            "red5_extra_number": 7,
            "hit_red5_top_100": True,
            "hit_red5_top_1000": True,
            "hit_red5_top_10000": True,
        }
    ]
    assert summary["reward"]["red5Reward"] > 0
    assert summary["rank_quality"]["top_50000_hits"] == 1
    assert summary["rank_quality"]["tail_over_1000000_count"] == 0
    assert summary["reward"]["tailRiskPenalty"] > 0
    assert summary["reward"]["rankQualityReward"] > 0


def test_load_prior_supervisor_candidates_keeps_same_protocol_global_best(tmp_path):
    config = FrequencyRankerConfig(frequency_weight=0.765, omission_weight=0)
    summary = {
        "config": {key: value for key, value in config.__dict__.items() if key != "stable_range_weight"},
        "as_of_issue": "2026067",
        "history_fingerprint": "history-1",
        "config_hash": config_hash(config),
        "evaluated_draws": 100,
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 585483.5,
        "best_rank": 864,
        "worst_rank": 1_096_000,
        "run_key": "prior-best",
    }
    current = tmp_path / "training-supervisor-current.json"
    prior = tmp_path / "training-supervisor-prior.json"
    current.write_text("{}")
    prior.write_text(
        json.dumps(
            {
                "train_window": 900,
                "train_mode": "expanding",
                "eval_window": 100,
                "top_n": 10000,
                "best": summary,
                "rounds": [{"best": summary, "top_results": [summary]}],
            }
        )
    )

    candidates = load_prior_supervisor_candidates(
        output_dir=tmp_path,
        current_status_path=current,
        as_of_issue="2026067",
        history_fingerprint_value="history-1",
        train_window=900,
        train_mode="expanding",
        eval_window=100,
        top_n=10000,
        universe_size=1_107_568,
    )

    assert candidates[0]["run_key"] == "prior-best"
    assert candidates[0]["top_1000_hits"] == 1
    assert candidates[0]["reward"]["hitReward"] == 130
    assert candidates[0]["config"]["stable_range_weight"] == 0
