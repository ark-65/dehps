from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from statistics import median

import numpy as np

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.db import get_connection
from dehps.models.frequency_ranker import history_draw_date, history_issue, history_numbers
from dehps.optimization.dynamic_kdj_backtest import target_indexes
from dehps.optimization.near_residual import (
    orthogonal_residual_blend,
    random_top_n_overlap_baseline,
    rank_metrics_from_scores,
)
from dehps.optimization.next_candidates import (
    dynamic_kdj_config_for_next,
    dynamic_strength_policy_from_anchor,
)
from dehps.optimization.regime import select_history
from dehps.optimization.walk_forward import (
    build_ranked_universe,
    fingerprint_history,
    score_config_grid,
)
from dehps.storage.postgres_store import (
    CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,
    load_recent_training_weight_signals,
    load_red_combination_universe,
)
from scripts.run_dynamic_kdj_backtest import resolve_base_config


def _summary(rows: list[dict], key: str) -> dict:
    metrics = [row[key] for row in rows]
    exact_ranks = [int(metric["exact_rank"]) for metric in metrics if metric["exact_rank"] is not None]
    count = len(metrics)
    return {
        "issues": count,
        "red4_plus_top100_count": sum(bool(metric["red4_plus_top_n"]) for metric in metrics),
        "red4_plus_top100_rate": sum(bool(metric["red4_plus_top_n"]) for metric in metrics) / count,
        "red5_plus_top100_count": sum(bool(metric["red5_plus_top_n"]) for metric in metrics),
        "red5_plus_top100_rate": sum(bool(metric["red5_plus_top_n"]) for metric in metrics) / count,
        "exact_top100_count": sum(bool(metric["exact_top_n"]) for metric in metrics),
        "exact_top100_rate": sum(bool(metric["exact_top_n"]) for metric in metrics) / count,
        "median_exact_rank": median(exact_ranks) if exact_ranks else None,
        "mean_max_overlap_top100": sum(int(metric["max_overlap_top_n"]) for metric in metrics) / count,
    }


