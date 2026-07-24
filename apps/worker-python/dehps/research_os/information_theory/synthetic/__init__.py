"""P2.1 synthetic contracts and the exact uniform SSQ null generator."""

from .contracts import (
    DATASET_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    TRUTH_SCHEMA_VERSION,
    SyntheticDatasetArtifact,
    SyntheticIssue,
    SyntheticRunManifest,
    SyntheticScale,
    SyntheticScenario,
    SyntheticTruth,
)
from .generator import (
    full_combination_probability,
    generate_null_dataset,
    legal_combination_count,
    number_marginal_probability,
    pair_marginal_probability,
)
from .validation import load_synthetic_run_manifest, validate_synthetic_run_manifest

__all__ = [
    "DATASET_SCHEMA_VERSION",
    "RUN_SCHEMA_VERSION",
    "SCENARIO_SCHEMA_VERSION",
    "TRUTH_SCHEMA_VERSION",
    "SyntheticDatasetArtifact",
    "SyntheticIssue",
    "SyntheticRunManifest",
    "SyntheticScale",
    "SyntheticScenario",
    "SyntheticTruth",
    "full_combination_probability",
    "generate_null_dataset",
    "legal_combination_count",
    "load_synthetic_run_manifest",
    "number_marginal_probability",
    "pair_marginal_probability",
    "validate_synthetic_run_manifest",
]
