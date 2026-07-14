from dehps.pattern_discovery.significance import PatternSignificanceReviewer
from pattern_fixtures import ap_candidate


def test_pattern_significance_applies_family_and_sequential_adjustment() -> None:
    result = PatternSignificanceReviewer().review(
        ap_candidate(),
        multiplicity_count=10,
        multiplicity_complete=True,
        sequential_search_count=3,
    )

    assert result.family_adjusted_p_value >= result.raw_p_value
    assert result.sequential_adjusted_p_value >= result.family_adjusted_p_value
    assert result.interpretable is True


def test_incomplete_multiplicity_is_not_interpretable() -> None:
    result = PatternSignificanceReviewer().review(
        ap_candidate(),
        multiplicity_count=10,
        multiplicity_complete=False,
    )

    assert result.interpretable is False
    assert "incomplete_multiplicity_accounting" in result.blocker_codes


def test_large_sample_binomial_tail_does_not_overflow() -> None:
    candidate = ap_candidate()
    large = type(candidate)(
        **{
            **candidate.__dict__,
            "observed_support": 120.0,
            "expected_support": 80.0,
            "source_artifacts": tuple(f"issue-{index}" for index in range(120)),
            "metadata": {"sample_count": 3476},
        }
    )

    result = PatternSignificanceReviewer().review(
        large,
        multiplicity_count=20,
        multiplicity_complete=True,
    )

    assert 0.0 <= result.raw_p_value <= 1.0
