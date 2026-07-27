from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from math import isclose
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from dehps import cli
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory import metrics as metric_kernel
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.probes import (
    FORMAL_PROBE_REGISTRY,
    prepare_empirical_baseline,
    prepare_logistic_probe,
    prepare_probe,
    prepare_theoretical_baseline,
)
from dehps.research_os.information_theory.walk_forward import (
    FEATURE_MANIFEST_DIGEST,
    BlindTestFeatureView,
    OuterFold,
    WalkForwardError,
    aggregate_settlements,
    build_blind_test_feature_view,
    build_fold_identity,
    build_fold_views,
    build_prediction_checkpoint,
    build_train_feature_view,
    expanding_inner_folds,
    expanding_outer_folds,
    fit_preprocessor,
    illegal_future_feature_canary,
    load_harness_manifest,
    persist_prediction_checkpoint,
    reject_random_inner_validation,
    resume_walk_forward,
    restrict_to_training_history,
    reveal_target,
    run_walk_forward,
    select_inner_candidate,
    settle_fold,
    transform_blind,
    validate_harness_manifest,
    validate_outer_fold,
    validate_prediction_checkpoint,
    validate_synthetic_dataset,
)
from dehps.research_os.information_theory.walk_forward.artifacts import (
    build_run_artifact,
)
from dehps.research_os.information_theory.walk_forward.leakage import (
    guard_dataset_identity,
    guard_inner_boundaries,
    guard_number_event_rows,
)
from dehps.research_os.information_theory.walk_forward.manifest import (
    preprocessing_manifest_digest,
    probe_manifest_digest,
)
from dehps.research_os.information_theory.synthetic import (
    generate_null_dataset,
    load_synthetic_run_manifest,
)


ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC_MANIFEST_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-p2-synthetic-run-manifest-v1.json"
)
HARNESS_MANIFEST_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
)
GIT_COMMIT = "f59a6b1b1dde6f02f13aa3465e560cb38931b448"
PREREGISTRATION_DIGEST = (
    "6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1"
)
METRIC_KERNEL_DIGEST = (
    "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2"
)


@pytest.fixture(scope="module")
def dataset_payload() -> dict:
    return generate_null_dataset(
        load_synthetic_run_manifest(SYNTHETIC_MANIFEST_PATH),
        scale_id="FORWARD_61",
        seed=200000,
    ).to_dict()


@pytest.fixture(scope="module")
def dataset(dataset_payload):
    return validate_synthetic_dataset(dataset_payload)


@pytest.fixture(scope="module")
def harness_manifest():
    return load_harness_manifest(HARNESS_MANIFEST_PATH)


@pytest.fixture(scope="module")
def first_fold(dataset):
    return expanding_outer_folds(dataset)[0]


@pytest.fixture(scope="module")
def fold_views(dataset, first_fold):
    return build_fold_views(dataset, first_fold)


@pytest.fixture(scope="module")
def training_dataset(dataset, first_fold):
    return restrict_to_training_history(
        dataset, available_through_issue=first_fold.train_issues[-1]
    )


@pytest.fixture(scope="module")
def prepared_logistic(training_dataset, harness_manifest, first_fold, fold_views):
    return prepare_logistic_probe(
        training_dataset,
        fold_views[0],
        config=harness_manifest.probe("REGULARIZED_LOGISTIC_REGRESSION"),
        outer_test_issue=first_fold.test_issue,
    )


def _dataset_redigest(payload: dict) -> dict:
    payload["draw_digest"] = canonical_digest(
        [
            {
                "issue_index": item["issue_index"],
                "sorted_red_numbers": item["sorted_red_numbers"],
            }
            for item in payload["issues"]
        ],
        domain="dehps.m4.synthetic.draws.v1",
    )
    payload["target_digest"] = canonical_digest(
        [item["target_vector"] for item in payload["issues"]],
        domain="dehps.m4.synthetic.targets.v1",
    )
    identity = dict(payload)
    identity.pop("artifact_digest", None)
    payload["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4.synthetic.dataset.v1"
    )
    return payload


def _fold_identity(dataset, harness_manifest, first_fold):
    return build_fold_identity(
        dataset_digest=dataset.artifact_digest,
        fold=first_fold,
        feature_view_digest=FEATURE_MANIFEST_DIGEST,
        preprocessing_manifest_digest=preprocessing_manifest_digest(
            harness_manifest
        ),
        probe_manifest_digest=probe_manifest_digest(
            harness_manifest, probe_id="THEORETICAL_BASELINE"
        ),
    )


