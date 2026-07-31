from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from dehps.research_os.information_theory.walk_forward.contracts import (
    TrainFeatureView,
)
from dehps.research_os.information_theory.walk_forward.errors import (
    WalkForwardError,
)
from dehps.research_os.information_theory.walk_forward.preprocessing import (
    FittedPreprocessor,
    fit_preprocessor,
)


@dataclass
class ExactProbeRuntimeCache:
    """Fold-local reuse of immutable preprocessing inputs.

    The cache changes no numerical operation.  It only prevents the same
    tuple-backed feature view from being converted, scaled, and validated
    again for every frozen hyperparameter candidate and probe.
    """

    _values: dict[str, np.ndarray] = field(default_factory=dict)
    _targets: dict[str, np.ndarray] = field(default_factory=dict)
    _preprocessors: dict[str, FittedPreprocessor] = field(default_factory=dict)
    _transformed: dict[tuple[str, str], np.ndarray] = field(default_factory=dict)
    _tree_inputs: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = field(
        default_factory=dict
    )

    def values(self, view: TrainFeatureView) -> np.ndarray:
        cached = self._values.get(view.feature_view_digest)
        if cached is None:
            cached = np.asarray(view.values, dtype=np.float64)
            if cached.ndim != 2 or not np.isfinite(cached).all():
                raise WalkForwardError(
                    "invalid_feature_matrix",
                    "features must be a finite matrix",
                )
            self._values[view.feature_view_digest] = cached
        return cached

    def targets(self, view: TrainFeatureView) -> np.ndarray:
        cached = self._targets.get(view.feature_view_digest)
        if cached is None:
            cached = np.asarray(view.targets, dtype=np.int8)
            self._targets[view.feature_view_digest] = cached
        return cached

    def fitted(self, view: TrainFeatureView) -> FittedPreprocessor:
        cached = self._preprocessors.get(view.feature_view_digest)
        if cached is None:
            cached = fit_preprocessor(
                view,
                outer_train_end=max(view.issue_ids),
                prepared_matrix=self.values(view),
            )
            self._preprocessors[view.feature_view_digest] = cached
        return cached

    def transformed(
        self,
        fitted: FittedPreprocessor,
        view: TrainFeatureView,
    ) -> np.ndarray:
        key = (fitted.state.state_digest, view.feature_view_digest)
        cached = self._transformed.get(key)
        if cached is None:
            if fitted.state.feature_names != view.feature_names:
                raise WalkForwardError(
                    "feature_manifest_mismatch",
                    "preprocessor feature names changed",
                )
            cached = fitted.scaler.transform(self.values(view))
            if not np.isfinite(cached).all():
                raise WalkForwardError(
                    "invalid_feature_matrix",
                    "transformed feature matrix is non-finite",
                )
            self._transformed[key] = cached
        return cached

    def tree_inputs(
        self,
        fitted: FittedPreprocessor,
        view: TrainFeatureView,
    ) -> tuple[np.ndarray, np.ndarray]:
        key = (fitted.state.state_digest, view.feature_view_digest)
        cached = self._tree_inputs.get(key)
        if cached is None:
            cached = (
                np.asarray(
                    self.transformed(fitted, view),
                    dtype=np.float32,
                    order="C",
                ),
                np.asarray(
                    self.targets(view),
                    dtype=np.float64,
                    order="C",
                ).reshape(-1, 1),
            )
            self._tree_inputs[key] = cached
        return cached
