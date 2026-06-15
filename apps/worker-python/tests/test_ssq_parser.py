import pytest

from dehps.crawler.ssq_parser import validate_ssq_draw


def test_validate_legal_draw_sorts_red_numbers():
    draw = validate_ssq_draw(
        {"issue": "2026001", "draw_date": "2026-01-04", "red_numbers": [6, 1, 10, 17, 22, 30], "blue_number": 8}
    )
    assert draw.red_numbers == (1, 6, 10, 17, 22, 30)


def test_duplicate_red_numbers_error():
    with pytest.raises(ValueError):
        validate_ssq_draw({"issue": "x", "red_numbers": [1, 1, 2, 3, 4, 5], "blue_number": 8})


def test_red_out_of_range_error():
    with pytest.raises(ValueError):
        validate_ssq_draw({"issue": "x", "red_numbers": [1, 2, 3, 4, 5, 34], "blue_number": 8})


def test_blue_out_of_range_error():
    with pytest.raises(ValueError):
        validate_ssq_draw({"issue": "x", "red_numbers": [1, 2, 3, 4, 5, 6], "blue_number": 17})

