from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from dehps.models.frequency_ranker import FrequencyRankerConfig, HistoryDraw, history_draw_date, history_issue, train_frequency_stats
from dehps.optimization.walk_forward import (
    CONFIG_WEIGHT_FIELDS,
    RankedUniverseMatrix,
    _components_for_matrix,
    _lex_less_than,
    _rank_targets_from_scores,
    _score_matrix,
    _target_scores,
    config_hash,
    is_excluded_red_combination,
)

PRIMARY_WEIGHT_FIELDS = {"structural_weight", "frequency_weight", "omission_weight"}
EPSILON_SCORE_MARGIN = 1e-8
SIMPLIFIED_COMPONENT_NAMES = {
    "structural_score": "structural_weight",
    "frequency_score": "frequency_weight",
    "omission_score": "omission_weight",
    "previous_consecutive_score": "previous_consecutive_weight",
}


@dataclass(frozen=True)
class TargetWeightInversion:
    target_issue: str
    red_numbers: tuple[int, ...]
    current_rank: int
    hit_top10000: bool
    score: float
    rank_margin: int
    base_config_hash: str
    required_delta_config: dict[str, float]
    adjusted_config: dict[str, float]
    adjusted_rank: int | None
    adjusted_hit_top10000: bool
    delta_norm: float
    changed_fields: tuple[str, ...]
    success: bool
    outlier_reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "target_issue": self.target_issue,
            "red_numbers": list(self.red_numbers),
            "current_rank": self.current_rank,
            "hit_top10000": self.hit_top10000,
            "score": self.score,
            "rank_margin": self.rank_margin,
            "base_config_hash": self.base_config_hash,
            "required_delta_config": self.required_delta_config,
            "adjusted_config": self.adjusted_config,
            "adjusted_rank": self.adjusted_rank,
            "adjusted_hit_top10000": self.adjusted_hit_top10000,
            "delta_norm": self.delta_norm,
            "changed_fields": list(self.changed_fields),
            "success": self.success,
            "outlier_reason": self.outlier_reason,
        }


@dataclass(frozen=True)
class TargetInversionCandidate:
    label: str
    config: FrequencyRankerConfig
    delta_config: dict[str, float]

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "config": config_dict(self.config),
            "config_hash": config_hash(self.config),
            "delta_config": self.delta_config,
        }


def config_dict(config: FrequencyRankerConfig) -> dict[str, float]:
    return {field: float(getattr(config, field)) for field in CONFIG_WEIGHT_FIELDS}


def config_vector(config: FrequencyRankerConfig) -> np.ndarray:
    return np.array([float(getattr(config, field)) for field in CONFIG_WEIGHT_FIELDS], dtype=np.float64)


def delta_dict(delta: Sequence[float], *, min_abs: float = 1e-9) -> dict[str, float]:
    return {
        field: round(float(value), 10)
        for field, value in zip(CONFIG_WEIGHT_FIELDS, delta, strict=True)
        if abs(float(value)) > min_abs
    }


def weight_bounds_for_field(field: str) -> tuple[float, float]:
    return (0.0, 1.25) if field in PRIMARY_WEIGHT_FIELDS else (-0.30, 0.30)


def clamp_weight_values(values: dict[str, float]) -> dict[str, float]:
    clamped = dict(values)
    for field in CONFIG_WEIGHT_FIELDS:
        lower, upper = weight_bounds_for_field(field)
        clamped[field] = min(upper, max(lower, float(clamped.get(field, 0.0))))
    return clamped


def apply_delta(base_config: FrequencyRankerConfig, delta: Sequence[float], *, scale: float = 1.0) -> FrequencyRankerConfig:
    values = config_dict(base_config)
    for field, value in zip(CONFIG_WEIGHT_FIELDS, delta, strict=True):
        values[field] += float(value) * scale
    return FrequencyRankerConfig(**clamp_weight_values(values))


