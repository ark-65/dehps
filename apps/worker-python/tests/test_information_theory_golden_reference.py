from __future__ import annotations

import ast
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.measurement_validation import (
    FIXTURE_GIT_COMMIT,
    GoldenReferenceError,
    PythonReferenceBackend,
    PythonReferenceEvaluation,
    StrictPriorFeatureCache,
    build_canonical_executor_fingerprint,
    build_exact_golden_attestation,
    build_golden_fixture_artifact,
    build_golden_reference_plan_artifact,
    canonical_journal_bytes,
    encode_float64_tree,
    float64_bits,
    full_blind_feature_view_payload_digest,
    full_train_feature_view_payload_digest,
    generate_evaluation_dataset,
    golden_boundary_identity_contract,
    golden_full_replicate,
    load_repaired_measurement_validation_manifest,
)
from dehps.research_os.information_theory.measurement_validation.contracts import (
    METRIC_KERNEL_DIGEST,
    RESAMPLING_KERNEL_DIGEST,
    WALK_FORWARD_HARNESS_DIGEST,
)
from dehps.research_os.information_theory.measurement_validation.repaired_contracts import (
    STATE_VISIBLE_FEATURE_MANIFEST_DIGEST,
)
from dehps.research_os.information_theory.probes import prepare_probe
from dehps.research_os.information_theory.probes.runtime_cache import (
    ExactProbeRuntimeCache,
)
from dehps.research_os.information_theory.synthetic import (
    load_synthetic_run_manifest,
)
from dehps.research_os.information_theory.walk_forward import (
    expanding_outer_folds,
    load_harness_manifest,
    restrict_to_training_history,
)

ROOT = Path(__file__).resolve().parents[3]
P261_MANIFEST = ROOT / (
    "configs/research-os/" "m4-information-theory-p2-6-1-measurement-validation-v1.json"
)
SYNTHETIC_MANIFEST = ROOT / (
    "configs/research-os/" "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
)
PREREGISTRATION = ROOT / (
    "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
)
HARNESS = ROOT / (
    "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
)
PROBES = (
    "EMPIRICAL_BASELINE",
    "REGULARIZED_LOGISTIC_REGRESSION",
    "NAIVE_BAYES",
    "SHALLOW_CALIBRATED_TREE",
)
CONSTRUCTION_SOURCE_IDENTITY = {
    "source_integrity_contract_digest": "1" * 64,
    "shared_frozen_source_set_digest": "2" * 64,
    "approved_acceleration_source_set_digest": "3" * 64,
    "independent_oracle_source_set_digest": "4" * 64,
    "audit_orchestration_source_set_digest": "5" * 64,
}
GOLDEN_SOURCE_CONTRACT = {"fixture": "source-contract-test-double"}
GOLDEN_SOURCE_IDENTITY = {
    "golden_source_contract_digest": "6" * 64,
    "shared_frozen_source_set_digest": "2" * 64,
    "independent_oracle_source_set_digest": "4" * 64,
}


def _fixture_probe_state(probe_id: str, test_issue: int, probe_index: int) -> dict:
    return {
        "probe_id": probe_id,
        "probe_type": "fixture_test_double",
        "training_start_issue": 1,
        "training_end_issue": test_issue - 1,
        "training_issue_count": test_issue - 1,
        "training_row_count": (test_issue - 1) * 33,
        "feature_manifest_digest": STATE_VISIBLE_FEATURE_MANIFEST_DIGEST,
        "hyperparameters": {},
        "hyperparameter_selection_digest": "none",
        "seed_policy": {"mode": "none"},
        "preprocessing_state_digest": "none",
        "model_parameters_digest": f"{probe_index + 1:x}" * 64,
        "convergence_status": "CONVERGED",
        "failure": None,
        "state_digest": f"{probe_index + 5:x}" * 64,
    }


