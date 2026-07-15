from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.db import get_connection
from dehps.optimization.control_experiments import validate_train_mode
from dehps.optimization.feature_ablation import (
    default_output_dir,
    run_feature_ablation,
    write_feature_ablation_artifacts,
)
from dehps.optimization.regime import select_history
from dehps.optimization.walk_forward import build_ranked_universe, fingerprint_history, normalize_worker_count
from scripts.run_control_experiments import latest_prior_base_config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run read-only leave-one-feature-family-out diagnostics on identical historical targets."
    )
    parser.add_argument("--as-of-issue")
    parser.add_argument("--train-mode", choices=["expanding", "rolling"], default="expanding")
    parser.add_argument("--train-window", type=int, default=900)
    parser.add_argument("--eval-window", type=int, default=100)
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument(
        "--history-scope",
        choices=["full_history_audit", "current_regime_default"],
        default="current_regime_default",
    )
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    args = parser.parse_args()

    train_mode = validate_train_mode(args.train_mode)
    workers = normalize_worker_count(args.workers)
    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=args.history_scope,
            as_of_issue=args.as_of_issue,
            regime_years=args.regime_years,
        )
    history = selection.dated_history
    if not history:
        raise ValueError("selected history is empty")
    ranked_universe = build_ranked_universe()
    base_config, base_metadata = latest_prior_base_config(
        as_of_issue=str(args.as_of_issue or history[-1][0]),
        history_fingerprint_value=fingerprint_history(history),
        train_window=args.train_window,
        train_mode=train_mode,
        eval_window=args.eval_window,
        top_n=args.top_n,
        universe_size=len(ranked_universe),
    )
    payload = run_feature_ablation(
        history=history,
        base_config=base_config,
        train_mode=train_mode,
        train_window=args.train_window,
        eval_window=args.eval_window,
        top_n=args.top_n,
        workers=workers,
        ranked_universe=ranked_universe,
    )
    payload["base_config_metadata"] = base_metadata
    payload["history_scope"] = {
        "scope": selection.scope,
        "regime_years": selection.regime_years,
        "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
        "evidence_note": selection.evidence_note,
    }
    json_path, report_path = write_feature_ablation_artifacts(payload, args.output_dir)
    print(
        json.dumps(
            {
                "json_path": str(json_path),
                "report_path": str(report_path),
                "status": payload["status"],
                "promotion_allowed": payload["promotion_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
