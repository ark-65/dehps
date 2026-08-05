"""P2.6 measurement-validation exports behind a lazy import boundary.

The literal golden module must be independently importable without importing
the mutable feature, journal, or runtime-cache acceleration modules. Public
package imports retain their existing API through PEP 562.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_CONTRACTS = "dehps.research_os.information_theory.measurement_validation.contracts"
_COORDINATOR = "dehps.research_os.information_theory.measurement_validation.coordinator"
_DATASET = "dehps.research_os.information_theory.measurement_validation.dataset"
_EXECUTOR = "dehps.research_os.information_theory.measurement_validation.executor"
_FEATURE_CACHE = (
    "dehps.research_os.information_theory.measurement_validation.feature_cache"
)
_GATE = "dehps.research_os.information_theory.measurement_validation.gate"
_GOLDEN = "dehps.research_os.information_theory.measurement_validation.golden_reference"
_PERIODIC_REFIT = (
    "dehps.research_os.information_theory.measurement_validation.periodic_refit"
)
_REPAIRED = (
    "dehps.research_os.information_theory.measurement_validation.repaired_contracts"
)
_SCHEDULE = "dehps.research_os.information_theory.measurement_validation.schedule"
_STATISTICS = "dehps.research_os.information_theory.measurement_validation.statistics"

_EXPORTS = {
    "MEASUREMENT_VALIDATION_MANIFEST_DIGEST": (
        _CONTRACTS,
        "MEASUREMENT_VALIDATION_MANIFEST_DIGEST",
    ),
    "MeasurementValidationContractError": (
        _CONTRACTS,
        "MeasurementValidationContractError",
    ),
    "MeasurementValidationManifest": (_CONTRACTS, "MeasurementValidationManifest"),
    "load_measurement_validation_manifest": (
        _CONTRACTS,
        "load_measurement_validation_manifest",
    ),
    "validate_measurement_validation_manifest": (
        _CONTRACTS,
        "validate_measurement_validation_manifest",
    ),
    "CoordinatorResult": (_COORDINATOR, "CoordinatorResult"),
    "run_parallel_execution": (_COORDINATOR, "run_parallel_execution"),
    "generate_evaluation_dataset": (_DATASET, "generate_evaluation_dataset"),
    "locate_repaired_truth_artifacts": (
        _DATASET,
        "locate_repaired_truth_artifacts",
    ),
    "locate_truth_artifacts": (_DATASET, "locate_truth_artifacts"),
    "CompletionResult": (_EXECUTOR, "CompletionResult"),
    "ReplicateEvaluator": (_EXECUTOR, "ReplicateEvaluator"),
    "ShardRunResult": (_EXECUTOR, "ShardRunResult"),
    "assemble_completion": (_EXECUTOR, "assemble_completion"),
    "run_shard": (_EXECUTOR, "run_shard"),
    "verify_completion_replay": (_EXECUTOR, "verify_completion_replay"),
    "StrictPriorFeatureCache": (_FEATURE_CACHE, "StrictPriorFeatureCache"),
    "PASS_FACT": (_GATE, "PASS_FACT"),
    "REPAIR_FACT": (_GATE, "REPAIR_FACT"),
    "aggregate_cell": (_GATE, "aggregate_cell"),
    "build_mde_summary": (_GATE, "build_mde_summary"),
    "evaluate_automatic_gate": (_GATE, "evaluate_automatic_gate"),
    "FIXTURE_GIT_COMMIT": (_GOLDEN, "FIXTURE_GIT_COMMIT"),
    "FIXTURE_PARENT_EXECUTION_ID": (_GOLDEN, "FIXTURE_PARENT_EXECUTION_ID"),
    "FLOAT64_ENCODING": (_GOLDEN, "FLOAT64_ENCODING"),
    "GoldenReferenceError": (_GOLDEN, "GoldenReferenceError"),
    "LiteralCheckpointJournal": (_GOLDEN, "LiteralCheckpointJournal"),
    "PythonReferenceBackend": (_GOLDEN, "PythonReferenceBackend"),
    "PythonReferenceEvaluation": (_GOLDEN, "PythonReferenceEvaluation"),
    "PythonReferenceInputs": (_GOLDEN, "PythonReferenceInputs"),
    "PythonReferenceReplicateEvaluator": (
        _GOLDEN,
        "PythonReferenceReplicateEvaluator",
    ),
    "assert_float64_tree": (_GOLDEN, "assert_float64_tree"),
    "build_canonical_executor_event_attestation": (
        _GOLDEN,
        "build_canonical_executor_event_attestation",
    ),
    "build_canonical_executor_fingerprint": (
        _GOLDEN,
        "build_canonical_executor_fingerprint",
    ),
    "build_exact_golden_attestation": (
        _GOLDEN,
        "build_exact_golden_attestation",
    ),
    "build_golden_fixture_artifact": (_GOLDEN, "build_golden_fixture_artifact"),
    "build_golden_reference_plan_artifact": (
        _GOLDEN,
        "build_golden_reference_plan_artifact",
    ),
    "build_reference_boundary_snapshots": (
        _GOLDEN,
        "build_reference_boundary_snapshots",
    ),
    "canonical_journal_bytes": (_GOLDEN, "canonical_journal_bytes"),
    "encode_float64_tree": (_GOLDEN, "encode_float64_tree"),
    "float64_bits": (_GOLDEN, "float64_bits"),
    "full_blind_feature_view_payload_digest": (
        _GOLDEN,
        "full_blind_feature_view_payload_digest",
    ),
    "full_train_feature_view_payload_digest": (
        _GOLDEN,
        "full_train_feature_view_payload_digest",
    ),
    "golden_boundary_identity_contract": (
        _GOLDEN,
        "golden_boundary_identity_contract",
    ),
    "golden_full_replicate": (_GOLDEN, "golden_full_replicate"),
    "journal_bytes_sha256": (_GOLDEN, "journal_bytes_sha256"),
    "literal_outer_folds": (_GOLDEN, "literal_outer_folds"),
    "literal_training_view": (_GOLDEN, "literal_training_view"),
    "PERIODIC_REFIT_CONTRACT_DIGEST": (
        _PERIODIC_REFIT,
        "PERIODIC_REFIT_CONTRACT_DIGEST",
    ),
    "PeriodicRefitContract": (_PERIODIC_REFIT, "PeriodicRefitContract"),
    "load_periodic_refit_contract": (
        _PERIODIC_REFIT,
        "load_periodic_refit_contract",
    ),
    "REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST": (
        _REPAIRED,
        "REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST",
    ),
    "load_repaired_measurement_validation_manifest": (
        _REPAIRED,
        "load_repaired_measurement_validation_manifest",
    ),
    "AnalysisCell": (_SCHEDULE, "AnalysisCell"),
    "AnalysisReplicate": (_SCHEDULE, "AnalysisReplicate"),
    "ShardAssignment": (_SCHEDULE, "ShardAssignment"),
    "assign_shard": (_SCHEDULE, "assign_shard"),
    "build_cells": (_SCHEDULE, "build_cells"),
    "build_replicate": (_SCHEDULE, "build_replicate"),
    "execution_plan_summary": (_SCHEDULE, "execution_plan_summary"),
    "iter_replicates": (_SCHEDULE, "iter_replicates"),
    "bca_interval": (_STATISTICS, "bca_interval"),
    "block_permutation_statistics": (_STATISTICS, "block_permutation_statistics"),
    "delete_contiguous_block_jackknife": (
        _STATISTICS,
        "delete_contiguous_block_jackknife",
    ),
    "holm_adjust": (_STATISTICS, "holm_adjust"),
    "moving_block_bootstrap_statistics": (
        _STATISTICS,
        "moving_block_bootstrap_statistics",
    ),
    "primary_inference": (_STATISTICS, "primary_inference"),
    "seed_set_digest": (_STATISTICS, "seed_set_digest"),
    "type7_quantile": (_STATISTICS, "type7_quantile"),
    "wilson_interval": (_STATISTICS, "wilson_interval"),
}

__all__ = [
    "FIXTURE_GIT_COMMIT",
    "FIXTURE_PARENT_EXECUTION_ID",
    "FLOAT64_ENCODING",
    "MEASUREMENT_VALIDATION_MANIFEST_DIGEST",
    "PASS_FACT",
    "PERIODIC_REFIT_CONTRACT_DIGEST",
    "REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST",
    "REPAIR_FACT",
    "AnalysisCell",
    "AnalysisReplicate",
    "CompletionResult",
    "CoordinatorResult",
    "GoldenReferenceError",
    "LiteralCheckpointJournal",
    "MeasurementValidationContractError",
    "MeasurementValidationManifest",
    "PeriodicRefitContract",
    "PythonReferenceBackend",
    "PythonReferenceEvaluation",
    "PythonReferenceInputs",
    "PythonReferenceReplicateEvaluator",
    "ReplicateEvaluator",
    "ShardAssignment",
    "ShardRunResult",
    "StrictPriorFeatureCache",
    "aggregate_cell",
    "assemble_completion",
    "assert_float64_tree",
    "assign_shard",
    "bca_interval",
    "block_permutation_statistics",
    "build_canonical_executor_event_attestation",
    "build_canonical_executor_fingerprint",
    "build_cells",
    "build_exact_golden_attestation",
    "build_golden_fixture_artifact",
    "build_golden_reference_plan_artifact",
    "build_mde_summary",
    "build_reference_boundary_snapshots",
    "build_replicate",
    "canonical_journal_bytes",
    "delete_contiguous_block_jackknife",
    "encode_float64_tree",
    "evaluate_automatic_gate",
    "execution_plan_summary",
    "float64_bits",
    "full_blind_feature_view_payload_digest",
    "full_train_feature_view_payload_digest",
    "generate_evaluation_dataset",
    "golden_boundary_identity_contract",
    "golden_full_replicate",
    "holm_adjust",
    "iter_replicates",
    "journal_bytes_sha256",
    "literal_outer_folds",
    "literal_training_view",
    "load_measurement_validation_manifest",
    "load_periodic_refit_contract",
    "load_repaired_measurement_validation_manifest",
    "locate_repaired_truth_artifacts",
    "locate_truth_artifacts",
    "moving_block_bootstrap_statistics",
    "primary_inference",
    "run_parallel_execution",
    "run_shard",
    "seed_set_digest",
    "type7_quantile",
    "validate_measurement_validation_manifest",
    "verify_completion_replay",
    "wilson_interval",
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
