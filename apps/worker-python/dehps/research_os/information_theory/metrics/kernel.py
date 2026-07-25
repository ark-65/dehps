from __future__ import annotations

from math import fsum, isclose
from typing import Any, Sequence

from .brier import brier_per_number_event
from .calibration import issue_calibration_statistics
from .contracts import IssueMetric, NumberEventMetric
from .errors import MetricKernelError
from .information_gain import observed_log_loss_gain
from .log_loss import bernoulli_log_loss_nats, nats_to_bits
from .probability import (
    PROBABILITY_EPSILON,
    clip_probabilities,
    theoretical_number_probability,
    validate_target_vector,
)


BASELINE_IDENTITY = "NUMBER_EVENT_COMPOSITE_BASELINE"


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
    probe, probe_clip = clip_probabilities(
        probe_probability_vector, epsilon=epsilon
    )
    expected = float(theoretical_number_probability())
    if any(not isclose(value, expected, rel_tol=0.0, abs_tol=1e-15) for value in baseline_probability_vector):
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
    baseline_brier_issue = fsum(
        item.baseline_brier_per_number_event for item in events
    )
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
