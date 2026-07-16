from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.optimization.regime import HistoryScope, select_history
from dehps.optimization.walk_forward import fingerprint_history, random_uniform_baseline
from dehps.storage.postgres_store import TOTAL_SSQ_RED_COMBINATIONS


def build_analytic_null_baseline(
    *,
    as_of_issue: str,
    history_fingerprint_value: str,
    history_length: int,
    train_mode: str,
    train_window: int,
    eval_window: int,
    top_n: int,
    history_scope: str,
    regime_years: int,
) -> dict:
    if history_length <= train_window:
        raise ValueError("history must be longer than train_window")
    start_index = max(train_window, history_length - eval_window)
    evaluated_draws = history_length - start_index
    baseline = random_uniform_baseline(
        evaluated_draws=evaluated_draws,
        universe_size=TOTAL_SSQ_RED_COMBINATIONS,
    )
    return {
        "protocol": "analytic-uniform-rank-null-v1",
        "execution_mode": "deterministic",
        "as_of_issue": as_of_issue,
        "history_fingerprint": history_fingerprint_value,
        "history_scope": history_scope,
        "regime_years": regime_years,
        "train_mode": train_mode,
        "train_window": train_window,
        "configured_eval_window": eval_window,
        "evaluated_draws": evaluated_draws,
        "top_n": top_n,
        "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
        "baseline": baseline,
        "seed": None,
        "random_sampling_performed": False,
    }


def render_report(payload: dict) -> str:
    baseline = payload["baseline"]
    rows = [
        "# Analytic Uniform-Rank Null Baseline",
        "",
        f"- As-of issue: `{payload['as_of_issue']}`",
        f"- Evaluated draws: `{payload['evaluated_draws']}`",
        f"- Legal sample space: `{payload['legal_sample_space']}`",
        "- Execution: deterministic analytic expectation; no random samples and no seed.",
        "",
        "| Band | Hit probability | Expected hits |",
        "| --- | ---: | ---: |",
    ]
    for label in ("top_100", "top_1000", "top_10000"):
        item = baseline[label]
        rows.append(f"| {label} | {item['hit_rate']:.12f} | {item['expected_hits']:.8f} |")
    rows.append("")
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a deterministic analytic random-rank null baseline.")
    parser.add_argument("--as-of-issue", required=True)
    parser.add_argument("--train-mode", choices=["expanding", "rolling"], default="expanding")
    parser.add_argument("--train-window", type=int, default=900)
    parser.add_argument("--eval-window", type=int, default=100)
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--history-scope", choices=["full_history_audit", "current_regime_default"], default="current_regime_default")
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "data/output/optimization/analytic-null-baseline",
    )
    args = parser.parse_args()

    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=args.history_scope,  # type: ignore[arg-type]
            as_of_issue=args.as_of_issue,
            regime_years=args.regime_years,
        )
    history = selection.dated_history
    if not history or str(history[-1][0]) != args.as_of_issue:
        raise ValueError("selected history does not end at --as-of-issue")
    payload = build_analytic_null_baseline(
        as_of_issue=args.as_of_issue,
        history_fingerprint_value=fingerprint_history(history),
        history_length=len(history),
        train_mode=args.train_mode,
        train_window=args.train_window,
        eval_window=args.eval_window,
        top_n=args.top_n,
        history_scope=selection.scope,
        regime_years=args.regime_years,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    key = f"analytic-null-baseline-asof-{args.as_of_issue}-{args.train_mode}-tw{args.train_window}-ew{args.eval_window}-top{args.top_n}"
    json_path = args.output_dir / f"{key}.json"
    report_path = args.output_dir / f"{key}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "report": str(report_path), "payload": payload}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
