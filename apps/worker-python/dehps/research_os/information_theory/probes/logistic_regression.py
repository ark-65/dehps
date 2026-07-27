from __future__ import annotations

import warnings
from dataclasses import dataclass
from math import fsum
from typing import Any, Mapping

import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

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
from .convergence import (
    CONVERGED,
    FAILED_CONVERGENCE,
    INSUFFICIENT_CLASS_VARIATION,
    INVALID_FEATURE_MATRIX,
)


@dataclass(frozen=True)
class PreparedLogisticProbe:
    state: ProbeState
    model: LogisticRegression
    preprocessor: FittedPreprocessor

    def predict(self, view: BlindTestFeatureView) -> tuple[float, ...]:
        matrix = transform_blind(self.preprocessor, view)
        probabilities = self.model.predict_proba(matrix)[:, 1]
        if probabilities.shape != (33,) or not np.isfinite(probabilities).all():
            raise WalkForwardError(
                "invalid_probe_probability", "logistic output must be 33 finite values"
            )
        if np.any(probabilities < 0) or np.any(probabilities > 1):
            raise WalkForwardError(
                "invalid_probe_probability", "probability outside [0,1]"
            )
        return tuple(float(value) for value in probabilities)


def _new_model(config: Mapping[str, Any], *, c_value: float, seed: int) -> LogisticRegression:
    return LogisticRegression(
        penalty="l2",
        C=c_value,
        class_weight=None,
        solver=str(config["solver"]),
        max_iter=int(config["max_iter"]),
        tol=float(config["tol"]),
        random_state=seed,
    )


def _fit_model(
    model: LogisticRegression,
    matrix: np.ndarray,
    targets: np.ndarray,
) -> None:
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise WalkForwardError(INVALID_FEATURE_MATRIX, "invalid logistic feature matrix")
    if set(np.unique(targets)) != {0, 1}:
        raise WalkForwardError(
            INSUFFICIENT_CLASS_VARIATION, "logistic targets require both classes"
        )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        try:
            model.fit(matrix, targets)
        except Exception as exc:
            raise WalkForwardError(
                FAILED_CONVERGENCE, f"logistic solver failed: {exc}"
            ) from exc
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        raise WalkForwardError(
            FAILED_CONVERGENCE,
            "frozen convergence policy invalidates the outer prediction",
        )


def _candidate_id(c_value: float) -> str:
    return f"L2_LIBLINEAR_C_{c_value:g}"


