from __future__ import annotations

from math import comb

from dehps.domain.combination import iter_ssq_red_combinations
from dehps.scoring.strategy import StrategyConfig, keep_by_baseline


TOTAL_SSQ_RED_COMBINATIONS = comb(33, 6)


def run_baseline_backtest(
    history: list[tuple[str, tuple[int, ...]]],
    config: StrategyConfig | None = None,
) -> dict[str, float | int | list[str]]:
    cfg = config or StrategyConfig()
    kept_total = sum(1 for numbers in iter_ssq_red_combinations() if keep_by_baseline(numbers, cfg))
    covered = [issue for issue, numbers in history if keep_by_baseline(numbers, cfg)]
    keep_rate = kept_total / TOTAL_SSQ_RED_COMBINATIONS
    coverage_rate = len(covered) / len(history) if history else 0.0
    lift = coverage_rate / keep_rate if keep_rate else 0.0
    return {
        "total_combinations": TOTAL_SSQ_RED_COMBINATIONS,
        "kept_combinations": kept_total,
        "keep_rate": round(keep_rate, 8),
        "history_draws": len(history),
        "covered_draws": len(covered),
        "coverage_rate": round(coverage_rate, 8),
        "lift": round(lift, 8),
        "covered_issues": covered,
        "missed_issues": [issue for issue, _ in history if issue not in set(covered)],
    }

