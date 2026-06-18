from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.storage.postgres_store import ensure_training_round_results_schema

try:
    from scripts.run_training_supervisor import ALL_FIELDS
except ModuleNotFoundError:
    from run_training_supervisor import ALL_FIELDS


def config_fingerprint(config: dict[str, Any]) -> str:
    return json.dumps(config or {}, sort_keys=True, separators=(",", ":"))


def summarize_training_rounds(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row["round_index"]))
    phase_counts: dict[str, int] = defaultdict(int)
    phase_improvements: dict[str, int] = defaultdict(int)
    weight_coverage: Counter[str] = Counter()
    target_tail_counts: Counter[str] = Counter()
    validation_scores: list[float] = []
    config_changes = 0
    previous_config = None
    last_improved_round = None

    for row in ordered:
        phase = str(row["phase"])
        phase_counts[phase] += 1
        if row.get("improved"):
            phase_improvements[phase] += 1
            last_improved_round = int(row["round_index"])
        best_config = row.get("best_config") if isinstance(row.get("best_config"), dict) else {}
        current_config = config_fingerprint(best_config)
        if previous_config is not None and current_config != previous_config:
            config_changes += 1
        previous_config = current_config
        for field in ALL_FIELDS:
            if abs(float(best_config.get(field, 0) or 0)) > 1e-12:
                weight_coverage[field] += 1
        top_results = row.get("top_results")
        if isinstance(top_results, list):
            for result in top_results:
                config = result.get("config") if isinstance(result, dict) and isinstance(result.get("config"), dict) else {}
                for field in ALL_FIELDS:
                    if abs(float(config.get(field, 0) or 0)) > 1e-12:
                        weight_coverage[field] += 1
        target_results = row.get("target_results")
        if isinstance(target_results, list):
            for target in target_results:
                if not isinstance(target, dict):
                    continue
                rank = int(target.get("rank") or 0)
                issue = str(target.get("issue") or "")
                if issue and rank > 900_000:
                    target_tail_counts[issue] += 1
        validation = row.get("best_summary", {}).get("frozen_validation") if isinstance(row.get("best_summary"), dict) else None
        validation_reward = validation.get("reward") if isinstance(validation, dict) and isinstance(validation.get("reward"), dict) else {}
        if isinstance(validation_reward.get("objectiveScore"), int | float):
            validation_scores.append(float(validation_reward["objectiveScore"]))

    latest = ordered[-1] if ordered else {}
    latest_prefilter = latest.get("prefilter") if isinstance(latest.get("prefilter"), dict) else {}
    latest_controls = latest_prefilter.get("control_experiments") if isinstance(latest_prefilter.get("control_experiments"), list) else []
    latest_round = int(latest.get("round_index") or 0)
    return {
        "run_id": latest.get("run_id"),
        "round_count": len(ordered),
        "latest_round": latest_round,
        "last_improved_round": last_improved_round,
        "stagnation_rounds": latest_round - last_improved_round if latest_round and last_improved_round else latest_round,
        "config_changes": config_changes,
        "phase_counts": dict(phase_counts),
        "phase_improvements": dict(phase_improvements),
        "phase_improvement_rates": {
            phase: phase_improvements.get(phase, 0) / count
            for phase, count in phase_counts.items()
            if count
        },
        "least_covered_weights": [
            {"field": field, "count": weight_coverage.get(field, 0)}
            for field in sorted(ALL_FIELDS, key=lambda item: (weight_coverage.get(item, 0), item))[:12]
        ],
        "most_covered_weights": [
            {"field": field, "count": count}
            for field, count in weight_coverage.most_common(12)
        ],
        "tail_target_issues": [
            {"issue": issue, "tail_count": count}
            for issue, count in target_tail_counts.most_common(20)
        ],
        "validation_objective_avg": sum(validation_scores) / len(validation_scores) if validation_scores else None,
        "latest_control_experiments": [
            item for item in latest_controls if isinstance(item, dict)
        ][:12],
        "latest_exact_hits": {
            "top_100": int(latest.get("top_100_hits") or 0),
            "top_1000": int(latest.get("top_1000_hits") or 0),
            "top_10000": int(latest.get("top_10000_hits") or 0),
        },
        "latest_red5_hits": {
            "top_100": int(latest.get("red5_top_100_hits") or 0),
            "top_1000": int(latest.get("red5_top_1000_hits") or 0),
            "top_10000": int(latest.get("red5_top_10000_hits") or 0),
        },
    }


