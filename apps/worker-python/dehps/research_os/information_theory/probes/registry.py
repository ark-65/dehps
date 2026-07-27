from __future__ import annotations

from typing import Any, Mapping

from dehps.research_os.information_theory.walk_forward.contracts import (
    TrainingDatasetView,
    TrainFeatureView,
)
from dehps.research_os.information_theory.walk_forward.errors import WalkForwardError

from .contracts import PreparedProbe, TrainViewBuilder
from .empirical_baseline import prepare_empirical_baseline
from .logistic_regression import prepare_logistic_probe
from .naive_bayes import prepare_naive_bayes_probe
from .shallow_calibrated_tree import prepare_shallow_calibrated_tree
from .theoretical_baseline import prepare_theoretical_baseline


FORMAL_PROBE_REGISTRY = (
    "THEORETICAL_BASELINE",
    "EMPIRICAL_BASELINE",
    "REGULARIZED_LOGISTIC_REGRESSION",
    "NAIVE_BAYES",
    "SHALLOW_CALIBRATED_TREE",
)


def prepare_probe(
    *,
    probe_id: str,
    dataset: TrainingDatasetView,
    train_view: TrainFeatureView,
    probe_config: Mapping[str, Any],
    outer_test_issue: int,
    train_view_builder: TrainViewBuilder | None = None,
) -> PreparedProbe:
    if probe_id not in FORMAL_PROBE_REGISTRY:
        raise WalkForwardError(
            "unknown_probe", "canaries and post-result probes are not registrable"
        )
    if probe_id == "THEORETICAL_BASELINE":
        return prepare_theoretical_baseline(
            feature_manifest_digest=train_view.feature_manifest_digest
        )
    if probe_id == "EMPIRICAL_BASELINE":
        return prepare_empirical_baseline(dataset, train_view)
    if probe_id == "REGULARIZED_LOGISTIC_REGRESSION":
        return prepare_logistic_probe(
            dataset,
            train_view,
            config=probe_config,
            outer_test_issue=outer_test_issue,
            train_view_builder=train_view_builder,
        )
    if probe_id == "NAIVE_BAYES":
        return prepare_naive_bayes_probe(
            dataset,
            train_view,
            config=probe_config,
            outer_test_issue=outer_test_issue,
            train_view_builder=train_view_builder,
        )
    return prepare_shallow_calibrated_tree(
        dataset,
        train_view,
        config=probe_config,
        outer_test_issue=outer_test_issue,
        train_view_builder=train_view_builder,
    )
