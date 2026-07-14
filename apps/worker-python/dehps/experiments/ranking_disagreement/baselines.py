from __future__ import annotations

from typing import Any

import numpy as np

from dehps.experiments.ranking_disagreement.metrics import add_baseline_lift, evaluate_selection
from dehps.experiments.ranking_disagreement.models import (
    BASELINE_KEYS,
    BASELINE_VERSION,
    STRATA_KEYS,
    FeatureFrame,
    RankMatrix,
    StrataThresholds,
    stable_hash,
)
from dehps.experiments.ranking_disagreement.strata import assign_strata


def evaluate_strata_and_baselines(
    *,
    frame: FeatureFrame,
    matrix: RankMatrix,
    thresholds: StrataThresholds,
    target_combination_id: int,
    seed: int,
) -> dict[str, Any]:
    labels = assign_strata(frame, thresholds)
    rank_mean = frame.numeric["rank_mean"]
    target_index = target_combination_id - 1
    combination_count = int(frame.combination_ids.shape[0])
    if target_index < 0 or target_index >= combination_count:
        raise ValueError(f"target combination id is outside legal universe for issue: {target_combination_id}")

    strata_results: dict[str, dict[str, Any]] = {}
    baseline_results: dict[str, dict[str, dict[str, Any]]] = {}
    for stratum_index, stratum in enumerate(STRATA_KEYS):
        candidate_indices = np.flatnonzero(labels == stratum).astype(np.int32)
        stratum_metrics = evaluate_selection(
            selection_key=stratum,
            candidate_indices=candidate_indices,
            rank_mean=rank_mean,
            target_index=target_index,
            combination_count=combination_count,
        )
        baselines = _baseline_indices(
            stratum=stratum,
            stratum_index=stratum_index,
            candidate_indices=candidate_indices,
            rank_mean=rank_mean,
            frequency_ranks=matrix.values[:, 0],
            seed=seed,
        )
        baseline_metrics = {
            key: evaluate_selection(
                selection_key=key,
                candidate_indices=indices,
                rank_mean=rank_mean,
                target_index=target_index,
                combination_count=combination_count,
            )
            | {"match_error": float(match_error)}
            for key, (indices, match_error) in baselines.items()
        }
        for key, metrics in baseline_metrics.items():
            if int(metrics["candidate_count"]) != int(stratum_metrics["candidate_count"]):
                raise ValueError(
                    f"baseline {key} budget mismatch for {stratum}: "
                    f"{metrics['candidate_count']} != {stratum_metrics['candidate_count']}"
                )
        strata_results[stratum] = add_baseline_lift(stratum_metrics, baseline_metrics)
        baseline_results[stratum] = baseline_metrics
    return {
        "version": BASELINE_VERSION,
        "baseline_keys": list(BASELINE_KEYS),
        "baseline_hash": stable_hash({"version": BASELINE_VERSION, "keys": BASELINE_KEYS, "seed": seed}),
        "strata": strata_results,
        "baselines": baseline_results,
    }


def _baseline_indices(
    *,
    stratum: str,
    stratum_index: int,
    candidate_indices: np.ndarray,
    rank_mean: np.ndarray,
    frequency_ranks: np.ndarray,
    seed: int,
) -> dict[str, tuple[np.ndarray, float]]:
    budget = int(candidate_indices.size)
    if budget <= 0:
        raise ValueError(f"stratum has zero candidates: {stratum}")
    combination_count = int(rank_mean.shape[0])
    rng = np.random.default_rng(seed + stratum_index)
    random_indices = rng.choice(combination_count, size=budget, replace=False).astype(np.int32)

    candidate_mean_rank = float(np.mean(rank_mean[candidate_indices]))
    rank_matched_indices = _closest_rank_indices(rank_mean, candidate_mean_rank, budget)
    rank_match_error = float(abs(np.mean(rank_mean[rank_matched_indices]) - candidate_mean_rank))

    production_indices = np.flatnonzero(frequency_ranks <= budget).astype(np.int32)
    if production_indices.size != budget:
        raise ValueError(f"current_production_ranker baseline did not produce exact budget for {stratum}")

    return {
        "budget_matched_random": (random_indices, 0.0),
        "rank_matched_consensus": (rank_matched_indices, rank_match_error),
        "current_production_ranker": (production_indices, 0.0),
    }


def _closest_rank_indices(rank_mean: np.ndarray, center: float, budget: int) -> np.ndarray:
    count = int(rank_mean.shape[0])
    if budget >= count:
        return np.arange(count, dtype=np.int32)
    distance = np.abs(rank_mean - center)
    indices = np.argpartition(distance, budget - 1)[:budget].astype(np.int32)
    # Stable order for deterministic artifacts.
    order = np.lexsort((indices, distance[indices]))
    return indices[order]