def _checkpoint(dataset, harness_manifest, first_fold):
    state = prepare_theoretical_baseline(
        feature_manifest_digest=FEATURE_MANIFEST_DIGEST
    ).state
    return build_prediction_checkpoint(
        fold=_fold_identity(dataset, harness_manifest, first_fold),
        probe_state=state,
        probabilities=(6 / 33,) * 33,
        probe_manifest_digest=probe_manifest_digest(
            harness_manifest, probe_id="THEORETICAL_BASELINE"
        ),
        scenario=dataset.scenario_id,
        created_at=harness_manifest.created_at,
        git_commit=GIT_COMMIT,
        working_tree_clean=True,
    )


# Splitter requirements 1-8.
def test_outer_split_is_expanding(dataset) -> None:
    folds = expanding_outer_folds(dataset)
    assert folds[0].train_issues == tuple(range(1, 901))
    assert folds[1].train_issues == tuple(range(1, 902))


def test_outer_test_horizon_is_one(dataset) -> None:
    assert all(fold.test_issue == fold.train_issues[-1] + 1 for fold in expanding_outer_folds(dataset))


def test_outer_train_always_ends_before_test(dataset) -> None:
    assert all(max(fold.train_issues) < fold.test_issue for fold in expanding_outer_folds(dataset))


def test_minimum_training_length_is_enforced(dataset) -> None:
    with pytest.raises(WalkForwardError, match="insufficient_training_history"):
        validate_outer_fold(
            OuterFold(tuple(range(1, 900)), 900),
            minimum_training_issues=900,
            dataset_issue_count=dataset.issue_count,
        )


def test_outer_test_issues_are_unique(dataset) -> None:
    tests = [fold.test_issue for fold in expanding_outer_folds(dataset)]
    assert len(tests) == len(set(tests)) == 61


def test_fold_digest_is_stable(dataset, harness_manifest, first_fold) -> None:
    assert _fold_identity(dataset, harness_manifest, first_fold) == _fold_identity(
        dataset, harness_manifest, first_fold
    )


def test_fold_boundary_change_changes_digest(dataset, harness_manifest, first_fold) -> None:
    changed = OuterFold(tuple(range(1, 902)), 902)
    assert _fold_identity(dataset, harness_manifest, first_fold).fold_digest != _fold_identity(
        dataset, harness_manifest, changed
    ).fold_digest


def test_outer_train_test_overlap_is_rejected() -> None:
    with pytest.raises(WalkForwardError, match="outer_train_test_overlap"):
        OuterFold((1, 2, 3), 3)


# Dataset adapter requirements 9-14.
def test_dataset_adapter_accepts_only_p2_1_synthetic(dataset) -> None:
    assert dataset.scenario_id == "NULL_UNIFORM"
    assert dataset.scale_id == "FORWARD_61"


def test_real_dataset_source_is_rejected(dataset_payload) -> None:
    payload = deepcopy(dataset_payload)
    payload["data_source"] = "real_history"
    _dataset_redigest(payload)
    with pytest.raises(WalkForwardError, match="non_synthetic_dataset_forbidden_in_p2"):
        validate_synthetic_dataset(payload)


def test_dataset_issue_order_is_validated(dataset_payload) -> None:
    payload = deepcopy(dataset_payload)
    payload["issues"][0], payload["issues"][1] = payload["issues"][1], payload["issues"][0]
    _dataset_redigest(payload)
    with pytest.raises(WalkForwardError, match="non_chronological_dataset"):
        validate_synthetic_dataset(payload)


def test_dataset_red_mask_target_consistency_is_validated(dataset_payload) -> None:
    payload = deepcopy(dataset_payload)
    payload["issues"][0]["red_mask"] = 1
    _dataset_redigest(payload)
    with pytest.raises(WalkForwardError, match="red_mask_target_mismatch"):
        validate_synthetic_dataset(payload)


def test_dataset_requires_six_reds(dataset_payload) -> None:
    payload = deepcopy(dataset_payload)
    positive = payload["issues"][0]["target_vector"].index(1)
    payload["issues"][0]["target_vector"][positive] = 0
    _dataset_redigest(payload)
    with pytest.raises(WalkForwardError, match="invalid_six_red_target"):
        validate_synthetic_dataset(payload)


