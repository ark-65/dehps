from __future__ import annotations

from dehps.advisors.neural_kdj_adapter import NeuralKdjAdvisorAdapter
from dehps.advisors.protocol import AdvisorCandidate, AdvisorContext
from dehps.advisors.registry import AdvisorRegistry
from dehps.advisors.ridge_kdj_adapter import RidgeKdjAdvisorAdapter
from dehps.advisors.weight_kdj_adapter import WeightKdjAdvisorAdapter
from dehps.models.frequency_ranker import FrequencyRankerConfig
import scripts.run_training_supervisor as supervisor


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


def test_candidate_summaries_retain_advisor_source_and_protocol_version() -> None:
    config = FrequencyRankerConfig(frequency_weight=0.5)
    summary = {"config_hash": supervisor.config_hash(config)}
    candidate = AdvisorCandidate(
        config=config,
        source_key="ridge_kdj",
        protocol_version="ridge_kdj_advisor_v1",
    )

    supervisor.attach_candidate_source_metadata(
        [summary],
        {"normal": (), "ridge_kdj": (config,)},
        advisor_candidates=(candidate,),
    )

    assert summary["source_key"] == "ridge_kdj"
    assert summary["source_protocol_version"] == "ridge_kdj_advisor_v1"
    assert summary["candidate_source"] == {
        "key": "ridge_kdj",
        "protocol_version": "ridge_kdj_advisor_v1",
    }
