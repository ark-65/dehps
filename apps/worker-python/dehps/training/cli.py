from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from dehps.config import ROOT_DIR
from dehps.training import runtime
from dehps.training.production_runtime import build_production_training_session
from dehps.training.supervisor import (
    SupervisorDependencies,
    TrainingSupervisor,
    TrainingSupervisorSettings,
)
from dehps.training.round_runner import TrainingRoundRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-hours", type=float, default=0.0, help="Training duration. Use 0 or a negative value to run continuously until stopped.")
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
    parser.add_argument("--max-configs-per-round", type=int, default=28)
    parser.add_argument("--max-rounds", type=int, help="Bound completed rounds for isolated smoke validation; defaults to unbounded.")
    parser.add_argument(
        "--frozen-plateau-patience",
        type=int,
        help=(
            "Stop between completed rounds after this many rounds without a strict "
            "frozen-validation frontier improvement."
        ),
    )
    parser.add_argument(
        "--observability-only",
        action="store_true",
        help=(
            "Run bounded full training rounds while disabling database, prediction, "
            "promotion-state, and event writes. Requires --max-rounds >= 1."
        ),
    )
    parser.add_argument("--memory-budget-gb", type=int, default=20)
    parser.add_argument("--event-url", default=os.getenv("DEHPS_TRAINING_EVENT_URL", runtime.DEFAULT_TRAINING_EVENT_URL))
    parser.add_argument("--write-status-json", action="store_true", help="Write a compact legacy status JSON snapshot.")
    parser.add_argument("--enable-weight-kdj-advisor", action="store_true", help="Use stored weight KDJ signals as advisor-only candidate proposals.")
    parser.add_argument("--enable-ridge-kdj-advisor", action="store_true", help="Use stored weight KDJ signals for advisor-only Ridge offset proposals.")
    parser.add_argument("--enable-neural-kdj-advisor", action="store_true", help="Use stored weight KDJ signals for advisor-only NumPy MLP offset proposals.")
    parser.add_argument("--disable-target-weight-inversion-advisor", action="store_true", help="Disable target-results inversion proposals for the next round.")
    parser.add_argument("--weight-kdj-run-id", help="Optional training_weight_signals signal_run_id to read.")
    parser.add_argument("--weight-kdj-limit", type=int, default=1000, help="Recent signal points per weight for advisor context.")
    parser.add_argument("--weight-kdj-budget-share", type=float, default=runtime.DEFAULT_WEIGHT_KDJ_BUDGET_SHARE, help="Candidate budget share reserved for KDJ advisor proposals when enabled.")
    parser.add_argument("--weight-kdj-min-objective-delta", type=float, default=runtime.DEFAULT_WEIGHT_KDJ_MIN_OBJECTIVE_DELTA)
    parser.add_argument("--weight-kdj-min-abs-offset", type=float, default=runtime.DEFAULT_WEIGHT_KDJ_MIN_ABS_OFFSET)
    parser.add_argument("--weight-kdj-slope-window", type=int, default=runtime.DEFAULT_WEIGHT_KDJ_SLOPE_WINDOW)
    parser.add_argument("--weight-kdj-neutral-band", type=float, default=runtime.DEFAULT_WEIGHT_KDJ_NEUTRAL_BAND)
    parser.add_argument("--ridge-kdj-budget-share", type=float, default=runtime.DEFAULT_RIDGE_KDJ_BUDGET_SHARE, help="Candidate budget share reserved for Ridge KDJ advisor proposals when enabled.")
    parser.add_argument("--ridge-kdj-alpha", type=float, default=runtime.DEFAULT_RIDGE_KDJ_ALPHA)
    parser.add_argument("--ridge-kdj-min-confidence", type=float, default=runtime.DEFAULT_RIDGE_KDJ_MIN_CONFIDENCE)
    parser.add_argument("--ridge-kdj-min-train-rows", type=int, default=runtime.DEFAULT_RIDGE_KDJ_MIN_TRAIN_ROWS)
    parser.add_argument("--ridge-kdj-min-validation-rows", type=int, default=runtime.DEFAULT_RIDGE_KDJ_MIN_VALIDATION_ROWS)
    parser.add_argument("--neural-kdj-budget-share", type=float, default=runtime.DEFAULT_NEURAL_KDJ_BUDGET_SHARE, help="Candidate budget share reserved for Neural KDJ advisor proposals when enabled.")
    parser.add_argument("--neural-kdj-min-confidence", type=float, default=runtime.DEFAULT_NEURAL_KDJ_MIN_CONFIDENCE)
    parser.add_argument("--neural-kdj-seed", type=int, default=runtime.DEFAULT_NEURAL_KDJ_SEED)
    parser.add_argument("--neural-kdj-hidden-units", type=int, default=runtime.DEFAULT_NEURAL_KDJ_HIDDEN_UNITS)
    parser.add_argument("--neural-kdj-epochs", type=int, default=runtime.DEFAULT_NEURAL_KDJ_EPOCHS)
    parser.add_argument("--target-weight-inversion-budget-share", type=float, default=runtime.DEFAULT_TARGET_WEIGHT_INVERSION_BUDGET_SHARE)
    parser.add_argument("--target-weight-inversion-max-candidates", type=int, default=runtime.DEFAULT_TARGET_WEIGHT_INVERSION_MAX_CANDIDATES)
    parser.add_argument("--target-weight-inversion-max-targets", type=int, default=runtime.DEFAULT_TARGET_WEIGHT_INVERSION_MAX_TARGETS)
    parser.add_argument("--target-weight-inversion-max-deltas-per-target", type=int, default=runtime.DEFAULT_TARGET_WEIGHT_INVERSION_MAX_DELTAS_PER_TARGET)
    parser.add_argument("--heavy-job-lock-timeout-seconds", type=float, default=0.0)
    parser.add_argument("--cpu-threads", type=int, default=1)
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def build_training_dependencies(_args: argparse.Namespace) -> SupervisorDependencies:
    return SupervisorDependencies(
        build_round_runner=lambda arguments: TrainingRoundRunner.for_production(
            build_production_training_session(**arguments)
        )
    )