def test_dataset_mutation_is_detected(dataset_payload) -> None:
    payload = deepcopy(dataset_payload)
    payload["target_digest"] = "0" * 64
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4.synthetic.dataset.v1"
    )
    with pytest.raises(WalkForwardError, match="dataset_digest_mismatch"):
        validate_synthetic_dataset(payload)


# Feature boundary requirements 15-20.
def test_legal_history_feature_view_passes(fold_views) -> None:
    train, blind = fold_views
    assert train.construction_end_issue < blind.target_issue
    assert blind.available_through_issue < blind.target_issue


def test_target_feature_canary_is_rejected(dataset, first_fold) -> None:
    with pytest.raises(WalkForwardError, match="future_feature_leakage"):
        illegal_future_feature_canary(dataset, target_issue=first_fold.test_issue)


def test_timestamp_equal_to_target_is_rejected(fold_views) -> None:
    blind = fold_views[1]
    with pytest.raises(WalkForwardError, match="future_feature_leakage"):
        replace(
            blind,
            available_through_issue=blind.target_issue,
            construction_end_issue=blind.target_issue,
        )


def test_global_scaler_canary_is_rejected(fold_views, first_fold) -> None:
    with pytest.raises(WalkForwardError, match="preprocessor_fit_range_violation"):
        fit_preprocessor(
            fold_views[0],
            outer_train_end=first_fold.train_issues[-1],
            claimed_fit_end_issue=first_fold.test_issue,
        )


def test_missing_issue_identity_is_rejected(dataset) -> None:
    with pytest.raises(WalkForwardError, match="missing_issue_identity"):
        dataset.issue(0)


def test_number_event_long_table_has_33_rows_per_issue(fold_views) -> None:
    train = fold_views[0]
    assert len(train.values) == 33 * len(train.issue_ids)
    guard_number_event_rows(issue_ids=train.issue_ids, red_numbers=train.red_numbers)


# Inner validation requirements 21-25.
def test_inner_folds_are_chronological(first_fold) -> None:
    folds = expanding_inner_folds(
        first_fold.train_issues, outer_test_issue=first_fold.test_issue
    )
    assert len(folds) == 3
    assert all(max(item.train_issues) < min(item.validation_issues) for item in folds)


@pytest.mark.parametrize("method", ["random_kfold", "stratified_kfold", "shuffle_split"])
def test_random_inner_validation_is_rejected(method: str) -> None:
    with pytest.raises(WalkForwardError, match="non_chronological_inner_validation"):
        reject_random_inner_validation(method)


def test_outer_test_never_enters_inner(first_fold) -> None:
    folds = expanding_inner_folds(
        first_fold.train_issues, outer_test_issue=first_fold.test_issue
    )
    assert all(first_fold.test_issue not in item.train_issues + item.validation_issues for item in folds)


def test_inner_validation_cannot_precede_training() -> None:
    with pytest.raises(WalkForwardError, match="non_chronological_inner_validation"):
        guard_inner_boundaries(
            (type("Bad", (), {"train_issues": (2,), "validation_issues": (1,)})(),),
            outer_train_end=2,
            outer_test_issue=3,
        )


def test_hyperparameter_selection_uses_only_inner_metric() -> None:
    selected, summaries = select_inner_candidate(
        {"C_0.01": (1.0, 1.0, 1.0), "C_1": (2.0, 2.0, 2.0)},
        complexity_order={"C_0.01": 0, "C_1": 1},
    )
    assert selected == "C_0.01"
    assert summaries == {"C_0.01": 1.0, "C_1": 2.0}


# Probe requirements 26-33.
def test_theoretical_probe_outputs_exact_six_over_33(fold_views) -> None:
    prepared = prepare_theoretical_baseline(
        feature_manifest_digest=FEATURE_MANIFEST_DIGEST
    )
    assert prepared.predict(fold_views[1]) == (6 / 33,) * 33
    assert prepared.state.seed_policy == {"mode": "none"}


def test_empirical_baseline_uses_outer_train_only(dataset, training_dataset, fold_views) -> None:
    prepared = prepare_empirical_baseline(training_dataset, fold_views[0])
    counts = [
        sum(dataset.issue(issue).target_vector[offset] for issue in range(1, 901))
        for offset in range(33)
    ]
    assert prepared.probabilities == tuple((count + 0.5) / 901 for count in counts)


