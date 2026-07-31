from __future__ import annotations

from collections.abc import Sequence
from math import fsum, isclose, log, log1p
from typing import Any

import numpy as np
from numba import njit

from .brier import brier_per_number_event
from .calibration import issue_calibration_statistics
from .contracts import IssueMetric, NumberEventMetric
from .errors import MetricKernelError
from .information_gain import observed_log_loss_gain
from .log_loss import LN_2, bernoulli_log_loss_nats, nats_to_bits
from .probability import (
    PROBABILITY_EPSILON,
    clip_probabilities,
    theoretical_number_probability,
    validate_target_vector,
)

BASELINE_IDENTITY = "NUMBER_EVENT_COMPOSITE_BASELINE"


def probe_log_loss_bits_per_issue_batch(
    *,
    target_vectors: Sequence[Sequence[Any]],
    probe_probability_vectors: Sequence[Sequence[Any]],
    epsilon: float = PROBABILITY_EPSILON,
) -> tuple[float, ...]:
    """P2.2 aggregate API for nested validation without event artifacts.

    It deliberately uses the same validators, clipping rule, Bernoulli loss,
    ``fsum`` order, and nats-to-bits conversion as ``evaluate_issue``.
    """

    if len(target_vectors) == 0 or len(target_vectors) != len(
        probe_probability_vectors
    ):
        raise MetricKernelError(
            "issue_cluster_missing",
            "batch targets and predictions must be non-empty and aligned",
        )
    targets = np.asarray(target_vectors)
    probabilities = np.asarray(probe_probability_vectors, dtype=np.float64)
    if (
        targets.ndim != 2
        or targets.shape != probabilities.shape
        or targets.shape[1] != 33
        or not np.issubdtype(targets.dtype, np.integer)
        or not np.isin(targets, (0, 1)).all()
        or not np.all(targets.sum(axis=1) == 6)
    ):
        raise MetricKernelError(
            "invalid_target_vector",
            "batch targets must be legal aligned N x 33 six-of-33 vectors",
        )
    if (
        not np.isfinite(probabilities).all()
        or np.any(probabilities < 0.0)
        or np.any(probabilities > 1.0)
        or not np.isfinite(epsilon)
        or epsilon <= 0.0
        or epsilon >= 0.5
    ):
        raise MetricKernelError(
            "invalid_probability_vector",
            "batch probabilities must be finite in [0,1] with legal epsilon",
        )
    clipped = np.clip(probabilities, epsilon, 1.0 - epsilon)
    result: list[float] = []
    for target, probability in zip(targets, clipped, strict=True):
        nats = fsum(
            (
                -log(float(probability[index]))
                if int(actual) == 1
                else -log1p(-float(probability[index]))
            )
            for index, actual in enumerate(target)
        )
        result.append(nats_to_bits(nats))
    return tuple(result)


@njit(cache=True, nogil=True)
def _exact_positive_fsum(values: np.ndarray) -> float:
    """Numba transcription of CPython ``math.fsum`` for finite positive terms."""

    partials = np.empty(33, dtype=np.float64)
    partial_count = 0
    for value_index in range(values.size):
        x = values[value_index]
        next_partial = 0
        for partial_index in range(partial_count):
            y = partials[partial_index]
            if abs(x) < abs(y):
                x, y = y, x
            hi = x + y
            lo = y - (hi - x)
            if lo != 0.0:
                partials[next_partial] = lo
                next_partial += 1
            x = hi
        partial_count = next_partial
        if x != 0.0:
            partials[partial_count] = x
            partial_count += 1

    hi = 0.0
    if partial_count:
        partial_count -= 1
        hi = partials[partial_count]
        lo = 0.0
        while partial_count:
            x = hi
            partial_count -= 1
            y = partials[partial_count]
            hi = x + y
            lo = y - (hi - x)
            if lo != 0.0:
                break
        if partial_count and (
            (lo < 0.0 and partials[partial_count - 1] < 0.0)
            or (lo > 0.0 and partials[partial_count - 1] > 0.0)
        ):
            y = lo * 2.0
            x = hi + y
            if y == x - hi:
                hi = x
    return hi