def delta_between(base_config: FrequencyRankerConfig, adjusted_config: FrequencyRankerConfig) -> np.ndarray:
    return config_vector(adjusted_config) - config_vector(base_config)


def delta_norm(delta: Sequence[float]) -> float:
    return round(float(np.linalg.norm(np.array(delta, dtype=np.float64))), 10)


def changed_fields_from_delta(delta: Sequence[float], *, min_abs: float = 1e-6) -> tuple[str, ...]:
    return tuple(
        field
        for field, value in zip(CONFIG_WEIGHT_FIELDS, delta, strict=True)
        if abs(float(value)) >= min_abs
    )


def rank_for_scores(
    *,
    scores: np.ndarray,
    matrix: RankedUniverseMatrix,
    target_index: int,
    target_numbers: tuple[int, ...],
) -> int:
    target_score = float(scores[target_index])
    better = int((scores > target_score).sum())
    equal_before = int(((scores == target_score) & _lex_less_than(matrix.numbers, target_numbers)).sum())
    return better + equal_before + 1


def target_index_in_matrix(matrix: RankedUniverseMatrix, target_numbers: tuple[int, ...]) -> int | None:
    matches = np.flatnonzero(np.all(matrix.numbers == np.array(target_numbers, dtype=np.uint8), axis=1))
    return int(matches[0]) if len(matches) else None


def _boundary_indices(scores: np.ndarray, *, top_n: int, current_score: float, limit: int = 6) -> np.ndarray:
    safe_top_n = min(max(1, top_n), len(scores))
    if safe_top_n >= len(scores):
        return np.array([], dtype=np.int64)
    top_indices = np.argpartition(scores, -safe_top_n)[-safe_top_n:]
    top_scores = scores[top_indices]
    ordered = top_indices[np.argsort(top_scores)]
    boundary = list(ordered[:limit])
    better_indices = np.flatnonzero(scores > current_score)
    if len(better_indices):
        sample_count = min(limit, len(better_indices))
        sampled = better_indices[np.linspace(0, len(better_indices) - 1, num=sample_count, dtype=np.int64)]
        boundary.extend(int(index) for index in sampled)
    return np.array(boundary[: max(limit, 1)], dtype=np.int64)


def _minimal_delta_against_components(
    *,
    target_components: np.ndarray,
    competitor_components: np.ndarray,
    required_score_margin: float,
) -> np.ndarray | None:
    diff = target_components - competitor_components
    denom = float(diff @ diff)
    if denom <= 1e-12:
        return None
    return diff * (max(required_score_margin, EPSILON_SCORE_MARGIN) / denom)


def _clamp_delta_to_bounds(base_config: FrequencyRankerConfig, delta: np.ndarray) -> np.ndarray:
    clamped = delta.astype(np.float64, copy=True)
    for index, field in enumerate(CONFIG_WEIGHT_FIELDS):
        lower, upper = weight_bounds_for_field(field)
        base_value = float(getattr(base_config, field))
        clamped[index] = min(upper - base_value, max(lower - base_value, float(clamped[index])))
    return clamped


def _candidate_deltas(
    *,
    base_config: FrequencyRankerConfig,
    components: np.ndarray,
    scores: np.ndarray,
    target_index: int,
    top_n: int,
) -> list[np.ndarray]:
    target_components = components[target_index]
    target_score = float(scores[target_index])
    candidates: list[np.ndarray] = []
    for competitor_index in _boundary_indices(scores, top_n=top_n, current_score=target_score):
        margin = float(scores[competitor_index]) - target_score + EPSILON_SCORE_MARGIN
        raw = _minimal_delta_against_components(
            target_components=target_components,
            competitor_components=components[int(competitor_index)],
            required_score_margin=margin,
        )
        if raw is None:
            continue
        for scale in (1.0, 1.25, 1.5, 2.0, 3.0):
            candidates.append(_clamp_delta_to_bounds(base_config, raw * scale))
        diff = target_components - components[int(competitor_index)]
        for field_index in np.argsort(np.abs(diff))[-6:][::-1]:
            if abs(float(diff[field_index])) <= 1e-12:
                continue
            coordinate = np.zeros(len(CONFIG_WEIGHT_FIELDS), dtype=np.float64)
            coordinate[field_index] = margin / float(diff[field_index])
            candidates.append(_clamp_delta_to_bounds(base_config, coordinate))
    unique: list[np.ndarray] = []
    seen: set[tuple[float, ...]] = set()
    for delta in candidates:
        key = tuple(round(float(value), 10) for value in delta)
        if key in seen or not any(abs(value) > 1e-12 for value in delta):
            continue
        seen.add(key)
        unique.append(delta)
    unique.sort(key=delta_norm)
    return unique[:24]


