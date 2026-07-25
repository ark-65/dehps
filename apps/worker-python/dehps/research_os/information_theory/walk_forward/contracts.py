from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from dehps.contracts import canonical_digest

from .errors import WalkForwardError


HARNESS_VERSION = "m4-information-theory-walk-forward-harness-v1"
HARNESS_SCHEMA_VERSION = "dehps-m4-information-theory-walk-forward-harness.v1"
FOLD_SCHEMA_VERSION = "dehps-m4-information-theory-walk-forward-fold.v1"
PREDICTION_SCHEMA_VERSION = "dehps-m4-information-theory-prediction-checkpoint.v1"
SETTLEMENT_SCHEMA_VERSION = "dehps-m4-information-theory-fold-settlement.v1"
RUN_SCHEMA_VERSION = "dehps-m4-information-theory-walk-forward-run.v1"

FROZEN_PREREGISTRATION_DIGEST = (
    "6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1"
)
FROZEN_DECISION_POLICY_DIGEST = (
    "824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d"
)
FROZEN_SYNTHETIC_MANIFEST_DIGEST = (
    "8493987cc4414414e33fb5c5ea148be1f42a1d9e57609600c4346fb642cbfa08"
)
FROZEN_METRIC_KERNEL_DIGEST = (
    "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2"
)
THEORETICAL_PROBABILITY = 6 / 33


def digest_payload(payload: Mapping[str, Any], *, domain: str) -> str:
    value = dict(payload)
    value.pop("artifact_digest", None)
    value.pop("fold_digest", None)
    return canonical_digest(value, domain=domain)


@dataclass(frozen=True)
class DatasetIssue:
    issue_index: int
    red_mask: int
    sorted_red_numbers: tuple[int, ...]
    target_vector: tuple[int, ...]


@dataclass(frozen=True)
class SyntheticDataset:
    artifact_digest: str
    scenario_id: str
    scale_id: str
    minimum_training_length: int
    outer_evaluation_length: int
    seed_policy: Mapping[str, Any]
    seed_policy_digest: str
    replicate_seed: int
    issues: tuple[DatasetIssue, ...]
    raw_payload: Mapping[str, Any]

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def issue(self, issue_index: int) -> DatasetIssue:
        if issue_index < 1 or issue_index > len(self.issues):
            raise WalkForwardError("missing_issue_identity", f"unknown issue {issue_index}")
        item = self.issues[issue_index - 1]
        if item.issue_index != issue_index:
            raise WalkForwardError(
                "missing_issue_identity", "dataset issue sequence is not canonical"
            )
        return item


@dataclass(frozen=True)
class TrainingDatasetView:
    source_dataset_digest: str
    scenario_id: str
    scale_id: str
    minimum_training_length: int
    seed_policy: Mapping[str, Any]
    seed_policy_digest: str
    replicate_seed: int
    issues: tuple[DatasetIssue, ...]
    available_through_issue: int

    @property
    def artifact_digest(self) -> str:
        return self.source_dataset_digest

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def issue(self, issue_index: int) -> DatasetIssue:
        if issue_index < 1 or issue_index > self.available_through_issue:
            raise WalkForwardError(
                "target_access_boundary_violation",
                "probe training view cannot access outer test or future issues",
            )
        return self.issues[issue_index - 1]


@dataclass(frozen=True)
class FoldIdentity:
    fold_id: str
    fold_digest: str
    dataset_digest: str
    train_start_issue: int
    train_end_issue: int
    test_issue: int
    feature_view_digest: str
    preprocessing_manifest_digest: str
    probe_manifest_digest: str
    metric_kernel_digest: str
    preregistration_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": FOLD_SCHEMA_VERSION,
            "fold_id": self.fold_id,
            "fold_digest": self.fold_digest,
            "dataset_digest": self.dataset_digest,
            "train_start_issue": self.train_start_issue,
            "train_end_issue": self.train_end_issue,
            "test_issue": self.test_issue,
            "test_horizon": 1,
            "feature_view_digest": self.feature_view_digest,
            "preprocessing_manifest_digest": self.preprocessing_manifest_digest,
            "probe_manifest_digest": self.probe_manifest_digest,
            "metric_kernel_digest": self.metric_kernel_digest,
            "preregistration_digest": self.preregistration_digest,
        }