def test_future_data_change_does_not_change_prior_empirical_prediction(dataset_payload) -> None:
    first = validate_synthetic_dataset(dataset_payload)
    changed = deepcopy(dataset_payload)
    issue = changed["issues"][-1]
    present = set(issue["sorted_red_numbers"])
    removed = min(present)
    added = min(set(range(1, 34)) - present)
    numbers = sorted((present - {removed}) | {added})
    issue["sorted_red_numbers"] = numbers
    issue["target_vector"] = [1 if value in numbers else 0 for value in range(1, 34)]
    issue["red_mask"] = sum(1 << (value - 1) for value in numbers)
    second = validate_synthetic_dataset(_dataset_redigest(changed))
    first_training = restrict_to_training_history(first, available_through_issue=900)
    second_training = restrict_to_training_history(second, available_through_issue=900)
    first_view = build_train_feature_view(first_training, tuple(range(1, 901)))
    second_view = build_train_feature_view(second_training, tuple(range(1, 901)))
    assert prepare_empirical_baseline(first_training, first_view).probabilities == prepare_empirical_baseline(second_training, second_view).probabilities


def test_logistic_outputs_33_probabilities(prepared_logistic, fold_views) -> None:
    assert len(prepared_logistic.predict(fold_views[1])) == 33


def test_logistic_probabilities_are_finite(prepared_logistic, fold_views) -> None:
    values = prepared_logistic.predict(fold_views[1])
    assert all(np.isfinite(value) and 0 <= value <= 1 for value in values)


def test_probability_order_is_fixed_by_blind_view(fold_views) -> None:
    assert fold_views[1].red_numbers == tuple(range(1, 34))


def test_probe_state_records_training_boundary(prepared_logistic) -> None:
    state = prepared_logistic.state
    assert state.training_start_issue == 1
    assert state.training_end_issue == 900
    assert state.training_issue_count == 900
    assert state.training_row_count == 29700


def test_logistic_is_deterministic(training_dataset, harness_manifest, first_fold, fold_views, prepared_logistic) -> None:
    replay = prepare_logistic_probe(
        training_dataset,
        fold_views[0],
        config=harness_manifest.probe("REGULARIZED_LOGISTIC_REGRESSION"),
        outer_test_issue=first_fold.test_issue,
    )
    assert replay.state.state_digest == prepared_logistic.state.state_digest
    assert replay.predict(fold_views[1]) == prepared_logistic.predict(fold_views[1])


def test_convergence_failure_is_structured(training_dataset, harness_manifest, first_fold, fold_views) -> None:
    invalid = replace(fold_views[0], targets=(0,) * len(fold_views[0].targets))
    with pytest.raises(WalkForwardError, match="INSUFFICIENT_CLASS_VARIATION"):
        prepare_logistic_probe(
            training_dataset,
            invalid,
            config=harness_manifest.probe("REGULARIZED_LOGISTIC_REGRESSION"),
            outer_test_issue=first_fold.test_issue,
        )


# Prediction checkpoint requirements 34-38.
def test_prediction_checkpoint_contains_no_target(dataset, harness_manifest, first_fold) -> None:
    checkpoint = _checkpoint(dataset, harness_manifest, first_fold)
    assert not {"target", "target_vector", "red_mask", "sorted_red_numbers"}.intersection(checkpoint)


def test_checkpoint_is_created_before_target_reveal(dataset, harness_manifest, first_fold, tmp_path) -> None:
    checkpoint = _checkpoint(dataset, harness_manifest, first_fold)
    path = persist_prediction_checkpoint(checkpoint, output_dir=tmp_path)
    assert path.exists()
    assert reveal_target(
        dataset,
        test_issue=first_fold.test_issue,
        prediction_checkpoint=checkpoint,
    ) == dataset.issue(first_fold.test_issue).target_vector


