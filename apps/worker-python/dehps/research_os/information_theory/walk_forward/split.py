from __future__ import annotations

from dehps.contracts import canonical_digest

from .contracts import (
    FROZEN_METRIC_KERNEL_DIGEST,
    FROZEN_PREREGISTRATION_DIGEST,
    FoldIdentity,
    OuterFold,
    SyntheticDataset,
)
from .errors import WalkForwardError


def expanding_outer_folds(dataset: SyntheticDataset) -> tuple[OuterFold, ...]:
    minimum = dataset.minimum_training_length
    if dataset.issue_count <= minimum:
        raise WalkForwardError(
            "insufficient_training_history",
            f"need more than {minimum} issues for one outer prediction",
        )
    folds = tuple(
        OuterFold(tuple(range(1, test_issue)), test_issue)
        for test_issue in range(minimum + 1, dataset.issue_count + 1)
    )
    if len(folds) != dataset.outer_evaluation_length:
        raise WalkForwardError(
            "outer_scale_contract_mismatch",
            "outer fold count does not match the synthetic scale contract",
        )
    if len({fold.test_issue for fold in folds}) != len(folds):
        raise WalkForwardError("duplicate_test_issue", "outer test issue repeated")
    return folds


def validate_outer_fold(
    fold: OuterFold,
    *,
    minimum_training_issues: int,
    dataset_issue_count: int,
) -> None:
    if len(fold.train_issues) < minimum_training_issues:
        raise WalkForwardError(
            "insufficient_training_history", "minimum training length not met"
        )
    if fold.test_issue > dataset_issue_count:
        raise WalkForwardError("missing_issue_identity", "test issue is outside dataset")
    if set(fold.train_issues).intersection({fold.test_issue}):
        raise WalkForwardError(
            "outer_train_test_overlap", "train and test issues overlap"
        )
    if fold.train_issues[-1] >= fold.test_issue:
        raise WalkForwardError(
            "non_chronological_outer_split", "train_end must be before test issue"
        )


def build_fold_identity(
    *,
    dataset_digest: str,
    fold: OuterFold,
    feature_view_digest: str,
    preprocessing_manifest_digest: str,
    probe_manifest_digest: str,
) -> FoldIdentity:
    identity = {
        "dataset_digest": dataset_digest,
        "train_start_issue": fold.train_issues[0],
        "train_end_issue": fold.train_issues[-1],
        "test_issue": fold.test_issue,
        "feature_view_digest": feature_view_digest,
        "preprocessing_manifest_digest": preprocessing_manifest_digest,
        "probe_manifest_digest": probe_manifest_digest,
        "metric_kernel_digest": FROZEN_METRIC_KERNEL_DIGEST,
        "preregistration_digest": FROZEN_PREREGISTRATION_DIGEST,
    }
    fold_digest = canonical_digest(identity, domain="dehps.m4.walk-forward.fold.v1")
    return FoldIdentity(
        fold_id=f"WF-{fold.test_issue:07d}-{fold_digest[:12]}",
        fold_digest=fold_digest,
        dataset_digest=dataset_digest,
        train_start_issue=fold.train_issues[0],
        train_end_issue=fold.train_issues[-1],
        test_issue=fold.test_issue,
        feature_view_digest=feature_view_digest,
        preprocessing_manifest_digest=preprocessing_manifest_digest,
        probe_manifest_digest=probe_manifest_digest,
        metric_kernel_digest=FROZEN_METRIC_KERNEL_DIGEST,
        preregistration_digest=FROZEN_PREREGISTRATION_DIGEST,
    )
