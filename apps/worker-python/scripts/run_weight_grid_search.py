from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.regime import HistoryScope, select_history
from dehps.optimization.walk_forward import deterministic_run_key, run_walk_forward
from dehps.storage.postgres_store import load_red_combination_universe


DEFAULT_GRID = [
    FrequencyRankerConfig(structural_weight=0.55, frequency_weight=0.30, omission_weight=0.15),
    FrequencyRankerConfig(structural_weight=0.40, frequency_weight=0.45, omission_weight=0.15),
    FrequencyRankerConfig(structural_weight=0.40, frequency_weight=0.30, omission_weight=0.30),
    FrequencyRankerConfig(structural_weight=0.25, frequency_weight=0.50, omission_weight=0.25),
    FrequencyRankerConfig(structural_weight=0.25, frequency_weight=0.25, omission_weight=0.50),
    FrequencyRankerConfig(
        structural_weight=0.40,
        frequency_weight=0.30,
        omission_weight=0.25,
        previous_consecutive_weight=0.05,
    ),
    FrequencyRankerConfig(
        structural_weight=0.40,
        frequency_weight=0.30,
        omission_weight=0.25,
        previous_overlap_weight=-0.05,
        previous_parity_shape_weight=0.05,
        previous_zone_shape_weight=0.05,
    ),
    FrequencyRankerConfig(
        structural_weight=0.35,
        frequency_weight=0.30,
        omission_weight=0.25,
        previous_consecutive_weight=0.03,
        previous_overlap_weight=-0.04,
        previous_parity_shape_weight=0.03,
        previous_zone_shape_weight=0.08,
    ),
]


def summarize_result(result, config: FrequencyRankerConfig) -> dict:
    ranks = [target.rank for target in result.target_ranks]
    return {
        "config": config.__dict__,
        "as_of_issue": result.as_of_issue,
        "history_fingerprint": result.history_fingerprint,
        "config_hash": result.config_hash,
        "evaluated_draws": result.evaluated_draws,
        "top_100_hits": result.top_100_hits,
        "top_1000_hits": result.top_1000_hits,
        "top_10000_hits": result.top_10000_hits,
        "median_rank": median(ranks) if ranks else None,
        "best_rank": min(ranks) if ranks else None,
        "worst_rank": max(ranks) if ranks else None,
    }


def sort_key(summary: dict) -> tuple:
    return (
        summary["top_100_hits"],
        summary["top_1000_hits"],
        summary["top_10000_hits"],
        -(summary["median_rank"] or 0),
        -(summary["best_rank"] or 0),
    )


def render_grid_report(payload: dict) -> str:
    rows = "\n".join(
        (
            f"| {index} | `{json.dumps(item['config'], sort_keys=True)}` | "
            f"{item['top_100_hits']} | {item['top_1000_hits']} | {item['top_10000_hits']} | "
            f"{item['median_rank']} | {item['best_rank']} | {item['worst_rank']} |"
        )
        for index, item in enumerate(payload["results"], start=1)
    )
    return f"""# DEHPS Weight Grid Search Report

- History scope: `{payload["history_scope"]}`
- Regime years: {payload["regime_years"]}
- Regime start date: {payload["regime_start_date"]}
- As-of issue: `{payload["as_of_issue"]}`
- Train window: {payload["train_window"]}
- Train mode: {payload["train_mode"]}
- Eval window: {payload["eval_window"]}
- Top-N cutoff: {payload["top_n"]}
- Workers: {payload["workers"]}
- Universe size: {payload["universe_size"]}

## Results

| Rank | Config | Top 100 | Top 1000 | Top 10000 | Median rank | Best rank | Worst rank |
| --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

## Protocol

- Every config scans the same complete `C(33,6)` universe from `ssq_red_combinations`.
- Each target issue trains only on prior draws.
- Random baseline is not used for candidate generation.
- Config promotion requires frozen-window improvement over baselines and prior configs.
"""


def run_grid_search(
    *,
    train_window: int,
    eval_window: int,
    top_n: int,
    as_of_issue: str | None,
    workers: int | None,
    train_mode: str,
    history_scope: HistoryScope,
    regime_years: int,
    output_dir: Path,
) -> dict:
    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=history_scope,
            as_of_issue=as_of_issue,
            regime_years=regime_years,
        )
        universe = load_red_combination_universe(conn)

    summaries = []
    for config in DEFAULT_GRID:
        result = run_walk_forward(
            history=selection.history,
            train_window=train_window,
            eval_window=eval_window,
            top_n=top_n,
            train_mode=train_mode,
            config=config,
            universe=universe,
            workers=workers,
        )
        summary = summarize_result(result, config)
        summary["run_key"] = deterministic_run_key(
            strategy_key=result.strategy_key,
            as_of_issue=result.as_of_issue,
            train_window=result.train_window,
            train_mode=result.train_mode,
            eval_window=result.eval_window,
            top_n=result.top_n,
            history_fingerprint_value=result.history_fingerprint,
            config_hash_value=result.config_hash,
        )
        summaries.append(summary)

    summaries.sort(key=sort_key, reverse=True)
    payload = {
        "history_scope": selection.scope,
        "regime_years": selection.regime_years,
        "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
        "regime_evidence_note": selection.evidence_note,
        "as_of_issue": summaries[0]["as_of_issue"] if summaries else "",
        "train_window": train_window,
        "train_mode": train_mode,
        "eval_window": eval_window,
        "top_n": top_n,
        "workers": workers,
        "universe_size": len(universe),
        "results": summaries,
    }
    key = f"weight-grid-asof-{payload['as_of_issue']}-{train_mode}-tw{train_window}-ew{eval_window}-top{top_n}"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{key}.json"
    report_path = output_dir / f"{key}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    report_path.write_text(render_grid_report(payload))
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(report_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-window", type=int, default=1000)
    parser.add_argument("--train-mode", choices=["expanding", "rolling"], default="expanding")
    parser.add_argument("--eval-window", type=int, default=100)
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--as-of-issue")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--history-scope", choices=["full_history_audit", "current_regime_default"], default="current_regime_default")
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "data/output/optimization")
    args = parser.parse_args()
    print(
        json.dumps(
            run_grid_search(
                train_window=args.train_window,
                eval_window=args.eval_window,
                top_n=args.top_n,
                as_of_issue=args.as_of_issue,
                workers=args.workers,
                train_mode=args.train_mode,
                history_scope=args.history_scope,
                regime_years=args.regime_years,
                output_dir=args.output_dir,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
