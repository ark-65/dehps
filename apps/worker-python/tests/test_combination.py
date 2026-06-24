from __future__ import annotations

import pytest

from dehps.domain.combination import normalize_red_numbers


def test_normalize_red_numbers_accepts_sorted_integer_strings():
    assert normalize_red_numbers(["06", "01", "10", "17", "22", "30"]) == (1, 6, 10, 17, 22, 30)


@pytest.mark.parametrize("value", [1.0, 1.9, True, False, "1.0", "abc"])
def test_normalize_red_numbers_rejects_non_integer_values(value: object):
    with pytest.raises(ValueError, match="red numbers must be integers"):
        normalize_red_numbers([value, 2, 3, 4, 5, 6])