def build_settings(args: argparse.Namespace) -> TrainingSupervisorSettings:
    return TrainingSupervisorSettings(
        cpu_threads=args.cpu_threads,
        heavy_job_lock_timeout_seconds=args.heavy_job_lock_timeout_seconds,
        run_arguments={
            "duration_hours": args.duration_hours,
            "train_window": args.train_window,
            "eval_window": args.eval_window,
            "top_n": args.top_n,
            "as_of_issue": args.as_of_issue,
            "workers": args.workers,
            "train_mode": args.train_mode,
            "history_scope": args.history_scope,
            "regime_years": args.regime_years,
            "output_dir": args.output_dir,
            "progress_interval": args.progress_interval,
            "max_configs_per_round": args.max_configs_per_round,
            "max_rounds": args.max_rounds,
            "frozen_plateau_patience": args.frozen_plateau_patience,
            "observability_only": args.observability_only,
            "memory_budget_gb": args.memory_budget_gb,
            "event_url": args.event_url,
            "write_status_json": args.write_status_json,
            "enable_weight_kdj_advisor": args.enable_weight_kdj_advisor,
            "enable_ridge_kdj_advisor": args.enable_ridge_kdj_advisor,
            "enable_neural_kdj_advisor": args.enable_neural_kdj_advisor,
            "enable_target_weight_inversion_advisor": not args.disable_target_weight_inversion_advisor,
            "weight_kdj_run_id": args.weight_kdj_run_id,
            "weight_kdj_limit": args.weight_kdj_limit,
            "weight_kdj_budget_share": args.weight_kdj_budget_share,
            "weight_kdj_min_objective_delta": args.weight_kdj_min_objective_delta,
            "weight_kdj_min_abs_offset": args.weight_kdj_min_abs_offset,
            "weight_kdj_slope_window": args.weight_kdj_slope_window,
            "weight_kdj_neutral_band": args.weight_kdj_neutral_band,
            "ridge_kdj_budget_share": args.ridge_kdj_budget_share,
            "ridge_kdj_alpha": args.ridge_kdj_alpha,
            "ridge_kdj_min_confidence": args.ridge_kdj_min_confidence,
            "ridge_kdj_min_train_rows": args.ridge_kdj_min_train_rows,
            "ridge_kdj_min_validation_rows": args.ridge_kdj_min_validation_rows,
            "neural_kdj_budget_share": args.neural_kdj_budget_share,
            "neural_kdj_min_confidence": args.neural_kdj_min_confidence,
            "neural_kdj_seed": args.neural_kdj_seed,
            "neural_kdj_hidden_units": args.neural_kdj_hidden_units,
            "neural_kdj_epochs": args.neural_kdj_epochs,
            "target_weight_inversion_budget_share": args.target_weight_inversion_budget_share,
            "target_weight_inversion_max_candidates": args.target_weight_inversion_max_candidates,
            "target_weight_inversion_max_targets": args.target_weight_inversion_max_targets,
            "target_weight_inversion_max_deltas_per_target": args.target_weight_inversion_max_deltas_per_target,
        },
    )


def main(argv: Sequence[str] | None = None) -> None:
    from dehps.prediction.v2.retirement import require_legacy_compute_allowed

    require_legacy_compute_allowed("legacy_training_supervisor")
    args = parse_args(argv)
    dependencies = build_training_dependencies(args)
    supervisor = TrainingSupervisor(settings=build_settings(args), dependencies=dependencies)
    print(json.dumps(supervisor.run(), ensure_ascii=False, indent=2))
