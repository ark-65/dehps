from __future__ import annotations

from dehps.evaluation.objective_policy import ObjectivePolicy


def calculate_tail_risk_penalty(
    *,
    median_rank: int | float,
    worst_rank: int | float,
    p95_rank: int | float | None,
    tail_over_750000_count: int,
    tail_over_900000_count: int,
    tail_over_1000000_count: int,
    universe_size: int,
    policy: ObjectivePolicy,
) -> float:
    safe_universe = max(1, universe_size)
    normalized_median = min(1.0, max(0.0, float(median_rank) / safe_universe))
    normalized_worst = min(1.0, max(0.0, float(worst_rank) / safe_universe))
    normalized_p95 = min(
        1.0,
        max(0.0, float(p95_rank if p95_rank is not None else worst_rank) / safe_universe),
    )
    count_penalty = (
        tail_over_750000_count * policy.tail_over_750000_penalty
        + tail_over_900000_count * policy.tail_over_900000_penalty
        + tail_over_1000000_count * policy.tail_over_1000000_penalty
    )
    shape_penalty = (
        normalized_worst**2 * policy.worst_rank_penalty_weight
        + normalized_p95**2 * policy.p95_rank_penalty_weight
        + normalized_median**2 * policy.median_rank_penalty_weight
    )
    return round(count_penalty + shape_penalty, 6)
