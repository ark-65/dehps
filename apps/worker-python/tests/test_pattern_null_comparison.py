from dehps.pattern_discovery.arithmetic import ArithmeticProgressionExtractor, legal_universe_probability
from pattern_fixtures import HISTORY


def test_pattern_null_comparison_includes_legal_and_matched_nulls() -> None:
    nulls = ArithmeticProgressionExtractor().compare_to_matched_nulls((3, 1, 1), HISTORY)

    assert set(nulls) == {
        "legal_universe",
        "same_sum",
        "same_span",
        "same_odd_even",
        "random_history_permutation",
    }
    assert nulls["legal_universe"] == legal_universe_probability((3, 1, 1))
    assert all(0.0 <= value <= 1.0 for value in nulls.values())
