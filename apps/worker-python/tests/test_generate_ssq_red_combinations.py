from __future__ import annotations

import argparse

import pytest

from scripts.generate_ssq_red_combinations import positive_int


@pytest.mark.parametrize(("value", "expected"), [("1", 1), ("5000", 5000)])
def test_positive_int_accepts_positive_values(value: str, expected: int):
    assert positive_int(value) == expected


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_positive_int_rejects_non_positive_or_invalid_values(value: str):
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int(value)
