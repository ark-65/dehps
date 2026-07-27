from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from dehps.contracts import canonical_digest

from .contracts import CONTROL_IDS, ResamplingError, ResamplingKernelManifest
from .plans import _derive


def negative_control_registry(
    manifest: ResamplingKernelManifest,
) -> dict[str, Mapping[str, Any]]:
    registry = {
        str(item["control_id"]): dict(item) for item in manifest.controls
    }
    if tuple(registry) != CONTROL_IDS:
        raise ResamplingError(
            "negative_control_semantic_failure",
            "registry does not contain the six frozen controls in order",
        )
    return registry


def apply_number_mapping(
    issue: Mapping[str, Any],
    mapping: Mapping[int, int],
) -> dict[str, Any]:
    if set(mapping) != set(range(1, 34)) or set(mapping.values()) != set(range(1, 34)):
        raise ResamplingError("invalid_permutation_mapping", "number mapping is not a 1..33 bijection")
    target = issue.get("target_vector")
    numbers = issue.get("sorted_red_numbers")
    if not isinstance(target, list) or len(target) != 33 or not isinstance(numbers, list):
        raise ResamplingError("issue_cluster_split", "number mapping requires a complete issue")
    mapped_numbers = sorted(mapping[int(number)] for number in numbers)
    mapped_target = [0] * 33
    for number in mapped_numbers:
        mapped_target[number - 1] = 1
    result = dict(issue)
    result["sorted_red_numbers"] = mapped_numbers
    result["target_vector"] = mapped_target
    result["red_mask"] = sum(1 << (number - 1) for number in mapped_numbers)
    probabilities = issue.get("probabilities")
    if isinstance(probabilities, list) and len(probabilities) == 33:
        mapped_probabilities = [0.0] * 33
        for source_number, target_number in mapping.items():
            mapped_probabilities[target_number - 1] = float(
                probabilities[source_number - 1]
            )
        result["probabilities"] = mapped_probabilities
    return result


def matched_random_features(
    features: np.ndarray,
    *,
    missing_mask: np.ndarray | None,
    strategy: str,
    source_feature_manifest_digest: str,
    source_provenance: str,
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    replicate_index: int,
    parent_run_digest: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    if source_provenance != "pre_target_feature_view":
        raise ResamplingError(
            "target_dependent_negative_control",
            "matched random features require a pre-target feature view",
        )
    if features.ndim < 2:
        raise ResamplingError("invalid_feature_shape", "matched features require issue x feature shape")
    if missing_mask is not None and missing_mask.shape != features.shape:
        raise ResamplingError("invalid_missingness_pattern", "missing mask shape differs")
    if missing_mask is not None and not np.issubdtype(features.dtype, np.floating):
        raise ResamplingError(
            "invalid_missingness_dtype",
            "missing matched features require a floating dtype",
        )
    rng, seed, seed_digest = _derive(
        manifest=manifest,
        seed_domain="M4_P2_RANDOM_FEATURE",
        scenario_id=scenario_id,
        method_id=f"matched_random_features:{strategy}",
        replicate_index=replicate_index,
        parent_run_digest=parent_run_digest,
    )
    mask = (
        np.zeros(features.shape, dtype=bool)
        if missing_mask is None
        else missing_mask
    )
    result = np.array(features, copy=True)
    if strategy == "independent_matched_noise":
        for column in range(result.shape[1]):
            observed = ~mask[:, column]
            result[observed, column] = rng.permutation(
                features[observed, column]
            )
        temporal = "independent_issue_permutation"
    elif strategy == "block_correlated_matched_noise":
        block = 5
        blocks = [
            np.arange(start, min(start + block, result.shape[0]))
            for start in range(0, result.shape[0], block)
        ]
        order = np.arange(len(blocks))
        if len(blocks) > 1:
            for _ in range(32):
                candidate = rng.permutation(len(blocks))
                if not np.array_equal(candidate, order):
                    order = candidate
                    break
        indices = np.concatenate([blocks[int(index)] for index in order])
        for column in range(result.shape[1]):
            target_positions = np.flatnonzero(~mask[:, column])
            source_positions = indices[~mask[indices, column]]
            result[target_positions, column] = features[
                source_positions, column
            ]
        temporal = "non_circular_block_permutation_L5"
    elif strategy == "permutation_derived_matched_noise":
        indices = rng.permutation(result.shape[0])
        for column in range(result.shape[1]):
            target_positions = np.flatnonzero(~mask[:, column])
            source_positions = indices[~mask[indices, column]]
            result[target_positions, column] = features[
                source_positions, column
            ]
        temporal = "global_issue_permutation"
    else:
        raise ResamplingError("unknown_matching_strategy", strategy)
    if missing_mask is not None:
        result = np.where(mask, np.nan, result)
    metadata = {
        "matching_strategy": strategy,
        "source_feature_manifest_digest": source_feature_manifest_digest,
        "source_provenance": source_provenance,
        "dimension": list(features.shape),
        "dtype": str(features.dtype),
        "missingness_pattern_digest": canonical_digest(
            None if missing_mask is None else missing_mask.astype(int).tolist(),
            domain="dehps.m4-p2.missingness-pattern.v1",
        ),
        "marginal_distribution": "empirical_column_distribution_preserved",
        "temporal_correlation_rule": temporal,
        "seed": seed,
        "seed_digest": seed_digest,
        "target_access": "forbidden_by_function_signature",
    }
    return result, metadata


def matched_random_score(
    scores: Sequence[float],
    *,
    strategy: str,
    source_provenance: str,
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    replicate_index: int,
    parent_run_digest: str,
) -> tuple[tuple[float, ...], dict[str, Any]]:
    if source_provenance not in {
        "pre_target_probe_score",
        "synthetic_probe_score",
    }:
        raise ResamplingError(
            "target_dependent_random_score",
            "matched random score source must be independent of target settlement",
        )
    if not scores:
        raise ResamplingError("empty_score_source", "matched score source is empty")
    rng, seed, seed_digest = _derive(
        manifest=manifest,
        seed_domain="M4_P2_RANDOM_SCORE",
        scenario_id=scenario_id,
        method_id=f"matched_random_score:{strategy}",
        replicate_index=replicate_index,
        parent_run_digest=parent_run_digest,
    )
    values = np.asarray(scores, dtype=float)
    if not np.all(np.isfinite(values)):
        raise ResamplingError("nan_statistic", "score source must be finite")
    if strategy == "rank_distribution":
        result = rng.permutation(values)
    elif strategy == "quantile_distribution":
        uniforms = (np.arange(len(values)) + 0.5) / len(values)
        result = np.quantile(values, uniforms, method="linear")
        result = result[rng.permutation(len(result))]
    elif strategy == "issue_mean_variance":
        standardized = (rng.standard_normal(len(values)) - 0.0)
        result = standardized * float(values.std()) + float(values.mean())
    else:
        raise ResamplingError("unknown_matching_strategy", strategy)
    metadata = {
        "matching_strategy": strategy,
        "source_provenance": source_provenance,
        "dimension": len(values),
        "source_mean": float(values.mean()),
        "source_variance": float(values.var()),
        "seed": seed,
        "seed_digest": seed_digest,
        "target_access": "forbidden_by_function_signature",
        "forbidden_inputs": ["target", "PE1", "Brier", "hit_rank", "settlement"],
    }
    return tuple(float(value) for value in result), metadata
