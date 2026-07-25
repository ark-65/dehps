from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.preprocessing import StandardScaler

from dehps.contracts import canonical_digest

from .contracts import (
    BlindTestFeatureView,
    PreprocessingState,
    TrainFeatureView,
)
from .errors import WalkForwardError
from .leakage import guard_preprocessor_boundary


@dataclass(frozen=True)
class FittedPreprocessor:
    state: PreprocessingState
    scaler: StandardScaler


def fit_preprocessor(
    view: TrainFeatureView,
    *,
    outer_train_end: int,
    claimed_fit_end_issue: int | None = None,
) -> FittedPreprocessor:
    if not view.issue_ids:
        raise WalkForwardError("invalid_feature_matrix", "train view is empty")
    matrix = np.asarray(view.values, dtype=np.float64)
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise WalkForwardError(
            "invalid_feature_matrix", "features must be a finite matrix"
        )
    scaler = StandardScaler().fit(matrix)
    fit_end = claimed_fit_end_issue or max(view.issue_ids)
    identity = {
        "fit_start_issue": min(view.issue_ids),
        "fit_end_issue": fit_end,
        "feature_names": list(view.feature_names),
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "method": "sklearn_standard_scaler_fold_local",
    }
    state = PreprocessingState(
        fit_start_issue=min(view.issue_ids),
        fit_end_issue=fit_end,
        feature_names=view.feature_names,
        mean=tuple(float(value) for value in scaler.mean_),
        scale=tuple(float(value) for value in scaler.scale_),
        state_digest=canonical_digest(
            identity, domain="dehps.m4.walk-forward.preprocessing.v1"
        ),
    )
    guard_preprocessor_boundary(state, outer_train_end=outer_train_end)
    return FittedPreprocessor(state=state, scaler=scaler)


def transform_train(
    fitted: FittedPreprocessor,
    view: TrainFeatureView,
) -> np.ndarray:
    if fitted.state.feature_names != view.feature_names:
        raise WalkForwardError(
            "feature_manifest_mismatch", "preprocessor feature names changed"
        )
    matrix = fitted.scaler.transform(np.asarray(view.values, dtype=np.float64))
    if not np.isfinite(matrix).all():
        raise WalkForwardError(
            "invalid_feature_matrix", "transformed train matrix is non-finite"
        )
    return matrix

def transform_blind(
    fitted: FittedPreprocessor,
    view: BlindTestFeatureView,
) -> np.ndarray:
    if fitted.state.feature_names != view.feature_names:
        raise WalkForwardError(
            "feature_manifest_mismatch", "blind feature names changed"
        )
    matrix = fitted.scaler.transform(np.asarray(view.values, dtype=np.float64))
    if matrix.shape[0] != 33 or not np.isfinite(matrix).all():
        raise WalkForwardError(
            "invalid_feature_matrix", "blind matrix must contain 33 finite rows"
        )
    return matrix
