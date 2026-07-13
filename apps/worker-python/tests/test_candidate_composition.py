from __future__ import annotations

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.training.candidate_composition import CandidateSourceComposer, ReservedCandidateSource
from dehps.training.runtime import config_hash, merge_reserved_candidate_configs, refill_candidate_configs


def _config(value: float) -> FrequencyRankerConfig:
    return FrequencyRankerConfig(frequency_weight=value)


def test_candidate_source_composer_preserves_runtime_merge_order_and_budget() -> None:
    normal = tuple(_config(value) for value in (0.1, 0.2, 0.3, 0.4, 0.5))
    weight = (_config(0.6), _config(0.7))
    inversion = (_config(0.8),)
    composer = CandidateSourceComposer(
        merge_reserved=merge_reserved_candidate_configs,
        refill=refill_candidate_configs,
        config_hash=config_hash,
    )

    composition = composer.compose(
        normal_pool=normal,
        normal_budget=2,
        reserved_sources=(
            ReservedCandidateSource("weight_kdj", weight, 2, capacity=4),
            ReservedCandidateSource("target_weight_inversion", inversion, 1),
        ),
        max_configs=5,
    )

    expected = merge_reserved_candidate_configs(normal[:2], weight, max_configs=4, reserved_budget=2)
    expected = merge_reserved_candidate_configs(expected, inversion, max_configs=5, reserved_budget=1)
    expected = refill_candidate_configs(expected, normal, max_configs=5)
    assert composition.configs == expected
    assert composition.source_configs["weight_kdj"] == weight
    assert composition.source_configs["target_weight_inversion"] == inversion
    assert len(composition.configs) == 5
