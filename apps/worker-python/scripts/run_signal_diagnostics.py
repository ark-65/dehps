from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.optimization.control_experiments import (
    load_config_json_candidate,
    validate_train_mode,
)
from dehps.optimization.regime import select_history
from dehps.optimization.signal_diagnostics import (
    DEFAULT_RANDOM_SEEDS,
    bind_signal_diagnostic_context,
    run_signal_diagnostics,
    write_signal_diagnostic_artifacts,
)
from dehps.optimization.walk_forward import (
    build_ranked_universe,
    fingerprint_history,
)
from scripts.run_control_experiments import latest_prior_base_config


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile diagnostic-only common-window feature ablation and full-space "
            "score-decile evidence."
        )
    )
    parser.add_argument("--as-of-issue")
    parser.add_argument("--train-mode", choices=("expanding", "rolling"), default="expanding")
    parser.add_argument("--train-window", type=int, default=900)
    parser.add_argument("--eval-window", type=int, default=60)
    parser.add_argument("--top-n", type=int, default=10_000)
    parser.add_argument(
        "--base-config-json",
        type=Path,
        help=(
            "Explicit frozen config artifact. When omitted, resolve the latest "
            "protocol-matched durable config and fall back visibly to defaults."
        ),
    )
    parser.add_argument(
        "--history-scope",
        choices=("full_history_audit", "current_regime_default"),
        default="current_regime_default",
    )
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument("--bootstrap-resamples", type=int, default=2_000)
    parser.add_argument("--random-pool-size", type=int, default=10_000)
    parser.add_argument(
        "--include-negative-controls",
        action="store_true",
        help=(
            "Add issue-outcome permutation, red-label permutation, and random-score "
            "controls while reusing the production scorer/selector boundaries."
        ),
    )
    parser.add_argument(
        "--seed-digests",
        default=",".join(DEFAULT_RANDOM_SEEDS),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "data/output/optimization/signal-diagnostics",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Do not create database schema while resolving the frozen base config.",
    )
    parser.add_argument(
        "--allow-dirty-smoke",
        action="store_true",
        help="Allow an explicitly non-authoritative development smoke from a dirty tree.",
    )
    args = parser.parse_args()

    if not args.allow_dirty_smoke:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        if status.stdout.strip():
            raise RuntimeError(
                "authoritative signal diagnostics require a clean source tree"
            )
    train_mode = validate_train_mode(args.train_mode)
    seed_digests = tuple(
        item.strip() for item in args.seed_digests.split(",") if item.strip()
    )
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

    if args.base_config_json is not None:
        loaded = load_config_json_candidate(args.base_config_json)
        if loaded.config is None:
            raise ValueError("explicit base config JSON did not produce a config")
        base_config = loaded.config
        base_metadata = {
            "source": "explicit_frozen_config_json",
            "path": str(args.base_config_json),
            "file_sha256": hashlib.sha256(
                args.base_config_json.read_bytes()
            ).hexdigest(),
        }
    else:
        production_universe = build_ranked_universe()
        base_config, base_metadata = latest_prior_base_config(
            as_of_issue=str(args.as_of_issue or history[-1][0]),
            history_fingerprint_value=fingerprint_history(history),
            train_window=args.train_window,
            train_mode=train_mode,
            eval_window=args.eval_window,
            top_n=args.top_n,
            universe_size=len(production_universe),
            ensure_schema=not args.read_only,
        )
    full_legal_universe = build_ranked_universe(
        include_hard_filter_exclusions=True,
    )
    payload = run_signal_diagnostics(
        history=history,
        base_config=base_config,
        ranked_universe=full_legal_universe,
        train_mode=train_mode,
        train_window=args.train_window,
        eval_window=args.eval_window,
        seed_digests=seed_digests,
        random_pool_size=args.random_pool_size,
        bootstrap_resamples=args.bootstrap_resamples,
        include_negative_controls=args.include_negative_controls,
    )
    payload = bind_signal_diagnostic_context(
        payload,
        base_config_metadata=base_metadata,
        history_scope={
            "scope": selection.scope,
            "regime_years": selection.regime_years,
            "regime_start_date": (
                selection.start_date.isoformat() if selection.start_date else None
            ),
            "evidence_note": selection.evidence_note,
        },
    )
    json_path, report_path = write_signal_diagnostic_artifacts(
        payload,
        args.output_dir,
    )
    print(
        json.dumps(
            {
                "status": payload["protocol"]["status"],
                "promotion_allowed": payload["protocol"]["promotion_allowed"],
                "snapshot_digest": payload["snapshot_digest"],
                "json_path": str(json_path),
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
