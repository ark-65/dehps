from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.neural_kdj_advisor import (
    config_dict,
    neural_kdj_advice_to_frequency_ranker_config_candidates,
    neural_kdj_config_json_payload,
    numpy_neural_kdj_offset_v0,
)
from dehps.runtime.heavy_job import apply_cpu_thread_env_defaults, heavy_job_lock


DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization"


def load_base_config(path: Path | None) -> FrequencyRankerConfig:
    if path is None:
        return FrequencyRankerConfig()
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("--base-config-json must point to a JSON object")
    raw_config = payload.get("config") or payload.get("candidate_config") or payload.get("best_config") or payload
    if not isinstance(raw_config, dict):
        raise ValueError("--base-config-json must contain a config object")
    values = config_dict(FrequencyRankerConfig())
    unknown = sorted(set(raw_config) - set(values))
    if unknown:
        raise ValueError(f"unknown base config fields: {', '.join(unknown)}")
    values.update({field: float(raw_config[field]) for field in raw_config})
    return FrequencyRankerConfig(**values)


def load_signal_rows(
    *,
    signal_run_id: str,
    limit: int,
    train_window: int | None,
    top_n: int | None,
) -> list[dict[str, Any]]:
    if limit < 1:
        return []
    conditions = ["signal_run_id = %s"]
    params: list[Any] = [signal_run_id]
    if train_window is not None:
        conditions.append("train_window = %s")
        params.append(train_window)
    if top_n is not None:
        conditions.append("top_n = %s")
        params.append(top_n)
    where_clause = " AND ".join(conditions)
    params.append(limit)
    with get_connection() as conn:
        with conn.cursor() as cur:
            rows = cur.execute(
                f"""
                WITH ranked AS (
                  SELECT signal_run_id, issue, draw_date, weight_name, train_mode, train_window, eval_window,
                         top_n, source, base_value, close_value, rsv, k_value, d_value, j_value,
                         recommended_offset, objective_delta, best_objective_score, sample_count,
                         row_number() OVER (PARTITION BY weight_name ORDER BY issue DESC) AS row_number
                  FROM training_weight_signals
                  WHERE {where_clause}
                )
                SELECT signal_run_id, issue, draw_date, weight_name, train_mode, train_window, eval_window,
                       top_n, source, base_value, close_value, rsv, k_value, d_value, j_value,
                       recommended_offset, objective_delta, best_objective_score, sample_count
                FROM ranked
                WHERE row_number <= %s
                ORDER BY weight_name ASC, issue ASC
                """,
                tuple(params),
            ).fetchall()
    return [
        {
            "signal_run_id": row[0],
            "issue": row[1],
            "draw_date": row[2].isoformat() if hasattr(row[2], "isoformat") else row[2],
            "weight_name": row[3],
            "train_mode": row[4],
            "train_window": row[5],
            "eval_window": row[6],
            "top_n": row[7],
            "source": row[8],
            "base_value": row[9],
            "close_value": row[10],
            "rsv": row[11],
            "k_value": row[12],
            "d_value": row[13],
            "j_value": row[14],
            "recommended_offset": row[15],
            "objective_delta": row[16],
            "best_objective_score": row[17],
            "sample_count": row[18],
        }
        for row in rows
    ]


def default_output_path(output_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return output_dir / f"neural-kdj-advisor-{stamp}.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate advisor-only Neural KDJ FrequencyRankerConfig candidates.")
    parser.add_argument("--signal-run-id", required=True, help="training_weight_signals signal_run_id to read.")
    parser.add_argument("--limit", type=int, default=1000, help="Recent rows per weight to read.")
    parser.add_argument("--train-window", type=int, help="Optional training_weight_signals train_window filter.")
    parser.add_argument("--top-n", type=int, help="Optional training_weight_signals top_n filter.")
    parser.add_argument("--base-config-json", type=Path, help="Optional base FrequencyRankerConfig JSON.")
    parser.add_argument("--max-configs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--hidden-units", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=400)
    parser.add_argument("--step", type=float, default=0.01)
    parser.add_argument("--mode", choices=["joint", "per-weight"], default="joint")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-json", type=Path, help="Optional exact output JSON path.")
    parser.add_argument("--heavy-job-lock-timeout-seconds", type=float, default=0.0)
    parser.add_argument("--cpu-threads", type=int, default=1)
    args = parser.parse_args()

    apply_cpu_thread_env_defaults(args.cpu_threads)
    with heavy_job_lock(
        owner="neural-kdj-advisor",
        timeout_seconds=args.heavy_job_lock_timeout_seconds,
        context={"signal_run_id": args.signal_run_id, "limit": args.limit},
    ) as lock:
        base_config = load_base_config(args.base_config_json)
        rows = load_signal_rows(
            signal_run_id=args.signal_run_id,
            limit=args.limit,
            train_window=args.train_window,
            top_n=args.top_n,
        )
        lock.heartbeat(context={"loaded_signals": len(rows)})
        advice = numpy_neural_kdj_offset_v0(
            rows,
            step=args.step,
            seed=args.seed,
            hidden_units=args.hidden_units,
            epochs=args.epochs,
            mode=args.mode,  # type: ignore[arg-type]
        )
        configs = neural_kdj_advice_to_frequency_ranker_config_candidates(
            base_config,
            advice,
            max_configs=args.max_configs,
        )
        payload = neural_kdj_config_json_payload(
            base_config=base_config,
            advice=advice,
            configs=configs,
            seed=args.seed,
            hidden_units=args.hidden_units,
            epochs=args.epochs,
            mode=args.mode,  # type: ignore[arg-type]
            signal_run_id=args.signal_run_id,
            train_window=args.train_window,
            top_n=args.top_n,
        )

        output_path = args.output_json or default_output_path(args.output_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        lock.heartbeat(status="completed", context={"candidate_count": len(configs), "output_json": str(output_path)})
    print(
        json.dumps(
            {
                "json_path": str(output_path),
                "advisor_source": payload["advisor_source"],
                "advisory_only": payload["advisory_only"],
                "advice_count": len(advice),
                "candidate_count": len(configs),
                "loadable_by_config_json": "config" in payload,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
