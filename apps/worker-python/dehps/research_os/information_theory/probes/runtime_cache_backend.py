from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from scipy import sparse
from sklearn.tree import DecisionTreeClassifier

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.walk_forward.contracts import (
    ProbeState,
    TrainFeatureView,
    TrainingDatasetView,
)

from .convergence import CONVERGED
from .empirical_baseline import PreparedEmpiricalBaseline

if TYPE_CHECKING:
    from dehps.research_os.information_theory.measurement_validation.feature_cache import (
        StrictPriorFeatureCache,
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
    """Fold-local reuse of immutable preprocessing inputs."""

    feature_cache: StrictPriorFeatureCache | None = None
    outer_train_view: TrainFeatureView | None = None
    _values: dict[str, np.ndarray] = field(default_factory=dict)
    _targets: dict[str, np.ndarray] = field(default_factory=dict)
    _preprocessors: dict[str, FittedPreprocessor] = field(default_factory=dict)
    _transformed: dict[tuple[str, str], np.ndarray] = field(default_factory=dict)
    _tree_inputs: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = field(
        default_factory=dict
    )

    def _persistent_prefix_key(
        self,
        view: TrainFeatureView,
    ) -> tuple[object, ...] | None:
        issue_ids = view.issue_ids
        if (
            self.feature_cache is None
            or not issue_ids
            or issue_ids[-1] - issue_ids[0] + 1 != len(issue_ids)
        ):
            return None
        return (
            issue_ids[0],
            issue_ids[-1],
            len(issue_ids),
            view.feature_manifest_digest,
        )

    def values(self, view: TrainFeatureView) -> np.ndarray:
        cached = self._values.get(view.feature_view_digest)
        if cached is None:
            cached = (
                self.feature_cache.runtime_values(view.issue_ids)
                if self.feature_cache is not None
                else np.asarray(view.values, dtype=np.float64)
            )
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
            cached = (
                self.feature_cache.runtime_targets(view.issue_ids)
                if self.feature_cache is not None
                else np.asarray(view.targets, dtype=np.int8)
            )
            self._targets[view.feature_view_digest] = cached
        return cached

    def contiguous_subview(
        self,
        parent: TrainFeatureView,
        issue_ids: tuple[int, ...],
    ) -> TrainFeatureView:
        if (
            self.feature_cache is None
            or not issue_ids
            or issue_ids != tuple(range(issue_ids[0], issue_ids[-1] + 1))
            or issue_ids[0] < parent.issue_ids[0]
            or issue_ids[-1] > parent.issue_ids[-1]
        ):
            raise WalkForwardError(
                "target_access_boundary_violation",
                "runtime subview must be a contiguous subset of the outer training view",
            )
        digest = canonical_digest(
            {
                "parent_feature_view_digest": parent.feature_view_digest,
                "issue_start": issue_ids[0],
                "issue_end": issue_ids[-1],
                "scope": "internal_exact_runtime_subview",
            },
            domain="dehps.m4-p2.internal-exact-runtime-subview.v1",
        )
        return TrainFeatureView(
            issue_ids=issue_ids,
            red_numbers=(),
            feature_names=parent.feature_names,
            values=(),
            targets=(),
            available_through_by_issue=(),
            construction_start_issue=parent.construction_start_issue,
            construction_end_issue=issue_ids[-1] - 1,
            feature_manifest_digest=parent.feature_manifest_digest,
            feature_view_digest=digest,
        )

    def build_train_feature_view(
        self,
        dataset: TrainingDatasetView,
        issue_ids: tuple[int, ...],
    ) -> TrainFeatureView:
        del dataset
        parent = self.outer_train_view
        if parent is None:
            raise WalkForwardError(
                "target_access_boundary_violation",
                "runtime subview requires the current outer training view",
            )
        if issue_ids == parent.issue_ids:
            return parent
        return self.contiguous_subview(parent, issue_ids)

    def prepare_empirical_baseline(
        self,
        view: TrainFeatureView,
    ) -> PreparedEmpiricalBaseline:
        issue_ids = view.issue_ids
        counts_array = self.targets(view).reshape(len(issue_ids), 33).sum(axis=0)
        counts = [int(value) for value in counts_array]
        denominator = len(issue_ids) + 1.0
        probabilities = tuple((count + 0.5) / denominator for count in counts)
        model_digest = canonical_digest(
            {
                "smoothing": "beta_binomial_jeffreys_alpha_0_5_beta_0_5",
                "counts": counts,
                "training_issue_count": len(issue_ids),
                "probabilities": list(probabilities),
            },
            domain="dehps.m4.probe.empirical-baseline.v1",
        )
        state = ProbeState(
            probe_id="EMPIRICAL_BASELINE",
            probe_type="expanding_empirical_baseline",
            training_start_issue=min(issue_ids),
            training_end_issue=max(issue_ids),
            training_issue_count=len(issue_ids),
            training_row_count=len(issue_ids) * 33,
            feature_manifest_digest=view.feature_manifest_digest,
            preprocessing_state_digest="none",
            hyperparameter_selection_digest="none",
            model_parameters_digest=model_digest,
            convergence_status=CONVERGED,
            hyperparameters={"smoothing": "beta_binomial_jeffreys_alpha_0_5_beta_0_5"},
            state_digest=canonical_digest(
                {
                    "probe_id": "EMPIRICAL_BASELINE",
                    "training_start_issue": min(issue_ids),
                    "training_end_issue": max(issue_ids),
                    "model_parameters_digest": model_digest,
                    "feature_manifest_digest": view.feature_manifest_digest,
                },
                domain="dehps.m4.probe-state.v1",
            ),
            seed_policy={"mode": "none"},
        )
        return PreparedEmpiricalBaseline(state=state, probabilities=probabilities)

    def fitted(self, view: TrainFeatureView) -> FittedPreprocessor:
        cached = self._preprocessors.get(view.feature_view_digest)
        if cached is None:
            persistent_key = self._persistent_prefix_key(view)
            persistent = (
                None
                if persistent_key is None or self.feature_cache is None
                else self.feature_cache.runtime_acceleration_get(
                    "fitted_preprocessor",
                    persistent_key,
                )
            )
            if isinstance(persistent, FittedPreprocessor):
                cached = persistent
            else:
                cached = fit_preprocessor(
                    view,
                    outer_train_end=max(view.issue_ids),
                    prepared_matrix=self.values(view),
                )
                if persistent_key is not None and self.feature_cache is not None:
                    self.feature_cache.runtime_acceleration_put(
                        "fitted_preprocessor",
                        persistent_key,
                        cached,
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

    def fit_exact_sparse_tree(
        self,
        fitted: FittedPreprocessor,
        view: TrainFeatureView,
        *,
        max_depth: int,
        min_samples_leaf: int,
        random_state: int,
    ) -> DecisionTreeClassifier:
        """Fit the frozen tree on sparse raw values and restore exact thresholds.

        A decision tree depends on feature order, not affine location or scale.
        The frozen matrix has 33 structurally sparse interaction columns which
        become dense after centering. Fitting on raw CSC values avoids that
        dense scan. The chosen partitions are then projected back through the
        accepted scaler with sklearn's float32 midpoint rule so the public tree
        identity and prediction boundary remain the standardized ones.
        """
        persistent_prefix = self._persistent_prefix_key(view)
        persistent_key = (
            None
            if persistent_prefix is None
            else (
                *persistent_prefix,
                fitted.state.state_digest,
                max_depth,
                min_samples_leaf,
                random_state,
            )
        )
        persistent = (
            None
            if persistent_key is None or self.feature_cache is None
            else self.feature_cache.runtime_acceleration_get(
                "fitted_sparse_tree",
                persistent_key,
            )
        )
        if isinstance(persistent, DecisionTreeClassifier):
            return persistent

        raw64 = self.values(view)
        raw32 = np.asarray(raw64, dtype=np.float32, order="C")
        tree_targets = np.asarray(
            self.targets(view),
            dtype=np.float64,
            order="C",
        ).reshape(-1, 1)
        raw_csc = sparse.csc_matrix(raw32)
        tree = DecisionTreeClassifier(
            criterion="log_loss",
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            random_state=random_state,
        )
        tree.fit(raw_csc, tree_targets)

        structure = tree.tree_
        raw_thresholds = structure.threshold.copy()
        restored_thresholds = structure.threshold.copy()
        children_left = structure.children_left
        children_right = structure.children_right
        features = structure.feature

        pending = [(0, np.arange(raw32.shape[0], dtype=np.intp))]
        while pending:
            node, indices = pending.pop()
            left_node = int(children_left[node])
            if left_node < 0:
                continue
            feature = int(features[node])
            left_mask = raw32[indices, feature] <= raw_thresholds[node]
            left_indices = indices[left_mask]
            right_indices = indices[~left_mask]
            standardized = raw64[indices, feature].copy()
            standardized -= fitted.scaler.mean_[feature]
            standardized /= fitted.scaler.scale_[feature]
            standardized32 = standardized.astype(np.float32)
            left_max = np.max(standardized32[left_mask])
            right_min = np.min(standardized32[~left_mask])
            if not left_max < right_min:
                raise WalkForwardError(
                    "invalid_feature_matrix",
                    "sparse tree split is not affine-order compatible",
                )
            restored_thresholds[node] = (
                float(left_max) / 2.0 + float(right_min) / 2.0
            )
            pending.append((int(children_right[node]), right_indices))
            pending.append((left_node, left_indices))

        structure.threshold[:] = restored_thresholds
        if persistent_key is not None and self.feature_cache is not None:
            self.feature_cache.runtime_acceleration_put(
                "fitted_sparse_tree",
                persistent_key,
                tree,
                max_entries=8,
            )
        return tree
