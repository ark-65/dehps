from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time
from statistics import median

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig
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


PRIMARY_FIELDS = ("structural_weight", "frequency_weight", "omission_weight")
CONTEXT_FIELDS = (
    "previous_consecutive_weight",
    "previous_overlap_weight",
    "previous_parity_shape_weight",
    "previous_zone_shape_weight",
)
ALL_FIELDS = PRIMARY_FIELDS + CONTEXT_FIELDS
DEFAULT_UNIVERSE_SIZE = 1_107_568
PHASES = (
    ("micro", 0.01),
    ("small", 0.03),
    ("medium", 0.07),
    ("large", 0.15),
)


def log(message: str) -> None:
    print(f"[supervisor] {datetime.now().isoformat(timespec='seconds')} {message}", file=sys.stderr, flush=True)


def config_dict(config: FrequencyRankerConfig) -> dict[str, float]:
    return dict(config.__dict__)


def clamp_config(config: FrequencyRankerConfig) -> FrequencyRankerConfig:
    values = config_dict(config)
    for field in PRIMARY_FIELDS:
        values[field] = min(1.25, max(0.0, values[field]))
    for field in CONTEXT_FIELDS:
        values[field] = min(0.30, max(-0.30, values[field]))
    return FrequencyRankerConfig(**values)


def add_unique(configs: list[FrequencyRankerConfig], seen: set[str], config: FrequencyRankerConfig) -> None:
    normalized = clamp_config(config)
    key = json.dumps(config_dict(normalized), sort_keys=True)
    if key not in seen:
        seen.add(key)
        configs.append(normalized)


def generate_configs(
    base: FrequencyRankerConfig,
    *,
    phase: str,
    step: float,
    max_configs: int,
    elite_configs: tuple[FrequencyRankerConfig, ...] = (),
) -> list[FrequencyRankerConfig]:
    configs: list[FrequencyRankerConfig] = []
    seen: set[str] = set()
    add_unique(configs, seen, base)

    fine_step = max(0.005, step / 2)
    for elite in elite_configs[:4]:
        add_unique(configs, seen, elite)
        for field in ALL_FIELDS:
            add_unique(configs, seen, replace(elite, **{field: getattr(elite, field) + fine_step}))
            add_unique(configs, seen, replace(elite, **{field: getattr(elite, field) - fine_step}))

    if elite_configs:
        best = elite_configs[0]
        for other in elite_configs[1:4]:
            add_unique(configs, seen, blend_configs(best, other, 0.50))
            add_unique(configs, seen, extrapolate_config(best, other, 0.50))

    for field in ALL_FIELDS:
        add_unique(configs, seen, replace(base, **{field: getattr(base, field) + step}))
        add_unique(configs, seen, replace(base, **{field: getattr(base, field) - step}))

    if phase in {"medium", "large"}:
        add_unique(
            configs,
            seen,
            replace(
                base,
                structural_weight=base.structural_weight + step,
                frequency_weight=base.frequency_weight - step / 2,
                omission_weight=base.omission_weight - step / 2,
            ),
        )
        add_unique(
            configs,
            seen,
            replace(
                base,
                structural_weight=base.structural_weight - step / 2,
                frequency_weight=base.frequency_weight + step,
                omission_weight=base.omission_weight - step / 2,
            ),
        )
        add_unique(
            configs,
            seen,
            replace(
                base,
                structural_weight=base.structural_weight - step / 2,
                frequency_weight=base.frequency_weight - step / 2,
                omission_weight=base.omission_weight + step,
            ),
        )

    if phase == "large":
        large_candidates = (
            FrequencyRankerConfig(structural_weight=0.55, frequency_weight=0.30, omission_weight=0.15, previous_consecutive_weight=0.00),
            FrequencyRankerConfig(structural_weight=0.25, frequency_weight=0.50, omission_weight=0.25, previous_consecutive_weight=0.00),
            FrequencyRankerConfig(structural_weight=0.25, frequency_weight=0.25, omission_weight=0.50, previous_consecutive_weight=0.00),
            FrequencyRankerConfig(
                structural_weight=0.35,
                frequency_weight=0.30,
                omission_weight=0.25,
                previous_consecutive_weight=0.03,
                previous_overlap_weight=-0.04,
                previous_parity_shape_weight=0.03,
                previous_zone_shape_weight=0.08,
            ),
        )
        for config in large_candidates:
            add_unique(configs, seen, config)

    return configs[:max_configs]


