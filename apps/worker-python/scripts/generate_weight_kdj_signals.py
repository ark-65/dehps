from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from dataclasses import asdict, replace
from pathlib import Path
from typing import Literal

import numpy as np

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig, history_draw_date, history_issue, history_numbers
from dehps.optimization.walk_forward import (
    CONFIG_WEIGHT_FIELDS,
    RedFiveMatch,
    TargetRank,
    _components_for_matrix,
    _lex_less_than,
    build_ranked_universe,
    config_hash,
    fingerprint_history,
    is_excluded_red_combination,
    rank_target_grid_with_red5,
    score_components_for_numbers,
    score_from_components,
    train_frequency_stats,
)
from dehps.optimization.weight_kdj import (
    DEFAULT_KDJ_WINDOW,
    WeightKdjSignal,
    WeightKdjState,
    WeightProbeResult,
    signal_from_probe_results,
)
from dehps.runtime.heavy_job import apply_cpu_thread_env_defaults, heavy_job_lock
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


def build_weight_signals_for_issue(
    *,
    signal_run_id: str,
    target_draw,
    train_history,
    train_fingerprint: str,
    ranked_universe,
    weight_names: tuple[str, ...],
    train_mode: TrainMode,
    train_window: int,
    top_n: int,
    base_config: FrequencyRankerConfig,
    primary_step: float,
    context_step: float,
    previous_bounds: dict[str, deque[tuple[float, float]]],
    previous_states: dict[str, WeightKdjState | None],
) -> list[tuple[str, WeightKdjSignal, WeightKdjState]]:
    if not weight_names:
        return []
    issue = history_issue(target_draw)
    draw_date = history_draw_date(target_draw)
    red_numbers = history_numbers(target_draw)
    configs_by_weight: dict[str, tuple[FrequencyRankerConfig, ...]] = {}
    unique_configs: list[FrequencyRankerConfig] = []
    seen_hashes: set[str] = set()
    for weight_name in weight_names:
        step = field_step(weight_name, primary_step=primary_step, context_step=context_step)
        configs = probe_configs(base_config, weight_name=weight_name, step=step)
        configs_by_weight[weight_name] = configs
        for config in configs:
            key = config_hash(config)
            if key not in seen_hashes:
                seen_hashes.add(key)
                unique_configs.append(config)

    ranked_by_hash = fast_rank_probe_configs_with_red5(
        target_numbers=red_numbers,
        train_history=train_history,
        ranked_universe=ranked_universe,
        base_config=base_config,
        configs=tuple(unique_configs),
        target_draw_date=draw_date,
    )

    signals: list[tuple[str, WeightKdjSignal, WeightKdjState]] = []
    for weight_name, configs in configs_by_weight.items():
        step = field_step(weight_name, primary_step=primary_step, context_step=context_step)
        probe_results: list[WeightProbeResult] = []
        for config in configs:
            ranked_target = ranked_by_hash[config_hash(config)]
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
        signals.append((weight_name, signal, state))
    return signals


