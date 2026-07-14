from dehps.pattern_discovery.models import SynthesizedFeatureMode
from dehps.pattern_discovery.service import PatternFeatureSynthesizer
from dehps.pattern_discovery.validation import PatternContractValidator
from pattern_fixtures import ap_candidate


def test_feature_synthesis_is_declarative_and_validated() -> None:
    feature = PatternFeatureSynthesizer().synthesize(ap_candidate())
    report = PatternContractValidator().validate_feature(feature)

    assert feature.execution_mode == SynthesizedFeatureMode.DECLARATIVE
    assert "contains" in feature.allowed_operations
    assert report.valid
