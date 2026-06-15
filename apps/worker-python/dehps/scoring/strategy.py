from __future__ import annotations

from dataclasses import dataclass

from dehps.features.pattern_complexity import calculate_pattern_complexity
from dehps.scoring.formula import calculate_dehps_score


@dataclass(frozen=True)
class StrategyConfig:
    min_score: float = 0.45
    max_anomaly_penalty: float = 0.70


def score_numbers(numbers: tuple[int, ...]) -> dict[str, float]:
    complexity = calculate_pattern_complexity(numbers)
    score = calculate_dehps_score(**complexity)
    return {**complexity, "score": score}


def keep_by_baseline(numbers: tuple[int, ...], config: StrategyConfig | None = None) -> bool:
    cfg = config or StrategyConfig()
    scored = score_numbers(numbers)
    return scored["score"] >= cfg.min_score and scored["anomaly_penalty"] <= cfg.max_anomaly_penalty

