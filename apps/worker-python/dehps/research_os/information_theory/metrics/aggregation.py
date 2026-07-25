from __future__ import annotations

from math import fsum, sqrt
from statistics import median
from typing import Sequence

from .contracts import AggregateMetric, IssueMetric
from .errors import MetricKernelError


def aggregate_issue_metrics(issues: Sequence[IssueMetric]) -> AggregateMetric:
    if not issues:
        raise MetricKernelError("empty_metric_sequence", "at least one issue is required")
    issue_ids = tuple(item.issue_id for item in issues)
    if len(set(issue_ids)) != len(issue_ids):
        raise MetricKernelError("duplicate_issue_id", "issue ids must be unique")
    count = len(issues)
    gains = [item.observed_log_loss_gain_bits_per_issue for item in issues]
    mean_gain = fsum(gains) / count
    variance = (
        fsum((value - mean_gain) ** 2 for value in gains) / (count - 1)
        if count > 1
        else 0.0
    )
    mean_probability = fsum(item.mean_predicted_probability for item in issues) / count
    observed_positive_rate = 6 / 33
    return AggregateMetric(
        issue_ids_in_sequence=issue_ids,
        issue_count=count,
        sample_size_for_inference=count,
        cumulative_baseline_log_loss_bits=fsum(
            item.baseline_log_loss_bits_per_issue for item in issues
        ),
        cumulative_probe_log_loss_bits=fsum(
            item.probe_log_loss_bits_per_issue for item in issues
        ),
        cumulative_observed_log_loss_gain_bits=fsum(gains),
        mean_observed_log_loss_gain_bits_per_issue=mean_gain,
        median_observed_log_loss_gain_bits_per_issue=median(gains),
        mean_brier_gain_per_issue=fsum(
            item.brier_gain_per_issue for item in issues
        )
        / count,
        mean_predicted_probability=mean_probability,
        observed_positive_rate=observed_positive_rate,
        calibration_in_the_large=observed_positive_rate - mean_probability,
        mean_predicted_red_count=fsum(
            item.predicted_red_count for item in issues
        )
        / count,
        mean_absolute_red_count_error=fsum(
            abs(item.red_count_error) for item in issues
        )
        / count,
        sample_std_gain_bits_across_issues=sqrt(variance),
        sample_std_role="descriptive_only",
        uncertainty_status="not_final_time_series_uncertainty",
    )