def _simplified_component_vector(components: dict) -> np.ndarray:
    values = np.zeros(len(CONFIG_WEIGHT_FIELDS), dtype=np.float64)
    index_by_field = {field: index for index, field in enumerate(CONFIG_WEIGHT_FIELDS)}
    for component_name, value in components.items():
        weight_field = SIMPLIFIED_COMPONENT_NAMES.get(component_name)
        if weight_field is None:
            weight_field = component_name if component_name in index_by_field else component_name.replace("_score", "_weight")
        if weight_field in index_by_field:
            values[index_by_field[weight_field]] = float(value)
    return values


def _rank_simplified(scores: Sequence[float], numbers: Sequence[tuple[int, ...]], target_numbers: tuple[int, ...], target_score: float) -> int:
    better = sum(score > target_score for score in scores)
    equal_before = sum(score == target_score and combo < target_numbers for score, combo in zip(scores, numbers, strict=True))
    return int(better + equal_before + 1)


def invert_target_weight_delta(
    *,
    base_config: FrequencyRankerConfig,
    target_issue: str,
    red_numbers: tuple[int, ...],
    current_rank: int,
    score: float,
    ranked_universe: Sequence[dict],
    top_n: int = 10000,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
) -> dict:
    if current_rank <= top_n:
        return TargetWeightInversion(
            target_issue=target_issue,
            red_numbers=red_numbers,
            current_rank=current_rank,
            hit_top10000=True,
            score=float(score),
            rank_margin=0,
            base_config_hash=config_hash(base_config),
            required_delta_config={field: 0.0 for field in CONFIG_WEIGHT_FIELDS},
            adjusted_config=config_dict(base_config),
            adjusted_rank=current_rank,
            adjusted_hit_top10000=True,
            delta_norm=0.0,
            changed_fields=(),
            success=True,
        ).as_dict()

    target_row = next((row for row in ranked_universe if tuple(row.get("numbers") or ()) == red_numbers), None)
    if not target_row or not isinstance(target_row.get("components"), dict):
        return TargetWeightInversion(
            target_issue=target_issue,
            red_numbers=red_numbers,
            current_rank=current_rank,
            hit_top10000=False,
            score=float(score),
            rank_margin=max(0, current_rank - top_n),
            base_config_hash=config_hash(base_config),
            required_delta_config={},
            adjusted_config=config_dict(base_config),
            adjusted_rank=None,
            adjusted_hit_top10000=False,
            delta_norm=0.0,
            changed_fields=(),
            success=False,
            outlier_reason="missing_target_components",
        ).as_dict()

    rows = [row for row in ranked_universe if isinstance(row.get("components"), dict)]
    numbers = [tuple(row.get("numbers") or ()) for row in rows]
    components = np.vstack([_simplified_component_vector(row["components"]) for row in rows])
    base_vector = config_vector(base_config)
    scores = components @ base_vector
    target_index = numbers.index(red_numbers)
    target_score = float(scores[target_index])
    candidate_deltas = _candidate_deltas(
        base_config=base_config,
        components=components,
        scores=scores,
        target_index=target_index,
        top_n=top_n,
    )
    if lower_bound is not None or upper_bound is not None:
        lo = -float("inf") if lower_bound is None else lower_bound
        hi = float("inf") if upper_bound is None else upper_bound
        candidate_deltas = [
            np.array(
                [
                    min(hi - float(getattr(base_config, field)), max(lo - float(getattr(base_config, field)), value))
                    for value, field in zip(delta, CONFIG_WEIGHT_FIELDS, strict=True)
                ],
                dtype=np.float64,
            )
            for delta in candidate_deltas
        ]
    best: dict | None = None
    for delta in candidate_deltas:
        adjusted_config = apply_delta(base_config, delta)
        adjusted_delta = delta_between(base_config, adjusted_config)
        adjusted_scores = components @ config_vector(adjusted_config)
        adjusted_rank = _rank_simplified(adjusted_scores, numbers, red_numbers, float(adjusted_scores[target_index]))
        success = adjusted_rank <= top_n
        result = TargetWeightInversion(
            target_issue=target_issue,
            red_numbers=red_numbers,
            current_rank=current_rank,
            hit_top10000=False,
            score=float(score),
            rank_margin=max(0, current_rank - top_n),
            base_config_hash=config_hash(base_config),
            required_delta_config=delta_dict(adjusted_delta),
            adjusted_config=config_dict(adjusted_config),
            adjusted_rank=adjusted_rank,
            adjusted_hit_top10000=success,
            delta_norm=delta_norm(adjusted_delta),
            changed_fields=changed_fields_from_delta(adjusted_delta),
            success=success,
            outlier_reason=None if success else "clamp_limit",
        ).as_dict()
        if success:
            if best is None or float(result["delta_norm"]) < float(best["delta_norm"]):
                best = result
        elif best is None or (best.get("adjusted_rank") is not None and adjusted_rank < int(best["adjusted_rank"])):
            best = result
    if best is not None:
        return best
    return TargetWeightInversion(
        target_issue=target_issue,
        red_numbers=red_numbers,
        current_rank=current_rank,
        hit_top10000=False,
        score=float(score),
        rank_margin=max(0, current_rank - top_n),
        base_config_hash=config_hash(base_config),
        required_delta_config={},
        adjusted_config=config_dict(base_config),
        adjusted_rank=None,
        adjusted_hit_top10000=False,
        delta_norm=0.0,
        changed_fields=(),
        success=False,
        outlier_reason="no_direction",
    ).as_dict()