@njit(cache=True, nogil=True)
def _probe_log_loss_bits_exact_native(
    targets: np.ndarray,
    probabilities: np.ndarray,
) -> np.ndarray:
    losses = np.empty(targets.shape[0], dtype=np.float64)
    terms = np.empty(33, dtype=np.float64)
    for row_index in range(targets.shape[0]):
        for number_index in range(33):
            probability = probabilities[row_index, number_index]
            terms[number_index] = (
                -log(probability)
                if targets[row_index, number_index] == 1
                else -log1p(-probability)
            )
        losses[row_index] = _exact_positive_fsum(terms) / LN_2
    return losses


def probe_log_loss_bits_per_issue_batch_exact_native(
    *,
    target_vectors: Sequence[Sequence[Any]],
    probe_probability_vectors: Sequence[Sequence[Any]],
    epsilon: float = PROBABILITY_EPSILON,
) -> tuple[float, ...]:
    """Exact compiled backend for the frozen P2.2 nested-validation aggregate."""

    if len(target_vectors) == 0 or len(target_vectors) != len(
        probe_probability_vectors
    ):
        raise MetricKernelError(
            "issue_cluster_missing",
            "batch targets and predictions must be non-empty and aligned",
        )
    targets = np.asarray(target_vectors)
    probabilities = np.asarray(probe_probability_vectors, dtype=np.float64)
    if (
        targets.ndim != 2
        or targets.shape != probabilities.shape
        or targets.shape[1] != 33
        or not np.issubdtype(targets.dtype, np.integer)
        or not np.isin(targets, (0, 1)).all()
        or not np.all(targets.sum(axis=1) == 6)
    ):
        raise MetricKernelError(
            "invalid_target_vector",
            "batch targets must be legal aligned N x 33 six-of-33 vectors",
        )
    if (
        not np.isfinite(probabilities).all()
        or np.any(probabilities < 0.0)
        or np.any(probabilities > 1.0)
        or not np.isfinite(epsilon)
        or epsilon <= 0.0
        or epsilon >= 0.5
    ):
        raise MetricKernelError(
            "invalid_probability_vector",
            "batch probabilities must be finite in [0,1] with legal epsilon",
        )
    clipped = np.clip(probabilities, epsilon, 1.0 - epsilon)
    return tuple(
        float(value) for value in _probe_log_loss_bits_exact_native(targets, clipped)
    )


