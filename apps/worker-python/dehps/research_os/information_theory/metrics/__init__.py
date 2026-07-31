"""Deterministic P2.2 information-theory metric kernel."""

from .aggregation import aggregate_issue_metrics
from .artifacts import (
    build_metric_artifact,
    load_metric_kernel_manifest,
    show_metric_artifact,
    validate_metric_artifact,
    validate_metric_input,
)
from .code_length import (
    joint_uniform_code_length,
    reject_marginal_product_as_joint,
)
from .contracts import (
    AGGREGATE_SCHEMA_VERSION,
    ISSUE_SCHEMA_VERSION,
    KERNEL_VERSION,
    METRIC_ARTIFACT_SCHEMA_VERSION,
    METRIC_INPUT_SCHEMA_VERSION,
    METRIC_MANIFEST_SCHEMA_VERSION,
    NUMBER_EVENT_SCHEMA_VERSION,
    AggregateMetric,
    IssueMetric,
    MetricKernelManifest,
    NumberEventMetric,
    UnitContract,
)
from .errors import MetricKernelError
from .information_gain import ObservedLogLossGain, observed_log_loss_gain
from .kernel import (
    evaluate_issue,
    probe_log_loss_bits_per_issue_batch,
    probe_log_loss_bits_per_issue_batch_exact_native,
)
from .log_loss import (
    bernoulli_log_loss_nats,
    bits_to_nats,
    nats_to_bits,
    theoretical_baseline_loss,
)
from .probability import (
    PROBABILITY_EPSILON,
    adapt_number_event_rows,
    clip_probabilities,
    theoretical_number_probability,
    validate_probability_vector,
    validate_target_vector,
)

__all__ = [
    "AGGREGATE_SCHEMA_VERSION",
    "ISSUE_SCHEMA_VERSION",
    "KERNEL_VERSION",
    "METRIC_ARTIFACT_SCHEMA_VERSION",
    "METRIC_INPUT_SCHEMA_VERSION",
    "METRIC_MANIFEST_SCHEMA_VERSION",
    "NUMBER_EVENT_SCHEMA_VERSION",
    "PROBABILITY_EPSILON",
    "AggregateMetric",
    "IssueMetric",
    "MetricKernelError",
    "MetricKernelManifest",
    "NumberEventMetric",
    "ObservedLogLossGain",
    "UnitContract",
    "adapt_number_event_rows",
    "aggregate_issue_metrics",
    "bernoulli_log_loss_nats",
    "bits_to_nats",
    "build_metric_artifact",
    "clip_probabilities",
    "evaluate_issue",
    "joint_uniform_code_length",
    "load_metric_kernel_manifest",
    "nats_to_bits",
    "observed_log_loss_gain",
    "probe_log_loss_bits_per_issue_batch",
    "probe_log_loss_bits_per_issue_batch_exact_native",
    "reject_marginal_product_as_joint",
    "show_metric_artifact",
    "theoretical_baseline_loss",
    "theoretical_number_probability",
    "validate_metric_artifact",
    "validate_metric_input",
    "validate_probability_vector",
    "validate_target_vector",
]
