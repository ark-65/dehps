from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from dataclasses import asdict, replace
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
    CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,
    ensure_training_weight_signals_schema,
    has_training_weight_signal_run,
    load_history_until_with_dates,
    load_red_combination_universe,
    load_training_weight_signal_coverage,
    load_training_weight_signal_rows,
    load_training_weight_signal_tail,
    prune_stale_training_weight_signals,
    upsert_training_weight_signal,
)
from scripts.run_training_supervisor import ALL_FIELDS, PRIMARY_FIELDS
from scripts.run_training_supervisor import clamp_config, config_dict, summarize_target_ranks


TrainMode = Literal["expanding", "rolling"]
GenerationMode = Literal["full", "incremental"]
CANONICAL_SIGNAL_RUN_ID = CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID
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


def eligible_target_indexes(*, history_len: int, train_window: int) -> range:
    if train_window < 1:
        raise ValueError("train_window must be at least 1")
    if history_len <= train_window:
        return range(history_len, history_len)
    return range(train_window, history_len)


def selected_recent_eligible_target_indexes(
    *,
    history_len: int,
    train_window: int,
    issues: int,
    allow_partial: bool,
) -> range:
    if issues < 1:
        raise ValueError("issues must be at least 1")
    eligible = eligible_target_indexes(history_len=history_len, train_window=train_window)
    eligible_count = len(eligible)
    if eligible_count < issues and not allow_partial:
        raise ValueError(
            f"not enough eligible issues: requested {issues}, found {eligible_count}; "
            "use --allow-partial to materialize the available eligible issues"
        )
    selected_count = min(issues, eligible_count)
    start = history_len - selected_count
    return range(start, history_len)


def kdj_state_from_signal_row(row: dict) -> WeightKdjState:
    return WeightKdjState(
        rsv=float(row["rsv"]),
        k_value=float(row["k_value"]),
        d_value=float(row["d_value"]),
        j_value=float(row["j_value"]),
    )


def remember_signal_row(
    row: dict,
    *,
    previous_states: dict[str, WeightKdjState | None],
    previous_bounds: dict[str, deque[tuple[float, float]]],
) -> None:
    weight_name = str(row["weight_name"])
    if weight_name not in previous_states:
        return
    previous_states[weight_name] = kdj_state_from_signal_row(row)
    previous_bounds[weight_name].append((float(row["issue_low_value"]), float(row["issue_high_value"])))


def build_weight_signal(
    *,
    signal_run_id: str,
    target_draw,
    train_history,
    train_fingerprint: str,
    ranked_universe,
    weight_name: str,
    train_mode: TrainMode,
    train_window: int,
    top_n: int,
    base_config: FrequencyRankerConfig,
    primary_step: float,
    context_step: float,
    previous_bounds,
    previous_state: WeightKdjState | None,
):
    issue = history_issue(target_draw)
    draw_date = history_draw_date(target_draw)
    red_numbers = history_numbers(target_draw)
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

    return signal_from_probe_results(
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
        rolling_issue_bounds=previous_bounds,
        previous_state=previous_state,
    )


