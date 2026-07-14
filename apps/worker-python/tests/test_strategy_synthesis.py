from dehps.pattern_discovery.models import SynthesizedStrategyType
from dehps.pattern_discovery.service import PatternFeatureSynthesizer, PatternStrategySynthesizer
from dehps.pattern_discovery.validation import PatternContractValidator
from pattern_fixtures import ap_candidate


def test_strategy_synthesis_uses_allow_list_and_no_production_impact() -> None:
    candidate = ap_candidate()
    feature = PatternFeatureSynthesizer().synthesize(candidate)
    strategy = PatternStrategySynthesizer().synthesize(feature, candidate)
    report = PatternContractValidator().validate_strategy(strategy)

    assert strategy.strategy_type == SynthesizedStrategyType.SINGLE_FEATURE_RANK
    assert strategy.production_impact == "none"
    assert report.valid
