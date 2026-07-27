from __future__ import annotations

import json
from functools import cache
from pathlib import Path

import numpy as np

from dehps.research_os.information_theory.synthetic import (
    generate_null_dataset,
    load_synthetic_run_manifest,
)
from dehps.research_os.information_theory.walk_forward import (
    build_blind_test_feature_view,
    build_train_feature_view,
    restrict_to_training_history,
    validate_synthetic_dataset,
)
from dehps.research_os.information_theory.probes import (
    FORMAL_PROBE_REGISTRY,
    prepare_probe,
    prepare_naive_bayes_probe,
    prepare_shallow_calibrated_tree,
)
from dehps.research_os.information_theory.measurement_validation import (
    StrictPriorFeatureCache,
)


ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC_MANIFEST = (
    ROOT
    / "configs/research-os/"
    "m4-information-theory-p2-synthetic-run-manifest-v1.json"
)
PREREGISTRATION = (
    ROOT / "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
)
HARNESS = (
    ROOT
    / "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
)


@cache
def _fixture():
    synthetic = load_synthetic_run_manifest(SYNTHETIC_MANIFEST)
    dataset = validate_synthetic_dataset(
        generate_null_dataset(
            synthetic,
            scale_id="FORWARD_61",
            seed=synthetic.seed_policy.seeds[0],
        ).to_dict()
    )
    training = restrict_to_training_history(dataset, available_through_issue=900)
    train_view = build_train_feature_view(training, tuple(range(1, 901)))
    blind = build_blind_test_feature_view(dataset, target_issue=901)
    configs = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))[
        "probe_models"
    ]["hyperparameters"]
    configs["REGULARIZED_LOGISTIC_REGRESSION"] = json.loads(
        HARNESS.read_text(encoding="utf-8")
    )["probes"]["REGULARIZED_LOGISTIC_REGRESSION"]
    return dataset, training, train_view, blind, configs


def test_registry_contains_all_four_p26_probes_and_theoretical_reference() -> None:
    assert FORMAL_PROBE_REGISTRY == (
        "THEORETICAL_BASELINE",
        "EMPIRICAL_BASELINE",
        "REGULARIZED_LOGISTIC_REGRESSION",
        "NAIVE_BAYES",
        "SHALLOW_CALIBRATED_TREE",
    )


def test_naive_bayes_uses_frozen_inner_selection_and_prior_only_prediction() -> None:
    _dataset, training, train_view, blind, configs = _fixture()
    prepared = prepare_naive_bayes_probe(
        training,
        train_view,
        config=configs["NAIVE_BAYES"],
        outer_test_issue=901,
    )
    prediction = np.asarray(prepared.predict(blind))
    assert prediction.shape == (33,)
    assert np.isfinite(prediction).all()
    assert (prediction > 0.0).all() and (prediction < 1.0).all()
    assert prepared.state.training_end_issue == 900
    assert prepared.state.hyperparameters["outer_test_metrics_used"] is False
    assert prepared.state.hyperparameters["alpha"] in {0.5, 1.0, 2.0}


def test_shallow_tree_uses_frozen_platt_holdout_and_prior_only_prediction() -> None:
    _dataset, training, train_view, blind, configs = _fixture()
    prepared = prepare_shallow_calibrated_tree(
        training,
        train_view,
        config=configs["SHALLOW_CALIBRATED_TREE"],
        outer_test_issue=901,
    )
    prediction = np.asarray(prepared.predict(blind))
    assert prediction.shape == (33,)
    assert np.isfinite(prediction).all()
    assert (prediction > 0.0).all() and (prediction < 1.0).all()
    assert prepared.state.training_end_issue == 900
    assert prepared.state.hyperparameters["calibration_issue_count"] == 180
    assert prepared.state.hyperparameters["calibration_end_issue"] == 900
    assert prepared.state.hyperparameters["outer_test_metrics_used"] is False


def test_cached_and_literal_feature_paths_produce_identical_four_probe_outputs() -> None:
    dataset, training, train_view, blind, configs = _fixture()
    cache = StrictPriorFeatureCache(dataset)
    cache.reveal_training_history(training, through_issue=900)
    cached_train = cache.build_train_feature_view(
        training,
        tuple(range(1, 901)),
    )
    cached_blind = cache.build_blind_test_feature_view(target_issue=901)
    assert cached_train == train_view
    assert cached_blind == blind

    for probe_id in (
        "EMPIRICAL_BASELINE",
        "REGULARIZED_LOGISTIC_REGRESSION",
        "NAIVE_BAYES",
        "SHALLOW_CALIBRATED_TREE",
    ):
        config = {} if probe_id == "EMPIRICAL_BASELINE" else configs[probe_id]
        literal = prepare_probe(
            probe_id=probe_id,
            dataset=training,
            train_view=train_view,
            probe_config=config,
            outer_test_issue=901,
        )
        cached = prepare_probe(
            probe_id=probe_id,
            dataset=training,
            train_view=cached_train,
            probe_config=config,
            outer_test_issue=901,
            train_view_builder=cache.build_train_feature_view,
        )
        assert cached.state.state_digest == literal.state.state_digest
        assert cached.predict(cached_blind) == literal.predict(blind)
