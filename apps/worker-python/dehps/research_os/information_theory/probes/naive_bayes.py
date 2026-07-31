from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import fsum
from typing import Any

import numpy as np
import sklearn
from sklearn.naive_bayes import BernoulliNB

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.metrics import (
    probe_log_loss_bits_per_issue_batch_exact_native,
)
from dehps.research_os.information_theory.walk_forward.contracts import (
    BlindTestFeatureView,
    ProbeState,
    TrainFeatureView,
    TrainingDatasetView,
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
from .runtime_cache import ExactProbeRuntimeCache


@dataclass(frozen=True)
class PreparedNaiveBayesProbe:
    state: ProbeState
    model: BernoulliNB
    preprocessor: FittedPreprocessor

    def predict(self, view: BlindTestFeatureView) -> tuple[float, ...]:
        probabilities = self.model.predict_proba(
            transform_blind(self.preprocessor, view)
        )[:, 1]
        if probabilities.shape != (33,) or not np.isfinite(probabilities).all():
            raise WalkForwardError(
                "invalid_probe_probability",
                "naive Bayes output must be 33 finite values",
            )
        return tuple(float(value) for value in probabilities)


def _fit(model: BernoulliNB, matrix: np.ndarray, targets: np.ndarray) -> None:
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise WalkForwardError(INVALID_FEATURE_MATRIX, "invalid naive Bayes matrix")
    if set(np.unique(targets)) != {0, 1}:
        raise WalkForwardError(
            INSUFFICIENT_CLASS_VARIATION,
            "naive Bayes targets require both classes",
        )
    model.fit(matrix, targets)


def _candidate_id(alpha: float) -> str:
    return f"BERNOULLI_NB_ALPHA_{alpha:g}"


def prepare_naive_bayes_probe(
    dataset: TrainingDatasetView,
    train_view: TrainFeatureView,
    *,
    config: Mapping[str, Any],
    outer_test_issue: int,
    train_view_builder: TrainViewBuilder | None = None,
    runtime_cache: ExactProbeRuntimeCache | None = None,
) -> PreparedNaiveBayesProbe:
    if not isinstance(dataset, TrainingDatasetView):
        raise WalkForwardError(
            "target_access_boundary_violation",
            "naive Bayes requires a training-only dataset view",
        )
    if config.get("type") != "bernoulli" or config.get("alpha") != [0.5, 1.0, 2.0]:
        raise WalkForwardError(
            "missing_probe_hyperparameter_contract",
            "naive Bayes candidates changed",
        )
    inner_folds = expanding_inner_folds(
        train_view.issue_ids,
        outer_test_issue=outer_test_issue,
    )
    build_view = train_view_builder or build_train_feature_view
    fitted_by_view: dict[str, FittedPreprocessor] = {}

    def fitted_for(view: TrainFeatureView) -> FittedPreprocessor:
        if runtime_cache is not None:
            return runtime_cache.fitted(view)
        cached = fitted_by_view.get(view.feature_view_digest)
        if cached is None:
            cached = fit_preprocessor(
                view,
                outer_train_end=max(view.issue_ids),
            )
            fitted_by_view[view.feature_view_digest] = cached
        return cached

    def transformed_for(
        fitted: FittedPreprocessor,
        view: TrainFeatureView,
    ) -> np.ndarray:
        if runtime_cache is not None:
            return runtime_cache.transformed(fitted, view)
        return transform_train(fitted, view)

    def targets_for(view: TrainFeatureView) -> np.ndarray:
        if runtime_cache is not None:
            return runtime_cache.targets(view)
        return np.asarray(view.targets, dtype=np.int8)

    scores_by_candidate: dict[str, tuple[float, ...]] = {}
    alpha_by_candidate: dict[str, float] = {}
    for raw_alpha in config["alpha"]:
        alpha = float(raw_alpha)
        candidate_id = _candidate_id(alpha)
        alpha_by_candidate[candidate_id] = alpha
        fold_scores: list[float] = []
        for inner in inner_folds:
            inner_train = build_view(dataset, inner.train_issues)
            inner_validation = build_view(dataset, inner.validation_issues)
            fitted = fitted_for(inner_train)
            model = BernoulliNB(alpha=alpha, binarize=0.0)
            _fit(
                model,
                transformed_for(fitted, inner_train),
                targets_for(inner_train),
            )
            validation_matrix = (
                runtime_cache.transformed(fitted, inner_validation)
                if runtime_cache is not None
                else fitted.scaler.transform(
                    np.asarray(inner_validation.values, dtype=np.float64)
                )
            )
            predictions = model.predict_proba(validation_matrix)[:, 1]
            issue_losses = probe_log_loss_bits_per_issue_batch_exact_native(
                target_vectors=tuple(
                    dataset.issue(issue_id).target_vector
                    for issue_id in inner.validation_issues
                ),
                probe_probability_vectors=tuple(
                    predictions[position * 33 : (position + 1) * 33]
                    for position in range(len(inner.validation_issues))
                ),
            )
            fold_scores.append(fsum(issue_losses) / len(issue_losses))
        scores_by_candidate[candidate_id] = tuple(fold_scores)
    selected, summaries = select_inner_candidate(
        scores_by_candidate,
        complexity_order={
            _candidate_id(0.5): 2,
            _candidate_id(1.0): 1,
            _candidate_id(2.0): 0,
        },
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
    fitted = fitted_for(train_view)
    model = BernoulliNB(alpha=alpha_by_candidate[selected], binarize=0.0)
    _fit(
        model,
        transformed_for(fitted, train_view),
        targets_for(train_view),
    )
    model_payload = {
        "class_count": model.class_count_.tolist(),
        "class_log_prior": model.class_log_prior_.tolist(),
        "feature_count": model.feature_count_.tolist(),
        "feature_log_prob": model.feature_log_prob_.tolist(),
        "implementation": f"scikit-learn=={sklearn.__version__}",
        "selected_config_id": selected,
        "selected_alpha": alpha_by_candidate[selected],
        "binarize": 0.0,
    }
    model_digest = canonical_digest(
        model_payload,
        domain="dehps.m4.probe.naive-bayes-parameters.v1",
    )
    state_identity = {
        "probe_id": "NAIVE_BAYES",
        "training_start_issue": min(train_view.issue_ids),
        "training_end_issue": max(train_view.issue_ids),
        "feature_manifest_digest": train_view.feature_manifest_digest,
        "preprocessing_state_digest": fitted.state.state_digest,
        "hyperparameter_selection_digest": selection_digest,
        "model_parameters_digest": model_digest,
        "seed": dataset.replicate_seed,
    }
    state = ProbeState(
        probe_id="NAIVE_BAYES",
        probe_type="bernoulli_naive_bayes",
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
            "type": "bernoulli",
            "alpha": alpha_by_candidate[selected],
            "binarize": 0.0,
            "implementation": f"scikit-learn=={sklearn.__version__}",
            "selected_config_id": selected,
            "outer_test_metrics_used": False,
        },
        state_digest=canonical_digest(
            state_identity,
            domain="dehps.m4.probe-state.v1",
        ),
        seed_policy={"mode": "none"},
    )
    return PreparedNaiveBayesProbe(
        state=state,
        model=model,
        preprocessor=fitted,
    )