def blend_configs(left: FrequencyRankerConfig, right: FrequencyRankerConfig, alpha: float) -> FrequencyRankerConfig:
    return clamp_config(
        FrequencyRankerConfig(
            **{
                field: getattr(left, field) * alpha + getattr(right, field) * (1 - alpha)
                for field in ALL_FIELDS
            }
        )
    )


def extrapolate_config(best: FrequencyRankerConfig, other: FrequencyRankerConfig, scale: float) -> FrequencyRankerConfig:
    return clamp_config(
        FrequencyRankerConfig(
            **{
                field: getattr(best, field) + (getattr(best, field) - getattr(other, field)) * scale
                for field in ALL_FIELDS
            }
        )
    )


def reward_summary(summary: dict, *, universe_size: int = DEFAULT_UNIVERSE_SIZE) -> dict[str, float]:
    safe_universe = max(1, universe_size)
    hit_reward = summary["top_100_hits"] * 100 + summary["top_1000_hits"] * 20 + summary["top_10000_hits"] * 5
    median_rank = summary.get("median_rank") or safe_universe
    worst_rank = summary.get("worst_rank") or safe_universe
    rank_penalty = median_rank / safe_universe + worst_rank / safe_universe / 4
    return {
        "hitReward": round(hit_reward, 6),
        "rankPenalty": round(rank_penalty, 6),
        "objectiveScore": round(hit_reward - rank_penalty, 6),
    }


