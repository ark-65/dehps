from datetime import date, datetime

import pytest

from dehps.crawler.ssq_parser import validate_ssq_draw


def test_validate_legal_draw_sorts_red_numbers():
    draw = validate_ssq_draw(
        {"issue": "2026001", "draw_date": "2026-01-04", "red_numbers": [6, 1, 10, 17, 22, 30], "blue_number": 8}
    )
    assert draw.red_numbers == (1, 6, 10, 17, 22, 30)


def test_datetime_draw_date_is_normalized_to_date():
    draw = validate_ssq_draw(
        {
            "issue": "2026001",
            "draw_date": datetime(2026, 1, 4, 12, 30),
            "red_numbers": [1, 2, 3, 4, 5, 6],
            "blue_number": 8,
        }
    )

    assert draw.draw_date == date(2026, 1, 4)


def test_blank_draw_date_is_treated_as_missing():
    draw = validate_ssq_draw(
        {
            "issue": "2026001",
            "draw_date": "   ",
            "red_numbers": [1, 2, 3, 4, 5, 6],
            "blue_number": 8,
        }
    )

    assert draw.draw_date is None


def test_duplicate_red_numbers_error():
    with pytest.raises(ValueError):
        validate_ssq_draw({"issue": "x", "red_numbers": [1, 1, 2, 3, 4, 5], "blue_number": 8})


def test_red_out_of_range_error():
    with pytest.raises(ValueError):
        validate_ssq_draw({"issue": "x", "red_numbers": [1, 2, 3, 4, 5, 34], "blue_number": 8})


def test_blue_out_of_range_error():
    with pytest.raises(ValueError):
        validate_ssq_draw({"issue": "x", "red_numbers": [1, 2, 3, 4, 5, 6], "blue_number": 17})


@pytest.mark.parametrize("value", [1.5, "1.5", True])
def test_non_integer_red_number_error(value):
    with pytest.raises(ValueError, match="red_numbers must be an integer"):
        validate_ssq_draw({"issue": "x", "red_numbers": [value, 2, 3, 4, 5, 6], "blue_number": 8})


@pytest.mark.parametrize("value", [8.5, "8.5", False])
def test_non_integer_blue_number_error(value):
    with pytest.raises(ValueError, match="blue_number must be an integer"):
        validate_ssq_draw({"issue": "x", "red_numbers": [1, 2, 3, 4, 5, 6], "blue_number": value})
