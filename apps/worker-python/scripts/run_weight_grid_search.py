from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from statistics import median

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.models.frequency_ranker import history_draw_date, history_issue, history_numbers
from dehps.optimization.regime import HistoryScope, select_history
from dehps.optimization.walk_forward import (
    TargetRank,
    build_ranked_universe,
    config_hash,
    create_worker_pool,
    deterministic_run_key,
    fingerprint_history,
    normalize_worker_count,
    rank_target_grid,
)
from dehps.storage.postgres_store import load_red_combination_universe


DEFAULT_GRID = [
    FrequencyRankerConfig(
        structural_weight=0.55,
        frequency_weight=0.30,
        omission_weight=0.15,
        previous_consecutive_weight=0.00,
    ),
    FrequencyRankerConfig(
        structural_weight=0.40,
        frequency_weight=0.45,
        omission_weight=0.15,
        previous_consecutive_weight=0.00,
    ),
    FrequencyRankerConfig(
        structural_weight=0.40,
        frequency_weight=0.30,
        omission_weight=0.30,
        previous_consecutive_weight=0.00,
    ),
    FrequencyRankerConfig(
        structural_weight=0.25,
        frequency_weight=0.50,
        omission_weight=0.25,
        previous_consecutive_weight=0.00,
    ),
    FrequencyRankerConfig(
        structural_weight=0.25,
        frequency_weight=0.25,
        omission_weight=0.50,
        previous_consecutive_weight=0.00,
    ),
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
        previous_consecutive_weight=0.00,
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


def summarize_target_ranks(
    *,
    target_ranks: list[TargetRank],
    config: FrequencyRankerConfig,
    as_of_issue: str,
    history_fingerprint_value: str,
) -> dict:
    ranks = [target.rank for target in target_ranks]
    return {
        "config": config.__dict__,
        "as_of_issue": as_of_issue,
        "history_fingerprint": history_fingerprint_value,
        "config_hash": config_hash(config),
        "evaluated_draws": len(target_ranks),
        "top_100_hits": sum(target.hit_top_100 for target in target_ranks),
        "top_1000_hits": sum(target.hit_top_1000 for target in target_ranks),
        "top_10000_hits": sum(target.hit_top_10000 for target in target_ranks),
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
- Static feature matrix rows: {payload["feature_matrix_cache"]["static_rows"]}
- Cached dynamic components: {payload["feature_matrix_cache"]["dynamic_components"]}

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
    progress_interval: int = 1,
) -> dict:
    started = time.time()

    def progress(message: str) -> None:
        print(f"[grid] {message}", file=sys.stderr, flush=True)

    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=history_scope,
            as_of_issue=as_of_issue,
            regime_years=regime_years,
        )
        universe = load_red_combination_universe(conn)

    configs = tuple(DEFAULT_GRID)
    worker_count = normalize_worker_count(workers)
    history = selection.dated_history
    if len(history) <= train_window:
        raise ValueError("history must be longer than train_window")
    if train_mode not in ("expanding", "rolling"):
        raise ValueError("train_mode must be 'expanding' or 'rolling'")

    progress(f"building static feature matrix rows={len(universe)} configs={len(configs)} workers={worker_count}")
    ranked_universe = build_ranked_universe(universe)
    progress(f"static feature matrix ready elapsed={time.time() - started:.1f}s")

    start_index = max(train_window, len(history) - eval_window)
    total_targets = len(history) - start_index
    target_rank_lists: list[list[TargetRank]] = [[] for _ in configs]
    pool = create_worker_pool(worker_count, ranked_universe)
    try:
        for progress_index, target_index in enumerate(range(start_index, len(history)), start=1):
            train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
            train_history = history[train_start:target_index]
            target_draw = history[target_index]
            issue = history_issue(target_draw)
            numbers = history_numbers(target_draw)
            ranked_targets = rank_target_grid(
                target_numbers=numbers,
                train_history=train_history,
                configs=configs,
                ranked_universe=ranked_universe,
                target_draw_date=history_draw_date(target_draw),
                workers=worker_count,
                pool=pool,
            )
            for config_index, (rank, score) in enumerate(ranked_targets):
                target_rank_lists[config_index].append(
                    TargetRank(
                        issue=issue,
                        rank=rank,
                        score=score,
                        hit_top_100=rank <= 100,
                        hit_top_1000=rank <= 1000,
                        hit_top_10000=rank <= 10000,
                    )
                )
            if progress_interval > 0 and (
                progress_index == 1 or progress_index == total_targets or progress_index % progress_interval == 0
            ):
                progress(
                    "target "
                    f"{progress_index}/{total_targets} issue={issue} train_draws={len(train_history)} "
                    f"elapsed={time.time() - started:.1f}s"
                )
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    as_of_issue_value = history[-1][0]
    history_fingerprint_value = fingerprint_history(history)
    summaries = []
    for config, target_ranks in zip(configs, target_rank_lists, strict=True):
        summary = summarize_target_ranks(
            target_ranks=target_ranks,
            config=config,
            as_of_issue=as_of_issue_value,
            history_fingerprint_value=history_fingerprint_value,
        )
        summary["run_key"] = deterministic_run_key(
            strategy_key="frequency_v1",
            as_of_issue=summary["as_of_issue"],
            train_window=train_window,
            train_mode=train_mode,
            eval_window=len(target_ranks),
            top_n=top_n,
            history_fingerprint_value=summary["history_fingerprint"],
            config_hash_value=summary["config_hash"],
        )
        summaries.append(summary)

    summaries.sort(key=sort_key, reverse=True)
    payload = {
        "history_scope": selection.scope,
        "regime_years": selection.regime_years,
        "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
        "regime_evidence_note": selection.evidence_note,
        "as_of_issue": as_of_issue_value,
        "train_window": train_window,
        "train_mode": train_mode,
        "eval_window": total_targets,
        "top_n": top_n,
        "workers": worker_count,
        "universe_size": len(universe),
        "feature_matrix_cache": {
            "static_rows": len(ranked_universe),
            "config_count": len(configs),
            "dynamic_components": "computed once per target and shared across all configs",
        },
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
    parser.add_argument("--progress-interval", type=int, default=1)
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
                progress_interval=args.progress_interval,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