def _fixture_issue_metric(test_issue: int, target: list[int]) -> dict:
    clip = {
        "raw_min_probability": 0.1,
        "raw_max_probability": 0.1,
        "clipped_min_probability": 0.1,
        "clipped_max_probability": 0.1,
        "clip_count_low": 0,
        "clip_count_high": 0,
        "clip_fraction": 0.0,
        "epsilon": 0.000001,
    }
    events = [
        {
            "schema_version": "dehps-m4-number-event-metric.v1",
            "issue_id": str(test_issue),
            "cluster_id": str(test_issue),
            "red_number": red_number,
            "target": target[red_number - 1],
            "baseline_raw_probability": 6 / 33,
            "probe_raw_probability": 0.1,
            "baseline_clipped_probability": 6 / 33,
            "probe_clipped_probability": 0.1,
            "baseline_log_loss_nats_per_number_event": 0.0,
            "probe_log_loss_nats_per_number_event": 0.0,
            "baseline_log_loss_bits_per_number_event": 0.0,
            "probe_log_loss_bits_per_number_event": 0.0,
            "baseline_brier_per_number_event": 0.0,
            "probe_brier_per_number_event": 0.0,
        }
        for red_number in range(1, 34)
    ]
    return {
        "schema_version": "dehps-m4-issue-metric.v1",
        "issue_id": str(test_issue),
        "cluster_id": str(test_issue),
        "probability_epsilon": 0.000001,
        "baseline_identity": "NUMBER_EVENT_COMPOSITE_BASELINE",
        "number_events": events,
        "baseline_log_loss_nats_per_issue": 0.0,
        "probe_log_loss_nats_per_issue": 0.0,
        "observed_log_loss_gain_nats_per_issue": 0.0,
        "baseline_log_loss_bits_per_issue": 0.0,
        "probe_log_loss_bits_per_issue": 0.0,
        "observed_log_loss_gain_bits_per_issue": 0.0,
        "baseline_log_loss_nats_per_number_event": 0.0,
        "probe_log_loss_nats_per_number_event": 0.0,
        "baseline_log_loss_bits_per_number_event": 0.0,
        "probe_log_loss_bits_per_number_event": 0.0,
        "baseline_brier_sum_per_issue": 0.0,
        "probe_brier_sum_per_issue": 0.0,
        "brier_gain_per_issue": -0.0,
        "baseline_brier_mean_per_number_event": 0.0,
        "probe_brier_mean_per_number_event": 0.0,
        "actual_red_count": 6,
        "predicted_red_count": 3.3,
        "red_count_error": -2.7,
        "mean_predicted_probability": 0.1,
        "eligible_for_pe1": True,
        "eligible_for_final_pe2": False,
        "gain_direction": "zero_equal",
        "baseline_clip_diagnostics": dict(clip),
        "probe_clip_diagnostics": dict(clip),
    }


