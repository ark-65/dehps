import pytest

from dehps.pattern_discovery.models import (
    SynthesizedFeature,
    SynthesizedFeatureMode,
    SynthesizedStrategy,
    SynthesizedStrategyType,
)
from dehps.pattern_discovery.service import PatternFeatureSynthesizer, PatternStrategySynthesizer
from pattern_fixtures import ap_candidate


def test_pattern_candidate_is_serializable_with_formula_hash() -> None:
    candidate = ap_candidate()

    assert candidate.formula_hash
    assert '"formula"' in candidate.stable_json()
    assert candidate.null_definition["primary"] == "legal_universe"


def test_feature_rejects_arbitrary_program_tokens() -> None:
    candidate = ap_candidate()
    feature = PatternFeatureSynthesizer().synthesize(candidate)

    with pytest.raises(ValueError, match="forbidden"):
        SynthesizedFeature(
            **{
                **feature.__dict__,
                "formula": {"operator": "eval", "source": "eval('1+1')"},
            }
        )


def test_strategy_rejects_production_impact() -> None:
    candidate = ap_candidate()
    feature = PatternFeatureSynthesizer().synthesize(candidate)
    strategy = PatternStrategySynthesizer().synthesize(feature, candidate)

    with pytest.raises(ValueError, match="production_impact"):
        SynthesizedStrategy(**{**strategy.__dict__, "production_impact": "replace_ranker"})

    assert strategy.strategy_type == SynthesizedStrategyType.SINGLE_FEATURE_RANK
    assert feature.execution_mode == SynthesizedFeatureMode.DECLARATIVE
