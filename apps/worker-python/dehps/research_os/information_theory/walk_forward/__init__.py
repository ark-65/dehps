"""Strict deterministic P2.3 synthetic walk-forward harness."""

from .artifacts import aggregate_settlements, build_run_artifact, settle_fold
from .checkpoint import (
    build_prediction_checkpoint,
    persist_prediction_checkpoint,
    prediction_identity,
    validate_prediction_checkpoint,
)
from .contracts import (
    FOLD_SCHEMA_VERSION,
    HARNESS_SCHEMA_VERSION,
    HARNESS_VERSION,
    PREDICTION_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SETTLEMENT_SCHEMA_VERSION,
    BlindTestFeatureView,
    FoldIdentity,
    HarnessManifest,
    InnerFold,
    OuterFold,
    PreprocessingState,
    ProbeState,
    SyntheticDataset,
    TrainingDatasetView,
    TrainFeatureView,
)
from .dataset import (
    load_synthetic_dataset,
    restrict_to_training_history,
    reveal_target,
    validate_synthetic_dataset,
)
from .errors import WalkForwardError
from .feature_view import (
    FEATURE_MANIFEST_DIGEST,
    build_blind_test_feature_view,
    build_fold_views,
    build_train_feature_view,
    fold_feature_view_digest,
    illegal_future_feature_canary,
)
from .harness import inspect_fold, resume_walk_forward, run_walk_forward, show_run
from .inner_validation import (
    expanding_inner_folds,
    reject_random_inner_validation,
    select_inner_candidate,
)
from .manifest import load_harness_manifest, validate_harness_manifest
from .preprocessing import fit_preprocessor, transform_blind, transform_train
from .split import build_fold_identity, expanding_outer_folds, validate_outer_fold

__all__ = [
    "FOLD_SCHEMA_VERSION",
    "FEATURE_MANIFEST_DIGEST",
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
    "resume_walk_forward",
    "restrict_to_training_history",
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
