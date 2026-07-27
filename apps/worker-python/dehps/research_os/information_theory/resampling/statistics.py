from __future__ import annotations

from math import isfinite
from typing import Sequence

import numpy as np

from .contracts import ResamplingError


def _values(null_statistics: Sequence[float]) -> tuple[float, ...]:
    values = tuple(float(value) for value in null_statistics)
    if not values:
        raise ResamplingError("empty_null_distribution", "at least one null statistic is required")
    if any(not isfinite(value) for value in values):
        raise ResamplingError("nan_statistic", "statistics must be finite")
    return values


def plus_one_p_value(
    observed: float,
    null_statistics: Sequence[float],
    *,
    tail: str = "upper",
) -> float:
    if not isfinite(observed):
        raise ResamplingError("nan_statistic", "observed statistic must be finite")
    values = _values(null_statistics)
    upper = (1 + sum(value >= observed for value in values)) / (len(values) + 1)
    lower = (1 + sum(value <= observed for value in values)) / (len(values) + 1)
    if tail == "upper":
        return upper
    if tail == "lower":
        return lower
    if tail == "two_sided":
        return min(1.0, 2.0 * min(upper, lower))
    raise ResamplingError("invalid_tail", "tail must be upper, lower, or two_sided")


def percentile_summary(observed: float, null_statistics: Sequence[float]) -> dict[str, float]:
    if not isfinite(observed):
        raise ResamplingError("nan_statistic", "observed statistic must be finite")
    values = _values(null_statistics)
    less = sum(value < observed for value in values)
    equal = sum(value == observed for value in values)
    less_equal = less + equal
    return {
        "rank_mid": less + 0.5 * equal,
        "percentile_midrank": (less + 0.5 * equal) / len(values),
        "empirical_cdf_inclusive": less_equal / len(values),
        "upper_tail_p_plus_one": plus_one_p_value(observed, values, tail="upper"),
        "lower_tail_p_plus_one": plus_one_p_value(observed, values, tail="lower"),
    }


def type7_quantiles(values: Sequence[float]) -> dict[str, float]:
    clean = _values(values)
    quantiles = np.quantile(np.asarray(clean), [0.025, 0.25, 0.5, 0.75, 0.975], method="linear")
    return {
        "q025": float(quantiles[0]),
        "q25": float(quantiles[1]),
        "q50": float(quantiles[2]),
        "q75": float(quantiles[3]),
        "q975": float(quantiles[4]),
    }
