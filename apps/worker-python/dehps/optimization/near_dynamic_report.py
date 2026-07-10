from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.config import ROOT_DIR
from dehps.optimization.next_candidates import (
    NEAR_DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_LINE_LABEL,
    NEAR_DYNAMIC_KDJ_SUCCESS_TOP100_GOAL,
    NEAR_DYNAMIC_KDJ_SUCCESS_WINDOW,
)
from dehps.storage.postgres_store import TOTAL_SSQ_RED_COMBINATIONS


DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/near-dynamic-line-reports"


def default_output_dir() -> Path:
    return DEFAULT_OUTPUT_DIR


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    return value


def _safe_file_part(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip())
    return text.strip("-")[:80] or "none"


def load_recent_near_dynamic_evaluations(
    conn: Connection,
    *,
    limit: int = NEAR_DYNAMIC_KDJ_SUCCESS_WINDOW - 1,
) -> list[dict[str, Any]]:
    table = conn.execute("SELECT to_regclass('public.training_prediction_evaluations')").fetchone()
    if not table or not table[0]:
        return []
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            WITH latest_per_issue AS (
                SELECT *,
                       row_number() OVER (
                         PARTITION BY predicted_issue
                         ORDER BY evaluated_at DESC, updated_at DESC
                       ) AS rn
                FROM training_prediction_evaluations
                WHERE line_key = %s
            )
            SELECT predicted_issue, as_of_issue, snapshot_key, run_id, source_round_index,
                   status, actual_draw_date, actual_red_numbers, actual_blue_number,
                   exact_rank, hit_top_100, hit_top_1000, hit_top_10000,
                   red5_rank, hit_red5_top_100, hit_red5_top_1000, hit_red5_top_10000,
                   candidate_count, summary, prediction_metadata, evaluated_at
            FROM latest_per_issue
            WHERE rn = 1
            ORDER BY predicted_issue DESC
            LIMIT %s
            """,
            (NEAR_DYNAMIC_KDJ_LINE_KEY, max(0, limit)),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def load_current_near_dynamic_prediction(conn: Connection) -> dict[str, Any] | None:
    table = conn.execute("SELECT to_regclass('public.training_next_candidates_current')").fetchone()
    if not table or not table[0]:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            """
            SELECT line_key, line_label, line_kind, snapshot_key, run_id, source_round_index,
                   as_of_issue, next_issue, next_draw_date, train_mode, train_window, eval_window,
                   top_n, history_fingerprint, config_hash, prediction_metadata,
                   count(*)::int AS candidate_count, max(generated_at) AS generated_at
            FROM training_next_candidates_current
            WHERE line_key = %s
            GROUP BY line_key, line_label, line_kind, snapshot_key, run_id, source_round_index,
                     as_of_issue, next_issue, next_draw_date, train_mode, train_window, eval_window,
                     top_n, history_fingerprint, config_hash, prediction_metadata
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (NEAR_DYNAMIC_KDJ_LINE_KEY,),
        ).fetchone()
    return dict(row) if row else None


def build_near_dynamic_line_report(conn: Connection) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    evaluations = load_recent_near_dynamic_evaluations(conn)
    pending = load_current_near_dynamic_prediction(conn)
    top100_hits = sum(1 for row in evaluations if bool(row.get("hit_top_100")) and row.get("status") == "evaluated")
    completed_count = sum(1 for row in evaluations if row.get("status") == "evaluated")
    near_metadata = {}
    if pending and isinstance(pending.get("prediction_metadata"), dict):
        near_metadata = pending["prediction_metadata"].get("near_window")
        if not isinstance(near_metadata, dict):
            near_metadata = {}
    expected_random_hits = NEAR_DYNAMIC_KDJ_SUCCESS_WINDOW * 100 / TOTAL_SSQ_RED_COMBINATIONS
    return json_safe(
        {
            "report_key": f"{NEAR_DYNAMIC_KDJ_LINE_KEY}:{(pending or {}).get('as_of_issue') or 'none'}:{(pending or {}).get('next_issue') or 'none'}",
            "line_key": NEAR_DYNAMIC_KDJ_LINE_KEY,
            "line_label": NEAR_DYNAMIC_KDJ_LINE_LABEL,
            "generated_at": generated_at,
            "status": "pending" if pending else "missing_current_prediction",
            "completed_count": completed_count,
            "pending_count": 1 if pending else 0,
            "success_window": NEAR_DYNAMIC_KDJ_SUCCESS_WINDOW,
            "success_top100_goal": NEAR_DYNAMIC_KDJ_SUCCESS_TOP100_GOAL,
            "exact_top100_hits": top100_hits,
            "goal_reached": top100_hits >= NEAR_DYNAMIC_KDJ_SUCCESS_TOP100_GOAL,
            "evaluations": evaluations,
            "pending_prediction": pending,
            "near_window": near_metadata,
            "guardrails": {
                "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
                "top100_random_probability_per_draw": round(100 / TOTAL_SSQ_RED_COMBINATIONS, 10),
                "top100_random_expected_hits_per_10": round(expected_random_hits, 8),
                "hit_definition": "exact red6 rank <= 100",
                "blue_scored": False,
                "evidence_level": "experimental_forward_monitoring",
            },
        }
    )