def summarize_target_ranks(
    *,
    target_ranks: list[TargetRank],
    config: FrequencyRankerConfig,
    as_of_issue: str,
    history_fingerprint_value: str,
    train_window: int,
    train_mode: str,
    top_n: int,
    universe_size: int,
) -> dict:
    ranks = [target.rank for target in target_ranks]
    summary = {
        "config": config_dict(config),
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
    summary["reward"] = reward_summary(summary, universe_size=universe_size)
    summary["run_key"] = deterministic_run_key(
        strategy_key="frequency_v1",
        as_of_issue=as_of_issue,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=len(target_ranks),
        top_n=top_n,
        history_fingerprint_value=history_fingerprint_value,
        config_hash_value=summary["config_hash"],
    )
    return summary


def sort_key(summary: dict) -> tuple:
    reward = summary.get("reward") or reward_summary(summary)
    return (
        summary["top_100_hits"],
        summary["top_1000_hits"],
        summary["top_10000_hits"],
        reward["objectiveScore"],
        -(summary["median_rank"] or 0),
        -(summary["best_rank"] or 0),
    )


def merge_leaderboard(existing: list[dict], candidates: list[dict], *, limit: int = 12) -> list[dict]:
    by_hash: dict[str, dict] = {item["config_hash"]: item for item in existing}
    for candidate in candidates:
        current = by_hash.get(candidate["config_hash"])
        if current is None or sort_key(candidate) > sort_key(current):
            by_hash[candidate["config_hash"]] = candidate
    return sorted(by_hash.values(), key=sort_key, reverse=True)[:limit]


def evaluate_configs(
    *,
    history: list[tuple[str, tuple[int, ...]]],
    ranked_universe,
    configs: tuple[FrequencyRankerConfig, ...],
    train_window: int,
    train_mode: str,
    eval_window: int,
    top_n: int,
    workers: int,
    pool,
    progress_interval: int,
    round_index: int,
) -> list[dict]:
    start_index = max(train_window, len(history) - eval_window)
    total_targets = len(history) - start_index
    target_rank_lists: list[list[TargetRank]] = [[] for _ in configs]
    started = time.time()

    for progress_index, target_index in enumerate(range(start_index, len(history)), start=1):
        train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
        train_history = history[train_start:target_index]
        issue, numbers = history[target_index]
        ranked_targets = rank_target_grid(
            target_numbers=numbers,
            train_history=train_history,
            configs=configs,
            ranked_universe=ranked_universe,
            workers=workers,
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
            log(
                f"round={round_index} target={progress_index}/{total_targets} "
                f"issue={issue} train_draws={len(train_history)} elapsed={time.time() - started:.1f}s"
            )

    as_of_issue = history[-1][0]
    history_fingerprint_value = fingerprint_history(history)
    summaries = [
        summarize_target_ranks(
            target_ranks=target_ranks,
            config=config,
            as_of_issue=as_of_issue,
            history_fingerprint_value=history_fingerprint_value,
            train_window=train_window,
            train_mode=train_mode,
            top_n=top_n,
            universe_size=len(ranked_universe),
        )
        for config, target_ranks in zip(configs, target_rank_lists, strict=True)
    ]
    summaries.sort(key=sort_key, reverse=True)
    return summaries


def write_status(output_path: Path, status: dict) -> None:
    output_path.write_text(json.dumps(status, ensure_ascii=False, indent=2))


def write_report(report_path: Path, status: dict) -> None:
    rounds = "\n".join(
        (
            f"| {round_info['round']} | {round_info['phase']} | {round_info['best']['top_10000_hits']} | "
            f"{round_info['best']['top_1000_hits']} | {round_info['best']['top_100_hits']} | "
            f"{round_info['best']['median_rank']} | `{json.dumps(round_info['best']['config'], sort_keys=True)}` |"
        )
        for round_info in status["rounds"]
    )
    best = status["best"]
    report_path.write_text(
        f"""# DEHPS 24h Training Supervisor Report

- Run id: `{status["run_id"]}`
- Started at: {status["started_at"]}
- Updated at: {status["updated_at"]}
- Deadline: {status["deadline"]}
- Status: {status["status"]}
- Train mode: `{status["train_mode"]}`
- Train window: {status["train_window"]}
- Eval window: {status["eval_window"]}
- Top-N: {status["top_n"]}
- Workers: {status["workers"]}
- Memory budget GB: {status["memory_budget_gb"]}
- Universe size: {status["universe_size"]}

## Current Best

```json
{json.dumps(best, ensure_ascii=False, indent=2, sort_keys=True)}
```

## Rounds

| Round | Phase | Top10000 | Top1000 | Top100 | Median rank | Config |
| --- | --- | --- | --- | --- | --- | --- |
{rounds}

## Guardrail

The supervisor optimizes historical expanding walk-forward rank coverage. Any large jump must be checked for leakage and validated on future frozen draws before promotion.
"""
    )


def run_supervisor(
    *,
    duration_hours: float,
    train_window: int,
    eval_window: int,
    top_n: int,
    as_of_issue: str | None,
    workers: int | None,
    train_mode: str,
    history_scope: HistoryScope,
    regime_years: int,
    output_dir: Path,
    progress_interval: int,
    max_configs_per_round: int,
    memory_budget_gb: int,
) -> dict:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    started_at = datetime.now()
    deadline = started_at + timedelta(hours=duration_hours)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / f"training-supervisor-{run_id}.json"
    report_path = output_dir / f"training-supervisor-{run_id}.md"

    with get_connection() as conn:
        selection = select_history(conn, scope=history_scope, as_of_issue=as_of_issue, regime_years=regime_years)
        universe = load_red_combination_universe(conn)

    worker_count = normalize_worker_count(workers)
    log(
        f"run_id={run_id} building static universe rows={len(universe)} workers={worker_count} "
        f"memory_budget_gb={memory_budget_gb}"
    )
    ranked_universe = build_ranked_universe(universe)
    pool = create_worker_pool(worker_count, ranked_universe)

    base_config = FrequencyRankerConfig()
    best_summary: dict | None = None
    leaderboard: list[dict] = []
    rounds: list[dict] = []
    status = {
        "run_id": run_id,
        "started_at": started_at.isoformat(timespec="seconds"),
        "updated_at": started_at.isoformat(timespec="seconds"),
        "deadline": deadline.isoformat(timespec="seconds"),
        "status": "running",
        "pid": os.getpid(),
        "history_scope": selection.scope,
        "regime_years": selection.regime_years,
        "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
        "train_mode": train_mode,
        "train_window": train_window,
        "eval_window": eval_window,
        "top_n": top_n,
        "workers": worker_count,
        "memory_budget_gb": memory_budget_gb,
        "universe_size": len(ranked_universe),
        "rounds": rounds,
        "best": None,
        "status_path": str(status_path),
        "report_path": str(report_path),
    }

    try:
        round_index = 0
        while round_index == 0 or datetime.now() < deadline:
            phase, step = PHASES[round_index % len(PHASES)]
            elite_configs = tuple(FrequencyRankerConfig(**summary["config"]) for summary in leaderboard[:4])
            configs = tuple(
                generate_configs(
                    base_config,
                    phase=phase,
                    step=step,
                    max_configs=max_configs_per_round,
                    elite_configs=elite_configs,
                )
            )
            log(f"round={round_index + 1} phase={phase} step={step} configs={len(configs)} base={config_dict(base_config)}")
            summaries = evaluate_configs(
                history=selection.history,
                ranked_universe=ranked_universe,
                configs=configs,
                train_window=train_window,
                train_mode=train_mode,
                eval_window=eval_window,
                top_n=top_n,
                workers=worker_count,
                pool=pool,
                progress_interval=progress_interval,
                round_index=round_index + 1,
            )
            round_best = summaries[0]
            leaderboard = merge_leaderboard(leaderboard, summaries[: min(8, len(summaries))])
            improved = best_summary is None or sort_key(round_best) > sort_key(best_summary)
            if improved:
                best_summary = round_best
                base_config = FrequencyRankerConfig(**round_best["config"])
                log(f"round={round_index + 1} retained_new_best={round_best}")
            else:
                log(f"round={round_index + 1} no_improvement best_top10000={best_summary['top_10000_hits'] if best_summary else 'n/a'}")

            rounds.append(
                {
                    "round": round_index + 1,
                    "phase": phase,
                    "step": step,
                    "config_count": len(configs),
                    "improved": improved,
                    "best": round_best,
                    "top_results": summaries[: min(5, len(summaries))],
                }
            )
            status["updated_at"] = datetime.now().isoformat(timespec="seconds")
            status["best"] = best_summary
            write_status(status_path, status)
            write_report(report_path, status)
            round_index += 1

        status["status"] = "completed"
    except KeyboardInterrupt:
        status["status"] = "interrupted"
        raise
    except Exception as exc:
        status["status"] = "failed"
        status["error_message"] = str(exc)
        raise
    finally:
        if pool is not None:
            pool.close()
            pool.join()
        status["updated_at"] = datetime.now().isoformat(timespec="seconds")
        status["best"] = best_summary
        write_status(status_path, status)
        write_report(report_path, status)
        log(f"finished status={status['status']} status_path={status_path} report_path={report_path}")

    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-hours", type=float, default=24.0)
    parser.add_argument("--train-window", type=int, default=900)
    parser.add_argument("--eval-window", type=int, default=100)
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--as-of-issue")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--train-mode", choices=["expanding", "rolling"], default="expanding")
    parser.add_argument("--history-scope", choices=["full_history_audit", "current_regime_default"], default="current_regime_default")
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "data/output/optimization")
    parser.add_argument("--progress-interval", type=int, default=10)
    parser.add_argument("--max-configs-per-round", type=int, default=20)
    parser.add_argument("--memory-budget-gb", type=int, default=20)
    args = parser.parse_args()
    print(
        json.dumps(
            run_supervisor(
                duration_hours=args.duration_hours,
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
                max_configs_per_round=args.max_configs_per_round,
                memory_budget_gb=args.memory_budget_gb,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