def prepare_logistic_probe(
    dataset: TrainingDatasetView,
    train_view: TrainFeatureView,
    *,
    config: Mapping[str, Any],
    outer_test_issue: int,
    train_view_builder: TrainViewBuilder | None = None,
) -> PreparedLogisticProbe:
    if not isinstance(dataset, TrainingDatasetView):
        raise WalkForwardError(
            "target_access_boundary_violation",
            "logistic probe requires a training-only dataset view",
        )
    if config.get("penalty") != ["l2"] or config.get("C") != [0.01, 0.1, 1.0]:
        raise WalkForwardError(
            "missing_probe_hyperparameter_contract",
            "logistic candidates must match frozen preregistration",
        )
    if (
        config.get("class_weight") != [None]
        or config.get("solver") != "liblinear"
        or config.get("max_iter") != 1000
        or config.get("tol") != 0.0001
        or config.get("implementation") != "scikit-learn==1.9.0"
    ):
        raise WalkForwardError(
            "missing_probe_hyperparameter_contract",
            "logistic solver contract changed",
        )
    inner_folds = expanding_inner_folds(
        train_view.issue_ids, outer_test_issue=outer_test_issue
    )
    build_view = train_view_builder or build_train_feature_view
    fitted_by_view: dict[str, FittedPreprocessor] = {}

    def fitted_for(view: TrainFeatureView) -> FittedPreprocessor:
        cached = fitted_by_view.get(view.feature_view_digest)
        if cached is None:
            cached = fit_preprocessor(
                view,
                outer_train_end=max(view.issue_ids),
            )
            fitted_by_view[view.feature_view_digest] = cached
        return cached
    candidate_scores: dict[str, tuple[float, ...]] = {}
    candidate_values: dict[str, float] = {}
    for c_value in config["C"]:
        identifier = _candidate_id(float(c_value))
        candidate_values[identifier] = float(c_value)
        scores: list[float] = []
        for inner in inner_folds:
            inner_train = build_view(dataset, inner.train_issues)
            inner_validation = build_view(
                dataset, inner.validation_issues
            )
            fitted = fitted_for(inner_train)
            model = _new_model(
                config, c_value=float(c_value), seed=dataset.replicate_seed
            )
            _fit_model(
                model,
                transform_train(fitted, inner_train),
                np.asarray(inner_train.targets, dtype=np.int8),
            )
            validation_matrix = fitted.scaler.transform(
                np.asarray(inner_validation.values, dtype=np.float64)
            )
            predictions = model.predict_proba(validation_matrix)[:, 1]
            issue_losses = probe_log_loss_bits_per_issue_batch(
                target_vectors=tuple(
                    dataset.issue(issue_id).target_vector
                    for issue_id in inner.validation_issues
                ),
                probe_probability_vectors=tuple(
                    predictions[position * 33 : (position + 1) * 33]
                    for position in range(len(inner.validation_issues))
                ),
            )
            scores.append(fsum(issue_losses) / len(issue_losses))
        candidate_scores[identifier] = tuple(scores)
    selected_id, summaries = select_inner_candidate(
        candidate_scores,
        complexity_order={
            _candidate_id(0.01): 0,
            _candidate_id(0.1): 1,
            _candidate_id(1.0): 2,
        },
    )
    selection_payload = {
        "method": "three_fold_expanding_blocked_time_series",
        "selection_metric": "issue_mean_log_loss",
        "candidate_fold_scores": {
            key: list(value) for key, value in sorted(candidate_scores.items())
        },
        "candidate_mean_scores": dict(sorted(summaries.items())),
        "selected_config_id": selected_id,
        "outer_test_metrics_used": False,
    }
    selection_digest = canonical_digest(
        selection_payload, domain="dehps.m4.probe.inner-selection.v1"
    )
    fitted = fitted_for(train_view)
    model = _new_model(
        config,
        c_value=candidate_values[selected_id],
        seed=dataset.replicate_seed,
    )
    _fit_model(
        model,
        transform_train(fitted, train_view),
        np.asarray(train_view.targets, dtype=np.int8),
    )
    model_payload = {
        "classes": model.classes_.tolist(),
        "coef": model.coef_.tolist(),
        "intercept": model.intercept_.tolist(),
        "n_iter": model.n_iter_.tolist(),
        "implementation": f"scikit-learn=={sklearn.__version__}",
        "selected_config_id": selected_id,
        "selected_C": candidate_values[selected_id],
    }
    model_digest = canonical_digest(
        model_payload, domain="dehps.m4.probe.logistic-parameters.v1"
    )
    state_payload = {
        "probe_id": "REGULARIZED_LOGISTIC_REGRESSION",
        "training_start_issue": min(train_view.issue_ids),
        "training_end_issue": max(train_view.issue_ids),
        "training_issue_count": len(train_view.issue_ids),
        "training_row_count": len(train_view.targets),
        "feature_manifest_digest": train_view.feature_manifest_digest,
        "preprocessing_state_digest": fitted.state.state_digest,
        "hyperparameter_selection_digest": selection_digest,
        "model_parameters_digest": model_digest,
        "convergence_status": CONVERGED,
        "seed": dataset.replicate_seed,
    }
    state = ProbeState(
        probe_id="REGULARIZED_LOGISTIC_REGRESSION",
        probe_type="regularized_logistic_regression",
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
            "penalty": "l2",
            "C": candidate_values[selected_id],
            "class_weight": None,
            "solver": "liblinear",
            "max_iter": 1000,
            "tol": 0.0001,
            "implementation": f"scikit-learn=={sklearn.__version__}",
            "selected_config_id": selected_id,
            "outer_test_metrics_used": False,
        },
        state_digest=canonical_digest(
            state_payload, domain="dehps.m4.probe-state.v1"
        ),
        seed_policy={
            "mode": "dataset_replicate_seed",
            "seed": dataset.replicate_seed,
        },
    )
    return PreparedLogisticProbe(state=state, model=model, preprocessor=fitted)
