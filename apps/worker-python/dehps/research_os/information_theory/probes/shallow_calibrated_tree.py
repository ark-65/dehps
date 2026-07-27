from __future__ import annotations

from dataclasses import dataclass
from math import ceil, fsum
from typing import Any, Mapping

import numpy as np
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.tree import DecisionTreeClassifier

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.metrics import (
    probe_log_loss_bits_per_issue_batch,
)
from dehps.research_os.information_theory.walk_forward.contracts import (
    BlindTestFeatureView,
    ProbeState,
    TrainingDatasetView,
    TrainFeatureView,
)
from dehps.research_os.information_theory.walk_forward.errors import WalkForwardError
from dehps.research_os.information_theory.walk_forward.feature_view import (
    build_train_feature_view,
)
from dehps.research_os.information_theory.walk_forward.inner_validation import (
    expanding_inner_folds,
    select_inner_candidate,
)
from dehps.research_os.information_theory.walk_forward.preprocessing import (
    FittedPreprocessor,
    fit_preprocessor,
    transform_blind,
    transform_train,
)

from .contracts import TrainViewBuilder
from .convergence import CONVERGED, INSUFFICIENT_CLASS_VARIATION, INVALID_FEATURE_MATRIX


MINIMUM_CALIBRATION_ISSUES = 120


@dataclass(frozen=True)
class PreparedShallowCalibratedTree:
    state: ProbeState
    model: CalibratedClassifierCV
    preprocessor: FittedPreprocessor

    def predict(self, view: BlindTestFeatureView) -> tuple[float, ...]:
        probabilities = self.model.predict_proba(
            transform_blind(self.preprocessor, view)
        )[:, 1]
        if probabilities.shape != (33,) or not np.isfinite(probabilities).all():
            raise WalkForwardError(
                "invalid_probe_probability",
                "calibrated tree output must be 33 finite values",
            )
        return tuple(float(value) for value in probabilities)


def _candidate_id(max_depth: int, min_samples_leaf: int) -> str:
    return f"TREE_D{max_depth}_LEAF{min_samples_leaf}_PLATT"