def invert_target_weight(
    *,
    target_issue: str,
    red_numbers: tuple[int, ...],
    train_history: list[HistoryDraw],
    base_config: FrequencyRankerConfig,
    ranked_universe: RankedUniverseMatrix,
    target_draw_date=None,
    top_n: int = 10000,
) -> TargetWeightInversion:
    base_hash = config_hash(base_config)
    if is_excluded_red_combination(red_numbers):
        return TargetWeightInversion(
            target_issue=target_issue,
            red_numbers=red_numbers,
            current_rank=len(ranked_universe) + 1,
            hit_top10000=False,
            score=0.0,
            rank_margin=max(0, len(ranked_universe) + 1 - top_n),
            base_config_hash=base_hash,
            required_delta_config={},
            adjusted_config=config_dict(base_config),
            adjusted_rank=None,
            adjusted_hit_top10000=False,
            delta_norm=0.0,
            changed_fields=(),
            success=False,
            outlier_reason="excluded_combination",
        )

    stats = train_frequency_stats(train_history, target_draw_date=target_draw_date)
    target_index = target_index_in_matrix(ranked_universe, red_numbers)
    if target_index is None:
        return TargetWeightInversion(
            target_issue=target_issue,
            red_numbers=red_numbers,
            current_rank=len(ranked_universe) + 1,
            hit_top10000=False,
            score=0.0,
            rank_margin=max(0, len(ranked_universe) + 1 - top_n),
            base_config_hash=base_hash,
            required_delta_config={},
            adjusted_config=config_dict(base_config),
            adjusted_rank=None,
            adjusted_hit_top10000=False,
            delta_norm=0.0,
            changed_fields=(),
            success=False,
            outlier_reason="target_not_in_universe",
        )

    components = _components_for_matrix(ranked_universe, stats)
    base_scores = _score_matrix(ranked_universe, stats, (base_config,))[:, 0]
    current_rank, target_score = _rank_targets_from_scores(
        matrix=ranked_universe,
        scores=base_scores[:, None],
        target_numbers=red_numbers,
        target_scores=_target_scores(red_numbers, stats, (base_config,)),
        target_excluded=False,
    )[0]
    rank_margin = max(0, int(current_rank) - int(top_n))
    if current_rank <= top_n:
        return TargetWeightInversion(
            target_issue=target_issue,
            red_numbers=red_numbers,
            current_rank=int(current_rank),
            hit_top10000=True,
            score=float(target_score),
            rank_margin=rank_margin,
            base_config_hash=base_hash,
            required_delta_config={},
            adjusted_config=config_dict(base_config),
            adjusted_rank=int(current_rank),
            adjusted_hit_top10000=True,
            delta_norm=0.0,
            changed_fields=(),
            success=True,
            outlier_reason=None,
        )

    best_result: TargetWeightInversion | None = None
    for delta in _candidate_deltas(
        base_config=base_config,
        components=components,
        scores=base_scores,
        target_index=target_index,
        top_n=top_n,
    ):
        adjusted_config = apply_delta(base_config, delta)
        actual_delta = delta_between(base_config, adjusted_config)
        adjusted_scores = _score_matrix(ranked_universe, stats, (adjusted_config,))[:, 0]
        adjusted_rank = rank_for_scores(
            scores=adjusted_scores,
            matrix=ranked_universe,
            target_index=target_index,
            target_numbers=red_numbers,
        )
        success = adjusted_rank <= top_n
        result = TargetWeightInversion(
            target_issue=target_issue,
            red_numbers=red_numbers,
            current_rank=int(current_rank),
            hit_top10000=False,
            score=float(target_score),
            rank_margin=rank_margin,
            base_config_hash=base_hash,
            required_delta_config=delta_dict(actual_delta),
            adjusted_config=config_dict(adjusted_config),
            adjusted_rank=int(adjusted_rank),
            adjusted_hit_top10000=success,
            delta_norm=delta_norm(actual_delta),
            changed_fields=changed_fields_from_delta(actual_delta),
            success=success,
            outlier_reason=None if success else "not_enough_shift",
        )
        if success:
            if best_result is None or result.delta_norm < best_result.delta_norm:
                best_result = result
        elif best_result is None or (best_result.adjusted_rank is not None and adjusted_rank < best_result.adjusted_rank):
            best_result = result

    if best_result is None:
        return TargetWeightInversion(
            target_issue=target_issue,
            red_numbers=red_numbers,
            current_rank=int(current_rank),
            hit_top10000=False,
            score=float(target_score),
            rank_margin=rank_margin,
            base_config_hash=base_hash,
            required_delta_config={},
            adjusted_config=config_dict(base_config),
            adjusted_rank=int(current_rank),
            adjusted_hit_top10000=False,
            delta_norm=0.0,
            changed_fields=(),
            success=False,
            outlier_reason="no_direction",
        )
    return best_result


