from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Literal

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig, history_draw_date, history_issue, history_numbers
from dehps.optimization.walk_forward import TargetRank, build_ranked_universe, fingerprint_history, rank_target_grid_with_red5
from dehps.optimization.weight_kdj import (
    DEFAULT_KDJ_WINDOW,
    WeightKdjState,
    WeightProbeResult,
    signal_from_probe_results,
)
from dehps.storage.postgres_store import (
    ensure_training_weight_signals_schema,
    load_history_until_with_dates,
    load_red_combination_universe,
    upsert_training_weight_signal,
)
from scripts.run_training_supervisor import ALL_FIELDS, PRIMARY_FIELDS
from scripts.run_training_supervisor import clamp_config, config_dict, summarize_target_ranks


TrainMode = Literal["expanding", "rolling"]
DEFAULT_OFFSETS = (-2, -1, 0, 1, 2)


def parse_weights(value: str | None) -> tuple[str, ...]:
    if not value:
        return tuple(ALL_FIELDS)
    weights = tuple(item.strip() for item in value.split(",") if item.strip())
    unknown = sorted(set(weights) - set(ALL_FIELDS))
    if unknown:
        raise ValueError(f"unknown weight fields: {', '.join(unknown)}")
    return weights


def field_step(weight_name: str, *, primary_step: float, context_step: float) -> float:
    return primary_step if weight_name in PRIMARY_FIELDS else context_step


def probe_configs(
    base_config: FrequencyRankerConfig,
    *,
    weight_name: str,
    step: float,
    offsets: tuple[int, ...] = DEFAULT_OFFSETS,
) -> tuple[FrequencyRankerConfig, ...]:
    configs: list[FrequencyRankerConfig] = []
    seen_values: set[float] = set()
    base_value = float(getattr(base_config, weight_name))
    for offset in offsets:
        config = clamp_config(replace(base_config, **{weight_name: base_value + step * offset}))
        value = round(float(getattr(config, weight_name)), 6)
        if value in seen_values:
            continue
        seen_values.add(value)
        configs.append(config)
    return tuple(configs)


def target_rank_payload(
    *,
    issue: str,
    draw_date,
    red_numbers: tuple[int, ...],
    ranked_target: tuple[int, float, object | None],
) -> TargetRank:
    rank, score, red5_match = ranked_target
    return TargetRank(
        issue=issue,
        rank=rank,
        score=score,
        hit_top_100=rank <= 100,
        hit_top_1000=rank <= 1000,
        hit_top_10000=rank <= 10000,
        draw_date=draw_date,
        red_numbers=red_numbers,
        red5_rank=red5_match.rank if red5_match else None,
        red5_score=red5_match.score if red5_match else None,
        red5_numbers=red5_match.numbers if red5_match else None,
        red5_missing_number=red5_match.missing_number if red5_match else None,
        red5_extra_number=red5_match.extra_number if red5_match else None,
        hit_red5_top_100=red5_match is not None and red5_match.rank <= 100,
        hit_red5_top_1000=red5_match is not None and red5_match.rank <= 1000,
        hit_red5_top_10000=red5_match is not None and red5_match.rank <= 10000,
    )


def load_base_config(path: str | None) -> FrequencyRankerConfig:
    if not path:
        return FrequencyRankerConfig()
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ValueError("--base-config-json must point to a JSON object")
    values = config_dict(FrequencyRankerConfig())
    values.update({field: float(value) for field, value in payload.items() if field in values})
    return clamp_config(FrequencyRankerConfig(**values))


def selected_target_indexes(*, history_len: int, train_window: int, issues: int) -> range:
    if history_len <= train_window:
        raise ValueError("history must contain more rows than train_window")
    start = max(train_window, history_len - issues)
    return range(start, history_len)