def _complete_fixture_inputs(plan_digest: str = "a" * 64):
    manifest = load_repaired_measurement_validation_manifest(P261_MANIFEST)
    synthetic = load_synthetic_run_manifest(SYNTHETIC_MANIFEST)
    replicate = golden_full_replicate(manifest=manifest, synthetic=synthetic)
    entries = []
    traces = []
    dataset_digest = "9" * 64
    for fold_index in range(61):
        test_issue = 901 + fold_index
        target = [1] * 6 + [0] * 27
        target_digest = canonical_digest(
            target,
            domain="dehps.m4-p2.formal-fold-target.v1",
        )
        checkpoint_digests = {}
        probe_payloads = {}
        for probe_index, probe_id in enumerate(PROBES):
            state = _fixture_probe_state(probe_id, test_issue, probe_index)
            probabilities = [0.1] * 33
            checkpoint = canonical_digest(
                {
                    "dataset_digest": dataset_digest,
                    "scale_id": replicate.cell.scale_id,
                    "scenario_id": replicate.cell.scenario_id,
                    "replicate_index": replicate.replicate_index,
                    "probe_id": probe_id,
                    "train_start_issue": 1,
                    "train_end_issue": test_issue - 1,
                    "test_issue": test_issue,
                    "probe_state_digest": state["state_digest"],
                    "probabilities": probabilities,
                    "probability_order": "red_numbers_1_to_33",
                    "target_access": "forbidden_before_this_checkpoint",
                    "metric_kernel_digest": METRIC_KERNEL_DIGEST,
                    "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
                    "git_commit": FIXTURE_GIT_COMMIT,
                },
                domain="dehps.m4-p2.formal-prediction-checkpoint.v1",
            )
            metric = _fixture_issue_metric(test_issue, target)
            settlement = canonical_digest(
                {
                    "prediction_checkpoint_digest": checkpoint,
                    "target_digest": target_digest,
                    "metric_kernel_digest": METRIC_KERNEL_DIGEST,
                    "PE1_bits_per_issue": metric[
                        "observed_log_loss_gain_bits_per_issue"
                    ],
                },
                domain="dehps.m4-p2.formal-fold-settlement.v1",
            )
            checkpoint_digests[probe_id] = checkpoint
            probe_payloads[probe_id] = {
                "probe_state": state,
                "probabilities": probabilities,
                "issue_metric": metric,
                "prediction_checkpoint_digest": checkpoint,
                "settlement_digest": settlement,
            }
        entries.append(
            {
                "schema_version": (
                    "dehps-m4-p2-strict-prior-checkpoint-journal-entry.v1"
                ),
                "fold_index": fold_index,
                "test_issue": test_issue,
                "probe_order": list(PROBES),
                "checkpoint_digests": checkpoint_digests,
                "target_access": "forbidden_before_this_persisted_entry",
            }
        )
        traces.append(
            {
                "fold_index": fold_index,
                "train_start_issue": 1,
                "train_end_issue": test_issue - 1,
                "test_issue": test_issue,
                "train_feature_view_digest": "7" * 64,
                "blind_feature_view_digest": "8" * 64,
                "target_digest": target_digest,
                "target_vector": target,
                "probes": probe_payloads,
            }
        )
    journal = canonical_journal_bytes(entries)
    result = {
        **replicate.to_dict(),
        "status": "COMPLETE",
        "actual_outer_fold_count": 61,
        "checkpoint_journal_entry_count": 61,
        "checkpoint_journal_digest": canonical_digest(
            entries,
            domain="dehps.m4-p2.strict-prior-checkpoint-journal.v1",
        ),
        "number_probability_predictions": 61 * 33 * len(PROBES),
        "dataset_digest": dataset_digest,
        "metric_kernel_digest": METRIC_KERNEL_DIGEST,
        "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
        "resampling_kernel_digest": RESAMPLING_KERNEL_DIGEST,
        "git_commit": FIXTURE_GIT_COMMIT,
    }
    evaluation = PythonReferenceEvaluation(
        result_payload=result,
        fold_traces=tuple(traces),
        checkpoint_journal_bytes=journal,
    )
    boundaries = tuple(
        {
            **identity,
            "replicate_digest": "5" * 64,
            "dataset_digest": "6" * 64,
            "train_feature_view_digest": "7" * 64,
            "blind_feature_view_digest": "8" * 64,
            "train_feature_view_payload_digest": "9" * 64,
            "blind_feature_view_payload_digest": "a" * 64,
        }
        for identity in golden_boundary_identity_contract()
    )
    fixture = build_golden_fixture_artifact(
        plan_digest=plan_digest,
        executor_fingerprint_digest="c" * 64,
        golden_source_integrity_identity=GOLDEN_SOURCE_IDENTITY,
        replicate=replicate,
        evaluation=evaluation,
        boundary_snapshots=boundaries,
        parent_digests=("b" * 64,),
    )
    return fixture, journal, replicate, evaluation, boundaries


def _dataset():
    manifest = load_repaired_measurement_validation_manifest(P261_MANIFEST)
    synthetic = load_synthetic_run_manifest(SYNTHETIC_MANIFEST)
    replicate = golden_full_replicate(manifest=manifest, synthetic=synthetic)
    return manifest, generate_evaluation_dataset(
        replicate,
        synthetic=synthetic,
        truth_artifact=None,
        expose_prior_state=True,
    )


def _configs(manifest) -> dict:
    configs = deepcopy(
        json.loads(PREREGISTRATION.read_text(encoding="utf-8"))["probe_models"][
            "hyperparameters"
        ]
    )
    frozen = manifest.payload["frozen_probe_configs"]
    selection_digest = manifest.payload["development_selection_artifact_digest"]
    harness = load_harness_manifest(HARNESS)
    configs["REGULARIZED_LOGISTIC_REGRESSION"] = dict(
        harness.probe("REGULARIZED_LOGISTIC_REGRESSION")
    )
    configs["REGULARIZED_LOGISTIC_REGRESSION"].update(
        {
            "selection_mode": "frozen_development",
            "selected_C": frozen["REGULARIZED_LOGISTIC_REGRESSION"]["selected_C"],
            "C": [frozen["REGULARIZED_LOGISTIC_REGRESSION"]["selected_C"]],
            "development_selection_digest": selection_digest,
        }
    )
    configs["NAIVE_BAYES"].update(
        {
            "selection_mode": "frozen_development",
            "selected_alpha": frozen["NAIVE_BAYES"]["selected_alpha"],
            "alpha": [frozen["NAIVE_BAYES"]["selected_alpha"]],
            "development_selection_digest": selection_digest,
        }
    )
    configs["SHALLOW_CALIBRATED_TREE"].update(
        {
            "selection_mode": "frozen_development",
            "selected_max_depth": frozen["SHALLOW_CALIBRATED_TREE"][
                "selected_max_depth"
            ],
            "selected_min_samples_leaf": frozen["SHALLOW_CALIBRATED_TREE"][
                "selected_min_samples_leaf"
            ],
            "max_depth": [frozen["SHALLOW_CALIBRATED_TREE"]["selected_max_depth"]],
            "min_samples_leaf": [
                frozen["SHALLOW_CALIBRATED_TREE"]["selected_min_samples_leaf"]
            ],
            "development_selection_digest": selection_digest,
        }
    )
    return configs


