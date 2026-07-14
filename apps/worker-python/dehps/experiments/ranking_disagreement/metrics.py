from __future__ import annotations

from typing import Any

import numpy as np

from dehps.experiments.ranking_disagreement.models import METRICS_VERSION


TOP_KS = (100, 1000, 10000)
TAILS = (750000, 900000, 1000000)


def evaluate_selection(
    *,
    selection_key: str,
    candidate_indices: np.ndarray,
    rank_mean: np.ndarray,
    target_index: int,
    combination_count: int,
) -> dict[str, Any]:
    if candidate_indices.ndim != 1:
        raise ValueError("candidate indices must be a one-dimensional array")
    if candidate_indices.size == 0:
        raise ValueError(f"{selection_key} produced zero candidates")
    if np.unique(candidate_indices).size != candidate_indices.size:
        raise ValueError(f"{selection_key} produced duplicate candidates")
    if int(candidate_indices.min()) < 0 or int(candidate_indices.max()) >= combination_count:
        raise ValueError(f"{selection_key} produced out-of-range candidate indices")
    selected_ranks = rank_mean[candidate_indices]
    target_rank = float(rank_mean[target_index])
    target_hit = bool(np.any(candidate_indices == target_index))
    return {
        "version": METRICS_VERSION,
        "selection_key": selection_key,
        "candidate_count": int(candidate_indices.size),
        "exact_target_rank": target_rank,
        "target_hit": target_hit,
        "top_100_hits": bool(target_hit and target_rank <= 100),
        "top_1000_hits": bool(target_hit and target_rank <= 1000),
        "top_10000_hits": bool(target_hit and target_rank <= 10000),
        "median_rank": float(np.median(selected_ranks)),
        "mean_rank": float(np.mean(selected_ranks)),
        "p95_rank": float(np.quantile(selected_ranks, 0.95, method="linear")),
        "worst_rank": float(np.max(selected_ranks)),
        "mean_reciprocal_rank": float(np.mean(1.0 / np.maximum(selected_ranks, 1.0))),
        "tail_over_750000": int(np.sum(selected_ranks > min(750000, combination_count))),
        "tail_over_900000": int(np.sum(selected_ranks > min(900000, combination_count))),
        "tail_over_1000000": int(np.sum(selected_ranks > min(1000000, combination_count))),
    }


def add_baseline_lift(stratum_metrics: dict[str, Any], baseline_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    lifted = dict(stratum_metrics)
    base = {}
    for key, metrics in baseline_metrics.items():
        base[key] = int(bool(stratum_metrics["target_hit"])) - int(bool(metrics["target_hit"]))
    lifted["baseline_lift"] = base
    return lifted
