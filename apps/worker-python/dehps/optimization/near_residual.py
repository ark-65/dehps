from __future__ import annotations

from dataclasses import dataclass
from math import comb, exp, log1p

import numpy as np

from dehps.optimization.walk_forward import RankedUniverseMatrix, top_indices_for_scores


@dataclass(frozen=True)
class ResidualBlend:
    scores: np.ndarray
    static_z: np.ndarray
    residual_z: np.ndarray
    metadata: dict[str, float | bool]


def _standardize(values: np.ndarray) -> tuple[np.ndarray, float]:
    centered = values - float(values.mean())
    scale = float(centered.std())
    if scale <= 1e-12:
        return np.zeros_like(centered), scale
    return centered / scale, scale


def orthogonal_residual_blend(
    static_scores: np.ndarray,
    dynamic_scores: np.ndarray,
    *,
    residual_strength: float,
) -> ResidualBlend:
    """Blend static rank with the standardized dynamic residual orthogonal to static score."""
    static = np.asarray(static_scores, dtype=np.float64)
    dynamic = np.asarray(dynamic_scores, dtype=np.float64)
    strength = float(residual_strength)
    if static.ndim != 1 or dynamic.ndim != 1 or static.shape != dynamic.shape or not len(static):
        raise ValueError("static_scores and dynamic_scores must be non-empty matching vectors")
    if not np.isfinite(static).all() or not np.isfinite(dynamic).all():
        raise ValueError("score vectors must contain only finite values")
    if not np.isfinite(strength) or strength < 0:
        raise ValueError("residual_strength must be a finite non-negative number")

    static_z, static_scale = _standardize(static)
    delta = dynamic - static
    delta_centered = delta - float(delta.mean())
    denominator = float(np.dot(static_z, static_z))
    beta = float(np.dot(delta_centered, static_z) / denominator) if denominator > 1e-12 else 0.0
    residual = delta_centered - beta * static_z
    residual_z, residual_scale = _standardize(residual)
    before_corr = float(np.corrcoef(static_z, delta_centered)[0, 1]) if static_scale > 1e-12 and float(delta_centered.std()) > 1e-12 else 0.0
    after_corr = float(np.corrcoef(static_z, residual_z)[0, 1]) if static_scale > 1e-12 and residual_scale > 1e-12 else 0.0
    scores = static_z + strength * residual_z
    return ResidualBlend(
        scores=scores,
        static_z=static_z,
        residual_z=residual_z,
        metadata={
            "residual_strength": strength,
            "static_std": static_scale,
            "dynamic_delta_std": float(delta_centered.std()),
            "residual_std": residual_scale,
            "projection_beta": beta,
            "static_delta_correlation": before_corr,
            "static_residual_correlation": after_corr,
            "degenerate_residual": residual_scale <= 1e-12,
        },
    )


def rank_metrics_from_scores(
    *,
    ranked_universe: RankedUniverseMatrix,
    scores: np.ndarray,
    target_numbers: tuple[int, ...],
    top_n: int,
) -> dict[str, int | bool | None]:
    score_vector = np.asarray(scores, dtype=np.float64)
    top_indices = top_indices_for_scores(scores=score_vector, ranked_universe=ranked_universe, top_n=top_n)
    target = np.asarray(target_numbers, dtype=ranked_universe.numbers.dtype)
    exact_rows = np.flatnonzero(np.all(ranked_universe.numbers == target, axis=1))
    exact_rank: int | None = None
    if len(exact_rows):
        row = int(exact_rows[0])
        target_score = float(score_vector[row])
        lex_less = np.zeros(len(ranked_universe), dtype=bool)
        undecided = np.ones(len(ranked_universe), dtype=bool)
        for column, value in enumerate(target_numbers):
            lex_less |= undecided & (ranked_universe.numbers[:, column] < value)
            undecided &= ranked_universe.numbers[:, column] == value
        exact_rank = int((score_vector > target_score).sum() + ((score_vector == target_score) & lex_less).sum() + 1)

    overlaps = ranked_universe.number_presence[top_indices][:, list(target_numbers)].sum(axis=1)
    max_overlap = int(overlaps.max()) if len(overlaps) else 0
    return {
        "exact_rank": exact_rank,
        "max_overlap_top_n": max_overlap,
        "red4_plus_top_n": max_overlap >= 4,
        "red5_plus_top_n": max_overlap >= 5,
        "exact_top_n": exact_rank is not None and exact_rank <= top_n,
    }


def random_top_n_overlap_baseline(*, top_n: int, minimum_overlap: int, universe_size: int = comb(33, 6)) -> float:
    """Exact probability that a uniform sample without replacement contains an overlap hit."""
    matching = sum(comb(6, overlap) * comb(27, 6 - overlap) for overlap in range(minimum_overlap, 7))
    sample = min(max(int(top_n), 0), universe_size)
    if sample == 0 or matching == 0:
        return 0.0
    if sample > universe_size - matching:
        return 1.0
    log_miss = sum(log1p(-matching / (universe_size - offset)) for offset in range(sample))
    return 1.0 - exp(log_miss)