def invert_targets_for_summary(
    *,
    history: list[HistoryDraw],
    ranked_universe: RankedUniverseMatrix,
    base_config: FrequencyRankerConfig,
    target_results: Sequence[dict],
    train_window: int,
    train_mode: str,
    top_n: int,
    max_targets: int | None = None,
) -> list[TargetWeightInversion]:
    issue_to_index = {history_issue(draw): index for index, draw in enumerate(history)}
    rows: list[TargetWeightInversion] = []
    selected_results = target_results[:max_targets] if max_targets is not None else target_results
    for target in selected_results:
        issue = str(target.get("issue") or "")
        target_index = issue_to_index.get(issue)
        red_numbers = tuple(int(number) for number in target.get("red_numbers") or ())
        if target_index is None or len(red_numbers) != 6:
            continue
        train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
        rows.append(
            invert_target_weight(
                target_issue=issue,
                red_numbers=red_numbers,
                train_history=history[train_start:target_index],
                base_config=base_config,
                ranked_universe=ranked_universe,
                target_draw_date=history_draw_date(history[target_index]),
                top_n=top_n,
            )
        )
    return rows


def _vector_from_delta_config(delta_config: dict[str, float]) -> np.ndarray:
    return np.array([float(delta_config.get(field, 0.0) or 0.0) for field in CONFIG_WEIGHT_FIELDS], dtype=np.float64)


