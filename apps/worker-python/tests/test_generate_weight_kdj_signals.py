from __future__ import annotations

import pytest

from dehps.models.frequency_ranker import FrequencyRankerConfig
from scripts.generate_weight_kdj_signals import parse_weights, probe_configs


def test_parse_weights_defaults_to_all_fields_and_rejects_unknown():
    fields = parse_weights(None)

    assert "frequency_weight" in fields
    assert "weekday_trend_weight" in fields
    with pytest.raises(ValueError, match="unknown weight fields"):
        parse_weights("frequency_weight,not_a_weight")


def test_probe_configs_deduplicates_clamped_values():
    configs = probe_configs(
        FrequencyRankerConfig(frequency_weight=0.0),
        weight_name="frequency_weight",
        step=0.03,
    )

    values = [config.frequency_weight for config in configs]
    assert values == sorted(set(values))
    assert values[0] == 0.0
    assert values[-1] == 0.06