def generate_signals(
    *,
    signal_run_id: str,
    mode: GenerationMode,
    as_of_issue: str | None,
    issues: int,
    allow_partial: bool,
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
        indexes = list(
            selected_recent_eligible_target_indexes(
                history_len=len(history),
                train_window=train_window,
                issues=issues,
                allow_partial=allow_partial or mode == "incremental",
            )
        )
        selected_issues = tuple(history_issue(history[index]) for index in indexes)

        existing_by_pair: dict[tuple[str, str], dict] = {}
        missing_by_issue: dict[str, set[str]] = {issue: set(weights) for issue in selected_issues}
        skipped_without_seed = 0

        if mode == "incremental":
            if not has_training_weight_signal_run(conn, signal_run_id=signal_run_id):
                return {
                    "signal_run_id": signal_run_id,
                    "mode": mode,
                    "status": "seed_missing",
                    "eligible_issues": len(indexes),
                    "issues": 0,
                    "signals": 0,
                    "weights": {},
                    "dry_run": dry_run,
                }

            coverage = load_training_weight_signal_coverage(
                conn,
                signal_run_id=signal_run_id,
                issues=selected_issues,
                weights=weights,
            )
            missing_by_issue = {
                issue: set(weights) - coverage.get(issue, set())
                for issue in selected_issues
                if set(weights) - coverage.get(issue, set())
            }
            if not missing_by_issue:
                pruned = 0
                if not dry_run and as_of_issue is None and selected_issues:
                    pruned = prune_stale_training_weight_signals(conn, signal_run_id=signal_run_id, keep_issues=selected_issues)
                    conn.commit()
                return {
                    "signal_run_id": signal_run_id,
                    "mode": mode,
                    "status": "noop",
                    "eligible_issues": len(indexes),
                    "issues": 0,
                    "signals": 0,
                    "weights": {},
                    "pruned": pruned,
                    "dry_run": dry_run,
                }

            existing_rows = load_training_weight_signal_rows(
                conn,
                signal_run_id=signal_run_id,
                issues=selected_issues,
                weights=weights,
            )
            existing_by_pair = {(str(row["issue"]), str(row["weight_name"])): row for row in existing_rows}

        universe = load_red_combination_universe(conn)
        ranked_universe = build_ranked_universe(universe)

        previous_states: dict[str, WeightKdjState | None] = {weight_name: None for weight_name in weights}
        previous_bounds: dict[str, deque[tuple[float, float]]] = {
            weight_name: deque(maxlen=max(0, kdj_window - 1)) for weight_name in weights
        }

        if mode == "incremental" and selected_issues:
            for row in load_training_weight_signal_tail(
                conn,
                signal_run_id=signal_run_id,
                before_issue=selected_issues[0],
                weights=weights,
                limit_per_weight=max(0, kdj_window - 1),
            ):
                remember_signal_row(row, previous_states=previous_states, previous_bounds=previous_bounds)

        generated_signals = 0
        generated_issues: set[str] = set()
        weight_counts: dict[str, int] = defaultdict(int)

        for chunk_start in range(0, len(indexes), chunk_size):
            chunk = indexes[chunk_start : chunk_start + chunk_size]
            for target_index in chunk:
                target_draw = history[target_index]
                issue = history_issue(target_draw)
                train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
                train_history = history[train_start:target_index]
                train_fingerprint = fingerprint_history(train_history)

                for weight_name in weights:
                    if mode == "incremental" and weight_name not in missing_by_issue.get(issue, set()):
                        existing = existing_by_pair.get((issue, weight_name))
                        if existing:
                            remember_signal_row(
                                existing,
                                previous_states=previous_states,
                                previous_bounds=previous_bounds,
                            )
                        continue

                    if mode == "incremental" and previous_states[weight_name] is None:
                        skipped_without_seed += 1
                        continue

                    signal, state = build_weight_signal(
                        signal_run_id=signal_run_id,
                        target_draw=target_draw,
                        train_history=train_history,
                        train_fingerprint=train_fingerprint,
                        ranked_universe=ranked_universe,
                        weight_name=weight_name,
                        train_mode=train_mode,
                        train_window=train_window,
                        top_n=top_n,
                        base_config=base_config,
                        primary_step=primary_step,
                        context_step=context_step,
                        previous_bounds=previous_bounds[weight_name],
                        previous_state=previous_states[weight_name],
                    )
                    previous_states[weight_name] = state
                    previous_bounds[weight_name].append((signal.issue_low_value, signal.issue_high_value))
                    if not dry_run:
                        upsert_training_weight_signal(conn, asdict(signal))
                    generated_signals += 1
                    generated_issues.add(issue)
                    weight_counts[weight_name] += 1

            if not dry_run:
                conn.commit()
            print(
                json.dumps(
                    {
                        "signal_run_id": signal_run_id,
                        "mode": mode,
                        "processed_issues": len(generated_issues),
                        "processed_signals": generated_signals,
                        "chunk_end_issue": history_issue(history[chunk[-1]]) if chunk else None,
                        "dry_run": dry_run,
                    },
                    ensure_ascii=False,
                )
            )

        pruned = 0
        if not dry_run and as_of_issue is None and selected_issues:
            pruned = prune_stale_training_weight_signals(conn, signal_run_id=signal_run_id, keep_issues=selected_issues)
            conn.commit()

    return {
        "signal_run_id": signal_run_id,
        "mode": mode,
        "status": "generated" if generated_signals else ("partial" if skipped_without_seed else "noop"),
        "eligible_issues": len(indexes),
        "issues": len(generated_issues),
        "signals": generated_signals,
        "weights": dict(weight_counts),
        "skipped_without_seed": skipped_without_seed,
        "pruned": pruned,
        "dry_run": dry_run,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate per-issue per-weight KDJ response signals.")
    parser.add_argument("--signal-run-id", default=CANONICAL_SIGNAL_RUN_ID)
    parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    parser.add_argument("--as-of-issue")
    parser.add_argument("--issues", type=int, default=1000)
    parser.add_argument("--allow-partial", action="store_true")
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
        mode=args.mode,
        as_of_issue=args.as_of_issue,
        issues=args.issues,
        allow_partial=args.allow_partial,
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