def write_near_dynamic_line_report(
    conn: Connection,
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    payload = build_near_dynamic_line_report(conn)
    target_dir = output_dir or default_output_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    pending = payload.get("pending_prediction") if isinstance(payload.get("pending_prediction"), dict) else {}
    as_of_issue = _safe_file_part(pending.get("as_of_issue") or "none")
    next_issue = _safe_file_part(pending.get("next_issue") or "none")
    json_path = target_dir / f"near-dynamic-line-{as_of_issue}-{next_issue}.json"
    md_path = target_dir / f"near-dynamic-line-{as_of_issue}-{next_issue}.md"
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(md_path)
    json_path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_near_dynamic_line_report(payload), encoding="utf-8")
    return payload


def render_near_dynamic_line_report(payload: dict[str, Any]) -> str:
    pending = payload.get("pending_prediction") if isinstance(payload.get("pending_prediction"), dict) else {}
    near_window = payload.get("near_window") if isinstance(payload.get("near_window"), dict) else {}
    evaluations = payload.get("evaluations") if isinstance(payload.get("evaluations"), list) else []
    rows = []
    for row in evaluations:
        if not isinstance(row, dict):
            continue
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row.get("predicted_issue") or ""),
                    str(row.get("status") or ""),
                    str(row.get("exact_rank") if row.get("exact_rank") is not None else "miss"),
                    "yes" if row.get("hit_top_100") else "no",
                    str(row.get("red5_rank") if row.get("red5_rank") is not None else "miss"),
                ]
            )
            + " |"
        )
    evaluation_table = "\n".join(rows) if rows else "| none | none | none | no | none |"
    return f"""# Near Dynamic KDJ Line Report

- Line: `{payload.get("line_key")}` ({payload.get("line_label")})
- Status: `{payload.get("status")}`
- Window: `{near_window.get("window_key") or "unknown"}`
- Current as-of: `{pending.get("as_of_issue") or "none"}`
- Pending next issue: `{pending.get("next_issue") or "none"}`
- Training mode: `{pending.get("train_mode") or near_window.get("train_mode") or "unknown"}` / continuous
- Snapshot source round: `{pending.get("source_round_index") if pending else "none"}`
- Exact Top100 progress: `{payload.get("exact_top100_hits")}/{payload.get("success_window")}` target `{payload.get("success_top100_goal")}`
- Goal reached: `{payload.get("goal_reached")}`

## Recent Forward Evaluations

| Issue | Status | Exact rank | Top100 | Red5 rank |
| --- | --- | --- | --- | --- |
{evaluation_table}

## Guardrails

- Legal red-ball sample space: `{(payload.get("guardrails") or {}).get("legal_sample_space", TOTAL_SSQ_RED_COMBINATIONS)}`
- Hit definition: exact red6 rank <= 100.
- Blue ball is recorded elsewhere but not scored.
- Random Top100 expected hits per 10 draws: `{(payload.get("guardrails") or {}).get("top100_random_expected_hits_per_10")}`
- Evidence level: experimental forward monitoring, not a settled prediction claim.
"""