def test_duplicate_formal_prediction_is_rejected(dataset, harness_manifest, first_fold, tmp_path) -> None:
    checkpoint = _checkpoint(dataset, harness_manifest, first_fold)
    persist_prediction_checkpoint(checkpoint, output_dir=tmp_path)
    changed = build_prediction_checkpoint(
        fold=_fold_identity(dataset, harness_manifest, first_fold),
        probe_state=prepare_theoretical_baseline(
            feature_manifest_digest=FEATURE_MANIFEST_DIGEST
        ).state,
        probabilities=(0.2,) * 33,
        probe_manifest_digest=checkpoint["probe_manifest_digest"],
        scenario=dataset.scenario_id,
        created_at=harness_manifest.created_at,
        git_commit=GIT_COMMIT,
        working_tree_clean=True,
    )
    with pytest.raises(WalkForwardError, match="duplicate_prediction_identity"):
        persist_prediction_checkpoint(changed, output_dir=tmp_path)


def test_checkpoint_replay_returns_same_digest(dataset, harness_manifest, first_fold, tmp_path) -> None:
    checkpoint = _checkpoint(dataset, harness_manifest, first_fold)
    first = persist_prediction_checkpoint(checkpoint, output_dir=tmp_path)
    second = persist_prediction_checkpoint(checkpoint, output_dir=tmp_path)
    assert first == second


def test_checkpoint_target_access_flag_is_true(dataset, harness_manifest, first_fold) -> None:
    assert _checkpoint(dataset, harness_manifest, first_fold)["created_before_target_access"] is True


def test_probe_training_view_cannot_access_outer_target(training_dataset, first_fold) -> None:
    with pytest.raises(WalkForwardError, match="target_access_boundary_violation"):
        training_dataset.issue(first_fold.test_issue)


def test_probe_rejects_full_dataset_object(dataset, harness_manifest, first_fold, fold_views) -> None:
    with pytest.raises(WalkForwardError, match="target_access_boundary_violation"):
        prepare_logistic_probe(
            dataset,
            fold_views[0],
            config=harness_manifest.probe("REGULARIZED_LOGISTIC_REGRESSION"),
            outer_test_issue=first_fold.test_issue,
        )


def test_checkpoint_validation_rejects_target_field(dataset, harness_manifest, first_fold) -> None:
    checkpoint = _checkpoint(dataset, harness_manifest, first_fold)
    checkpoint["target_vector"] = [0] * 33
    with pytest.raises(WalkForwardError, match="target_access_boundary_violation"):
        validate_prediction_checkpoint(checkpoint)


def test_dataset_change_after_checkpoint_rejects_settlement(dataset, harness_manifest, first_fold) -> None:
    checkpoint = _checkpoint(dataset, harness_manifest, first_fold)
    with pytest.raises(WalkForwardError, match="dataset_mutation_detected"):
        guard_dataset_identity(dataset, expected_digest="0" * 64)


# Metric integration requirements 39-44.
def test_harness_settlement_calls_unique_metric_kernel(dataset, harness_manifest, first_fold, monkeypatch) -> None:
    checkpoint = _checkpoint(dataset, harness_manifest, first_fold)
    called = 0
    original = metric_kernel.evaluate_issue

    def counting(*args, **kwargs):
        nonlocal called
        called += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(metric_kernel, "evaluate_issue", counting)
    settle_fold(
        fold=_fold_identity(dataset, harness_manifest, first_fold),
        prediction_checkpoint=checkpoint,
        target_vector=dataset.issue(first_fold.test_issue).target_vector,
        metric_kernel_digest=METRIC_KERNEL_DIGEST,
    )
    assert called == 1


def test_theoretical_settlement_pe1_is_zero(dataset, harness_manifest, first_fold) -> None:
    settlement = settle_fold(
        fold=_fold_identity(dataset, harness_manifest, first_fold),
        prediction_checkpoint=_checkpoint(dataset, harness_manifest, first_fold),
        target_vector=dataset.issue(first_fold.test_issue).target_vector,
        metric_kernel_digest=METRIC_KERNEL_DIGEST,
    )
    assert settlement["pe1_bits_per_issue"] == 0


def test_theoretical_settlement_brier_gain_is_zero(dataset, harness_manifest, first_fold) -> None:
    settlement = settle_fold(
        fold=_fold_identity(dataset, harness_manifest, first_fold),
        prediction_checkpoint=_checkpoint(dataset, harness_manifest, first_fold),
        target_vector=dataset.issue(first_fold.test_issue).target_vector,
        metric_kernel_digest=METRIC_KERNEL_DIGEST,
    )
    assert settlement["brier_gain_per_issue"] == 0


