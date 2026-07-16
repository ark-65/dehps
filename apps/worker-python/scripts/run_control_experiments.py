from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.control_experiments import (
    LoadedCandidate,
    default_output_dir,
    latest_neural_candidate_path,
    load_config_json_candidate,
    load_neural_candidate,
    normalize_candidate_source,
    parse_random_seeds,
    run_control_experiments,
    validate_train_mode,
    write_control_experiment_artifacts,
)
from dehps.optimization.regime import select_history
from dehps.optimization.walk_forward import build_ranked_universe, config_hash, fingerprint_history, normalize_worker_count
from dehps.storage.postgres_store import load_recent_training_weight_signals, load_red_combination_universe
from scripts.run_training_supervisor import (
    load_db_supervisor_candidates,
    weight_kdj_advisor_candidate_configs,
    weight_kdj_advisor_metadata,
)


def latest_prior_base_config(
    *,
    as_of_issue: str,
    history_fingerprint_value: str,
    train_window: int,
    train_mode: str,
    eval_window: int,
    top_n: int,
    universe_size: int,
    ensure_schema: bool = True,
) -> tuple[FrequencyRankerConfig, dict]:
    prior = load_db_supervisor_candidates(
        as_of_issue=as_of_issue,
        history_fingerprint_value=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=eval_window,
        top_n=top_n,
        universe_size=universe_size,
        limit=1,
        ensure_schema=ensure_schema,
    )
    if prior:
        return FrequencyRankerConfig(**prior[0]["config"]), {
            "source": "training_round_results",
            "config_hash": prior[0].get("config_hash"),
            "objective_score": (prior[0].get("reward") or {}).get("objectiveScore"),
        }
    base = FrequencyRankerConfig()
    return base, {"source": "default_frequency_ranker_config", "config_hash": config_hash(base)}


def load_kdj_candidate(
    *,
    base_config: FrequencyRankerConfig,
    signal_run_id: str | None,
    limit: int,
) -> LoadedCandidate:
    with get_connection() as conn:
        signals = load_recent_training_weight_signals(conn, signal_run_id=signal_run_id, limit=limit)
    if not signals:
        raise ValueError("no KDJ weight signals found; provide --signal-run-id after running generate_weight_kdj_signals")
    configs = weight_kdj_advisor_candidate_configs(base_config, signals, max_configs=4)
    if not configs:
        raise ValueError("KDJ signals did not produce a candidate config")
    base_hash = config_hash(base_config)
    selected = next((config for config in configs if config_hash(config) != base_hash), configs[0])
    return LoadedCandidate(
        label="candidate_kdj_advisor",
        source="kdj",
        config=selected,
        metadata=weight_kdj_advisor_metadata(signals, configs),
    )


def load_candidate_from_args(args, *, base_config: FrequencyRankerConfig) -> LoadedCandidate:
    source = normalize_candidate_source(args.candidate_source)
    if source == "config-json":
        if not args.config_json:
            raise ValueError("--config-json is required when --candidate-source config-json")
        return load_config_json_candidate(args.config_json)
    if source == "kdj":
        return load_kdj_candidate(
            base_config=base_config,
            signal_run_id=args.signal_run_id,
            limit=args.kdj_signal_limit,
        )
    neural_path = args.neural_json
    if neural_path is None and args.signal_run_id:
        maybe_path = Path(args.signal_run_id)
        neural_path = maybe_path if maybe_path.exists() else None
    if neural_path is None:
        neural_path = latest_neural_candidate_path(args.output_dir)
    return load_neural_candidate(neural_path, top_n=args.top_n)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run frozen control experiments for anti-overfitting checks.")
    parser.add_argument("--candidate-source", choices=["kdj", "neural", "config-json"], required=True)
    parser.add_argument("--as-of-issue")
    parser.add_argument("--train-mode", choices=["expanding", "rolling"], default="expanding")
    parser.add_argument("--train-window", type=int, default=900)
    parser.add_argument("--eval-window", type=int, default=100)
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--signal-run-id", help="KDJ signal_run_id, or a neural JSON path for --candidate-source neural.")
    parser.add_argument("--random-seeds", default="11,23,37")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--config-json", type=Path, help="Candidate config JSON for --candidate-source config-json.")
    parser.add_argument("--neural-json", type=Path, help="Neural feasibility JSON for --candidate-source neural.")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--history-scope", choices=["full_history_audit", "current_regime_default"], default="current_regime_default")
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument("--kdj-signal-limit", type=int, default=1000)
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Skip schema creation so the command can run under a read-only database guard.",
    )
    args = parser.parse_args()

    train_mode = validate_train_mode(args.train_mode)
    random_seeds = parse_random_seeds(args.random_seeds)
    worker_count = normalize_worker_count(args.workers)

    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=args.history_scope,  # type: ignore[arg-type]
            as_of_issue=args.as_of_issue,
            regime_years=args.regime_years,
        )
        universe = load_red_combination_universe(conn)

    ranked_universe = build_ranked_universe(universe)
    history = selection.dated_history
    if not history:
        raise ValueError("selected history is empty")
    base_config, base_metadata = latest_prior_base_config(
        as_of_issue=str(args.as_of_issue or history[-1][0]),
        history_fingerprint_value=fingerprint_history(history),
        train_window=args.train_window,
        train_mode=train_mode,
        eval_window=args.eval_window,
        top_n=args.top_n,
        universe_size=len(ranked_universe),
        ensure_schema=not args.read_only,
    )
    candidate = load_candidate_from_args(args, base_config=base_config)
    payload = run_control_experiments(
        history=history,
        universe=universe,
        candidate=candidate,
        base_config=base_config,
        train_mode=train_mode,
        train_window=args.train_window,
        eval_window=args.eval_window,
        top_n=args.top_n,
        random_seeds=random_seeds,
        workers=worker_count,
        ranked_universe=ranked_universe,
    )
    payload["current_best_frozen_baseline_metadata"] = base_metadata
    payload["history_scope"] = {
        "scope": selection.scope,
        "regime_years": selection.regime_years,
        "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
        "evidence_note": selection.evidence_note,
    }
    json_path, report_path = write_control_experiment_artifacts(payload, args.output_dir)
    print(
        json.dumps(
            {
                "json_path": str(json_path),
                "report_path": str(report_path),
                "verdict": payload["frozen_verdict"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