def fast_rank_probe_configs_with_red5(
    *,
    target_numbers: tuple[int, ...],
    train_history: list,
    ranked_universe,
    base_config: FrequencyRankerConfig,
    configs: tuple[FrequencyRankerConfig, ...],
    target_draw_date,
) -> dict[str, tuple[int, float, RedFiveMatch | None]]:
    if not configs:
        return {}
    if not hasattr(ranked_universe, "numbers"):
        ranked = rank_target_grid_with_red5(
            target_numbers=target_numbers,
            train_history=train_history,
            configs=configs,
            ranked_universe=ranked_universe,
            target_draw_date=target_draw_date,
        )
        return {config_hash(config): result for config, result in zip(configs, ranked, strict=True)}

    stats = train_frequency_stats(train_history, target_draw_date=target_draw_date)
    components = _components_for_matrix(ranked_universe, stats)
    base_weights = np.array([float(getattr(base_config, field)) for field in CONFIG_WEIGHT_FIELDS], dtype=np.float64)
    base_linear = components @ base_weights
    target_components = score_components_for_numbers(target_numbers, stats)
    target_excluded = is_excluded_red_combination(target_numbers)
    lex_less = _lex_less_than(ranked_universe.numbers, target_numbers)
    target_set = set(target_numbers)
    red5_indices = np.flatnonzero(ranked_universe.number_presence[:, list(target_numbers)].sum(axis=1) == 5)
    field_index = {field: index for index, field in enumerate(CONFIG_WEIGHT_FIELDS)}

    ranked: dict[str, tuple[int, float, RedFiveMatch | None]] = {}
    for config in configs:
        key = config_hash(config)
        if key in ranked:
            continue
        changed_fields = [
            field
            for field in CONFIG_WEIGHT_FIELDS
            if abs(float(getattr(config, field)) - float(getattr(base_config, field))) > 1e-12
        ]
        if len(changed_fields) == 1:
            field = changed_fields[0]
            delta = float(getattr(config, field)) - float(getattr(base_config, field))
            scores = np.round(base_linear + delta * components[:, field_index[field]], 8)
        elif not changed_fields:
            scores = np.round(base_linear, 8)
        else:
            weights = np.array([float(getattr(config, field)) for field in CONFIG_WEIGHT_FIELDS], dtype=np.float64)
            scores = np.round(components @ weights, 8)
        target_score = score_from_components(target_components, config)
        if target_excluded:
            target_rank = len(ranked_universe) + 1
        else:
            target_rank = int((scores > target_score).sum() + ((scores == target_score) & lex_less).sum() + 1)
        ranked[key] = (target_rank, float(target_score), best_red5_match_from_scores(ranked_universe, scores, red5_indices, target_set))
    return ranked


def best_red5_match_from_scores(
    ranked_universe,
    scores: np.ndarray,
    red5_indices: np.ndarray,
    target_set: set[int],
) -> RedFiveMatch | None:
    if not len(red5_indices):
        return None
    candidate_scores = scores[red5_indices]
    candidate_numbers = ranked_universe.numbers[red5_indices]
    order = np.lexsort(
        (
            candidate_numbers[:, 5],
            candidate_numbers[:, 5],
            candidate_numbers[:, 4],
            candidate_numbers[:, 3],
            candidate_numbers[:, 2],
            candidate_numbers[:, 1],
            candidate_numbers[:, 0],
            -candidate_scores,
        )
    )
    best_index = int(red5_indices[int(order[0])])
    best_numbers = tuple(int(number) for number in ranked_universe.numbers[best_index])
    best_score = float(scores[best_index])
    candidate_set = set(best_numbers)
    missing = sorted(target_set - candidate_set)
    extra = sorted(candidate_set - target_set)
    if len(missing) != 1 or len(extra) != 1:
        return None
    red5_better = int((scores > best_score).sum())
    red5_equal_before = int(((scores == best_score) & _lex_less_than(ranked_universe.numbers, best_numbers)).sum())
    return RedFiveMatch(
        rank=red5_better + red5_equal_before + 1,
        score=best_score,
        numbers=best_numbers,
        missing_number=missing[0],
        extra_number=extra[0],
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

                target_weights: list[str] = []
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
                    target_weights.append(weight_name)

                for weight_name, signal, state in build_weight_signals_for_issue(
                    signal_run_id=signal_run_id,
                    target_draw=target_draw,
                    train_history=train_history,
                    train_fingerprint=train_fingerprint,
                    ranked_universe=ranked_universe,
                    weight_names=tuple(target_weights),
                    train_mode=train_mode,
                    train_window=train_window,
                    top_n=top_n,
                    base_config=base_config,
                    primary_step=primary_step,
                    context_step=context_step,
                    previous_bounds=previous_bounds,
                    previous_states=previous_states,
                ):
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
    parser.add_argument("--heavy-job-lock-timeout-seconds", type=float, default=0.0)
    parser.add_argument("--cpu-threads", type=int, default=1)
    args = parser.parse_args()

    apply_cpu_thread_env_defaults(args.cpu_threads)
    with heavy_job_lock(
        owner="weight-kdj-signals",
        timeout_seconds=args.heavy_job_lock_timeout_seconds,
        context={"signal_run_id": args.signal_run_id, "mode": args.mode, "issues": args.issues},
    ) as lock:
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
        lock.heartbeat(status="completed", context={"signals": summary.get("signals"), "status": summary.get("status")})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