def generate_signals(
    *,
    signal_run_id: str,
    as_of_issue: str | None,
    issues: int,
    train_mode: TrainMode,
    train_window: int,
    top_n: int,
    weights: tuple[str, ...],
    primary_step: float,
    context_step: float,
    kdj_window: int,
    chunk_size: int,
    base_config: FrequencyRankerConfig,
    dry_run: bool,
) -> dict:
    if issues < 1:
        raise ValueError("issues must be at least 1")
    if train_window < 1:
        raise ValueError("train_window must be at least 1")
    if kdj_window < 1:
        raise ValueError("kdj_window must be at least 1")
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    with get_connection() as conn:
        if not dry_run:
            ensure_training_weight_signals_schema(conn)
        history = load_history_until_with_dates(conn, as_of_issue)
        universe = load_red_combination_universe(conn)
        ranked_universe = build_ranked_universe(universe)
        indexes = list(selected_target_indexes(history_len=len(history), train_window=train_window, issues=issues))

        previous_states: dict[str, WeightKdjState | None] = {weight_name: None for weight_name in weights}
        previous_bounds: dict[str, deque[tuple[float, float]]] = {
            weight_name: deque(maxlen=max(0, kdj_window - 1)) for weight_name in weights
        }
        inserted = 0
        issue_count = 0
        weight_counts: dict[str, int] = defaultdict(int)

        for chunk_start in range(0, len(indexes), chunk_size):
            chunk = indexes[chunk_start : chunk_start + chunk_size]
            for target_index in chunk:
                target_draw = history[target_index]
                issue = history_issue(target_draw)
                draw_date = history_draw_date(target_draw)
                red_numbers = history_numbers(target_draw)
                train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
                train_history = history[train_start:target_index]
                train_fingerprint = fingerprint_history(train_history)
                issue_count += 1

                for weight_name in weights:
                    step = field_step(weight_name, primary_step=primary_step, context_step=context_step)
                    configs = probe_configs(base_config, weight_name=weight_name, step=step)
                    ranked_targets = rank_target_grid_with_red5(
                        target_numbers=red_numbers,
                        train_history=train_history,
                        configs=configs,
                        ranked_universe=ranked_universe,
                        target_draw_date=draw_date,
                    )
                    probe_results: list[WeightProbeResult] = []
                    for config, ranked_target in zip(configs, ranked_targets, strict=True):
                        target_rank = target_rank_payload(
                            issue=issue,
                            draw_date=draw_date,
                            red_numbers=red_numbers,
                            ranked_target=ranked_target,
                        )
                        summary = summarize_target_ranks(
                            target_ranks=[target_rank],
                            config=config,
                            as_of_issue=issue,
                            history_fingerprint_value=train_fingerprint,
                            train_window=train_window,
                            train_mode=train_mode,
                            top_n=top_n,
                            universe_size=len(ranked_universe),
                        )
                        probe_results.append(
                            WeightProbeResult(
                                weight_name=weight_name,
                                weight_value=float(getattr(config, weight_name)),
                                objective_score=float(summary["reward"]["objectiveScore"]),
                                config_hash=str(summary["config_hash"]),
                                rank=int(target_rank.rank),
                            )
                        )

                    signal, state = signal_from_probe_results(
                        signal_run_id=signal_run_id,
                        issue=issue,
                        draw_date=draw_date.isoformat() if draw_date else None,
                        weight_name=weight_name,
                        train_mode=train_mode,
                        train_window=train_window,
                        eval_window=1,
                        top_n=top_n,
                        history_fingerprint=train_fingerprint,
                        source="weight_response_probe_v0",
                        base_value=float(getattr(base_config, weight_name)),
                        step=step,
                        probe_results=probe_results,
                        rolling_issue_bounds=previous_bounds[weight_name],
                        previous_state=previous_states[weight_name],
                    )
                    previous_states[weight_name] = state
                    previous_bounds[weight_name].append((signal.issue_low_value, signal.issue_high_value))
                    if not dry_run:
                        upsert_training_weight_signal(conn, asdict(signal))
                    inserted += 1
                    weight_counts[weight_name] += 1

            if not dry_run:
                conn.commit()
            print(
                json.dumps(
                    {
                        "signal_run_id": signal_run_id,
                        "processed_issues": issue_count,
                        "processed_signals": inserted,
                        "chunk_end_issue": history_issue(history[chunk[-1]]) if chunk else None,
                        "dry_run": dry_run,
                    },
                    ensure_ascii=False,
                )
            )

    return {
        "signal_run_id": signal_run_id,
        "issues": issue_count,
        "signals": inserted,
        "weights": dict(weight_counts),
        "dry_run": dry_run,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate per-issue per-weight KDJ response signals.")
    parser.add_argument("--signal-run-id", default=f"weight-kdj-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    parser.add_argument("--as-of-issue")
    parser.add_argument("--issues", type=int, default=1000)
    parser.add_argument("--train-mode", choices=["expanding", "rolling"], default="expanding")
    parser.add_argument("--train-window", type=int, default=900)
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--weights", help="Comma-separated FrequencyRankerConfig fields. Defaults to all weights.")
    parser.add_argument("--primary-step", type=float, default=0.03)
    parser.add_argument("--context-step", type=float, default=0.01)
    parser.add_argument("--kdj-window", type=int, default=DEFAULT_KDJ_WINDOW)
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--base-config-json", help="Optional JSON object with base FrequencyRankerConfig overrides.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = generate_signals(
        signal_run_id=args.signal_run_id,
        as_of_issue=args.as_of_issue,
        issues=args.issues,
        train_mode=args.train_mode,
        train_window=args.train_window,
        top_n=args.top_n,
        weights=parse_weights(args.weights),
        primary_step=args.primary_step,
        context_step=args.context_step,
        kdj_window=args.kdj_window,
        chunk_size=args.chunk_size,
        base_config=load_base_config(args.base_config_json),
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