def test_metric_kernel_digest_mismatch_fails_closed(dataset, harness_manifest, first_fold) -> None:
    with pytest.raises(WalkForwardError, match="metric_kernel_identity_mismatch"):
        settle_fold(
            fold=_fold_identity(dataset, harness_manifest, first_fold),
            prediction_checkpoint=_checkpoint(dataset, harness_manifest, first_fold),
            target_vector=dataset.issue(first_fold.test_issue).target_vector,
            metric_kernel_digest="0" * 64,
        )


def test_probe_modules_do_not_contain_metric_formulas() -> None:
    probe_root = ROOT / "apps/worker-python/dehps/research_os/information_theory/probes"
    sources = "\n".join(path.read_text() for path in probe_root.glob("*.py"))
    assert "bernoulli_log_loss_nats" not in sources
    assert "brier_per_number_event" not in sources


def test_aggregate_inference_sample_size_is_issue_count() -> None:
    aggregate = aggregate_settlements(
        [
            {
                "test_issue": 901,
                "pe1_bits_per_issue": 0.0,
                "brier_gain_per_issue": 0.0,
                "issue_metric": {"predicted_red_count": 6.0},
                "probability_clipping_diagnostics": {
                    "clip_count_low": 0,
                    "clip_count_high": 0,
                },
            }
        ],
        failed_folds=[],
        fallback_fold_count=0,
    )
    assert aggregate["sample_size_for_inference"] == aggregate["completed_fold_count"] == 1


# Leakage canaries requirements 45-49 are each independently exercised.
@pytest.mark.parametrize(
    ("canary", "expected"),
    [
        ("target_as_feature", "future_feature_leakage"),
        ("global_preprocessing", "preprocessor_fit_range_violation"),
        ("shuffled_cv", "non_chronological_inner_validation"),
        ("train_test_overlap", "outer_train_test_overlap"),
    ],
)
def test_leakage_canaries_fail_closed(canary, expected, dataset, first_fold, fold_views) -> None:
    with pytest.raises(WalkForwardError, match=expected):
        if canary == "target_as_feature":
            illegal_future_feature_canary(dataset, target_issue=first_fold.test_issue)
        elif canary == "global_preprocessing":
            fit_preprocessor(
                fold_views[0],
                outer_train_end=900,
                claimed_fit_end_issue=901,
            )
        elif canary == "shuffled_cv":
            reject_random_inner_validation("shuffle_split")
        else:
            OuterFold((899, 900, 901), 901)


def test_predict_and_select_second_checkpoint_fails_before_target(
    dataset, harness_manifest, first_fold, tmp_path
) -> None:
    checkpoint = _checkpoint(dataset, harness_manifest, first_fold)
    persist_prediction_checkpoint(checkpoint, output_dir=tmp_path)
    with pytest.raises(WalkForwardError, match="duplicate_prediction_identity"):
        changed = build_prediction_checkpoint(
            fold=_fold_identity(dataset, harness_manifest, first_fold),
            probe_state=prepare_theoretical_baseline(
                feature_manifest_digest=FEATURE_MANIFEST_DIGEST
            ).state,
            probabilities=(0.19,) * 33,
            probe_manifest_digest=checkpoint["probe_manifest_digest"],
            scenario=dataset.scenario_id,
            created_at=harness_manifest.created_at,
            git_commit=GIT_COMMIT,
            working_tree_clean=True,
        )
        persist_prediction_checkpoint(changed, output_dir=tmp_path)


# Aggregate requirements 50-55 and deterministic/resume requirements.
def test_theoretical_smoke_fold_count_and_zero_gain(dataset, harness_manifest, tmp_path) -> None:
    artifact = run_walk_forward(
        dataset=dataset,
        manifest=harness_manifest,
        probe_id="THEORETICAL_BASELINE",
        output_dir=tmp_path,
        git_commit=GIT_COMMIT,
        working_tree_clean=True,
    )
    assert artifact["aggregate"]["fold_count"] == 2
    assert artifact["aggregate"]["mean_pe1_bits_per_issue"] == 0
    assert artifact["aggregate"]["mean_brier_gain_per_issue"] == 0


def test_failed_folds_are_not_silently_deleted() -> None:
    aggregate = aggregate_settlements(
        [],
        failed_folds=[{"test_issue": 901, "code": "FAILED_CONVERGENCE"}],
        fallback_fold_count=0,
    )
    assert aggregate["fold_count"] == 1
    assert aggregate["failed_fold_count"] == 1
    assert aggregate["failed_folds"][0]["test_issue"] == 901


