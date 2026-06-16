from __future__ import annotations

import json

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.walk_forward import TargetRank
from scripts.run_training_supervisor import (
    config_hash,
    generate_configs,
    load_prior_supervisor_candidates,
    reward_summary,
    sort_key,
    summarize_target_ranks,
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
    assert summary["reward"]["red5Reward"] > 0
    assert summary["rank_quality"]["top_50000_hits"] == 1
    assert summary["reward"]["rankQualityReward"] > 0


def test_load_prior_supervisor_candidates_keeps_same_protocol_global_best(tmp_path):
    config = FrequencyRankerConfig(frequency_weight=0.765, omission_weight=0)
    summary = {
        "config": config.__dict__,
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
