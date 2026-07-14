from __future__ import annotations

import numpy as np

from dehps.experiments.ranking_disagreement.models import (
    FEATURE_VERSION,
    FROZEN_FEATURE_KEYS,
    FeatureFrame,
    RankMatrix,
    array_hash,
    stable_hash,
)


def compute_features(matrix: RankMatrix) -> FeatureFrame:
    ranks = matrix.values.astype(np.float64, copy=False)
    if np.isnan(ranks).any():
        raise ValueError("rank matrix contains missing ranks")

    rank_mean = ranks.mean(axis=1)
    rank_median = np.median(ranks, axis=1)
    rank_min = ranks.min(axis=1)
    rank_max = ranks.max(axis=1)
    rank_std = ranks.std(axis=1)
    rank_range = rank_max - rank_min
    pairwise_rank_gap = _pairwise_rank_gap(ranks)
    ranker_order_entropy = _ranker_order_entropy(ranks)

    consensus_band = _band_by_quantile(rank_mean, prefix="consensus")
    disagreement_band = _band_by_quantile(rank_range + rank_std, prefix="disagreement")
    numeric = {
        "rank_mean": rank_mean,
        "rank_median": rank_median,
        "rank_min": rank_min,
        "rank_max": rank_max,
        "rank_std": rank_std,
        "rank_range": rank_range,
        "pairwise_rank_gap": pairwise_rank_gap,
        "ranker_order_entropy": ranker_order_entropy,
    }
    categorical = {
        "consensus_band": consensus_band,
        "disagreement_band": disagreement_band,
    }
    missing = sorted(set(FROZEN_FEATURE_KEYS).difference({*numeric, *categorical}))
    if missing:
        raise ValueError(f"missing frozen feature keys: {missing}")
    fingerprint = stable_hash(
        {
            "version": FEATURE_VERSION,
            "rank_matrix_fingerprint": matrix.fingerprint,
            "numeric_hashes": {key: array_hash(value) for key, value in sorted(numeric.items())},
            "categorical_hashes": {key: array_hash(value) for key, value in sorted(categorical.items())},
        }
    )
    return FeatureFrame(
        combination_ids=matrix.combination_ids.copy(),
        numeric=numeric,
        categorical=categorical,
        as_of_issue=matrix.as_of_issue,
        rank_matrix_fingerprint=matrix.fingerprint,
        feature_fingerprint=fingerprint,
    )


def feature_summary(frame: FeatureFrame) -> dict[str, object]:
    return {
        "version": frame.version,
        "as_of_issue": frame.as_of_issue,
        "feature_fingerprint": frame.feature_fingerprint,
        "rank_matrix_fingerprint": frame.rank_matrix_fingerprint,
        "combination_count": int(frame.combination_ids.shape[0]),
        "numeric": {
            key: {
                "min": float(np.min(value)),
                "mean": float(np.mean(value)),
                "max": float(np.max(value)),
            }
            for key, value in frame.numeric.items()
        },
        "categorical_counts": {
            key: {str(label): int(count) for label, count in zip(*np.unique(value, return_counts=True), strict=True)}
            for key, value in frame.categorical.items()
        },
    }


def _pairwise_rank_gap(ranks: np.ndarray) -> np.ndarray:
    first = np.abs(ranks[:, 0] - ranks[:, 1])
    second = np.abs(ranks[:, 0] - ranks[:, 2])
    third = np.abs(ranks[:, 1] - ranks[:, 2])
    return np.maximum(first, np.maximum(second, third))


def _ranker_order_entropy(ranks: np.ndarray) -> np.ndarray:
    inverse = 1.0 / np.maximum(ranks, 1.0)
    weights = inverse / inverse.sum(axis=1, keepdims=True)
    entropy = -(weights * np.log2(np.maximum(weights, 1e-12))).sum(axis=1)
    return entropy / np.log2(ranks.shape[1])


def _band_by_quantile(values: np.ndarray, *, prefix: str) -> np.ndarray:
    q1, q2, q3 = np.quantile(values, [0.25, 0.50, 0.75], method="linear")
    bands = np.full(values.shape[0], f"{prefix}_extreme", dtype="U24")
    bands[values <= q3] = f"{prefix}_high"
    bands[values <= q2] = f"{prefix}_medium"
    bands[values <= q1] = f"{prefix}_low"
    return bands
