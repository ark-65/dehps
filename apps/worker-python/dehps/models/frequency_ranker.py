from __future__ import annotations

from dataclasses import dataclass

from dehps.features.red_ball_features import calculate_red_ball_features
from dehps.scoring.strategy import score_numbers


@dataclass(frozen=True)
class FrequencyRankerConfig:
    structural_weight: float = 0.55
    frequency_weight: float = 0.30
    omission_weight: float = 0.15


@dataclass(frozen=True)
class FrequencyStats:
    train_draws: int
    frequency_rate: dict[int, float]
    omission_rate: dict[int, float]


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
    return FrequencyStats(
        train_draws=train_draws,
        frequency_rate={number: counts[number] / denominator for number in range(1, 34)},
        omission_rate={
            number: (train_draws - 1 - last_seen_index[number]) / max_omission
            if last_seen_index[number] >= 0
            else 1.0
            for number in range(1, 34)
        },
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
    score = (
        cfg.structural_weight * structural_score
        + cfg.frequency_weight * frequency_score
        + cfg.omission_weight * omission_score
    )
    features = calculate_red_ball_features(numbers)
    return {
        "score": round(score, 8),
        "structural_score": round(structural_score, 8),
        "frequency_score": round(frequency_score, 8),
        "omission_score": round(omission_score, 8),
        "sum_value": float(features["sum_value"]),
        "span_value": float(features["span_value"]),
        "odd_count": float(features["odd_count"]),
    }