def test_fallback_folds_are_separately_counted() -> None:
    aggregate = aggregate_settlements([], failed_folds=[], fallback_fold_count=2)
    assert aggregate["fallback_fold_count"] == 2


def test_cumulative_gain_uses_stable_sum() -> None:
    records = [
        {
            "test_issue": issue,
            "pe1_bits_per_issue": gain,
            "brier_gain_per_issue": 0.0,
            "issue_metric": {"predicted_red_count": 6.0},
            "probability_clipping_diagnostics": {
                "clip_count_low": 0,
                "clip_count_high": 0,
            },
        }
        for issue, gain in [(901, 1e16), (902, 1.0), (903, -1e16)]
    ]
    assert aggregate_settlements(records, failed_folds=[], fallback_fold_count=0)["cumulative_pe1_bits"] == 1.0


def test_aggregate_contains_no_formal_uncertainty() -> None:
    aggregate = aggregate_settlements([], failed_folds=[], fallback_fold_count=0)
    assert aggregate["iid_confidence_interval"] is None
    assert aggregate["block_bootstrap_confidence_interval"] is None
    assert aggregate["permutation_p_value"] is None
    assert aggregate["power"] == "NOT_EVALUATED"


def test_aggregate_is_not_p2_gate_eligible() -> None:
    aggregate = aggregate_settlements([], failed_folds=[], fallback_fold_count=0)
    assert aggregate["eligible_for_p2_gate"] is False
    assert aggregate["descriptive_only"] is True


def test_run_replays_across_worker_count_and_order(dataset, harness_manifest, tmp_path) -> None:
    first = run_walk_forward(
        dataset=dataset,
        manifest=harness_manifest,
        probe_id="THEORETICAL_BASELINE",
        output_dir=tmp_path,
        git_commit=GIT_COMMIT,
        working_tree_clean=True,
        worker_count=1,
        execution_order="forward",
    )
    replay = run_walk_forward(
        dataset=dataset,
        manifest=harness_manifest,
        probe_id="THEORETICAL_BASELINE",
        output_dir=tmp_path,
        git_commit=GIT_COMMIT,
        working_tree_clean=True,
        worker_count=2,
        execution_order="reverse",
    )
    assert first == replay


def test_interrupted_run_resumes_without_competing_predictions(dataset, harness_manifest, tmp_path) -> None:
    partial = run_walk_forward(
        dataset=dataset,
        manifest=harness_manifest,
        probe_id="THEORETICAL_BASELINE",
        output_dir=tmp_path,
        git_commit=GIT_COMMIT,
        working_tree_clean=True,
        stop_after=1,
    )
    assert partial["status"] == "INTERRUPTED"
    resumed = resume_walk_forward(
        run_digest=partial["run_digest"],
        output_dir=tmp_path,
        dataset=dataset,
        manifest=harness_manifest,
        git_commit=GIT_COMMIT,
        working_tree_clean=True,
    )
    assert resumed["aggregate"]["completed_fold_count"] == 2


def test_logistic_null_smoke_is_descriptive_only(dataset, harness_manifest, tmp_path) -> None:
    artifact = run_walk_forward(
        dataset=dataset,
        manifest=harness_manifest,
        probe_id="REGULARIZED_LOGISTIC_REGRESSION",
        output_dir=tmp_path,
        git_commit=GIT_COMMIT,
        working_tree_clean=True,
    )
    assert artifact["aggregate"]["completed_fold_count"] == 2
    assert artifact["eligible_for_p2_gate"] is False
    assert artifact["formal_power_evidence"] is False
    assert artifact["real_data_evidence"] is False


# Governance requirements 56-68.
def test_formal_probe_registry_excludes_canary_and_post_result_models() -> None:
    assert FORMAL_PROBE_REGISTRY == (
        "THEORETICAL_BASELINE",
        "EMPIRICAL_BASELINE",
        "REGULARIZED_LOGISTIC_REGRESSION",
        "NAIVE_BAYES",
        "SHALLOW_CALIBRATED_TREE",
    )


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("injected_signal", "NOT_IMPLEMENTED"),
        ("bootstrap", "NOT_IMPLEMENTED"),
        ("permutation", "NOT_IMPLEMENTED"),
        ("real_history", "NOT_READ"),
        ("production_checkpoint", "NOT_CREATED"),
        ("promotion_gate", "CLOSED"),
        ("adaptive_supervisor", "STOPPED"),
        ("evidence_progress_percent", 0),
    ],
)
def test_harness_governance_is_fail_closed(harness_manifest, field, expected) -> None:
    assert harness_manifest.payload["governance"][field] == expected


