from __future__ import annotations

from typing import Iterable

from .contracts import (
    BlindTestFeatureView,
    InnerFold,
    OuterFold,
    PreprocessingState,
    SyntheticDataset,
)
from .errors import WalkForwardError


def guard_train_test_overlap(fold: OuterFold) -> None:
    if set(fold.train_issues).intersection({fold.test_issue}):
        raise WalkForwardError(
            "outer_train_test_overlap", "outer train and test overlap"
        )
    if max(fold.train_issues) >= fold.test_issue:
        raise WalkForwardError(
            "outer_train_test_overlap", "outer training reaches test issue"
        )


def guard_feature_timestamp(view: BlindTestFeatureView) -> None:
    if view.available_through_issue >= view.target_issue:
        raise WalkForwardError(
            "future_feature_leakage", "feature timestamp reaches target"
        )
    if view.construction_end_issue >= view.target_issue:
        raise WalkForwardError(
            "future_feature_leakage", "feature construction reaches target"
        )


def guard_preprocessor_boundary(
    state: PreprocessingState,
    *,
    outer_train_end: int,
) -> None:
    if state.fit_end_issue > outer_train_end:
        raise WalkForwardError(
            "preprocessor_fit_range_violation",
            "preprocessor used issues outside outer training",
        )


def guard_inner_boundaries(
    folds: Iterable[InnerFold],
    *,
    outer_train_end: int,
    outer_test_issue: int,
) -> None:
    for fold in folds:
        if (
            max(fold.train_issues) >= min(fold.validation_issues)
            or max(fold.validation_issues) > outer_train_end
            or outer_test_issue in fold.train_issues
            or outer_test_issue in fold.validation_issues
        ):
            raise WalkForwardError(
                "non_chronological_inner_validation",
                "inner validation escaped outer training history",
            )

def guard_dataset_identity(
    dataset: SyntheticDataset,
    *,
    expected_digest: str,
) -> None:
    if dataset.artifact_digest != expected_digest:
        raise WalkForwardError(
            "dataset_mutation_detected", "dataset digest changed after training"
        )


def guard_number_event_rows(
    *,
    issue_ids: tuple[int, ...],
    red_numbers: tuple[int, ...],
) -> None:
    if len(red_numbers) != len(issue_ids) * 33:
        raise WalkForwardError(
            "invalid_number_event_rows", "each issue requires exactly 33 rows"
        )
    expected = tuple(range(1, 34))
    for offset in range(0, len(red_numbers), 33):
        if red_numbers[offset : offset + 33] != expected:
            raise WalkForwardError(
                "invalid_number_event_rows", "red numbers must be 1..33 once"
            )
