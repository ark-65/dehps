from __future__ import annotations

from datetime import date

from dehps.optimization.regime import subtract_years


def test_subtract_years_handles_leap_day():
    assert subtract_years(date(2024, 2, 29), 10) == date(2014, 2, 28)