def _trimmed_vectors(vectors: list[np.ndarray], *, trim_ratio: float) -> list[np.ndarray]:
    if not vectors:
        return []
    drop = int(len(vectors) * trim_ratio)
    if drop <= 0:
        return vectors
    ordered = sorted(vectors, key=delta_norm)
    return ordered[: max(1, len(ordered) - drop)]


def _median_vector(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        return np.zeros(len(CONFIG_WEIGHT_FIELDS), dtype=np.float64)
    return np.median(np.vstack(vectors), axis=0)


def _mean_vector(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        return np.zeros(len(CONFIG_WEIGHT_FIELDS), dtype=np.float64)
    return np.mean(np.vstack(vectors), axis=0)


def _weighted_vector(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        return np.zeros(len(CONFIG_WEIGHT_FIELDS), dtype=np.float64)
    weights = np.array([1.0 / (float(np.linalg.norm(vector)) + 0.01) for vector in vectors], dtype=np.float64)
    return np.average(np.vstack(vectors), axis=0, weights=weights)


def _stable_field_mask(vectors: list[np.ndarray], *, min_consistency: float = 0.65) -> np.ndarray:
    if not vectors:
        return np.zeros(len(CONFIG_WEIGHT_FIELDS), dtype=bool)
    matrix = np.vstack(vectors)
    mask = np.zeros(len(CONFIG_WEIGHT_FIELDS), dtype=bool)
    for index in range(matrix.shape[1]):
        values = matrix[:, index]
        nonzero = values[np.abs(values) >= 1e-6]
        if len(nonzero) < max(2, len(vectors) // 5):
            continue
        positive_rate = float((nonzero > 0).sum()) / len(nonzero)
        negative_rate = float((nonzero < 0).sum()) / len(nonzero)
        if max(positive_rate, negative_rate) >= min_consistency:
            mask[index] = True
    return mask


def aggregate_target_inversions(
    inversions: Sequence[TargetWeightInversion | dict],
    *,
    base_config: FrequencyRankerConfig,
    trim_ratio: float = 0.10,
) -> dict:
    normalized = [item if isinstance(item, TargetWeightInversion) else TargetWeightInversion(**item) for item in inversions]
    successful_vectors = [
        _vector_from_delta_config(item.required_delta_config)
        for item in normalized
        if item.success and item.required_delta_config
    ]
    zero_vectors = [
        np.zeros(len(CONFIG_WEIGHT_FIELDS), dtype=np.float64)
        for item in normalized
        if item.success and not item.required_delta_config
    ]
    all_vectors = zero_vectors + successful_vectors
    trimmed = _trimmed_vectors(successful_vectors, trim_ratio=trim_ratio)
    mean_delta = _mean_vector(all_vectors)
    median_delta = _median_vector(all_vectors)
    trimmed_mean_delta = _mean_vector(trimmed)
    weighted_delta = _weighted_vector(successful_vectors)
    micro_delta_25 = weighted_delta * 0.25
    micro_delta_50 = weighted_delta * 0.50
    stable_mask = _stable_field_mask(successful_vectors)
    stable_delta = weighted_delta.copy()
    stable_delta[~stable_mask] = 0.0
    candidates = target_inversion_candidate_configs(
        base_config=base_config,
        median_delta=median_delta,
        trimmed_mean_delta=trimmed_mean_delta,
        weighted_delta=weighted_delta,
        stable_delta=stable_delta,
    )
    return {
        "mode": "target_weight_inversion_v0",
        "sample_count": len(normalized),
        "latest_issue": max((item.target_issue for item in normalized), default=""),
        "hit_count": sum(1 for item in normalized if item.hit_top10000),
        "miss_count": sum(1 for item in normalized if not item.hit_top10000),
        "success_count": sum(1 for item in normalized if item.success),
        "outlier_count": sum(1 for item in normalized if item.outlier_reason),
        "success_rate": round(sum(1 for item in normalized if item.success) / len(normalized), 6) if normalized else 0.0,
        "mean_delta": delta_dict(mean_delta),
        "median_delta": delta_dict(median_delta),
        "trimmed_mean_delta": delta_dict(trimmed_mean_delta),
        "weighted_delta": delta_dict(weighted_delta),
        "micro_delta": {
            "scale_25": delta_dict(micro_delta_25),
            "scale_50": delta_dict(micro_delta_50),
        },
        "stable_fields": [field for field, stable in zip(CONFIG_WEIGHT_FIELDS, stable_mask, strict=True) if bool(stable)],
        "stable_fields_delta": delta_dict(stable_delta),
        "median_delta_norm": delta_norm(median_delta),
        "trimmed_mean_delta_norm": delta_norm(trimmed_mean_delta),
        "weighted_delta_norm": delta_norm(weighted_delta),
        "candidate_count": len(candidates),
        "candidates": [candidate.as_dict() for candidate in candidates],
    }


def _candidate_from_delta(base_config: FrequencyRankerConfig, label: str, delta: np.ndarray, *, scale: float = 1.0) -> TargetInversionCandidate | None:
    config = apply_delta(base_config, delta, scale=scale)
    actual_delta = delta_between(base_config, config)
    if not changed_fields_from_delta(actual_delta):
        return None
    return TargetInversionCandidate(label=label, config=config, delta_config=delta_dict(actual_delta))


def target_inversion_candidate_configs(
    *,
    base_config: FrequencyRankerConfig,
    median_delta: np.ndarray,
    trimmed_mean_delta: np.ndarray,
    weighted_delta: np.ndarray,
    stable_delta: np.ndarray,
) -> tuple[TargetInversionCandidate, ...]:
    raw = (
        _candidate_from_delta(base_config, "current_plus_0_25_median_delta", median_delta, scale=0.25),
        _candidate_from_delta(base_config, "current_plus_0_50_trimmed_mean_delta", trimmed_mean_delta, scale=0.50),
        _candidate_from_delta(base_config, "current_plus_weighted_delta", weighted_delta, scale=1.0),
        _candidate_from_delta(base_config, "current_plus_only_stable_fields_delta", stable_delta, scale=1.0),
    )
    candidates: list[TargetInversionCandidate] = []
    seen: set[str] = set()
    for candidate in raw:
        if candidate is None:
            continue
        key = config_hash(candidate.config)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return tuple(candidates)


def aggregate_candidate_configs(aggregate: dict) -> tuple[FrequencyRankerConfig, ...]:
    configs = []
    for candidate in aggregate.get("candidates") or []:
        if isinstance(candidate, dict) and isinstance(candidate.get("config"), dict):
            configs.append(FrequencyRankerConfig(**clamp_weight_values(candidate["config"])))
    return tuple(configs)


def target_inversion_payload(
    *,
    inversions: Sequence[TargetWeightInversion],
    base_config: FrequencyRankerConfig,
) -> tuple[list[dict], dict, tuple[FrequencyRankerConfig, ...]]:
    rows = [item.as_dict() for item in inversions]
    aggregate = aggregate_target_inversions(inversions, base_config=base_config)
    return rows, aggregate, aggregate_candidate_configs(aggregate)
