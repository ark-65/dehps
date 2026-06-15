from __future__ import annotations

from itertools import combinations
from typing import Iterable


def normalize_red_numbers(numbers: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(sorted(int(n) for n in numbers))
    if len(normalized) != 6:
        raise ValueError("red numbers must contain exactly 6 values")
    if len(set(normalized)) != 6:
        raise ValueError("red numbers must be unique")
    if any(n < 1 or n > 33 for n in normalized):
        raise ValueError("red numbers must be between 1 and 33")
    return normalized


def iter_ssq_red_combinations() -> Iterable[tuple[int, ...]]:
    return combinations(range(1, 34), 6)

