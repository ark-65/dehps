from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from dehps.research_os.information_theory.measurement_validation import (
    StrictPriorFeatureCache,
    build_cells,
    build_replicate,
    generate_evaluation_dataset,
    load_measurement_validation_manifest,
)
from dehps.research_os.information_theory.measurement_validation.feature_cache import (
    STATE_NUMBER_INTERACTION_NAMES,
    STATE_VISIBLE_FEATURE_MANIFEST_DIGEST,
    STATE_VISIBLE_FEATURE_NAMES,
)
from dehps.research_os.information_theory.probes import (
    prepare_logistic_probe,
    prepare_naive_bayes_probe,
    prepare_shallow_calibrated_tree,
)
from dehps.research_os.information_theory.synthetic import (
    load_synthetic_run_manifest,
)
from dehps.research_os.information_theory.walk_forward import (
    WalkForwardError,
    restrict_to_training_history,
)

ROOT = Path(__file__).resolve().parents[3]
MEASUREMENT_MANIFEST = (
    ROOT
    / "configs/research-os/m4-information-theory-p2-6-measurement-validation-v1.json"
)
SYNTHETIC_MANIFEST = (
    ROOT
    / "configs/research-os/m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
)
PREREGISTRATION = (
    ROOT / "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
)
HARNESS = (
    ROOT / "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
)
DEVELOPMENT_SELECTION_DIGEST = "d" * 64


def _state_visible_null():
    manifest = load_measurement_validation_manifest(MEASUREMENT_MANIFEST)
    synthetic = load_synthetic_run_manifest(SYNTHETIC_MANIFEST)
    cell = next(
        item
        for item in build_cells(manifest, synthetic)
        if item.scale_id == "FORWARD_61" and item.scenario_id == "NULL_UNIFORM"
    )
    replicate = build_replicate(
        cell=cell,
        replicate_index=0,
        parent_execution_id="a" * 64,
    )
    return generate_evaluation_dataset(
        replicate,
        synthetic=synthetic,
        truth_artifact=None,
        expose_prior_state=True,
    )


def _views():
    dataset = _state_visible_null()
    training = restrict_to_training_history(
        dataset,
        available_through_issue=900,
    )
    cache = StrictPriorFeatureCache(dataset, include_prior_state=True)
    cache.reveal_training_history(training, through_issue=900)
    return (
        dataset,
        training,
        cache,
        cache.build_train_feature_view(training, tuple(range(1, 901))),
        cache.build_blind_test_feature_view(target_issue=901),
    )


def _frozen_configs() -> dict:
    configs = deepcopy(
        json.loads(PREREGISTRATION.read_text(encoding="utf-8"))["probe_models"][
            "hyperparameters"
        ]
    )
    configs["REGULARIZED_LOGISTIC_REGRESSION"] = deepcopy(
        json.loads(HARNESS.read_text(encoding="utf-8"))["probes"][
            "REGULARIZED_LOGISTIC_REGRESSION"
        ]
    )
    configs["REGULARIZED_LOGISTIC_REGRESSION"].update(
        {
            "selection_mode": "frozen_development",
            "selected_C": 0.1,
            "C": [0.1],
            "development_selection_digest": DEVELOPMENT_SELECTION_DIGEST,
        }
    )
    configs["NAIVE_BAYES"].update(
        {
            "selection_mode": "frozen_development",
            "selected_alpha": 1.0,
            "alpha": [1.0],
            "development_selection_digest": DEVELOPMENT_SELECTION_DIGEST,
        }
    )
    configs["SHALLOW_CALIBRATED_TREE"].update(
        {
            "selection_mode": "frozen_development",
            "selected_max_depth": 2,
            "selected_min_samples_leaf": 100,
            "max_depth": [2],
            "min_samples_leaf": [100],
            "development_selection_digest": DEVELOPMENT_SELECTION_DIGEST,
        }
    )
    return configs