def test_pe2_remains_not_implemented(harness_manifest) -> None:
    assert harness_manifest.payload["pe2_status"] == "NOT_IMPLEMENTED"


def test_practical_null_is_not_present_in_new_harness_contract(harness_manifest) -> None:
    assert "practical_null" not in harness_manifest.payload


def test_harness_manifest_digest_is_stable(harness_manifest) -> None:
    assert harness_manifest.artifact_digest == config_digest(harness_manifest.payload)


def test_metric_kernel_identity_change_is_rejected(harness_manifest) -> None:
    payload = deepcopy(harness_manifest.payload)
    payload["metric_kernel_digest"] = "0" * 64
    payload["artifact_digest"] = config_digest(payload)
    with pytest.raises(WalkForwardError, match="metric_kernel_identity_mismatch"):
        validate_harness_manifest(payload)


def test_cli_validates_p2_3_manifest() -> None:
    result = CliRunner().invoke(
        cli.app,
        [
            "research-os",
            "information-theory",
            "walk-forward",
            "validate-config",
            "--preregistration-digest",
            PREREGISTRATION_DIGEST,
            "--input",
            str(HARNESS_MANIFEST_PATH),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["phase"] == "M4-P2.3"
    assert payload["eligible_for_p2_gate"] is False


def test_artifact_parent_graph_is_complete(dataset, harness_manifest, tmp_path) -> None:
    artifact = run_walk_forward(
        dataset=dataset,
        manifest=harness_manifest,
        probe_id="THEORETICAL_BASELINE",
        output_dir=tmp_path,
        git_commit=GIT_COMMIT,
        working_tree_clean=True,
    )
    assert dataset.artifact_digest in artifact["parent_digests"]
    assert harness_manifest.artifact_digest in artifact["parent_digests"]
    assert set(artifact["settlement_digests"]).issubset(artifact["parent_digests"])


def test_run_artifact_marks_no_production_or_real_evidence() -> None:
    artifact = build_run_artifact(
        run_digest="a" * 64,
        dataset_digest="b" * 64,
        harness_manifest_digest="c" * 64,
        probe_id="THEORETICAL_BASELINE",
        probe_manifest_digest="d" * 64,
        fold_digests=[],
        probe_state_digests=[],
        preprocessing_state_digests=[],
        prediction_digests=[],
        settlement_digests=[],
        aggregate=aggregate_settlements([], failed_folds=[], fallback_fold_count=0),
        git_commit=GIT_COMMIT,
        created_at="2026-07-25T14:00:00+08:00",
        seed_policy={"mode": "none"},
    )
    assert artifact["production_checkpoint"] is False
    assert artifact["real_data_evidence"] is False
    assert artifact["eligible_for_p2_gate"] is False


def test_all_walk_forward_schemas_are_present() -> None:
    expected = {
        "m4-information-theory-walk-forward-harness-v1.schema.json",
        "m4-information-theory-walk-forward-fold-v1.schema.json",
        "m4-information-theory-prediction-checkpoint-v1.schema.json",
        "m4-information-theory-fold-settlement-v1.schema.json",
        "m4-information-theory-walk-forward-run-v1.schema.json",
        "m4-information-theory-preprocessing-state-v1.schema.json",
        "m4-information-theory-probe-state-v1.schema.json",
        "m4-information-theory-feature-view-v1.schema.json",
    }
    schema_root = ROOT / "schemas/research-os"
    assert expected.issubset({path.name for path in schema_root.glob("*.json")})


def test_frozen_inputs_are_referenced_exactly(harness_manifest) -> None:
    assert harness_manifest.payload["preregistration_digest"] == PREREGISTRATION_DIGEST
    assert harness_manifest.payload["metric_kernel_digest"] == METRIC_KERNEL_DIGEST
    assert harness_manifest.minimum_training_issues == 900
    assert harness_manifest.payload["outer_split"]["test_horizon"] == 1