def _split_model_calibration(
    issue_ids: tuple[int, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    calibration_count = max(
        MINIMUM_CALIBRATION_ISSUES,
        ceil(0.2 * len(issue_ids)),
    )
    if calibration_count >= len(issue_ids):
        raise WalkForwardError(
            "insufficient_training_history",
            "tree calibration split leaves no model-training issues",
        )
    return issue_ids[:-calibration_count], issue_ids[-calibration_count:]


def _fit_calibrated(
    dataset: TrainingDatasetView,
    *,
    issue_ids: tuple[int, ...],
    max_depth: int,
    min_samples_leaf: int,
    train_view_builder: TrainViewBuilder | None = None,
    fitted_by_view: dict[str, FittedPreprocessor] | None = None,
) -> tuple[CalibratedClassifierCV, FittedPreprocessor, dict[str, Any]]:
    model_issues, calibration_issues = _split_model_calibration(issue_ids)
    build_view = train_view_builder or build_train_feature_view
    model_view = build_view(dataset, model_issues)
    calibration_view = build_view(dataset, calibration_issues)
    if fitted_by_view is None:
        fitted_by_view = {}
    fitted = fitted_by_view.get(model_view.feature_view_digest)
    if fitted is None:
        fitted = fit_preprocessor(
            model_view,
            outer_train_end=max(model_issues),
        )
        fitted_by_view[model_view.feature_view_digest] = fitted
    matrix = transform_train(fitted, model_view)
    targets = np.asarray(model_view.targets, dtype=np.int8)
    calibration_matrix = fitted.scaler.transform(
        np.asarray(calibration_view.values, dtype=np.float64)
    )
    calibration_targets = np.asarray(calibration_view.targets, dtype=np.int8)
    if (
        matrix.ndim != 2
        or not np.isfinite(matrix).all()
        or not np.isfinite(calibration_matrix).all()
    ):
        raise WalkForwardError(INVALID_FEATURE_MATRIX, "invalid tree feature matrix")
    if (
        set(np.unique(targets)) != {0, 1}
        or set(np.unique(calibration_targets)) != {0, 1}
    ):
        raise WalkForwardError(
            INSUFFICIENT_CLASS_VARIATION,
            "tree fit and calibration targets require both classes",
        )
    tree = DecisionTreeClassifier(
        criterion="log_loss",
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=dataset.replicate_seed,
    )
    tree.fit(matrix, targets)
    calibrated = CalibratedClassifierCV(
        FrozenEstimator(tree),
        method="sigmoid",
    )
    calibrated.fit(calibration_matrix, calibration_targets)
    split = {
        "model_training_start_issue": min(model_issues),
        "model_training_end_issue": max(model_issues),
        "model_training_issue_count": len(model_issues),
        "calibration_start_issue": min(calibration_issues),
        "calibration_end_issue": max(calibration_issues),
        "calibration_issue_count": len(calibration_issues),
        "calibration_split": "last_20_percent_of_inner_training",
        "minimum_calibration_issues": MINIMUM_CALIBRATION_ISSUES,
    }
    return calibrated, fitted, split


def _tree_payload(model: CalibratedClassifierCV) -> dict[str, Any]:
    calibrated = model.calibrated_classifiers_[0]
    tree = calibrated.estimator.estimator
    calibrator = calibrated.calibrators[0]
    structure = tree.tree_
    return {
        "children_left": structure.children_left.tolist(),
        "children_right": structure.children_right.tolist(),
        "feature": structure.feature.tolist(),
        "threshold": structure.threshold.tolist(),
        "value": structure.value.tolist(),
        "n_node_samples": structure.n_node_samples.tolist(),
        "weighted_n_node_samples": structure.weighted_n_node_samples.tolist(),
        "platt_a": float(calibrator.a_),
        "platt_b": float(calibrator.b_),
    }


def prepare_shallow_calibrated_tree(
    dataset: TrainingDatasetView,
    train_view: TrainFeatureView,
    *,
    config: Mapping[str, Any],
    outer_test_issue: int,
    train_view_builder: TrainViewBuilder | None = None,
) -> PreparedShallowCalibratedTree:
    if not isinstance(dataset, TrainingDatasetView):
        raise WalkForwardError(
            "target_access_boundary_violation",
            "calibrated tree requires a training-only dataset view",
        )
    if (
        config.get("max_depth") != [2, 3]
        or config.get("min_samples_leaf") != [50, 100]
        or config.get("criterion") != ["log_loss"]
        or config.get("calibration") != ["platt"]
        or config.get("calibration_split") != "last_20_percent_of_inner_training"
        or config.get("minimum_calibration_issues") != 120
    ):
        raise WalkForwardError(
            "missing_probe_hyperparameter_contract",
            "shallow calibrated tree candidates changed",
        )
    candidates = [
        (int(depth), int(leaf))
        for depth in config["max_depth"]
        for leaf in config["min_samples_leaf"]
    ]
    inner_folds = expanding_inner_folds(
        train_view.issue_ids,
        outer_test_issue=outer_test_issue,
    )
    scores_by_candidate: dict[str, tuple[float, ...]] = {}
    fitted_by_view: dict[str, FittedPreprocessor] = {}
    for depth, leaf in candidates:
        candidate_id = _candidate_id(depth, leaf)
        fold_scores: list[float] = []
        for inner in inner_folds:
            model, fitted, _split = _fit_calibrated(
                dataset,
                issue_ids=inner.train_issues,
                max_depth=depth,
                min_samples_leaf=leaf,
                train_view_builder=train_view_builder,
                fitted_by_view=fitted_by_view,
            )
            build_view = train_view_builder or build_train_feature_view
            validation = build_view(
                dataset,
                inner.validation_issues,
            )
            predictions = model.predict_proba(
                fitted.scaler.transform(
                    np.asarray(validation.values, dtype=np.float64)
                )
            )[:, 1]
            losses = probe_log_loss_bits_per_issue_batch(
                target_vectors=tuple(
                    dataset.issue(issue_id).target_vector
                    for issue_id in inner.validation_issues
                ),
                probe_probability_vectors=tuple(
                    predictions[position * 33 : (position + 1) * 33]
                    for position in range(len(inner.validation_issues))
                ),
            )
            fold_scores.append(fsum(losses) / len(losses))
        scores_by_candidate[candidate_id] = tuple(fold_scores)
    complexity = {
        _candidate_id(depth, leaf): depth * 1_000_000 - leaf
        for depth, leaf in candidates
    }
    selected, summaries = select_inner_candidate(
        scores_by_candidate,
        complexity_order=complexity,
    )
    selected_depth, selected_leaf = next(
        (depth, leaf)
        for depth, leaf in candidates
        if _candidate_id(depth, leaf) == selected
    )
    selection_payload = {
        "method": "three_fold_expanding_blocked_time_series",
        "selection_metric": "issue_mean_log_loss",
        "candidate_fold_scores": {
            key: list(value) for key, value in sorted(scores_by_candidate.items())
        },
        "candidate_mean_scores": dict(sorted(summaries.items())),
        "selected_config_id": selected,
        "outer_test_metrics_used": False,
    }
    selection_digest = canonical_digest(
        selection_payload,
        domain="dehps.m4.probe.inner-selection.v1",
    )
    model, fitted, split = _fit_calibrated(
        dataset,
        issue_ids=train_view.issue_ids,
        max_depth=selected_depth,
        min_samples_leaf=selected_leaf,
        train_view_builder=train_view_builder,
        fitted_by_view=fitted_by_view,
    )
    model_payload = {
        **_tree_payload(model),
        **split,
        "implementation": f"scikit-learn=={sklearn.__version__}",
        "selected_config_id": selected,
        "max_depth": selected_depth,
        "min_samples_leaf": selected_leaf,
        "criterion": "log_loss",
        "calibration": "platt",
    }
    model_digest = canonical_digest(
        model_payload,
        domain="dehps.m4.probe.shallow-calibrated-tree-parameters.v1",
    )
    state_identity = {
        "probe_id": "SHALLOW_CALIBRATED_TREE",
        "training_start_issue": min(train_view.issue_ids),
        "training_end_issue": max(train_view.issue_ids),
        "feature_manifest_digest": train_view.feature_manifest_digest,
        "preprocessing_state_digest": fitted.state.state_digest,
        "hyperparameter_selection_digest": selection_digest,
        "model_parameters_digest": model_digest,
        "seed": dataset.replicate_seed,
    }
    state = ProbeState(
        probe_id="SHALLOW_CALIBRATED_TREE",
        probe_type="shallow_calibrated_decision_tree",
        training_start_issue=min(train_view.issue_ids),
        training_end_issue=max(train_view.issue_ids),
        training_issue_count=len(train_view.issue_ids),
        training_row_count=len(train_view.targets),
        feature_manifest_digest=train_view.feature_manifest_digest,
        preprocessing_state_digest=fitted.state.state_digest,
        hyperparameter_selection_digest=selection_digest,
        model_parameters_digest=model_digest,
        convergence_status=CONVERGED,
        hyperparameters={
            "max_depth": selected_depth,
            "min_samples_leaf": selected_leaf,
            "criterion": "log_loss",
            "calibration": "platt",
            **split,
            "implementation": f"scikit-learn=={sklearn.__version__}",
            "selected_config_id": selected,
            "outer_test_metrics_used": False,
        },
        state_digest=canonical_digest(
            state_identity,
            domain="dehps.m4.probe-state.v1",
        ),
        seed_policy={
            "mode": "dataset_replicate_seed",
            "seed": dataset.replicate_seed,
        },
    )
    return PreparedShallowCalibratedTree(
        state=state,
        model=model,
        preprocessor=fitted,
    )
