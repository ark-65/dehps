from __future__ import annotations


def calculate_dehps_score(
    structure_naturalness_score: float,
    pattern_complexity_score: float,
    anomaly_penalty: float,
    historical_similarity_score: float = 0.5,
) -> float:
    score = (
        0.35 * structure_naturalness_score
        + 0.25 * pattern_complexity_score
        - 0.25 * anomaly_penalty
        + 0.15 * historical_similarity_score
    )
    return round(max(0.0, min(1.0, score)), 6)