def _observed_fold(dataset, fold, configs) -> dict:
    training = restrict_to_training_history(
        dataset,
        available_through_issue=fold.train_issues[-1],
    )
    cache = StrictPriorFeatureCache(dataset, include_prior_state=True)
    cache.reveal_training_history(training, through_issue=fold.train_issues[-1])
    train = cache.build_train_feature_view(training, fold.train_issues)
    blind = cache.build_blind_test_feature_view(target_issue=fold.test_issue)
    runtime_cache = ExactProbeRuntimeCache()
    result = {}
    for probe_id in PROBES:
        prepared = prepare_probe(
            probe_id=probe_id,
            dataset=training,
            train_view=train,
            probe_config=configs.get(probe_id, {}),
            outer_test_issue=fold.test_issue,
            train_view_builder=cache.build_train_feature_view,
            runtime_cache=runtime_cache,
        )
        result[probe_id] = {
            "state": prepared.state.to_dict(),
            "probabilities": list(prepared.predict(blind)),
        }
    return {
        "train": train,
        "blind": blind,
        "probes": result,
    }


def test_literal_state_visible_views_match_cache_at_all_forward_boundaries() -> None:
    _manifest, dataset = _dataset()
    reference = PythonReferenceBackend(dataset)
    literal_folds = reference.outer_folds()
    observed_folds = expanding_outer_folds(dataset)
    assert literal_folds == observed_folds
    for index in (0, len(literal_folds) // 2, len(literal_folds) - 1):
        fold = literal_folds[index]
        training = restrict_to_training_history(
            dataset,
            available_through_issue=fold.train_issues[-1],
        )
        cache = StrictPriorFeatureCache(dataset, include_prior_state=True)
        cache.reveal_training_history(training, through_issue=fold.train_issues[-1])
        assert reference.build_train_feature_view(
            reference.training_view(available_through_issue=fold.train_issues[-1]),
            fold.train_issues,
        ) == cache.build_train_feature_view(training, fold.train_issues)
        assert reference.build_blind_test_feature_view(
            target_issue=fold.test_issue
        ) == cache.build_blind_test_feature_view(target_issue=fold.test_issue)


def test_full_view_payload_digests_bind_targets_and_values_beyond_legacy_identity() -> (
    None
):
    _manifest, dataset = _dataset()
    reference = PythonReferenceBackend(dataset)
    fold = reference.outer_folds()[0]
    training = reference.training_view(available_through_issue=fold.train_issues[-1])
    train = reference.build_train_feature_view(training, fold.train_issues)
    blind = reference.build_blind_test_feature_view(target_issue=fold.test_issue)
    changed_targets = (1 - train.targets[0], *train.targets[1:])
    changed_train = replace(train, targets=changed_targets)
    changed_values = (
        (blind.values[0][0] + 1.0, *blind.values[0][1:]),
        *blind.values[1:],
    )
    changed_blind = replace(blind, values=changed_values)
    assert changed_train.feature_view_digest == train.feature_view_digest
    assert changed_blind.feature_view_digest == blind.feature_view_digest
    assert full_train_feature_view_payload_digest(changed_train) != (
        full_train_feature_view_payload_digest(train)
    )
    assert full_blind_feature_view_payload_digest(changed_blind) != (
        full_blind_feature_view_payload_digest(blind)
    )


def test_literal_uncached_probe_predictions_are_bit_exact_at_terminal_fold() -> None:
    manifest, dataset = _dataset()
    configs = _configs(manifest)
    reference = PythonReferenceBackend(dataset)
    fold = reference.outer_folds()[-1]
    literal = reference.evaluate_fold(fold=fold, probe_configs=configs)
    observed = _observed_fold(dataset, fold, configs)
    assert literal["train_feature_view_digest"] == observed["train"].feature_view_digest
    assert literal["blind_feature_view_digest"] == observed["blind"].feature_view_digest
    for probe_id in PROBES:
        assert (
            literal["probes"][probe_id]["probe_state"]
            == observed["probes"][probe_id]["state"]
        )
        assert [
            float64_bits(value)
            for value in literal["probes"][probe_id]["probabilities"]
        ] == [
            float64_bits(value)
            for value in observed["probes"][probe_id]["probabilities"]
        ]


def test_reference_module_has_no_optimized_backend_import() -> None:
    import dehps.research_os.information_theory.measurement_validation.golden_reference as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    forbidden = (
        "feature_cache",
        "runtime_cache",
        "measurement_validation.reference",
        "numba",
    )
    assert not [name for name in imported if any(item in name for item in forbidden)]
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "vectorized_p2_pe1" not in source
    assert "probe_log_loss_bits_per_issue_batch_exact_native" not in source
    boundary_builder = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_reference_boundary_snapshots"
    )
    assert not [
        node
        for node in ast.walk(boundary_builder)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "outer_folds"
    ]


