from __future__ import annotations

from dehps.advisors.neural_kdj_adapter import NeuralKdjAdvisorAdapter
from dehps.advisors.protocol import AdvisorContext
from dehps.advisors.registry import AdvisorRegistry
from dehps.advisors.ridge_kdj_adapter import RidgeKdjAdvisorAdapter
from dehps.advisors.weight_kdj_adapter import WeightKdjAdvisorAdapter
from dehps.models.frequency_ranker import FrequencyRankerConfig


def test_registry_preserves_source_and_protocol_metadata_without_mutating_base() -> None:
    base = FrequencyRankerConfig(frequency_weight=0.3)
    context = AdvisorContext(base_config=base)
    registry = AdvisorRegistry.build(
        (
            WeightKdjAdvisorAdapter(lambda ctx, budget: (FrequencyRankerConfig(frequency_weight=0.4),)[:budget]),
            RidgeKdjAdvisorAdapter(lambda ctx, budget: (FrequencyRankerConfig(frequency_weight=0.5),)[:budget]),
            NeuralKdjAdvisorAdapter(lambda ctx, budget: (FrequencyRankerConfig(frequency_weight=0.6),)[:budget]),
        )
    )

    candidates = registry.propose(
        context,
        budgets={"weight_kdj": 1, "ridge_kdj": 1, "neural_kdj": 0},
    )

    assert [(candidate.source_key, candidate.protocol_version) for candidate in candidates] == [
        ("weight_kdj", "weight_kdj_advisor_v1"),
        ("ridge_kdj", "ridge_kdj_advisor_v1"),
    ]
    assert [candidate.config.frequency_weight for candidate in candidates] == [0.4, 0.5]
    assert base.frequency_weight == 0.3


def test_registry_rejects_duplicate_source_keys() -> None:
    adapter = WeightKdjAdvisorAdapter(lambda ctx, budget: ())

    try:
        AdvisorRegistry.build((adapter, adapter))
    except ValueError as exc:
        assert str(exc) == "advisor keys must be unique"
    else:  # pragma: no cover - explicit assertion keeps dependency-free test readable.
        raise AssertionError("duplicate advisor keys should fail")
