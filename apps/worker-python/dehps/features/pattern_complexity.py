from __future__ import annotations

from dehps.features.red_ball_features import calculate_red_ball_features


def calculate_pattern_complexity(numbers: list[int] | tuple[int, ...]) -> dict[str, float]:
    f = calculate_red_ball_features(numbers)
    penalty = 0.0

    if f["max_consecutive_run"] >= 6:
        penalty += 0.35
    elif f["max_consecutive_run"] == 5:
        penalty += 0.25
    elif f["max_consecutive_run"] == 4:
        penalty += 0.15

    if f["odd_count"] in (0, 6) or f["small_count"] in (0, 6):
        penalty += 0.18
    if f["is_arithmetic_sequence"]:
        penalty += 0.22
    if f["span_value"] <= 8:
        penalty += 0.16
    if f["sum_value"] <= 55 or f["sum_value"] >= 145:
        penalty += 0.12
    if max(f["zone_1_count"], f["zone_2_count"], f["zone_3_count"]) >= 5:
        penalty += 0.14
    if f["max_gap"] - f["min_gap"] <= 1:
        penalty += 0.08

    anomaly_penalty = max(0.0, min(1.0, penalty))
    pattern_complexity_score = max(0.0, min(1.0, 1.0 - anomaly_penalty * 0.85))

    balance_bonus = 0.0
    if 2 <= f["odd_count"] <= 4:
        balance_bonus += 0.15
    if 2 <= f["small_count"] <= 4:
        balance_bonus += 0.15
    if max(f["zone_1_count"], f["zone_2_count"], f["zone_3_count"]) <= 3:
        balance_bonus += 0.15
    if 70 <= f["sum_value"] <= 130:
        balance_bonus += 0.15

    structure_naturalness_score = max(0.0, min(1.0, 0.45 + balance_bonus - anomaly_penalty * 0.35))
    return {
        "pattern_complexity_score": round(pattern_complexity_score, 4),
        "anomaly_penalty": round(anomaly_penalty, 4),
        "structure_naturalness_score": round(structure_naturalness_score, 4),
    }