def test_optional_trace_serialization_is_absent_from_default_backend_path() -> None:
    import dehps.research_os.information_theory.measurement_validation.reference as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    parents: dict[ast.AST, ast.AST] = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    trace_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and ast.unparse(node.func) in {"prepared.state.to_dict", "metric.to_dict"}
    ]
    assert len(trace_calls) == 2
    for call in trace_calls:
        ancestors: list[ast.AST] = []
        cursor: ast.AST | None = call
        while cursor in parents:
            cursor = parents[cursor]
            ancestors.append(cursor)
        assert any(
            isinstance(node, ast.If)
            and any(
                marker in ast.unparse(node.test)
                for marker in ("trace", "probe_state_payloads")
            )
            and "is not None" in ast.unparse(node.test)
            for node in ancestors
        )


def test_scalar_permutation_oracle_is_bit_exact_without_vectorized_reduction() -> None:
    from dehps.research_os.information_theory.measurement_validation import (
        golden_reference as golden_module,
    )
    from dehps.research_os.information_theory.measurement_validation.reference import (
        vectorized_p2_pe1,
    )

    generator = np.random.default_rng(20260803)
    probabilities = generator.uniform(0.000001, 0.999999, size=(61, 33))
    targets = np.zeros((61, 33), dtype=np.int8)
    for row in targets:
        row[generator.choice(33, size=6, replace=False)] = 1
    expected = vectorized_p2_pe1(probabilities, targets)
    observed = golden_module._literal_permutation_pe1(probabilities, targets)
    assert expected.view(np.uint64).tolist() == observed.view(np.uint64).tolist()


def test_controlled_migration_publishes_only_attested_executor_event() -> None:
    script = ROOT / "apps/worker-python/scripts/build_m4_v2_additive_manifest.py"
    source = script.read_text(encoding="utf-8")
    tree = ast.parse(source)
    migration_call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_additive_m4_v2_manifest"
    )
    keywords = {item.arg: item.value for item in migration_call.keywords}
    external_events = ast.unparse(keywords["add_external_events"])
    artifact_facts = ast.unparse(keywords["add_artifact_facts"])
    assert "m4-runtime-slot:p2-6-1-released" in external_events
    assert "executor_event" in external_events
    assert "executor_artifact_fact" in artifact_facts
    assert "build_canonical_executor_fingerprint()" in source
    assert (
        source.rindex("args.executor_attestation")
        < source.rindex("args.dry_run_artifact")
        < source.rindex("args.output")
    )


def test_float64_encoding_distinguishes_sign_and_rejects_nonfinite() -> None:
    assert float64_bits(0.0) == "0000000000000000"
    assert float64_bits(-0.0) == "8000000000000000"
    assert float64_bits(0.1) == "3fb999999999999a"
    assert float64_bits(float.fromhex("0x0.0000000000001p-1022")) == (
        "0000000000000001"
    )
    assert float64_bits(float.fromhex("0x1.fffffffffffffp+1023")) == (
        "7fefffffffffffff"
    )
    assert encode_float64_tree({"positive": 0.0}) != encode_float64_tree(
        {"positive": -0.0}
    )
    with pytest.raises(GoldenReferenceError, match="nonfinite"):
        float64_bits(float("nan"))
    with pytest.raises(GoldenReferenceError, match="nonfinite"):
        float64_bits(float("inf"))