def test_state_visible_instrument_has_number_specific_strict_prior_coordinates() -> (
    None
):
    dataset, _training, _cache, train_view, blind = _views()
    assert dataset.raw_payload["prior_state_for_real_history"] == "forbidden"
    assert train_view.feature_names == STATE_VISIBLE_FEATURE_NAMES
    assert blind.feature_names == STATE_VISIBLE_FEATURE_NAMES
    assert train_view.feature_manifest_digest == STATE_VISIBLE_FEATURE_MANIFEST_DIGEST
    assert STATE_NUMBER_INTERACTION_NAMES == tuple(
        f"prior_state_x_red_{number:02d}" for number in range(1, 34)
    )
    assert len(train_view.feature_names) == 38

    first_issue_second_number = train_view.values[1]
    assert first_issue_second_number[4] == 0.5
    assert first_issue_second_number[5] == 0.0
    assert first_issue_second_number[6] == 0.5
    assert sum(first_issue_second_number[5:]) == 0.5
    assert blind.available_through_issue == 900
    assert blind.target_issue == 901


def test_state_visible_instrument_fails_closed_on_state_mutation() -> None:
    dataset = _state_visible_null()
    changed = deepcopy(dict(dataset.raw_payload))
    changed["prior_states"][0] = 1
    mutated = type(dataset)(
        artifact_digest=dataset.artifact_digest,
        scenario_id=dataset.scenario_id,
        scale_id=dataset.scale_id,
        minimum_training_length=dataset.minimum_training_length,
        outer_evaluation_length=dataset.outer_evaluation_length,
        seed_policy=dataset.seed_policy,
        seed_policy_digest=dataset.seed_policy_digest,
        replicate_seed=dataset.replicate_seed,
        issues=dataset.issues,
        raw_payload=changed,
    )
    with pytest.raises(WalkForwardError, match="prior_state_digest_mismatch"):
        StrictPriorFeatureCache(mutated, include_prior_state=True)


def test_frozen_development_configs_skip_outer_fold_model_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dataset, training, cache, train_view, blind = _views()
    configs = _frozen_configs()

    import dehps.research_os.information_theory.probes.logistic_regression as logistic
    import dehps.research_os.information_theory.probes.shallow_calibrated_tree as tree
    from dehps.research_os.information_theory.probes import naive_bayes

    def forbidden_inner(*_args, **_kwargs):
        raise AssertionError("frozen outer fit must not run inner selection")

    monkeypatch.setattr(logistic, "expanding_inner_folds", forbidden_inner)
    monkeypatch.setattr(naive_bayes, "expanding_inner_folds", forbidden_inner)
    monkeypatch.setattr(tree, "expanding_inner_folds", forbidden_inner)

    logistic_fit_count = 0
    naive_fit_count = 0
    tree_calibrated_fit_count = 0
    original_logistic_fit = logistic._fit_model
    original_naive_fit = naive_bayes._fit
    original_tree_fit = tree._fit_calibrated

    def counted_logistic(*args, **kwargs):
        nonlocal logistic_fit_count
        logistic_fit_count += 1
        return original_logistic_fit(*args, **kwargs)

    def counted_naive(*args, **kwargs):
        nonlocal naive_fit_count
        naive_fit_count += 1
        return original_naive_fit(*args, **kwargs)

    def counted_tree(*args, **kwargs):
        nonlocal tree_calibrated_fit_count
        tree_calibrated_fit_count += 1
        return original_tree_fit(*args, **kwargs)

    monkeypatch.setattr(logistic, "_fit_model", counted_logistic)
    monkeypatch.setattr(naive_bayes, "_fit", counted_naive)
    monkeypatch.setattr(tree, "_fit_calibrated", counted_tree)

    prepared = (
        prepare_logistic_probe(
            training,
            train_view,
            config=configs["REGULARIZED_LOGISTIC_REGRESSION"],
            outer_test_issue=901,
        ),
        prepare_naive_bayes_probe(
            training,
            train_view,
            config=configs["NAIVE_BAYES"],
            outer_test_issue=901,
        ),
        prepare_shallow_calibrated_tree(
            training,
            train_view,
            config=configs["SHALLOW_CALIBRATED_TREE"],
            outer_test_issue=901,
            train_view_builder=cache.build_train_feature_view,
        ),
    )
    assert logistic_fit_count == 1
    assert naive_fit_count == 1
    assert tree_calibrated_fit_count == 1
    assert [
        item.state.hyperparameters["fit_count_per_outer_fold"] for item in prepared
    ] == [1, 1, 2]
    assert (
        sum(item.state.hyperparameters["fit_count_per_outer_fold"] for item in prepared)
        == 4
    )
    assert all(len(item.predict(blind)) == 33 for item in prepared)