def evaluate_issue(
    *,
    issue_id: str,
    target_vector: Sequence[Any],
    baseline_probability_vector: Sequence[Any],
    probe_probability_vector: Sequence[Any],
    epsilon: float = PROBABILITY_EPSILON,
    baseline_identity: str = BASELINE_IDENTITY,
    cluster_id: str | None = None,
) -> IssueMetric:
    normalized_issue = str(issue_id).strip()
    normalized_cluster = str(cluster_id if cluster_id is not None else issue_id).strip()
    if not normalized_issue or not normalized_cluster:
        raise MetricKernelError(
            "issue_cluster_missing", "issue_id and cluster_id are required"
        )
    if normalized_issue != normalized_cluster:
        raise MetricKernelError(
            "issue_cluster_mismatch", "cluster_id must equal issue_id"
        )
    if baseline_identity != BASELINE_IDENTITY:
        raise MetricKernelError("unknown_baseline", "unsupported baseline identity")
    target = validate_target_vector(target_vector)
    baseline, baseline_clip = clip_probabilities(
        baseline_probability_vector, epsilon=epsilon
    )
    probe, probe_clip = clip_probabilities(probe_probability_vector, epsilon=epsilon)
    expected = float(theoretical_number_probability())
    if any(
        not isclose(value, expected, rel_tol=0.0, abs_tol=1e-15)
        for value in baseline_probability_vector
    ):
        raise MetricKernelError(
            "baseline_probability_mismatch",
            "NUMBER_EVENT_COMPOSITE_BASELINE must use exact 6/33 marginals",
        )

    events: list[NumberEventMetric] = []
    for index, actual in enumerate(target):
        baseline_nats = bernoulli_log_loss_nats(actual, baseline[index])
        probe_nats = bernoulli_log_loss_nats(actual, probe[index])
        events.append(
            NumberEventMetric(
                issue_id=normalized_issue,
                cluster_id=normalized_cluster,
                red_number=index + 1,
                target=actual,
                baseline_raw_probability=float(baseline_probability_vector[index]),
                baseline_clipped_probability=baseline[index],
                probe_raw_probability=float(probe_probability_vector[index]),
                probe_clipped_probability=probe[index],
                baseline_log_loss_nats_per_number_event=baseline_nats,
                baseline_log_loss_bits_per_number_event=nats_to_bits(baseline_nats),
                probe_log_loss_nats_per_number_event=probe_nats,
                probe_log_loss_bits_per_number_event=nats_to_bits(probe_nats),
                baseline_brier_per_number_event=brier_per_number_event(
                    actual, baseline[index]
                ),
                probe_brier_per_number_event=brier_per_number_event(
                    actual, probe[index]
                ),
            )
        )
    baseline_nats_issue = fsum(
        item.baseline_log_loss_nats_per_number_event for item in events
    )
    probe_nats_issue = fsum(
        item.probe_log_loss_nats_per_number_event for item in events
    )
    baseline_brier_issue = fsum(item.baseline_brier_per_number_event for item in events)
    probe_brier_issue = fsum(item.probe_brier_per_number_event for item in events)
    gain = observed_log_loss_gain(
        baseline_nats_per_issue=baseline_nats_issue,
        probe_nats_per_issue=probe_nats_issue,
    )
    calibration = issue_calibration_statistics(
        [float(value) for value in probe_probability_vector]
    )
    return IssueMetric(
        issue_id=normalized_issue,
        cluster_id=normalized_cluster,
        baseline_identity=baseline_identity,
        probability_epsilon=epsilon,
        baseline_clip_diagnostics=baseline_clip,
        probe_clip_diagnostics=probe_clip,
        number_events=tuple(events),
        baseline_log_loss_nats_per_issue=baseline_nats_issue,
        baseline_log_loss_nats_per_number_event=baseline_nats_issue / 33,
        baseline_log_loss_bits_per_issue=nats_to_bits(baseline_nats_issue),
        baseline_log_loss_bits_per_number_event=nats_to_bits(baseline_nats_issue) / 33,
        probe_log_loss_nats_per_issue=probe_nats_issue,
        probe_log_loss_nats_per_number_event=probe_nats_issue / 33,
        probe_log_loss_bits_per_issue=nats_to_bits(probe_nats_issue),
        probe_log_loss_bits_per_number_event=nats_to_bits(probe_nats_issue) / 33,
        observed_log_loss_gain_nats_per_issue=gain.nats_per_issue,
        observed_log_loss_gain_bits_per_issue=gain.bits_per_issue,
        gain_direction=gain.direction,
        eligible_for_pe1=gain.eligible_for_pe1,
        eligible_for_final_pe2=gain.eligible_for_final_pe2,
        baseline_brier_sum_per_issue=baseline_brier_issue,
        baseline_brier_mean_per_number_event=baseline_brier_issue / 33,
        probe_brier_sum_per_issue=probe_brier_issue,
        probe_brier_mean_per_number_event=probe_brier_issue / 33,
        brier_gain_per_issue=baseline_brier_issue - probe_brier_issue,
        mean_predicted_probability=float(calibration["mean_predicted_probability"]),
        predicted_red_count=float(calibration["predicted_red_count"]),
        actual_red_count=int(calibration["actual_red_count"]),
        red_count_error=float(calibration["red_count_error"]),
    )
