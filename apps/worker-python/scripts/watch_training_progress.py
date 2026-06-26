from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.runtime.heavy_job import describe_heavy_job_owner


ADVISOR_KEYS = (
    "weight_kdj_advisor",
    "ridge_kdj_advisor",
    "neural_kdj_advisor",
    "target_weight_inversion_advisor",
)
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization/training-watch"
DEFAULT_ROUND_LIMIT = 5000
DEFAULT_STALE_MINUTES = 30


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp(moment: datetime | None = None) -> str:
    return (moment or utc_now()).strftime("%Y%m%d-%H%M%S")


def isoformat(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if isfinite(value) and value.is_integer() else None
    try:
        parsed = int(value)
    except (OverflowError, TypeError, ValueError):
        return None
    try:
        if not isinstance(value, str) and value != parsed:
            return None
    except Exception:
        return None
    return parsed


def positive_int_or_default(value: Any, *, default: int) -> int:
    parsed = safe_int(value)
    return parsed if parsed is not None and parsed > 0 else default


def resolve_run_id(run_id: str | None) -> str | None:
    if run_id:
        return run_id
    with get_connection() as conn:
        with conn.cursor() as cur:
            row = cur.execute(
                """
                SELECT run_id
                FROM training_round_results
                ORDER BY created_at DESC, round_index DESC
                LIMIT 1
                """
            ).fetchone()
    return str(row[0]) if row else None


def load_rounds(run_id: str, *, limit: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            return list(
                cur.execute(
                    """
                    SELECT *
                    FROM (
                        SELECT run_id, round_index, phase, step, improved, top_100_hits, top_1000_hits,
                               top_10000_hits, red5_top_100_hits, red5_top_1000_hits,
                               red5_top_10000_hits, median_rank, best_rank, worst_rank,
                               objective_score, best_config, best_summary, top_results,
                               target_results, prefilter, created_at, updated_at
                        FROM training_round_results
                        WHERE run_id = %s
                        ORDER BY round_index DESC
                        LIMIT %s
                    ) recent_rounds
                    ORDER BY round_index ASC
                    """,
                    (run_id, limit),
                ).fetchall()
            )


def heavy_lock_summary() -> dict[str, Any]:
    status = describe_heavy_job_owner()
    metadata = status.metadata or {}
    return {
        "active": status.active,
        "pid_active": status.pid_active,
        "reason": status.reason,
        "error": status.error,
        "owner": metadata.get("owner"),
        "pid": metadata.get("pid"),
        "status": metadata.get("status"),
        "started_at": metadata.get("started_at"),
        "heartbeat_at": metadata.get("heartbeat_at"),
        "context": metadata.get("context") if isinstance(metadata.get("context"), dict) else {},
    }


def advisor_summary(prefilter: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key in ADVISOR_KEYS:
        row = prefilter.get(key) if isinstance(prefilter.get(key), dict) else {}
        advice = row.get("advice") if isinstance(row.get("advice"), list) else []
        top_advice = [
            {
                "weight_name": item.get("weight_name"),
                "decision": item.get("decision"),
                "suggested_offset": item.get("suggested_offset", item.get("applied_offset", item.get("offset"))),
                "confidence": item.get("confidence"),
                "validation_metric": item.get("validation_metric"),
                "baseline_metric": item.get("baseline_metric"),
            }
            for item in advice[:8]
            if isinstance(item, dict)
        ]
        result[key] = {
            "enabled": bool(row.get("enabled")),
            "budget": safe_int(row.get("budget")),
            "candidate_count": safe_int(row.get("candidate_count")) or 0,
            "selected_count": safe_int(row.get("selected_count")) or 0,
            "downweighted_count": safe_int(row.get("downweighted_count")) or 0,
            "rejected_count": safe_int(row.get("rejected_count")) or 0,
            "latest_signal_issue": row.get("latest_signal_issue") or row.get("latest_issue"),
            "selected_fields": row.get("selected_fields") if isinstance(row.get("selected_fields"), list) else [],
            "top_advice": top_advice,
        }
    return result


def round_age_minutes(row: dict[str, Any], *, now: datetime) -> float | None:
    updated_at = row.get("updated_at") or row.get("created_at")
    if not isinstance(updated_at, datetime):
        return None
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return max(0.0, (now - updated_at.astimezone(timezone.utc)).total_seconds() / 60.0)


def improvement_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    improved_rounds = [safe_int(row.get("round_index")) for row in rows if row.get("improved")]
    improved_rounds = [item for item in improved_rounds if item is not None]
    latest_round = safe_int(rows[-1].get("round_index")) if rows else None
    last_improved_round = max(improved_rounds) if improved_rounds else None
    return {
        "latest_round": latest_round,
        "last_improved_round": last_improved_round,
        "stagnation_rounds": (latest_round - last_improved_round) if latest_round and last_improved_round else latest_round or 0,
        "improvement_count": len(improved_rounds),
    }


def recommendation_summary(
    *,
    rows: list[dict[str, Any]],
    lock: dict[str, Any],
    advisors: dict[str, dict[str, Any]],
    now: datetime,
    stale_minutes: int,
) -> dict[str, Any]:
    if not rows:
        return {
            "severity": "alert",
            "action": "no_rounds",
            "notes": ["No training_round_results rows found for this run."],
        }

    latest = rows[-1]
    improvement = improvement_summary(rows)
    latest_age = round_age_minutes(latest, now=now)
    notes: list[str] = []
    actions: list[str] = []
    severity = "ok"

    if lock.get("active") and lock.get("owner") == "training-supervisor":
        notes.append("Training process is active under the heavy-job lock.")
    else:
        severity = "warn"
        notes.append("Training heavy-job lock is not active; verify whether the supervisor stopped.")

    if latest_age is not None and latest_age > stale_minutes:
        severity = "warn"
        actions.append("inspect_training_log")
        notes.append(f"Latest round is stale: {latest_age:.1f} minutes since update.")

    stagnation_rounds = int(improvement["stagnation_rounds"] or 0)
    if stagnation_rounds >= 32:
        severity = "alert"
        actions.append("prepare_restart_with_more_exploration")
        notes.append("Stagnation is very high; prepare a new run with broader exploration and controls.")
    elif stagnation_rounds >= 16:
        severity = "warn" if severity == "ok" else severity
        actions.append("watch_stagnation_recovery")
        notes.append("Stagnation crossed the supervisor recovery threshold; check if diversity injection improves the next rounds.")
    else:
        notes.append("Stagnation is below the intervention threshold.")

    neural = advisors.get("neural_kdj_advisor", {})
    neural_candidates = int(neural.get("candidate_count") or 0)
    neural_top = neural.get("top_advice") if isinstance(neural.get("top_advice"), list) else []
    neural_confidence = safe_float(neural_top[0].get("confidence")) if neural_top and isinstance(neural_top[0], dict) else None
    if neural_candidates == 0:
        notes.append("Neural advisor produced no candidate in the latest round; keep neural budget conservative.")
    elif neural_confidence is not None and neural_confidence < 0.05:
        notes.append("Neural advisor produced candidates, but confidence is low; keep it advisor-only and do not increase its budget yet.")
    else:
        notes.append("Neural advisor produced candidates; require control experiments before any promotion.")

    ridge = advisors.get("ridge_kdj_advisor", {})
    if int(ridge.get("candidate_count") or 0) > 0:
        notes.append("Ridge advisor remains a viable lightweight candidate source.")

    if not actions:
        actions.append("continue_current_run")

    return {
        "severity": severity,
        "action": actions[0],
        "actions": actions,
        "notes": notes,
    }


def summarize_watch(run_id: str | None, *, limit: int, stale_minutes: int) -> dict[str, Any]:
    limit = positive_int_or_default(limit, default=DEFAULT_ROUND_LIMIT)
    stale_minutes = positive_int_or_default(stale_minutes, default=DEFAULT_STALE_MINUTES)
    generated_at = utc_now()
    resolved_run_id = resolve_run_id(run_id)
    rows = load_rounds(resolved_run_id, limit=limit) if resolved_run_id else []
    latest = rows[-1] if rows else {}
    prefilter = latest.get("prefilter") if isinstance(latest.get("prefilter"), dict) else {}
    advisors = advisor_summary(prefilter)
    lock = heavy_lock_summary()
    improvement = improvement_summary(rows)
    recommendation = recommendation_summary(
        rows=rows,
        lock=lock,
        advisors=advisors,
        now=generated_at,
        stale_minutes=stale_minutes,
    )
    objective_values = [safe_float(row.get("objective_score")) for row in rows]
    objective_values = [value for value in objective_values if value is not None]
    return {
        "generated_at": isoformat(generated_at),
        "run_id": resolved_run_id,
        "round_limit": limit,
        "stale_minutes": stale_minutes,
        "round_count": len(rows),
        "latest_round": improvement["latest_round"],
        "last_improved_round": improvement["last_improved_round"],
        "stagnation_rounds": improvement["stagnation_rounds"],
        "improvement_count": improvement["improvement_count"],
        "latest_round_age_minutes": round_age_minutes(latest, now=generated_at) if latest else None,
        "latest_metrics": {
            "phase": latest.get("phase"),
            "step": safe_float(latest.get("step")),
            "improved": bool(latest.get("improved")) if latest else False,
            "top_100_hits": safe_int(latest.get("top_100_hits")),
            "top_1000_hits": safe_int(latest.get("top_1000_hits")),
            "top_10000_hits": safe_int(latest.get("top_10000_hits")),
            "red5_top_10000_hits": safe_int(latest.get("red5_top_10000_hits")),
            "median_rank": safe_float(latest.get("median_rank")),
            "best_rank": safe_int(latest.get("best_rank")),
            "worst_rank": safe_int(latest.get("worst_rank")),
            "objective_score": safe_float(latest.get("objective_score")),
            "best_objective_seen": max(objective_values) if objective_values else None,
        },
        "candidate_budget": prefilter.get("candidate_budget") if isinstance(prefilter.get("candidate_budget"), dict) else {},
        "advisor_summary": advisors,
        "heavy_job_lock": lock,
        "recommendation": recommendation,
        "guardrail": "Historical response-surface monitoring only; no predictive claim and no automatic promotion without controls.",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    latest = payload["latest_metrics"]
    rec = payload["recommendation"]
    advisor_rows = "\n".join(
        f"| {key} | {value.get('candidate_count', 0)} | {value.get('selected_count', 0)} | "
        f"{value.get('rejected_count', 0)} | {', '.join(str(item) for item in value.get('selected_fields', [])[:6])} |"
        for key, value in payload["advisor_summary"].items()
    )
    note_rows = "\n".join(f"- {note}" for note in rec.get("notes", []))
    return f"""# DEHPS Training Watch

- Generated at: {payload.get("generated_at")}
- Run id: `{payload.get("run_id") or ""}`
- Rounds: {payload.get("round_count")}
- Latest round: {payload.get("latest_round")}
- Last improved round: {payload.get("last_improved_round")}
- Stagnation rounds: {payload.get("stagnation_rounds")}
- Severity: `{rec.get("severity")}`
- Action: `{rec.get("action")}`

## Latest Metrics

- Phase/step: {latest.get("phase")} / {latest.get("step")}
- Improved: {latest.get("improved")}
- Top100/1000/10000: {latest.get("top_100_hits")} / {latest.get("top_1000_hits")} / {latest.get("top_10000_hits")}
- Red5 Top10000: {latest.get("red5_top_10000_hits")}
- Rank best/median/worst: {latest.get("best_rank")} / {latest.get("median_rank")} / {latest.get("worst_rank")}
- Objective latest/best seen: {latest.get("objective_score")} / {latest.get("best_objective_seen")}

## Advisor Snapshot

| Advisor | Candidates | Selected | Rejected | Selected fields |
| --- | ---: | ---: | ---: | --- |
{advisor_rows}

## Heavy Job Lock

```json
{json.dumps(payload.get("heavy_job_lock", {}), ensure_ascii=False, indent=2)}
```

## Judgement

{note_rows}

## Guardrail

{payload.get("guardrail")}
"""


def write_outputs(payload: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    run_id = payload.get("run_id") or "none"
    json_path = output_dir / f"training-watch-{run_id}-{stamp}.json"
    md_path = output_dir / f"training-watch-{run_id}-{stamp}.md"
    latest_json = output_dir / "training-watch-latest.json"
    latest_md = output_dir / "training-watch-latest.md"
    json_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    md_text = render_markdown(payload)
    json_path.write_text(json_text)
    md_path.write_text(md_text)
    latest_json.write_text(json_text)
    latest_md.write_text(md_text)
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch active DEHPS training and write advisor-only progress judgement.")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int, default=DEFAULT_ROUND_LIMIT)
    parser.add_argument("--stale-minutes", type=int, default=DEFAULT_STALE_MINUTES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    payload = summarize_watch(args.run_id, limit=args.limit, stale_minutes=args.stale_minutes)
    json_path, md_path = write_outputs(payload, args.output_dir)
    print(
        json.dumps(
            {
                "run_id": payload.get("run_id"),
                "round_count": payload.get("round_count"),
                "severity": payload.get("recommendation", {}).get("severity"),
                "action": payload.get("recommendation", {}).get("action"),
                "json_path": str(json_path),
                "report_path": str(md_path),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
