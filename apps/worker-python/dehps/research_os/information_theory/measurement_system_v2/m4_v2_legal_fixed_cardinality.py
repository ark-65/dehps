from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from itertools import combinations
from typing import Final

LEGAL_BALL_COUNT: Final = 33
LEGAL_SELECTION_COUNT: Final = 6
LEGAL_STATE_COUNT: Final = 1_107_568


class LegalFixedCardinalityError(ValueError):
    pass


def legal_states() -> Iterable[tuple[int, ...]]:
    """Yield zero-based six-of-33 states in the frozen lexicographic order."""

    return combinations(range(LEGAL_BALL_COUNT), LEGAL_SELECTION_COUNT)


def elementary_symmetric(weights: Sequence[float], degree: int = 6) -> float:
    if len(weights) != LEGAL_BALL_COUNT or degree != LEGAL_SELECTION_COUNT:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_shape_invalid")
    coefficients = [0.0] * (degree + 1)
    coefficients[0] = 1.0
    for weight in weights:
        if not math.isfinite(weight) or weight <= 0.0:
            raise LegalFixedCardinalityError("legal_fixed_cardinality_weight_invalid")
        for index in range(degree, 0, -1):
            coefficients[index] += coefficients[index - 1] * weight
    partition = coefficients[degree]
    if not math.isfinite(partition) or partition <= 0.0:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_partition_invalid")
    return partition


def fixed_cardinality_marginals(weights: Sequence[float]) -> tuple[float, ...]:
    partition = elementary_symmetric(weights)
    marginals: list[float] = []
    for held_out, weight in enumerate(weights):
        remaining = [value for index, value in enumerate(weights) if index != held_out]
        marginals.append(weight * elementary_symmetric_degree_five(remaining) / partition)
    return tuple(marginals)


def elementary_symmetric_degree_five(weights: Sequence[float]) -> float:
    coefficients = [0.0] * 6
    coefficients[0] = 1.0
    for weight in weights:
        for index in range(5, 0, -1):
            coefficients[index] += coefficients[index - 1] * weight
    return coefficients[5]


__all__ = [
    "LEGAL_BALL_COUNT",
    "LEGAL_SELECTION_COUNT",
    "LEGAL_STATE_COUNT",
    "LegalFixedCardinalityError",
    "elementary_symmetric",
    "fixed_cardinality_marginals",
    "legal_states",
]