def _block_summaries(rows: list[dict], block_size: int) -> list[dict]:
    blocks: list[dict] = []
    for start in range(0, len(rows), block_size):
        block = rows[start : start + block_size]
        if not block:
            continue
        blocks.append(
            {
                "issues": [row["issue"] for row in block],
                "static": _summary(block, "static"),
                "dynamic": _summary(block, "dynamic"),
                "residual": _summary(block, "residual"),
                "shuffled_residual": _summary(block, "shuffled_residual"),
            }
        )
    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest an orthogonal near-term residual score without changing live snapshots.")
    parser.add_argument("--as-of-issue")
    parser.add_argument("--eval-window", type=int, default=27)
    parser.add_argument("--block-size", type=int, default=9)
    parser.add_argument("--train-window", type=int, default=900)
    parser.add_argument("--top-n", type=int, default=100)
    parser.add_argument("--anchor-offset-scale", type=float, default=0.25)
    parser.add_argument("--residual-strength", type=float, default=0.25)
    parser.add_argument("--signal-run-id", default=CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID)
    parser.add_argument("--kdj-signal-limit", type=int, default=1000)
    parser.add_argument("--base-config-source", choices=["latest-training-best", "default"], default="latest-training-best")
    parser.add_argument("--base-config-json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.eval_window < 1 or args.block_size < 1 or args.train_window < 1 or args.top_n < 1:
        raise ValueError("window and top-n arguments must be positive")
    if args.top_n != 100:
        raise ValueError("this frozen protocol requires --top-n 100")

    with get_connection() as conn:
        selection = select_history(
            conn,
            scope="current_regime_default",
            as_of_issue=args.as_of_issue,
            regime_years=10,
        )
        universe = load_red_combination_universe(conn)
        signals = load_recent_training_weight_signals(
            conn,
            signal_run_id=args.signal_run_id,
            as_of_issue=args.as_of_issue,
            # The live near line uses the supervisor's expanding-mode KDJ signal
            # stream, then scores each target on a rolling history window.
            train_mode="expanding",
            train_window=args.train_window,
            top_n=10000,
            limit=args.kdj_signal_limit,
        )
    history = selection.dated_history
    if not history or not signals:
        raise ValueError("history and KDJ signals are required")
    matrix = build_ranked_universe(universe)
    base_config, base_metadata = resolve_base_config(
        source=args.base_config_source,
        base_config_json=args.base_config_json,
        as_of_issue=history_issue(history[-1]),
        history_fingerprint_value=fingerprint_history(history),
        train_window=args.train_window,
        train_mode="expanding",
        eval_window=100,
        top_n=10000,
        universe_size=len(matrix),
    )
    strength_policy = dynamic_strength_policy_from_anchor(args.anchor_offset_scale)
    rows: list[dict] = []
    for target_index in target_indexes(
        history_len=len(history),
        train_window=args.train_window,
        eval_window=args.eval_window,
    ):
        target_draw = history[target_index]
        issue = history_issue(target_draw)
        train_history = history[max(0, target_index - args.train_window) : target_index]
        dynamic_config, dynamic_metadata = dynamic_kdj_config_for_next(
            base_config=base_config,
            signals=signals,
            target_issue=issue,
            offset_scale=args.anchor_offset_scale,
            strength_policy=strength_policy,
        )
        score_grid = score_config_grid(
            train_history=train_history,
            configs=(base_config, dynamic_config),
            ranked_universe=matrix,
            target_draw_date=history_draw_date(target_draw),
        )
        blend = orthogonal_residual_blend(
            score_grid[:, 0],
            score_grid[:, 1],
            residual_strength=args.residual_strength,
        )
        seed = int.from_bytes(sha256(issue.encode()).digest()[:8], "big")
        shuffled = np.random.default_rng(seed).permutation(blend.residual_z)
        shuffled_scores = blend.static_z + args.residual_strength * shuffled
        target_numbers = history_numbers(target_draw)
        rows.append(
            {
                "issue": issue,
                "latest_signal_issue": dynamic_metadata["latest_signal_issue"],
                "leakage_passed": dynamic_metadata["leakage_passed"],
                "effective_offset_scale": dynamic_metadata["effective_offset_scale"],
                "changed_weight_count": len(dynamic_metadata["applied_offsets"]),
                "blend": blend.metadata,
                "static": rank_metrics_from_scores(
                    ranked_universe=matrix, scores=score_grid[:, 0], target_numbers=target_numbers, top_n=args.top_n
                ),
                "dynamic": rank_metrics_from_scores(
                    ranked_universe=matrix, scores=score_grid[:, 1], target_numbers=target_numbers, top_n=args.top_n
                ),
                "residual": rank_metrics_from_scores(
                    ranked_universe=matrix, scores=blend.scores, target_numbers=target_numbers, top_n=args.top_n
                ),
                "shuffled_residual": rank_metrics_from_scores(
                    ranked_universe=matrix, scores=shuffled_scores, target_numbers=target_numbers, top_n=args.top_n
                ),
            }
        )
        print(f"completed issue {issue} ({len(rows)}/{args.eval_window})", file=sys.stderr, flush=True)

    summaries = {key: _summary(rows, key) for key in ("static", "dynamic", "residual", "shuffled_residual")}
    blocks = _block_summaries(rows, args.block_size)
    residual_red4 = summaries["residual"]["red4_plus_top100_count"]
    random_red4_rate = random_top_n_overlap_baseline(top_n=args.top_n, minimum_overlap=4)
    acceptance = {
        "passed": (
            residual_red4 > summaries["static"]["red4_plus_top100_count"]
            and residual_red4 > summaries["shuffled_residual"]["red4_plus_top100_count"]
            and summaries["residual"]["red4_plus_top100_rate"] > random_red4_rate
            and all(
                block["residual"]["red4_plus_top100_count"] >= block["static"]["red4_plus_top100_count"]
                for block in blocks
            )
            and all(row["leakage_passed"] for row in rows)
        ),
        "rule": "residual red4+ Top100 must beat static, shuffled control, and the same-budget random rate overall; never lose to static in a block; and pass leakage",
        "production_changed": False,
    }
    payload = {
        "protocol": "near-orthogonal-residual-v1-isolated",
        "as_of_issue": history_issue(history[-1]),
        "history_boundary": "each target uses only the preceding rolling train window; KDJ signals require issue < target",
        "train_window": args.train_window,
        "eval_window": args.eval_window,
        "block_size": args.block_size,
        "top_n": args.top_n,
        "anchor_offset_scale": args.anchor_offset_scale,
        "residual_strength": args.residual_strength,
        "base_config": base_metadata,
        "random_same_budget_baseline": {
            "red4_plus_top100": random_red4_rate,
            "red5_plus_top100": random_top_n_overlap_baseline(top_n=args.top_n, minimum_overlap=5),
            "exact_top100": random_top_n_overlap_baseline(top_n=args.top_n, minimum_overlap=6),
        },
        "summaries": summaries,
        "blocks": blocks,
        "acceptance": acceptance,
        "rows": rows,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
