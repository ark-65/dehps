from __future__ import annotations

import argparse
import json
import sys
import time
from math import isfinite
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.dynamic_kdj_backtest import (
    DEFAULT_KDJ_STRENGTH_SWEEP,
    DEFAULT_RETENTION_BANDS,
    DynamicKdjAcceptanceConfig,
    DynamicKdjThresholds,
    evaluate_dynamic_kdj_backtest,
    normalize_retention_bands,
    normalize_strength_sweep,
    render_dynamic_kdj_report,
)
from dehps.optimization.config_io import frequency_ranker_config_values
from dehps.optimization.regime import select_history
from dehps.optimization.walk_forward import build_ranked_universe, config_hash, fingerprint_history
from dehps.storage.postgres_store import (
    CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,
    load_recent_training_weight_signals,
    load_red_combination_universe,
)
from scripts.run_control_experiments import latest_prior_base_config, validate_train_mode
from scripts.run_training_supervisor import clamp_config


def default_output_dir() -> Path:
    return ROOT_DIR / "data/output/optimization"


def _csv_parts(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(",") if part.strip()]


def parse_strength_sweep(value: str) -> tuple[float, ...]:
    strengths: list[float] = []
    for part in _csv_parts(value):
        try:
            strength = float(part)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("--kdj-strength-sweep must be comma-separated numbers") from exc
        if not isfinite(strength) or strength < 0:
            raise argparse.ArgumentTypeError("--kdj-strength-sweep values must be finite non-negative numbers")
        strengths.append(strength)
    return normalize_strength_sweep(strengths)


def parse_retention_bands(value: str) -> tuple[int, ...]:
    bands: list[int] = []
    for part in _csv_parts(value):
        try:
            band = int(part)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("--retention-bands must be comma-separated positive integers") from exc
        if band < 1:
            raise argparse.ArgumentTypeError("--retention-bands values must be positive integers")
        bands.append(band)
    return normalize_retention_bands(bands)


def _csv_default(values: tuple[float, ...] | tuple[int, ...]) -> str:
    return ",".join(str(value) for value in values)


def load_base_config_json(path: Path) -> FrequencyRankerConfig:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("--base-config-json must point to a JSON object")
    raw_config = payload.get("config") or payload.get("candidate_config") or payload.get("best_config") or payload
    if not isinstance(raw_config, dict):
        raise ValueError("--base-config-json must contain a config object")
    values = frequency_ranker_config_values(
        raw_config,
        source_label="--base-config-json",
        unknown_error_prefix="unknown config fields in --base-config-json",
    )
    return clamp_config(FrequencyRankerConfig(**values))


def resolve_base_config(
    *,
    source: str,
    base_config_json: Path | None,
    as_of_issue: str,
    history_fingerprint_value: str,
    train_window: int,
    train_mode: str,
    eval_window: int,
    top_n: int,
    universe_size: int,
    ensure_schema: bool = True,
) -> tuple[FrequencyRankerConfig, dict]:
    if base_config_json is not None:
        config = load_base_config_json(base_config_json)
        return config, {"source": "base_config_json", "path": str(base_config_json), "config_hash": config_hash(config)}
    if source == "default":
        config = FrequencyRankerConfig()
        return config, {"source": "default_frequency_ranker_config", "config_hash": config_hash(config)}
    if source != "latest-training-best":
        raise ValueError("--base-config-source must be latest-training-best or default")
    config, metadata = latest_prior_base_config(
        as_of_issue=as_of_issue,
        history_fingerprint_value=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=eval_window,
        top_n=top_n,
        universe_size=universe_size,
        ensure_schema=ensure_schema,
    )
    return config, metadata


