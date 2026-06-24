from __future__ import annotations

from itertools import combinations
from operator import index
from typing import Iterable


def _coerce_red_number(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("red numbers must be integers")
    if isinstance(value, str):
        text = value.strip()
        signed_digits = text[1:] if text.startswith(("+", "-")) else text
        if text and signed_digits.isdecimal():
            return int(text)
        raise ValueError("red numbers must be integers")
    try:
        return index(value)
    except TypeError as exc:
        raise ValueError("red numbers must be integers") from exc


def normalize_red_numbers(numbers: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(sorted(_coerce_red_number(n) for n in numbers))
    if len(normalized) != 6:
        raise ValueError("red numbers must contain exactly 6 values")
    if len(set(normalized)) != 6:
        raise ValueError("red numbers must be unique")
    if any(n < 1 or n > 33 for n in normalized):
        raise ValueError("red numbers must be between 1 and 33")
    return normalized


def iter_ssq_red_combinations() -> Iterable[tuple[int, ...]]:
    return combinations(range(1, 34), 6)
