from __future__ import annotations

from dataclasses import dataclass

from dehps.features.red_ball_features import calculate_red_ball_features
from dehps.scoring.strategy import score_numbers


@dataclass(frozen=True)
class FrequencyRankerConfig:
    structural_weight: float = 0.40
    frequency_weight: float = 0.30
    omission_weight: float = 0.25
    previous_consecutive_weight: float = 0.05
    previous_overlap_weight: float = 0.00
    previous_parity_shape_weight: float = 0.00
    previous_zone_shape_weight: float = 0.00


@dataclass(frozen=True)
class FrequencyStats:
    train_draws: int
    frequency_rate: dict[int, float]
    omission_rate: dict[int, float]
    previous_numbers: tuple[int, ...]
    previous_number_set: frozenset[int]
    previous_consecutive_pair_count: int
    previous_odd_count: int
    previous_zone_counts: tuple[int, int, int]


def train_frequency_stats(history: list[tuple[str, tuple[int, ...]]]) -> FrequencyStats:
    if not history:
        raise ValueError("history must contain at least one draw")

    counts = {number: 0 for number in range(1, 34)}
    last_seen_index = {number: -1 for number in range(1, 34)}
    for index, (_, numbers) in enumerate(history):
        for number in numbers:
            counts[number] += 1
            last_seen_index[number] = index

    train_draws = len(history)
    denominator = train_draws * 6
    max_omission = max(1, train_draws)
    previous_numbers = history[-1][1]
    previous_features = calculate_red_ball_features(previous_numbers)
    return FrequencyStats(
        train_draws=train_draws,
        frequency_rate={number: counts[number] / denominator for number in range(1, 34)},
        omission_rate={
            number: (train_draws - 1 - last_seen_index[number]) / max_omission
            if last_seen_index[number] >= 0
            else 1.0
            for number in range(1, 34)
        },
        previous_numbers=previous_numbers,
        previous_number_set=frozenset(previous_numbers),
        previous_consecutive_pair_count=previous_features["consecutive_pair_count"],
        previous_odd_count=previous_features["odd_count"],
        previous_zone_counts=(
            previous_features["zone_1_count"],
            previous_features["zone_2_count"],
            previous_features["zone_3_count"],
        ),
    )


def score_frequency_candidate(
    numbers: tuple[int, ...],
    stats: FrequencyStats,
    config: FrequencyRankerConfig | None = None,
) -> dict[str, float]:
    cfg = config or FrequencyRankerConfig()
    structural_score = score_numbers(numbers)["score"]
    frequency_score = sum(stats.frequency_rate[number] for number in numbers)
    omission_score = sum(stats.omission_rate[number] for number in numbers) / 6
    features = calculate_red_ball_features(numbers)
    previous_consecutive_score = _previous_consecutive_score(
        candidate_pair_count=features["consecutive_pair_count"],
        previous_pair_count=stats.previous_consecutive_pair_count,
    )
    previous_overlap_score = len(set(numbers) & stats.previous_number_set) / 6
    previous_parity_shape_score = 1 - abs(features["odd_count"] - stats.previous_odd_count) / 6
    candidate_zone_counts = (features["zone_1_count"], features["zone_2_count"], features["zone_3_count"])
    previous_zone_shape_score = 1 - sum(
        abs(candidate_count - previous_count)
        for candidate_count, previous_count in zip(candidate_zone_counts, stats.previous_zone_counts, strict=True)
    ) / 12
    score = (
        cfg.structural_weight * structural_score
        + cfg.frequency_weight * frequency_score
        + cfg.omission_weight * omission_score
        + cfg.previous_consecutive_weight * previous_consecutive_score
        + cfg.previous_overlap_weight * previous_overlap_score
        + cfg.previous_parity_shape_weight * previous_parity_shape_score
        + cfg.previous_zone_shape_weight * previous_zone_shape_score
    )
    return {
        "score": round(score, 8),
        "structural_score": round(structural_score, 8),
        "frequency_score": round(frequency_score, 8),
        "omission_score": round(omission_score, 8),
        "previous_consecutive_score": round(previous_consecutive_score, 8),
        "previous_overlap_score": round(previous_overlap_score, 8),
        "previous_parity_shape_score": round(previous_parity_shape_score, 8),
        "previous_zone_shape_score": round(previous_zone_shape_score, 8),
        "sum_value": float(features["sum_value"]),
        "span_value": float(features["span_value"]),
        "odd_count": float(features["odd_count"]),
    }


def _previous_consecutive_score(*, candidate_pair_count: int, previous_pair_count: int) -> float:
    candidate_score = min(candidate_pair_count, 5) / 5
    if previous_pair_count > 0:
        return candidate_score
    return 1 - candidate_score