def test_executor_fingerprint_is_single_threaded_and_plan_bound(monkeypatch) -> None:
    import dehps.research_os.information_theory.measurement_validation.golden_reference as golden_module

    thread_keys = (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    )
    for key in thread_keys:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(GoldenReferenceError, match="single_thread_environment"):
        build_canonical_executor_fingerprint()
    for key in thread_keys:
        monkeypatch.setenv(key, "1")
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv("NUMBA_OPT", "3")
    with pytest.raises(GoldenReferenceError, match="unset_jit_environment"):
        build_canonical_executor_fingerprint()
    monkeypatch.delenv("NUMBA_OPT")
    monkeypatch.setattr(
        golden_module,
        "threadpool_info",
        lambda: [
            {
                "user_api": "blas",
                "internal_api": "openblas",
                "prefix": "libscipy_openblas",
                "version": "0.3.test",
                "num_threads": 1,
                "threading_layer": "pthreads",
                "architecture": "Haswell",
            }
        ],
    )
    monkeypatch.setattr(golden_module, "_binary_sha256", lambda _path: "e" * 64)
    monkeypatch.setattr(
        golden_module,
        "project_golden_source_integrity_contract",
        lambda _contract: deepcopy(GOLDEN_SOURCE_CONTRACT),
    )
    monkeypatch.setattr(
        golden_module,
        "golden_source_identity_from_contract",
        lambda _contract: dict(GOLDEN_SOURCE_IDENTITY),
    )
    fingerprint = build_canonical_executor_fingerprint()
    assert fingerprint["replay_scope"] == ("same_canonical_executor_fingerprint_only")
    assert fingerprint["jit_environment"] == {}
    exact_numerical_packages = {
        "joblib",
        "llvmlite",
        "narwhals",
        "numba",
        "numpy",
        "orjson",
        "scipy",
        "scikit-learn",
        "threadpoolctl",
    }
    assert set(fingerprint["packages"]) == {
        *exact_numerical_packages - {"scikit-learn"},
        "scikit_learn",
    }
    assert set(fingerprint["distribution_record_sha256"]) == (exact_numerical_packages)
    assert set(fingerprint["distribution_installed_tree_identity"]) == (
        exact_numerical_packages
    )
    assert all(
        identity["file_count"] > 0 and len(identity["installed_tree_digest"]) == 64
        for identity in fingerprint["distribution_installed_tree_identity"].values()
    )
    assert {
        "llvmlite.binding.libllvmlite",
        "numba._helperlib",
        "orjson.orjson",
    } < set(fingerprint["critical_binary_sha256"])
    assert fingerprint["jit_runtime"]["host_cpu_name"]
    assert fingerprint["jit_runtime"]["host_cpu_features"]
    assert fingerprint["jit_runtime"]["numba_codegen_config"] == {
        "disable_jit": 0,
        "cpu_name": None,
        "cpu_features": None,
        "optimization_level": 3,
        "loop_vectorize": 1,
        "slp_vectorize": 0,
        "enable_avx": True,
        "boundscheck": None,
    }
    assert fingerprint["machine_learning_runtime"]["joblib_active_backend"] == {
        "module": "joblib._parallel_backends",
        "qualname": "LokyBackend",
        "configured_n_jobs": None,
        "effective_n_jobs_for_none": 1,
        "nesting_level": 0,
        "inner_max_num_threads": None,
    }
    runtime_plan = {
        "artifact_digest": "a" * 64,
        "oracle_contract": {
            "canonical_executor_fingerprint": {
                "required_fingerprint_digest": fingerprint["artifact_digest"]
            }
        },
    }
    plan = build_golden_reference_plan_artifact(
        runtime_plan,
        executor_fingerprint=fingerprint,
        construction_source_integrity_identity=CONSTRUCTION_SOURCE_IDENTITY,
    )
    assert plan["executor_fingerprint_digest"] == fingerprint["artifact_digest"]
    assert (
        plan["construction_source_integrity_identity"] == CONSTRUCTION_SOURCE_IDENTITY
    )
    assert plan["golden_source_integrity_contract"] == GOLDEN_SOURCE_CONTRACT
    assert plan["golden_source_integrity_identity"] == GOLDEN_SOURCE_IDENTITY
    assert plan["boundary_suite"]["replicate_index"] == 0
    assert plan["boundary_suite"]["identity_count"] == 45
    assert len(plan["boundary_suite"]["identities"]) == 45
    assert plan["boundary_suite"]["identity_schedule_digest"] == canonical_digest(
        plan["boundary_suite"]["identities"],
        domain="dehps.m4-p2-9.golden-boundary-identity-schedule.v1",
    )
    assert set(CONSTRUCTION_SOURCE_IDENTITY.values()) < set(plan["parent_digests"])
    assert set(GOLDEN_SOURCE_IDENTITY.values()) < set(plan["parent_digests"])
    assert plan["oracle_contract"]["immutable_golden_fixture_is_oracle"] is True
    assert plan["oracle_contract"]["acceleration_boundary_independence_scope"] == (
        "literal_behavior_path_and_fresh_import_closure"
    )
    assert plan["oracle_contract"]["oracle_construction_process_isolated"] is False
    assert (
        plan["oracle_contract"]["oracle_construction_fully_implementation_independent"]
        is False
    )
    executor_attestation = golden_module.build_canonical_executor_event_attestation(
        runtime_plan,
        executor_fingerprint=fingerprint,
        construction_source_integrity_identity=CONSTRUCTION_SOURCE_IDENTITY,
    )
    assert executor_attestation["external_event"] == (
        f"m4-canonical-executor:{fingerprint['artifact_digest']}"
    )
    assert executor_attestation["import_performed"] is False
    assert (
        executor_attestation["construction_source_integrity_identity"]
        == CONSTRUCTION_SOURCE_IDENTITY
    )
    assert set(CONSTRUCTION_SOURCE_IDENTITY.values()) < set(
        executor_attestation["parent_digests"]
    )
    attestation_identity = dict(executor_attestation)
    attestation_digest = attestation_identity.pop("artifact_digest")
    assert attestation_digest == canonical_digest(
        attestation_identity,
        domain="dehps.m4-p2-9.canonical-executor-event-attestation.v1",
    )
    noncanonical_plan = deepcopy(runtime_plan)
    noncanonical_plan["oracle_contract"]["canonical_executor_fingerprint"][
        "required_fingerprint_digest"
    ] = ("d" * 64)
    with pytest.raises(GoldenReferenceError, match="not_canonical"):
        build_golden_reference_plan_artifact(
            noncanonical_plan,
            executor_fingerprint=fingerprint,
            construction_source_integrity_identity=CONSTRUCTION_SOURCE_IDENTITY,
        )
    tampered = deepcopy(fingerprint)
    tampered["packages"]["numpy"] = "changed"
    with pytest.raises(GoldenReferenceError, match="fingerprint_invalid"):
        build_golden_reference_plan_artifact(
            runtime_plan,
            executor_fingerprint=tampered,
            construction_source_integrity_identity=CONSTRUCTION_SOURCE_IDENTITY,
        )
    with pytest.raises(GoldenReferenceError, match="attestation_invalid"):
        golden_module.build_canonical_executor_event_attestation(
            runtime_plan,
            executor_fingerprint=tampered,
            construction_source_integrity_identity=CONSTRUCTION_SOURCE_IDENTITY,
        )


