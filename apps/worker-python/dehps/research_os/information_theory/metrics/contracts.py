from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from dehps.training.research_fingerprint import SeedPolicy

from .errors import MetricKernelError


KERNEL_VERSION = "m4-information-theory-metric-kernel-v1"
METRIC_MANIFEST_SCHEMA_VERSION = (
    "dehps-m4-information-theory-metric-kernel-manifest.v1"
)
METRIC_INPUT_SCHEMA_VERSION = "dehps-m4-information-theory-metric-input.v1"
METRIC_ARTIFACT_SCHEMA_VERSION = "dehps-m4-information-theory-metric-artifact.v1"
NUMBER_EVENT_SCHEMA_VERSION = "dehps-m4-number-event-metric.v1"
ISSUE_SCHEMA_VERSION = "dehps-m4-issue-metric.v1"
AGGREGATE_SCHEMA_VERSION = "dehps-m4-aggregate-metric.v1"


@dataclass(frozen=True)
class UnitContract:
    internal_log_unit: str = "nats"
    primary_reporting_unit: str = "bits_per_issue"
    bits_per_number_event: str = "secondary_only"
    nats_per_issue: str = "secondary_only"
    brier_per_issue: str = "secondary_only"
    practical_null_compatible_unit: str = "bits_per_issue"

    def __post_init__(self) -> None:
        if (
            self.internal_log_unit != "nats"
            or self.primary_reporting_unit != "bits_per_issue"
            or self.practical_null_compatible_unit != "bits_per_issue"
        ):
            raise MetricKernelError("unit_mismatch", "frozen unit contract changed")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def require_practical_null_compatible(self, unit: str) -> None:
        if unit != self.practical_null_compatible_unit:
            raise MetricKernelError(
                "unit_mismatch",
                f"{unit} cannot be compared with a bits_per_issue practical-null",
            )


@dataclass(frozen=True)
class ClipDiagnostics:
    raw_min_probability: float
    raw_max_probability: float
    clipped_min_probability: float
    clipped_max_probability: float
    clip_count_low: int
    clip_count_high: int
    clip_fraction: float
    epsilon: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NumberEventMetric:
    issue_id: str
    cluster_id: str
    red_number: int
    target: int
    baseline_raw_probability: float
    baseline_clipped_probability: float
    probe_raw_probability: float
    probe_clipped_probability: float
    baseline_log_loss_nats_per_number_event: float
    baseline_log_loss_bits_per_number_event: float
    probe_log_loss_nats_per_number_event: float
    probe_log_loss_bits_per_number_event: float
    baseline_brier_per_number_event: float
    probe_brier_per_number_event: float

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": NUMBER_EVENT_SCHEMA_VERSION, **asdict(self)}


@dataclass(frozen=True)
class IssueMetric:
    issue_id: str
    cluster_id: str
    baseline_identity: str
    probability_epsilon: float
    baseline_clip_diagnostics: ClipDiagnostics
    probe_clip_diagnostics: ClipDiagnostics
    number_events: tuple[NumberEventMetric, ...]
    baseline_log_loss_nats_per_issue: float
    baseline_log_loss_nats_per_number_event: float
    baseline_log_loss_bits_per_issue: float
    baseline_log_loss_bits_per_number_event: float
    probe_log_loss_nats_per_issue: float
    probe_log_loss_nats_per_number_event: float
    probe_log_loss_bits_per_issue: float
    probe_log_loss_bits_per_number_event: float
    observed_log_loss_gain_nats_per_issue: float
    observed_log_loss_gain_bits_per_issue: float
    gain_direction: str
    eligible_for_pe1: bool
    eligible_for_final_pe2: bool
    baseline_brier_sum_per_issue: float
    baseline_brier_mean_per_number_event: float
    probe_brier_sum_per_issue: float
    probe_brier_mean_per_number_event: float
    brier_gain_per_issue: float
    mean_predicted_probability: float
    predicted_red_count: float
    actual_red_count: int
    red_count_error: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = ISSUE_SCHEMA_VERSION
        payload["baseline_clip_diagnostics"] = self.baseline_clip_diagnostics.to_dict()
        payload["probe_clip_diagnostics"] = self.probe_clip_diagnostics.to_dict()
        payload["number_events"] = [item.to_dict() for item in self.number_events]
        return payload


@dataclass(frozen=True)
class AggregateMetric:
    issue_ids_in_sequence: tuple[str, ...]
    issue_count: int
    sample_size_for_inference: int
    cumulative_baseline_log_loss_bits: float
    cumulative_probe_log_loss_bits: float
    cumulative_observed_log_loss_gain_bits: float
    mean_observed_log_loss_gain_bits_per_issue: float
    median_observed_log_loss_gain_bits_per_issue: float
    mean_brier_gain_per_issue: float
    mean_predicted_probability: float
    observed_positive_rate: float
    calibration_in_the_large: float
    mean_predicted_red_count: float
    mean_absolute_red_count_error: float
    sample_std_gain_bits_across_issues: float
    sample_std_role: str
    uncertainty_status: str
    iid_confidence_interval: None = None

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": AGGREGATE_SCHEMA_VERSION, **asdict(self)}


@dataclass(frozen=True)
class MetricKernelManifest:
    payload: Mapping[str, Any]
    artifact_digest: str
    probability_epsilon: float
    unit_contract: UnitContract

    @property
    def baseline_identity(self) -> str:
        return str(self.payload["baseline"]["identity"])

    @property
    def metric_kernel_version(self) -> str:
        return str(self.payload["metric_kernel_version"])

    def deterministic_task_contract(self) -> None:
        if self.payload.get("seed_policy") != "none":
            raise MetricKernelError(
                "randomness_contract_violation",
                "metric kernel must declare seed_policy=none",
            )
        if isinstance(self.payload.get("seed_policy"), Mapping):
            SeedPolicy(seeds=tuple(self.payload["seed_policy"].get("seeds", ())))