def control_validation_objective(item: dict[str, Any]) -> Any:
    validation = item.get("frozen_validation")
    if not isinstance(validation, dict):
        return ""
    reward = validation.get("reward")
    if not isinstance(reward, dict):
        return ""
    return reward.get("objectiveScore", "")


def control_report_row(item: dict[str, Any]) -> str:
    return (
        f"| {item.get('label', '')} | {item.get('top_10000_hits', '')} | "
        f"{item.get('median_rank', '')} | {item.get('objective_score', '')} | "
        f"{control_validation_objective(item)} |"
    )


def render_diagnostics_report(summary: dict[str, Any]) -> str:
    phase_rows = "\n".join(
        f"| {phase} | {summary['phase_counts'][phase]} | {summary['phase_improvements'].get(phase, 0)} | "
        f"{summary['phase_improvement_rates'].get(phase, 0):.3f} |"
        for phase in sorted(summary["phase_counts"])
    )
    least_weights = "\n".join(
        f"| {item['field']} | {item['count']} |" for item in summary["least_covered_weights"]
    )
    tail_rows = "\n".join(
        f"| {item['issue']} | {item['tail_count']} |" for item in summary["tail_target_issues"]
    )
    control_rows = "\n".join(control_report_row(item) for item in summary["latest_control_experiments"])
    return f"""# DEHPS Training Diagnostics

- Run id: `{summary.get("run_id") or ""}`
- Generated at: {datetime.now().isoformat(timespec="seconds")}
- Rounds: {summary["round_count"]}
- Latest round: {summary["latest_round"]}
- Last improved round: {summary.get("last_improved_round")}
- Stagnation rounds: {summary["stagnation_rounds"]}
- Best-config changes: {summary["config_changes"]}
- Avg frozen-validation objective: {summary.get("validation_objective_avg")}

## Latest Metrics

- Exact Top100/1000/10000: {summary["latest_exact_hits"]["top_100"]} / {summary["latest_exact_hits"]["top_1000"]} / {summary["latest_exact_hits"]["top_10000"]}
- Red5 Top100/1000/10000: {summary["latest_red5_hits"]["top_100"]} / {summary["latest_red5_hits"]["top_1000"]} / {summary["latest_red5_hits"]["top_10000"]}

## Phase Improvement

| Phase | Rounds | Improved | Rate |
| --- | ---: | ---: | ---: |
{phase_rows}

## Least Covered Weights

| Weight | Evaluated nonzero count |
| --- | ---: |
{least_weights}

## Tail Target Issues

| Issue | Rank > 900000 count |
| --- | ---: |
{tail_rows}

## Latest Control Experiments

| Label | Top10000 | Median rank | Objective | Frozen validation objective |
| --- | ---: | ---: | ---: | ---: |
{control_rows}

## Guardrail

This report diagnoses historical walk-forward search behavior. It does not claim predictive ability.
"""


def load_round_rows(run_id: str | None, *, limit: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        ensure_training_round_results_schema(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            resolved_run_id = run_id
            if not resolved_run_id:
                latest = cur.execute(
                    "SELECT run_id FROM training_round_results ORDER BY created_at DESC, round_index DESC LIMIT 1"
                ).fetchone()
                resolved_run_id = latest["run_id"] if latest else None
            if not resolved_run_id:
                return []
            return list(
                cur.execute(
                    """
                    SELECT *
                    FROM training_round_results
                    WHERE run_id = %s
                    ORDER BY round_index DESC
                    LIMIT %s
                    """,
                    (resolved_run_id, limit),
                ).fetchall()
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "data/output/optimization")
    args = parser.parse_args()

    rows = load_round_rows(args.run_id, limit=args.limit)
    summary = summarize_training_rounds(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_id = summary.get("run_id") or "none"
    output_path = args.output_dir / f"training-diagnostics-{run_id}.md"
    output_path.write_text(render_diagnostics_report(summary))
    print(json.dumps({"run_id": run_id, "rounds": summary["round_count"], "report_path": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
