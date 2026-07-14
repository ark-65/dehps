from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from dehps.experiments.ranking_disagreement.models import STATISTICS_VERSION, STRATA_KEYS, BASELINE_KEYS


def summarize_statistics(per_issue_results: list[dict[str, Any]], *, seed: int = 24024) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    comparisons: list[dict[str, Any]] = []
    for stratum in STRATA_KEYS:
        stratum_hits = np.asarray(
            [int(item["strata"][stratum]["target_hit"]) for item in per_issue_results],
            dtype=np.float64,
        )
        for baseline in BASELINE_KEYS:
            baseline_hits = np.asarray(
                [int(item["baselines"][stratum][baseline]["target_hit"]) for item in per_issue_results],
                dtype=np.float64,
            )
            diff = stratum_hits - baseline_hits
            comparisons.append(
                {
                    "stratum": stratum,
                    "baseline": baseline,
                    "paired_rank_difference": float(np.mean(diff)),
                    "bootstrap_confidence_interval": _bootstrap_ci(diff, rng),
                    "permutation_null": _sign_flip_p_value(diff),
                    "effect_size": _effect_size(diff),
                }
            )
    adjusted = _holm_adjust([item["permutation_null"]["p_value"] for item in comparisons])
    for item, p_value in zip(comparisons, adjusted, strict=True):
        item["multiple_comparison_adjusted_p_value"] = float(p_value)
    return {
        "version": STATISTICS_VERSION,
        "issue_count": len(per_issue_results),
        "comparisons": comparisons,
        "stratum_stability": _stratum_stability(per_issue_results),
        "direction_consistency": _direction_consistency(comparisons),
        "seed": seed,
    }


def aggregate_results(per_issue_results: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate: dict[str, Any] = {"issue_count": len(per_issue_results), "strata": {}, "baselines": {}}
    for stratum in STRATA_KEYS:
        hits = [int(item["strata"][stratum]["target_hit"]) for item in per_issue_results]
        counts = [int(item["strata"][stratum]["candidate_count"]) for item in per_issue_results]
        aggregate["strata"][stratum] = {
            "target_hit_count": int(sum(hits)),
            "target_hit_rate": float(np.mean(hits)) if hits else 0.0,
            "mean_candidate_count": float(np.mean(counts)) if counts else 0.0,
        }
        aggregate["baselines"][stratum] = {}
        for baseline in BASELINE_KEYS:
            baseline_hits = [int(item["baselines"][stratum][baseline]["target_hit"]) for item in per_issue_results]
            baseline_counts = [int(item["baselines"][stratum][baseline]["candidate_count"]) for item in per_issue_results]
            aggregate["baselines"][stratum][baseline] = {
                "target_hit_count": int(sum(baseline_hits)),
                "target_hit_rate": float(np.mean(baseline_hits)) if baseline_hits else 0.0,
                "mean_candidate_count": float(np.mean(baseline_counts)) if baseline_counts else 0.0,
                "baseline_lift": float(np.mean(np.asarray(hits) - np.asarray(baseline_hits)))
                if hits
                else 0.0,
            }
    return aggregate


def _bootstrap_ci(values: np.ndarray, rng: np.random.Generator, *, samples: int = 500) -> dict[str, float]:
    if values.size == 0:
        return {"low": 0.0, "high": 0.0}
    means = np.empty(samples, dtype=np.float64)
    for index in range(samples):
        means[index] = rng.choice(values, size=values.size, replace=True).mean()
    return {
        "low": float(np.quantile(means, 0.025, method="linear")),
        "high": float(np.quantile(means, 0.975, method="linear")),
    }


def _sign_flip_p_value(values: np.ndarray) -> dict[str, float | int]:
    if values.size == 0 or np.all(values == 0):
        return {"method": "fixed_sign_flip", "p_value": 1.0, "sample_count": int(values.size)}
    observed = abs(float(values.mean()))
    rng = np.random.default_rng(240240)
    samples = 1000
    null = np.empty(samples, dtype=np.float64)
    for index in range(samples):
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=values.size, replace=True)
        null[index] = abs(float((values * signs).mean()))
    p_value = (np.sum(null >= observed) + 1) / (samples + 1)
    return {"method": "fixed_sign_flip", "p_value": float(p_value), "sample_count": samples}


def _effect_size(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    std = float(values.std(ddof=0))
    if std == 0.0:
        return 0.0
    return float(values.mean() / std)


def _holm_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values), dtype=np.float64)
    running = 0.0
    m = len(p_values)
    for rank, index in enumerate(order):
        value = min(1.0, float(p_values[index]) * (m - rank))
        running = max(running, value)
        adjusted[index] = running
    return adjusted.tolist()


def _stratum_stability(per_issue_results: list[dict[str, Any]]) -> dict[str, float]:
    counts_by_stratum: dict[str, list[int]] = defaultdict(list)
    for item in per_issue_results:
        for stratum in STRATA_KEYS:
            counts_by_stratum[stratum].append(int(item["strata"][stratum]["candidate_count"]))
    return {
        stratum: float(np.std(values) / max(1.0, np.mean(values)))
        for stratum, values in counts_by_stratum.items()
    }


def _direction_consistency(comparisons: list[dict[str, Any]]) -> dict[str, int]:
    positive = sum(1 for item in comparisons if item["paired_rank_difference"] > 0)
    negative = sum(1 for item in comparisons if item["paired_rank_difference"] < 0)
    zero = len(comparisons) - positive - negative
    return {"positive": positive, "negative": negative, "zero": zero}
