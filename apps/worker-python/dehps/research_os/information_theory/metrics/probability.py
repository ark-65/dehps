from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import isfinite
from numbers import Integral, Real
from typing import Any

from .contracts import ClipDiagnostics
from .errors import MetricKernelError


PROBABILITY_EPSILON = 1e-6
NUMBER_COUNT = 33
POSITIVE_COUNT = 6


def theoretical_number_probability() -> Fraction:
    return Fraction(POSITIVE_COUNT, NUMBER_COUNT)


def validate_target_vector(target: Sequence[Any]) -> tuple[int, ...]:
    if isinstance(target, (str, bytes)) or len(target) != NUMBER_COUNT:
        raise MetricKernelError(
            "invalid_target_vector", "target must contain exactly 33 entries"
        )
    normalized: list[int] = []
    for value in target:
        if not isinstance(value, Integral) or isinstance(value, bool) or int(value) not in (0, 1):
            raise MetricKernelError(
                "invalid_target_value", "target entries must be integer 0 or 1"
            )
        normalized.append(int(value))
    if sum(normalized) != POSITIVE_COUNT:
        raise MetricKernelError(
            "invalid_target_cardinality", "target must contain exactly six positives"
        )
    return tuple(normalized)


def validate_probability_vector(probabilities: Sequence[Any]) -> tuple[float, ...]:
    if isinstance(probabilities, (str, bytes)) or len(probabilities) != NUMBER_COUNT:
        raise MetricKernelError(
            "invalid_probability_vector",
            "probability vector must contain exactly 33 entries",
        )
    normalized: list[float] = []
    for value in probabilities:
        if not isinstance(value, Real) or isinstance(value, bool):
            raise MetricKernelError(
                "invalid_probability_value", "probabilities must be numeric"
            )
        probability = float(value)
        if not isfinite(probability):
            raise MetricKernelError(
                "non_finite_probability", "probability must be finite"
            )
        if probability < 0.0 or probability > 1.0:
            raise MetricKernelError(
                "probability_out_of_range", "probability must be within [0,1]"
            )
        normalized.append(probability)
    return tuple(normalized)


def clip_probabilities(
    probabilities: Sequence[Any],
    *,
    epsilon: float = PROBABILITY_EPSILON,
) -> tuple[tuple[float, ...], ClipDiagnostics]:
    raw = validate_probability_vector(probabilities)
    if not isfinite(epsilon) or epsilon <= 0.0 or epsilon >= 0.5:
        raise MetricKernelError(
            "invalid_probability_epsilon", "epsilon must be finite and in (0,0.5)"
        )
    upper = 1.0 - epsilon
    clipped = tuple(min(max(value, epsilon), upper) for value in raw)
    low = sum(value < epsilon for value in raw)
    high = sum(value > upper for value in raw)
    return clipped, ClipDiagnostics(
        raw_min_probability=min(raw),
        raw_max_probability=max(raw),
        clipped_min_probability=min(clipped),
        clipped_max_probability=max(clipped),
        clip_count_low=low,
        clip_count_high=high,
        clip_fraction=(low + high) / NUMBER_COUNT,
        epsilon=epsilon,
    )


@dataclass(frozen=True)
class AdaptedIssue:
    issue_id: str
    cluster_id: str
    target_vector: tuple[int, ...]
    probability_vector: tuple[float, ...]


def adapt_number_event_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[AdaptedIssue, ...]:
    if not rows:
        raise MetricKernelError("issue_cluster_missing", "number-event rows are empty")
    grouped: OrderedDict[str, list[Mapping[str, Any]]] = OrderedDict()
    for row in rows:
        issue_id = str(row.get("issue_id", "")).strip()
        cluster_id = str(row.get("cluster_id", "")).strip()
        if not issue_id or not cluster_id:
            raise MetricKernelError(
                "issue_cluster_missing", "issue_id and cluster_id are required"
            )
        if issue_id != cluster_id:
            raise MetricKernelError(
                "issue_cluster_mismatch", "cluster_id must equal issue_id"
            )
        grouped.setdefault(issue_id, []).append(row)
    result: list[AdaptedIssue] = []
    for issue_id, issue_rows in grouped.items():
        if len(issue_rows) != NUMBER_COUNT:
            raise MetricKernelError(
                "invalid_issue_cluster_size", "each issue must contain 33 rows"
            )
        numbers = [int(row.get("red_number", 0)) for row in issue_rows]
        if sorted(numbers) != list(range(1, NUMBER_COUNT + 1)):
            raise MetricKernelError(
                "invalid_red_number_identity",
                "red numbers 1 through 33 must be complete and unique",
            )
        ordered = sorted(issue_rows, key=lambda row: int(row["red_number"]))
        result.append(
            AdaptedIssue(
                issue_id=issue_id,
                cluster_id=issue_id,
                target_vector=validate_target_vector(
                    [row.get("target") for row in ordered]
                ),
                probability_vector=validate_probability_vector(
                    [row.get("probability") for row in ordered]
                ),
            )
        )
    return tuple(result)