def test_exact_attestation_rejects_metric_and_journal_byte_drift() -> None:
    reference, journal, *_ = _complete_fixture_inputs()
    attestation = build_exact_golden_attestation(
        plan_digest="a" * 64,
        reference_payload=reference,
        observed_payload=deepcopy(reference),
        reference_journal_bytes=journal,
        observed_journal_bytes=journal,
    )
    assert attestation["status"] == "EXACT_GOLDEN_REPLAY_VERIFIED"
    changed_metric = deepcopy(reference)
    changed_metric["fold_traces"][0]["probes"][PROBES[0]]["issue_metric"][
        "brier_gain_per_issue"
    ] = {"float64_bits": float64_bits(0.0)}
    with pytest.raises(GoldenReferenceError, match="payload_mismatch"):
        build_exact_golden_attestation(
            plan_digest="a" * 64,
            reference_payload=reference,
            observed_payload=changed_metric,
            reference_journal_bytes=journal,
            observed_journal_bytes=journal,
        )
    with pytest.raises(GoldenReferenceError, match="journal_bytes_mismatch"):
        build_exact_golden_attestation(
            plan_digest="a" * 64,
            reference_payload=reference,
            observed_payload=deepcopy(reference),
            reference_journal_bytes=journal,
            observed_journal_bytes=journal.removesuffix(b"\n"),
        )


def test_fixture_digest_is_the_registered_attestation_identity() -> None:
    fixture, journal, *_ = _complete_fixture_inputs()
    assert set(fixture["parent_digests"]) == {
        "a" * 64,
        "b" * 64,
        *GOLDEN_SOURCE_IDENTITY.values(),
    }
    attestation = build_exact_golden_attestation(
        plan_digest="a" * 64,
        reference_payload=fixture,
        observed_payload=deepcopy(fixture),
        reference_journal_bytes=journal,
        observed_journal_bytes=journal,
    )
    assert attestation["fixture_artifact_digest"] == fixture["artifact_digest"]
    assert attestation["golden_source_integrity_identity"] == GOLDEN_SOURCE_IDENTITY
    assert set(GOLDEN_SOURCE_IDENTITY.values()) < set(attestation["parent_digests"])
    tampered = deepcopy(fixture)
    tampered["artifact_digest"] = "0" * 64
    with pytest.raises(GoldenReferenceError, match="fixture_digest_mismatch"):
        build_exact_golden_attestation(
            plan_digest="a" * 64,
            reference_payload=tampered,
            observed_payload=deepcopy(tampered),
            reference_journal_bytes=journal,
            observed_journal_bytes=journal,
        )