@dataclass(frozen=True)
class OuterFold:
    train_issues: tuple[int, ...]
    test_issue: int

    def __post_init__(self) -> None:
        if not self.train_issues:
            raise WalkForwardError(
                "insufficient_training_history", "outer train range is empty"
            )
        if tuple(range(self.train_issues[0], self.train_issues[-1] + 1)) != self.train_issues:
            raise WalkForwardError(
                "non_chronological_outer_split", "outer train must be contiguous"
            )
        if self.train_issues[-1] >= self.test_issue:
            raise WalkForwardError(
                "outer_train_test_overlap", "outer train must end before test issue"
            )


@dataclass(frozen=True)
class InnerFold:
    train_issues: tuple[int, ...]
    validation_issues: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.train_issues or not self.validation_issues:
            raise WalkForwardError(
                "non_chronological_inner_validation", "inner folds cannot be empty"
            )
        if max(self.train_issues) >= min(self.validation_issues):
            raise WalkForwardError(
                "non_chronological_inner_validation",
                "inner training must end before validation",
            )


@dataclass(frozen=True)
class TrainFeatureView:
    issue_ids: tuple[int, ...]
    red_numbers: tuple[int, ...]
    feature_names: tuple[str, ...]
    values: tuple[tuple[float, ...], ...]
    targets: tuple[int, ...]
    available_through_by_issue: tuple[tuple[int, int], ...]
    construction_start_issue: int
    construction_end_issue: int
    feature_manifest_digest: str
    feature_view_digest: str


@dataclass(frozen=True)
class BlindTestFeatureView:
    target_issue: int
    red_numbers: tuple[int, ...]
    feature_names: tuple[str, ...]
    values: tuple[tuple[float, ...], ...]
    available_through_issue: int
    construction_start_issue: int
    construction_end_issue: int
    feature_manifest_digest: str
    feature_view_digest: str

    def __post_init__(self) -> None:
        if self.available_through_issue >= self.target_issue:
            raise WalkForwardError(
                "future_feature_leakage",
                "blind features must be available strictly before target issue",
            )
        if len(self.red_numbers) != 33 or self.red_numbers != tuple(range(1, 34)):
            raise WalkForwardError(
                "invalid_number_event_rows", "blind view must contain numbers 1..33"
            )
        if len(self.values) != 33:
            raise WalkForwardError(
                "invalid_number_event_rows", "blind view must contain 33 rows"
            )


@dataclass(frozen=True)
class PreprocessingState:
    fit_start_issue: int
    fit_end_issue: int
    feature_names: tuple[str, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    state_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fit_start_issue": self.fit_start_issue,
            "fit_end_issue": self.fit_end_issue,
            "feature_names": list(self.feature_names),
            "parameters": {"mean": list(self.mean), "scale": list(self.scale)},
            "state_digest": self.state_digest,
        }


@dataclass(frozen=True)
class ProbeState:
    probe_id: str
    probe_type: str
    training_start_issue: int | None
    training_end_issue: int | None
    training_issue_count: int
    training_row_count: int
    feature_manifest_digest: str
    preprocessing_state_digest: str
    hyperparameter_selection_digest: str
    model_parameters_digest: str
    convergence_status: str
    hyperparameters: Mapping[str, Any]
    state_digest: str
    seed_policy: Mapping[str, Any]
    failure: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "probe_type": self.probe_type,
            "training_start_issue": self.training_start_issue,
            "training_end_issue": self.training_end_issue,
            "training_issue_count": self.training_issue_count,
            "training_row_count": self.training_row_count,
            "feature_manifest_digest": self.feature_manifest_digest,
            "preprocessing_state_digest": self.preprocessing_state_digest,
            "hyperparameter_selection_digest": self.hyperparameter_selection_digest,
            "model_parameters_digest": self.model_parameters_digest,
            "convergence_status": self.convergence_status,
            "hyperparameters": dict(self.hyperparameters),
            "state_digest": self.state_digest,
            "seed_policy": dict(self.seed_policy),
            "failure": None if self.failure is None else dict(self.failure),
        }


@dataclass(frozen=True)
class HarnessManifest:
    payload: Mapping[str, Any]
    artifact_digest: str
    minimum_training_issues: int
    smoke_outer_fold_count: int
    created_at: str

    def probe(self, probe_id: str) -> Mapping[str, Any]:
        probes = self.payload["probes"]
        if probe_id not in probes:
            raise WalkForwardError("unknown_probe", f"unknown probe {probe_id}")
        return probes[probe_id]
