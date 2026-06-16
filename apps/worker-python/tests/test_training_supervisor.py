from __future__ import annotations

from dehps.models.frequency_ranker import FrequencyRankerConfig
from scripts.run_training_supervisor import generate_configs, sort_key


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
