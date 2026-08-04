"""Strict deterministic P2.3 walk-forward exports with lazy loading."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_ARTIFACTS = "dehps.research_os.information_theory.walk_forward.artifacts"
_CHECKPOINT = "dehps.research_os.information_theory.walk_forward.checkpoint"
_CONTRACTS = "dehps.research_os.information_theory.walk_forward.contracts"
_DATASET = "dehps.research_os.information_theory.walk_forward.dataset"
_ERRORS = "dehps.research_os.information_theory.walk_forward.errors"
_FEATURE_VIEW = "dehps.research_os.information_theory.walk_forward.feature_view"
_HARNESS = "dehps.research_os.information_theory.walk_forward.harness"
_INNER = "dehps.research_os.information_theory.walk_forward.inner_validation"
_MANIFEST = "dehps.research_os.information_theory.walk_forward.manifest"
_PREPROCESSING = "dehps.research_os.information_theory.walk_forward.preprocessing"
_SPLIT = "dehps.research_os.information_theory.walk_forward.split"

_EXPORTS = {
    "aggregate_settlements": (_ARTIFACTS, "aggregate_settlements"),
    "build_run_artifact": (_ARTIFACTS, "build_run_artifact"),
    "settle_fold": (_ARTIFACTS, "settle_fold"),
    "build_prediction_checkpoint": (_CHECKPOINT, "build_prediction_checkpoint"),
    "persist_prediction_checkpoint": (
        _CHECKPOINT,
        "persist_prediction_checkpoint",
    ),
    "prediction_identity": (_CHECKPOINT, "prediction_identity"),
    "validate_prediction_checkpoint": (
        _CHECKPOINT,
        "validate_prediction_checkpoint",
    ),
    **{
        name: (_CONTRACTS, name)
        for name in (
            "FOLD_SCHEMA_VERSION",
            "HARNESS_SCHEMA_VERSION",
            "HARNESS_VERSION",
            "PREDICTION_SCHEMA_VERSION",
            "RUN_SCHEMA_VERSION",
            "SETTLEMENT_SCHEMA_VERSION",
            "BlindTestFeatureView",
            "FoldIdentity",
            "HarnessManifest",
            "InnerFold",
            "OuterFold",
            "PreprocessingState",
            "ProbeState",
            "SyntheticDataset",
            "TrainingDatasetView",
            "TrainFeatureView",
        )
    },
    "load_synthetic_dataset": (_DATASET, "load_synthetic_dataset"),
    "restrict_to_training_history": (_DATASET, "restrict_to_training_history"),
    "reveal_target": (_DATASET, "reveal_target"),
    "validate_synthetic_dataset": (_DATASET, "validate_synthetic_dataset"),
    "WalkForwardError": (_ERRORS, "WalkForwardError"),
    **{
        name: (_FEATURE_VIEW, name)
        for name in (
            "FEATURE_MANIFEST_DIGEST",
            "build_blind_test_feature_view",
            "build_fold_views",
            "build_train_feature_view",
            "fold_feature_view_digest",
            "illegal_future_feature_canary",
        )
    },
    "inspect_fold": (_HARNESS, "inspect_fold"),
    "resume_walk_forward": (_HARNESS, "resume_walk_forward"),
    "run_walk_forward": (_HARNESS, "run_walk_forward"),
    "show_run": (_HARNESS, "show_run"),
    "expanding_inner_folds": (_INNER, "expanding_inner_folds"),
    "reject_random_inner_validation": (_INNER, "reject_random_inner_validation"),
    "select_inner_candidate": (_INNER, "select_inner_candidate"),
    "load_harness_manifest": (_MANIFEST, "load_harness_manifest"),
    "validate_harness_manifest": (_MANIFEST, "validate_harness_manifest"),
    "fit_preprocessor": (_PREPROCESSING, "fit_preprocessor"),
    "transform_blind": (_PREPROCESSING, "transform_blind"),
    "transform_train": (_PREPROCESSING, "transform_train"),
    "build_fold_identity": (_SPLIT, "build_fold_identity"),
    "expanding_outer_folds": (_SPLIT, "expanding_outer_folds"),
    "validate_outer_fold": (_SPLIT, "validate_outer_fold"),
}

__all__ = [
    "FEATURE_MANIFEST_DIGEST",
    "FOLD_SCHEMA_VERSION",
    "HARNESS_SCHEMA_VERSION",
    "HARNESS_VERSION",
    "PREDICTION_SCHEMA_VERSION",
    "RUN_SCHEMA_VERSION",
    "SETTLEMENT_SCHEMA_VERSION",
    "BlindTestFeatureView",
    "FoldIdentity",
    "HarnessManifest",
    "InnerFold",
    "OuterFold",
    "PreprocessingState",
    "ProbeState",
    "SyntheticDataset",
    "TrainFeatureView",
    "TrainingDatasetView",
    "WalkForwardError",
    "aggregate_settlements",
    "build_blind_test_feature_view",
    "build_fold_identity",
    "build_fold_views",
    "build_prediction_checkpoint",
    "build_run_artifact",
    "build_train_feature_view",
    "expanding_inner_folds",
    "expanding_outer_folds",
    "fit_preprocessor",
    "fold_feature_view_digest",
    "illegal_future_feature_canary",
    "inspect_fold",
    "load_harness_manifest",
    "load_synthetic_dataset",
    "persist_prediction_checkpoint",
    "prediction_identity",
    "reject_random_inner_validation",
    "restrict_to_training_history",
    "resume_walk_forward",
    "reveal_target",
    "run_walk_forward",
    "select_inner_candidate",
    "settle_fold",
    "show_run",
    "transform_blind",
    "transform_train",
    "validate_harness_manifest",
    "validate_outer_fold",
    "validate_prediction_checkpoint",
    "validate_synthetic_dataset",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