def test_superseding_acceleration_plan_reuses_registered_fixture_parents() -> None:
    fixture, _, replicate, evaluation, boundaries = _complete_fixture_inputs()
    observed = build_golden_fixture_artifact(
        plan_digest=str(fixture["benchmark_plan_digest"]),
        executor_fingerprint_digest=str(fixture["executor_fingerprint_digest"]),
        golden_source_integrity_identity=GOLDEN_SOURCE_IDENTITY,
        replicate=replicate,
        evaluation=evaluation,
        boundary_snapshots=boundaries,
        # A new runtime plan has different construction5 provenance.  Runtime
        # correctness must reuse the registered immutable fixture lineage,
        # not inject the superseding runtime-plan digest here.
        parent_digests=tuple(fixture["parent_digests"]),
    )
    assert observed == fixture

    incorrectly_reparented = build_golden_fixture_artifact(
        plan_digest=str(fixture["benchmark_plan_digest"]),
        executor_fingerprint_digest=str(fixture["executor_fingerprint_digest"]),
        golden_source_integrity_identity=GOLDEN_SOURCE_IDENTITY,
        replicate=replicate,
        evaluation=evaluation,
        boundary_snapshots=boundaries,
        parent_digests=("d" * 64,),
    )
    assert incorrectly_reparented["artifact_digest"] != fixture["artifact_digest"]


def test_fixture_builder_and_attestation_reject_incomplete_or_unbound_data() -> None:
    fixture, journal, replicate, evaluation, boundaries = _complete_fixture_inputs()
    incomplete = PythonReferenceEvaluation(
        result_payload=evaluation.result_payload,
        fold_traces=(),
        checkpoint_journal_bytes=b"",
    )
    with pytest.raises(GoldenReferenceError, match="journal_not_utf8_lf"):
        build_golden_fixture_artifact(
            plan_digest="a" * 64,
            executor_fingerprint_digest="c" * 64,
            golden_source_integrity_identity=GOLDEN_SOURCE_IDENTITY,
            replicate=replicate,
            evaluation=incomplete,
            boundary_snapshots=boundaries,
        )
    wrong_result = deepcopy(dict(evaluation.result_payload))
    wrong_result["artifact_digest"] = "0" * 64
    with pytest.raises(GoldenReferenceError, match="result_identity_mismatch"):
        build_golden_fixture_artifact(
            plan_digest="a" * 64,
            executor_fingerprint_digest="c" * 64,
            golden_source_integrity_identity=GOLDEN_SOURCE_IDENTITY,
            replicate=replicate,
            evaluation=PythonReferenceEvaluation(
                result_payload=wrong_result,
                fold_traces=evaluation.fold_traces,
                checkpoint_journal_bytes=journal,
            ),
            boundary_snapshots=boundaries,
        )
    with pytest.raises(GoldenReferenceError, match="fixture_type_invalid"):
        build_exact_golden_attestation(
            plan_digest="a" * 64,
            reference_payload={"artifact_type": "not-a-fixture"},
            observed_payload={"artifact_type": "not-a-fixture"},
            reference_journal_bytes=b"",
            observed_journal_bytes=b"",
        )
    wrong_source_identity = deepcopy(fixture)
    wrong_source_identity["golden_source_integrity_identity"].pop(
        "shared_frozen_source_set_digest"
    )
    with pytest.raises(GoldenReferenceError, match="source_identity_invalid"):
        build_exact_golden_attestation(
            plan_digest="a" * 64,
            reference_payload=wrong_source_identity,
            observed_payload=deepcopy(wrong_source_identity),
            reference_journal_bytes=journal,
            observed_journal_bytes=journal,
        )
    wrong_plan = deepcopy(fixture)
    wrong_plan["benchmark_plan_digest"] = "c" * 64
    with pytest.raises(GoldenReferenceError, match="fixture_plan_mismatch"):
        build_exact_golden_attestation(
            plan_digest="a" * 64,
            reference_payload=wrong_plan,
            observed_payload=deepcopy(wrong_plan),
            reference_journal_bytes=journal,
            observed_journal_bytes=journal,
        )
