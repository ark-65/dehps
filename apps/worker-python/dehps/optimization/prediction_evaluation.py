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
from dehps.storage.postgres_store import TOTAL_SSQ_RED_COMBINATIONS, upsert_training_prediction_evaluation


DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/prediction-evaluations"
DEFAULT_GUARDRAIL = (
    "Forward prediction evaluation only. Red-ball exact/red5 hits are measured after sync; "
    "blue ball is recorded but not scored."
)


def default_output_dir() -> Path:
    return DEFAULT_OUTPUT_DIR


def issue_less_than(left: object, right: object) -> bool:
    left_text = str(left)
    right_text = str(right)
    try:
        return int(left_text) < int(right_text)
    except ValueError:
        return left_text < right_text


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
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


def evaluation_key(*, line_key: str, predicted_issue: str, snapshot_key: str | None) -> str:
    return f"{line_key}:{predicted_issue}:{snapshot_key or 'missing-snapshot'}"


def load_prediction_rows(
    conn: Connection,
    *,
    line_key: str,
    predicted_issue: str,
    snapshot_key: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    exists = conn.execute("SELECT to_regclass('public.training_next_candidates_current')").fetchone()
    if not exists or not exists[0]:
        return [], None
    params: tuple[Any, ...]
    snapshot_filter = ""
    if snapshot_key:
        snapshot_filter = "AND snapshot_key = %s"
        params = (line_key, predicted_issue, snapshot_key)
    else:
        params = (line_key, predicted_issue)
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            f"""
            SELECT line_key, line_label, line_kind, snapshot_key, run_id, source_round_index,
                   as_of_issue, next_issue, next_draw_date, train_mode, train_window, eval_window,
                   top_n, history_fingerprint, config_hash, config, prediction_metadata,
                   rank, red_numbers, score, generated_at
            FROM training_next_candidates_current
            WHERE line_key = %s
              AND next_issue = %s
              {snapshot_filter}
            ORDER BY rank ASC
            """,
            params,
        ).fetchall()
    if rows or not snapshot_key:
        return [dict(row) for row in rows], None

    with conn.cursor(row_factory=dict_row) as cur:
        mismatch = cur.execute(
            """
            SELECT snapshot_key
            FROM training_next_candidates_current
            WHERE line_key = %s
              AND next_issue = %s
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (line_key, predicted_issue),
        ).fetchone()
    return [], str(mismatch["snapshot_key"]) if mismatch else None


def load_actual_draw(conn: Connection, *, issue: str) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            """
            SELECT issue, draw_date, red_numbers, blue_number
            FROM ssq_history
            WHERE issue = %s
            """,
            (issue,),
        ).fetchone()
    return dict(row) if row else None


def _line_defaults(line_key: str) -> tuple[str, str]:
    if line_key == "dynamic_kdj":
        return "Dynamic KDJ adjustment", "dynamic_kdj"
    return "100-period static training", "static"


def _base_payload(
    *,
    line_key: str,
    predicted_issue: str,
    snapshot_key: str | None,
    status: str,
    evaluated_at: str,
) -> dict[str, Any]:
    line_label, line_kind = _line_defaults(line_key)
    return {
        "evaluation_key": evaluation_key(line_key=line_key, predicted_issue=predicted_issue, snapshot_key=snapshot_key),
        "line_key": line_key,
        "line_label": line_label,
        "line_kind": line_kind,
        "snapshot_key": snapshot_key,
        "run_id": None,
        "source_round_index": None,
        "as_of_issue": None,
        "predicted_issue": predicted_issue,
        "actual_draw_date": None,
        "actual_red_numbers": None,
        "actual_blue_number": None,
        "exact_rank": None,
        "exact_score": None,
        "hit_top_100": False,
        "hit_top_1000": False,
        "hit_top_10000": False,
        "red5_rank": None,
        "red5_score": None,
        "red5_numbers": None,
        "hit_red5_top_100": False,
        "hit_red5_top_1000": False,
        "hit_red5_top_10000": False,
        "candidate_count": 0,
        "snapshot_generated_at": None,
        "status": status,
        "summary": {},
        "prediction_metadata": {},
        "json_path": None,
        "report_path": None,
        "guardrail": DEFAULT_GUARDRAIL,
        "evaluated_at": evaluated_at,
    }


def evaluate_prediction_snapshot(
    conn: Connection,
    *,
    line_key: str,
    predicted_issue: str,
    snapshot_key: str | None = None,
    output_dir: Path | None = None,
    write_report: bool = True,
    persist: bool = True,
) -> dict[str, Any]:
    evaluated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows, found_snapshot_key = load_prediction_rows(
        conn,
        line_key=line_key,
        predicted_issue=predicted_issue,
        snapshot_key=snapshot_key,
    )
    actual = load_actual_draw(conn, issue=predicted_issue)
    if actual is None:
        first = rows[0] if rows else {}
        payload = _base_payload(
            line_key=line_key,
            predicted_issue=predicted_issue,
            snapshot_key=str(first.get("snapshot_key") or snapshot_key or "") if first or snapshot_key else None,
            status="missing_actual_draw",
            evaluated_at=evaluated_at,
        )
        if first:
            payload.update(
                {
                    "line_label": str(first.get("line_label") or payload["line_label"]),
                    "line_kind": str(first.get("line_kind") or payload["line_kind"]),
                    "run_id": first.get("run_id"),
                    "source_round_index": first.get("source_round_index"),
                    "as_of_issue": first.get("as_of_issue"),
                    "candidate_count": len(rows),
                    "snapshot_generated_at": first.get("generated_at"),
                    "prediction_metadata": first.get("prediction_metadata")
                    if isinstance(first.get("prediction_metadata"), dict)
                    else {},
                }
            )
        return finalize_prediction_evaluation(conn, payload, output_dir=output_dir, write_report=write_report, persist=persist)
    if not rows:
        status = "prediction_snapshot_mismatch" if snapshot_key and found_snapshot_key else "missing_prediction_snapshot"
        payload = _base_payload(
            line_key=line_key,
            predicted_issue=predicted_issue,
            snapshot_key=snapshot_key,
            status=status,
            evaluated_at=evaluated_at,
        )
        payload["actual_draw_date"] = actual.get("draw_date")
        payload["actual_red_numbers"] = list(actual.get("red_numbers") or [])
        payload["actual_blue_number"] = actual.get("blue_number")
        payload["summary"] = {"found_snapshot_key": found_snapshot_key} if found_snapshot_key else {}
        return finalize_prediction_evaluation(conn, payload, output_dir=output_dir, write_report=write_report, persist=persist)

    first = rows[0]
    payload = _base_payload(
        line_key=line_key,
        predicted_issue=predicted_issue,
        snapshot_key=str(first.get("snapshot_key") or snapshot_key or ""),
        status="evaluated",
        evaluated_at=evaluated_at,
    )
    payload.update(
        {
            "line_label": str(first.get("line_label") or payload["line_label"]),
            "line_kind": str(first.get("line_kind") or payload["line_kind"]),
            "run_id": first.get("run_id"),
            "source_round_index": first.get("source_round_index"),
            "as_of_issue": first.get("as_of_issue"),
            "actual_draw_date": actual.get("draw_date"),
            "actual_red_numbers": list(actual.get("red_numbers") or []),
            "actual_blue_number": actual.get("blue_number"),
            "candidate_count": len(rows),
            "snapshot_generated_at": first.get("generated_at"),
            "prediction_metadata": first.get("prediction_metadata") if isinstance(first.get("prediction_metadata"), dict) else {},
        }
    )
    actual_red = tuple(int(value) for value in actual.get("red_numbers") or [])
    actual_set = set(actual_red)
    exact_row = None
    red5_row = None
    for row in rows:
        numbers = tuple(int(value) for value in row.get("red_numbers") or [])
        if numbers == actual_red and exact_row is None:
            exact_row = row
        if len(actual_set.intersection(numbers)) == 5 and red5_row is None:
            red5_row = row
        if exact_row is not None and red5_row is not None:
            break

    if exact_row is not None:
        rank = int(exact_row["rank"])
        payload["exact_rank"] = rank
        payload["exact_score"] = float(exact_row["score"])
        payload["hit_top_100"] = rank <= 100
        payload["hit_top_1000"] = rank <= 1000
        payload["hit_top_10000"] = rank <= 10000
    if red5_row is not None:
        rank = int(red5_row["rank"])
        payload["red5_rank"] = rank
        payload["red5_score"] = float(red5_row["score"])
        payload["red5_numbers"] = [int(value) for value in red5_row.get("red_numbers") or []]
        payload["hit_red5_top_100"] = rank <= 100
        payload["hit_red5_top_1000"] = rank <= 1000
        payload["hit_red5_top_10000"] = rank <= 10000

    leakage_passed = bool(payload["as_of_issue"]) and issue_less_than(payload["as_of_issue"], predicted_issue)
    if not leakage_passed:
        payload["status"] = "leakage_guard_failed"
    payload["summary"] = {
        "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
        "leakage_passed": leakage_passed,
        "candidate_count": len(rows),
        "exact_hit": exact_row is not None,
        "red5_hit": red5_row is not None,
        "actual_red_numbers": list(actual_red),
        "actual_blue_number": actual.get("blue_number"),
        "blue_scored": False,
    }
    return finalize_prediction_evaluation(conn, payload, output_dir=output_dir, write_report=write_report, persist=persist)


def finalize_prediction_evaluation(
    conn: Connection,
    payload: dict[str, Any],
    *,
    output_dir: Path | None,
    write_report: bool,
    persist: bool,
) -> dict[str, Any]:
    if write_report:
        json_path, report_path = write_prediction_evaluation_artifacts(payload, output_dir or default_output_dir())
        payload["json_path"] = str(json_path)
        payload["report_path"] = str(report_path)
    if persist:
        upsert_training_prediction_evaluation(conn, json_safe(payload))
    return json_safe(payload)


def write_prediction_evaluation_artifacts(payload: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issue = _safe_file_part(payload.get("predicted_issue"))
    line_key = _safe_file_part(payload.get("line_key"))
    snapshot = _safe_file_part(payload.get("snapshot_key") or payload.get("status"))
    json_path = output_dir / f"prediction-eval-{issue}-{line_key}-{snapshot}.json"
    md_path = output_dir / f"prediction-eval-{issue}-{line_key}-{snapshot}.md"
    json_path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_prediction_evaluation_report(payload), encoding="utf-8")
    return json_path, md_path


def render_prediction_evaluation_report(payload: dict[str, Any]) -> str:
    actual = payload.get("actual_red_numbers") or []
    exact_rank = payload.get("exact_rank")
    red5_rank = payload.get("red5_rank")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    prediction_metadata = (
        payload.get("prediction_metadata") if isinstance(payload.get("prediction_metadata"), dict) else {}
    )
    return f"""# Training Prediction Evaluation

- Line: `{payload.get("line_key")}` ({payload.get("line_label")})
- Status: `{payload.get("status")}`
- Predicted issue: `{payload.get("predicted_issue")}`
- Snapshot: `{payload.get("snapshot_key") or "none"}`
- As-of issue: `{payload.get("as_of_issue") or "none"}`
- Actual red: `{actual}`
- Actual blue: `{payload.get("actual_blue_number")}` (recorded, not scored)
- Exact red rank: `{exact_rank if exact_rank is not None else "miss"}`
- Exact Top100/1000/10000: `{payload.get("hit_top_100")}/{payload.get("hit_top_1000")}/{payload.get("hit_top_10000")}`
- Red5 best rank: `{red5_rank if red5_rank is not None else "miss"}`
- Red5 Top100/1000/10000: `{payload.get("hit_red5_top_100")}/{payload.get("hit_red5_top_1000")}/{payload.get("hit_red5_top_10000")}`
- Candidate count: `{payload.get("candidate_count")}`

## Guardrails

- Legal sample space: `{summary.get("legal_sample_space", TOTAL_SSQ_RED_COMBINATIONS)}`
- Leakage passed: `{summary.get("leakage_passed")}`
- Blue scored: `False`
- Fallback static base: `{prediction_metadata.get("fallback_static_base")}`

{payload.get("guardrail") or DEFAULT_GUARDRAIL}
"""
