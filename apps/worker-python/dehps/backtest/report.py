from __future__ import annotations

from datetime import date


def render_experiment_report(experiment_key: str, strategy_key: str, metrics: dict) -> str:
    return f"""# DEHPS Experiment Report

- Experiment: `{experiment_key}`
- Strategy: `{strategy_key}`
- Date: {date.today().isoformat()}

## Metrics

- total_combinations: {metrics["total_combinations"]}
- kept_combinations: {metrics["kept_combinations"]}
- keep_rate: {metrics["keep_rate"]}
- history_draws: {metrics["history_draws"]}
- covered_draws: {metrics["covered_draws"]}
- coverage_rate: {metrics["coverage_rate"]}
- lift: {metrics["lift"]}

## Risk Note

This report does not represent predictive ability and is not betting advice. It is historical strategy evaluation for DEHPS research.
"""


def render_daily_report(
    run_key: str,
    source: str,
    latest_draw: dict | None,
    is_new_data: bool,
    metrics: dict,
    previous_metrics: dict | None = None,
) -> str:
    latest_issue = latest_draw.get("issue") if latest_draw else "N/A"
    latest_red = latest_draw.get("red_numbers") if latest_draw else "N/A"
    latest_blue = latest_draw.get("blue_number") if latest_draw else "N/A"
    previous = previous_metrics or {}
    return f"""# DEHPS Daily Report

- Date: {date.today().isoformat()}
- Run: `{run_key}`
- Source: `{source}`
- Latest issue: {latest_issue}
- Latest red numbers: {latest_red}
- Latest blue number: {latest_blue}
- New data inserted: {is_new_data}

## Baseline Backtest

- keep_rate: {metrics.get("keep_rate", 0)}
- coverage_rate: {metrics.get("coverage_rate", 0)}
- lift: {metrics.get("lift", 0)}

## Previous Comparison

- previous_keep_rate: {previous.get("keep_rate", "N/A")}
- previous_coverage_rate: {previous.get("coverage_rate", "N/A")}
- previous_lift: {previous.get("lift", "N/A")}

## Risk Note

These metrics do not represent predictive ability and are not betting advice. They only describe historical behavior of a discrete-combination filter.

## Next Step

Inspect misses and decide whether the baseline is too strict, too broad, or overfit to simple structural preferences.
"""

