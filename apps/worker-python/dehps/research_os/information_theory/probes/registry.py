from __future__ import annotations

from typing import Any, Mapping

from dehps.research_os.information_theory.walk_forward.contracts import (
    TrainingDatasetView,
    TrainFeatureView,
)
from dehps.research_os.information_theory.walk_forward.errors import WalkForwardError

from .contracts import PreparedProbe
from .empirical_baseline import prepare_empirical_baseline
from .logistic_regression import prepare_logistic_probe
from .theoretical_baseline import prepare_theoretical_baseline


FORMAL_PROBE_REGISTRY = (
    "THEORETICAL_BASELINE",
    "EMPIRICAL_BASELINE",
    "REGULARIZED_LOGISTIC_REGRESSION",
)


def prepare_probe(
    *,
    probe_id: str,
    dataset: TrainingDatasetView,
    train_view: TrainFeatureView,
    probe_config: Mapping[str, Any],
    outer_test_issue: int,
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
    return prepare_logistic_probe(
        dataset,
        train_view,
        config=probe_config,
        outer_test_issue=outer_test_issue,
    )