def write_artifacts(payload: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    key = time.strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"dynamic-kdj-backtest-{key}.json"
    md_path = output_dir / f"dynamic-kdj-backtest-{key}.md"
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(md_path)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_dynamic_kdj_report(payload))
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a frozen per-target dynamic KDJ weight-vector backtest.")
    parser.add_argument("--signal-run-id", default=CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID)
    parser.add_argument("--as-of-issue")
    parser.add_argument("--train-mode", choices=["expanding", "rolling"], default="expanding")
    parser.add_argument("--train-window", type=int, default=900)
    parser.add_argument("--eval-window", type=int, default=100)
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--base-config-source", choices=["latest-training-best", "default"], default="latest-training-best")
    parser.add_argument("--base-config-json", type=Path)
    parser.add_argument("--history-scope", choices=["full_history_audit", "current_regime_default"], default="current_regime_default")
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument("--kdj-signal-limit", type=int, default=1000, help="Rows per weight loaded by issue tail.")
    parser.add_argument("--weight-kdj-min-objective-delta", type=float, default=0.0)
    parser.add_argument("--weight-kdj-min-abs-offset", type=float, default=0.005)
    parser.add_argument("--weight-kdj-slope-window", type=int, default=3)
    parser.add_argument("--weight-kdj-neutral-band", type=float, default=5.0)
    parser.add_argument("--min-eval-window-for-pass", type=int, default=50)
    parser.add_argument("--max-median-changed-weights", type=int, default=5)
    parser.add_argument("--max-max-changed-weights", type=int, default=8)
    parser.add_argument("--max-dynamic-abs-offset", type=float, default=0.06)
    parser.add_argument("--kdj-strength-sweep", type=parse_strength_sweep, default=_csv_default(DEFAULT_KDJ_STRENGTH_SWEEP))
    parser.add_argument("--retention-bands", type=parse_retention_bands, default=_csv_default(DEFAULT_RETENTION_BANDS))
    parser.add_argument("--disable-negative-controls", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--no-write", action="store_true", help="Print the summary without writing md/json artifacts.")
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Skip schema creation so the command can run under a read-only database guard.",
    )
    args = parser.parse_args()

    train_mode = validate_train_mode(args.train_mode)
    kdj_strength_sweep = args.kdj_strength_sweep if isinstance(args.kdj_strength_sweep, tuple) else parse_strength_sweep(args.kdj_strength_sweep)
    retention_bands = args.retention_bands if isinstance(args.retention_bands, tuple) else parse_retention_bands(args.retention_bands)
    started = time.time()
    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=args.history_scope,  # type: ignore[arg-type]
            as_of_issue=args.as_of_issue,
            regime_years=args.regime_years,
        )
        universe = load_red_combination_universe(conn)
        signals = load_recent_training_weight_signals(
            conn,
            signal_run_id=args.signal_run_id,
            as_of_issue=args.as_of_issue,
            train_mode=train_mode,
            train_window=args.train_window,
            top_n=args.top_n,
            limit=args.kdj_signal_limit,
        )

    history = selection.dated_history
    if not history:
        raise ValueError("selected history is empty")
    if not signals:
        raise ValueError(
            "no KDJ weight signals found; run generate_weight_kdj_signals first or pass a valid --signal-run-id"
        )
    ranked_universe = build_ranked_universe(universe)
    history_fingerprint_value = fingerprint_history(history)
    base_config, base_metadata = resolve_base_config(
        source=args.base_config_source,
        base_config_json=args.base_config_json,
        as_of_issue=str(history[-1][0]),
        history_fingerprint_value=history_fingerprint_value,
        train_window=args.train_window,
        train_mode=train_mode,
        eval_window=args.eval_window,
        top_n=args.top_n,
        universe_size=len(ranked_universe),
        ensure_schema=not args.read_only,
    )
    thresholds = DynamicKdjThresholds(
        min_objective_delta=args.weight_kdj_min_objective_delta,
        min_abs_offset=args.weight_kdj_min_abs_offset,
        slope_window=args.weight_kdj_slope_window,
        neutral_band=args.weight_kdj_neutral_band,
    )
    acceptance_config = DynamicKdjAcceptanceConfig(
        min_eval_window_for_pass=args.min_eval_window_for_pass,
        max_median_changed_weights=args.max_median_changed_weights,
        max_max_changed_weights=args.max_max_changed_weights,
        max_abs_offset=args.max_dynamic_abs_offset,
    )
    payload = evaluate_dynamic_kdj_backtest(
        history=history,
        ranked_universe=ranked_universe,
        base_config=base_config,
        signals=signals,
        train_window=args.train_window,
        train_mode=train_mode,
        eval_window=args.eval_window,
        top_n=args.top_n,
        thresholds=thresholds,
        acceptance_config=acceptance_config,
        include_negative_controls=not args.disable_negative_controls,
        strength_sweep=kdj_strength_sweep,
        retention_bands=retention_bands,
    )
    payload["signal_run_id"] = args.signal_run_id
    payload["signal_count"] = len(signals)
    payload["base_config_source"] = "base_config_json" if args.base_config_json else args.base_config_source
    payload["base_config_metadata"] = base_metadata
    payload["base_config_hash"] = config_hash(base_config)
    payload["command_args"] = {
        "signal_run_id": args.signal_run_id,
        "as_of_issue": args.as_of_issue,
        "train_mode": args.train_mode,
        "train_window": args.train_window,
        "eval_window": args.eval_window,
        "top_n": args.top_n,
        "base_config_source": args.base_config_source,
        "base_config_json": str(args.base_config_json) if args.base_config_json else None,
        "history_scope": args.history_scope,
        "regime_years": args.regime_years,
        "kdj_signal_limit": args.kdj_signal_limit,
        "kdj_strength_sweep": list(kdj_strength_sweep),
        "retention_bands": list(retention_bands),
        "disable_negative_controls": args.disable_negative_controls,
    }
    payload["elapsed_seconds"] = round(time.time() - started, 3)
    if args.no_write:
        print(
            json.dumps(
                {
                    "acceptance": payload["acceptance"],
                    "retention_audit": payload["retention_audit"],
                    "strength_sweep": payload["strength_sweep"],
                    "kdj_layer_audit": payload["kdj_layer_audit"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return
    json_path, report_path = write_artifacts(payload, args.output_dir)
    print(
        json.dumps(
            {
                "status": "completed",
                "json_path": str(json_path),
                "report_path": str(report_path),
                "acceptance_status": payload["acceptance"].get("status"),
                "acceptance": payload["acceptance"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
