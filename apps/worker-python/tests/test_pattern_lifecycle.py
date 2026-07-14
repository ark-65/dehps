from dehps.pattern_discovery.models import PatternLifecycleStatus, lifecycle_transition_allowed
from dehps.pattern_discovery.validation import PatternContractValidator


def test_frozen_rejected_cannot_become_forward_supported() -> None:
    assert lifecycle_transition_allowed(
        PatternLifecycleStatus.FROZEN_REJECTED,
        PatternLifecycleStatus.FORWARD_SUPPORTED,
    ) is False
    report = PatternContractValidator().validate_lifecycle_transition(
        PatternLifecycleStatus.FROZEN_REJECTED,
        PatternLifecycleStatus.FORWARD_SUPPORTED,
    )
    assert report.valid is False
