from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.domain.combination import normalize_red_numbers
from dehps.storage.postgres_store import ensure_training_next_candidates_current_schema


DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/prediction-evaluations"
TOP_BANDS = (100, 1000, 10000)
SAFE_FILENAME_COMPONENT_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")


def safe_filename_component(value: Any, *, fallback: str) -> str:
    text = str(value or "").strip()
    text = SAFE_FILENAME_COMPONENT_PATTERN.sub("-", text).strip("-")
    return (text or fallback)[:96]


def _date_to_json(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def load_latest_issue(conn: Connection) -> str | None:
    row = conn.execute("SELECT max(issue) FROM ssq_history").fetchone()
    return str(row[0]) if row and row[0] else None


def load_actual_draw(conn: Connection, issue: str) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            """
            SELECT issue, draw_date, red_numbers, blue_number, source
            FROM ssq_history
            WHERE issue = %s
            """,
            (issue,),
        ).fetchone()
    if not row:
        return None
    return {
        "issue": str(row["issue"]),
        "draw_date": _date_to_json(row.get("draw_date")),
        "red_numbers": list(normalize_red_numbers(row["red_numbers"])),
        "blue_number": int(row["blue_number"]) if row.get("blue_number") is not None else None,
        "source": row.get("source"),
    }


def _metadata_from_prediction_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_key": row.get("snapshot_key"),
        "run_id": row.get("run_id"),
        "source_round_index": row.get("source_round_index"),
        "as_of_issue": str(row.get("as_of_issue") or ""),
        "next_issue": str(row.get("next_issue") or ""),
        "next_draw_date": _date_to_json(row.get("next_draw_date")),
        "train_mode": row.get("train_mode"),
        "train_window": row.get("train_window"),
        "eval_window": row.get("eval_window"),
        "top_n": row.get("top_n"),
        "history_fingerprint": row.get("history_fingerprint"),
        "config_hash": row.get("config_hash"),
        "config": row.get("config") or {},
        "generated_at": _date_to_json(row.get("generated_at")),
    }


def _candidate_from_prediction_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": int(row["rank"]),
        "red_numbers": list(normalize_red_numbers(row["red_numbers"])),
        "score": float(row["score"]) if row.get("score") is not None else None,
    }


def load_current_prediction_metadata(conn: Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            """
            SELECT snapshot_key, run_id, source_round_index, as_of_issue, next_issue, next_draw_date,
                   train_mode, train_window, eval_window, top_n, history_fingerprint, config_hash,
                   config, generated_at
            FROM training_next_candidates_current
            ORDER BY generated_at DESC, rank ASC
            LIMIT 1
            """
        ).fetchone()
    return _metadata_from_prediction_row(row) if row else None


def load_prediction_snapshot_for_issue(conn: Connection, issue: str) -> dict[str, Any]:
    ensure_training_next_candidates_current_schema(conn)
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT snapshot_key, run_id, source_round_index, as_of_issue, next_issue, next_draw_date,
                   train_mode, train_window, eval_window, top_n, history_fingerprint, config_hash,
                   config, rank, red_numbers, score, generated_at
            FROM training_next_candidates_current
            WHERE next_issue = %s
            ORDER BY rank ASC
            """,
            (issue,),
        ).fetchall()
    if rows:
        return {
            "status": "loaded",
            "metadata": _metadata_from_prediction_row(rows[0]),
            "candidates": [_candidate_from_prediction_row(row) for row in rows],
        }
    current_metadata = load_current_prediction_metadata(conn)
    return {
        "status": "missing" if current_metadata is None else "mismatch",
        "metadata": current_metadata,
        "candidates": [],
    }


def issue_is_before(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    if str(left).isdigit() and str(right).isdigit():
        return int(left) < int(right)
    return str(left) < str(right)


def evaluate_prediction_candidates(
    actual_red_numbers: list[int] | tuple[int, ...],
    candidates: list[dict[str, Any]],
    *,
    top_bands: tuple[int, ...] = TOP_BANDS,
) -> dict[str, Any]:
    actual_numbers = normalize_red_numbers(actual_red_numbers)
    actual_set = set(actual_numbers)
    exact_rank: int | None = None
    red5_or_better_rank: int | None = None
    best_overlap = -1
    best_overlap_rank: int | None = None
    best_overlap_examples: list[dict[str, Any]] = []
    first_rank_by_overlap: dict[int, int] = {}

    for candidate in candidates:
        rank = int(candidate["rank"])
        red_numbers = normalize_red_numbers(candidate["red_numbers"])
        overlap = len(actual_set.intersection(red_numbers))
        first_rank_by_overlap.setdefault(overlap, rank)
        if red_numbers == actual_numbers and exact_rank is None:
            exact_rank = rank
        if overlap >= 5 and (red5_or_better_rank is None or rank < red5_or_better_rank):
            red5_or_better_rank = rank
        if overlap > best_overlap:
            best_overlap = overlap
            best_overlap_rank = rank
            best_overlap_examples = [
                {
                    "rank": rank,
                    "red_numbers": list(red_numbers),
                    "score": candidate.get("score"),
                    "overlap": overlap,
                }
            ]
        elif overlap == best_overlap and len(best_overlap_examples) < 5:
            best_overlap_examples.append(
                {
                    "rank": rank,
                    "red_numbers": list(red_numbers),
                    "score": candidate.get("score"),
                    "overlap": overlap,
                }
            )

    candidate_count = len(candidates)
    red5_rank = first_rank_by_overlap.get(5)
    if best_overlap < 0:
        best_overlap = 0

    exact = {
        "rank": exact_rank,
        "hit_top_n": exact_rank is not None and exact_rank <= candidate_count,
    }
    red5 = {
        "rank": red5_rank,
        "hit_top_n": red5_rank is not None and red5_rank <= candidate_count,
    }
    red5_or_better = {
        "rank": red5_or_better_rank,
        "hit_top_n": red5_or_better_rank is not None and red5_or_better_rank <= candidate_count,
    }
    for band in top_bands:
        exact[f"hit_top_{band}"] = exact_rank is not None and exact_rank <= band
        red5[f"hit_top_{band}"] = red5_rank is not None and red5_rank <= band
        red5_or_better[f"hit_top_{band}"] = red5_or_better_rank is not None and red5_or_better_rank <= band

    return {
        "actual_red_numbers": list(actual_numbers),
        "candidate_count": candidate_count,
        "exact_red6": exact,
        "red5": red5,
        "red5_or_better": red5_or_better,
        "red_overlap": {
            "best_overlap": best_overlap,
            "best_overlap_rank": best_overlap_rank,
            "first_rank_by_overlap": {str(key): value for key, value in sorted(first_rank_by_overlap.items())},
            "best_overlap_examples": best_overlap_examples,
        },
    }


def build_prediction_evaluation(conn: Connection, *, issue: str | None = None) -> dict[str, Any]:
    resolved_issue = issue or load_latest_issue(conn)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "evaluated_at": utc_now_iso(),
        "issue": str(resolved_issue or ""),
        "status": "unknown",
        "evaluable": False,
        "actual_draw": None,
        "prediction_snapshot": None,
        "result": None,
        "warnings": [],
    }
    if not resolved_issue:
        payload["status"] = "missing_issue"
        payload["warnings"].append("No issue was supplied and ssq_history has no latest issue.")
        return payload

    actual_draw = load_actual_draw(conn, str(resolved_issue))
    payload["actual_draw"] = actual_draw
    if actual_draw is None:
        payload["status"] = "missing_actual_draw"
        payload["warnings"].append(f"Issue {resolved_issue} is not present in ssq_history.")
        return payload

    snapshot = load_prediction_snapshot_for_issue(conn, str(resolved_issue))
    payload["prediction_snapshot"] = {
        "status": snapshot["status"],
        "metadata": snapshot["metadata"],
        "candidate_count": len(snapshot["candidates"]),
    }
    metadata = snapshot.get("metadata") or {}
    if snapshot["status"] == "missing":
        payload["status"] = "missing_prediction_snapshot"
        payload["warnings"].append(f"No current prediction snapshot exists for issue {resolved_issue}.")
        return payload
    if snapshot["status"] == "mismatch":
        payload["status"] = "prediction_snapshot_mismatch"
        payload["warnings"].append(
            "Current prediction snapshot targets "
            f"issue {metadata.get('next_issue') or 'unknown'}, not actual issue {resolved_issue}."
        )
        return payload
    if not issue_is_before(metadata.get("as_of_issue"), str(resolved_issue)):
        payload["status"] = "leakage_guard_failed"
        payload["warnings"].append(
            "Prediction snapshot is not strictly earlier than the actual issue; evaluation is blocked."
        )
        return payload

    payload["status"] = "evaluated"
    payload["evaluable"] = True
    payload["result"] = evaluate_prediction_candidates(actual_draw["red_numbers"], snapshot["candidates"])
    if actual_draw.get("blue_number") is not None:
        payload["warnings"].append("The current training prediction snapshot is red-ball only; blue is recorded but not scored.")
    return payload


def render_prediction_evaluation_report(payload: dict[str, Any]) -> str:
    issue = payload.get("issue") or "unknown"
    actual = payload.get("actual_draw") or {}
    snapshot = payload.get("prediction_snapshot") or {}
    metadata = snapshot.get("metadata") or {}
    result = payload.get("result") or {}
    exact = result.get("exact_red6") or {}
    red5 = result.get("red5") or {}
    red5_or_better = result.get("red5_or_better") or {}
    overlap = result.get("red_overlap") or {}
    warnings = payload.get("warnings") or []

    actual_red = " ".join(f"{number:02d}" for number in actual.get("red_numbers") or [])
    exact_rank = exact.get("rank")
    red5_rank = red5.get("rank")
    red5_or_better_rank = red5_or_better.get("rank")
    exact_rank_text = f"#{exact_rank}" if exact_rank else "not in snapshot"
    red5_rank_text = f"#{red5_rank}" if red5_rank else "not in snapshot"
    red5_or_better_rank_text = f"#{red5_or_better_rank}" if red5_or_better_rank else "not in snapshot"

    lines = [
        f"# Training Prediction Evaluation - Issue {issue}",
        "",
        f"- Status: {payload.get('status')}",
        f"- Evaluable: {payload.get('evaluable')}",
        f"- Evaluated at: {payload.get('evaluated_at')}",
        "",
        "## Actual Draw",
        "",
        f"- Issue: {actual.get('issue') or issue}",
        f"- Draw date: {actual.get('draw_date') or 'unknown'}",
        f"- Red balls: {actual_red or 'unknown'}",
        f"- Blue ball: {actual.get('blue_number') if actual.get('blue_number') is not None else 'unknown'}",
        f"- Source: {actual.get('source') or 'unknown'}",
        "",
        "## Prediction Snapshot",
        "",
        f"- Snapshot status: {snapshot.get('status') or 'unknown'}",
        f"- Snapshot key: {metadata.get('snapshot_key') or 'none'}",
        f"- Run id: {metadata.get('run_id') or 'none'}",
        f"- As-of issue: {metadata.get('as_of_issue') or 'none'}",
        f"- Target issue: {metadata.get('next_issue') or 'none'}",
        f"- Generated at: {metadata.get('generated_at') or 'none'}",
        f"- Train mode/window/eval: {metadata.get('train_mode') or 'none'} / "
        f"{metadata.get('train_window') or 'none'} / {metadata.get('eval_window') or 'none'}",
        f"- Candidate count: {snapshot.get('candidate_count') or 0}",
        "",
        "## Result",
        "",
        f"- Exact red6 rank: {exact_rank_text}",
        f"- Exact hit Top100/Top1000/Top10000: "
        f"{exact.get('hit_top_100', False)} / {exact.get('hit_top_1000', False)} / "
        f"{exact.get('hit_top_10000', False)}",
        f"- Red5 first rank: {red5_rank_text}",
        f"- Red5 hit Top100/Top1000/Top10000: "
        f"{red5.get('hit_top_100', False)} / {red5.get('hit_top_1000', False)} / "
        f"{red5.get('hit_top_10000', False)}",
        f"- Red5-or-better first rank: {red5_or_better_rank_text}",
        f"- Red5-or-better hit Top100/Top1000/Top10000: "
        f"{red5_or_better.get('hit_top_100', False)} / {red5_or_better.get('hit_top_1000', False)} / "
        f"{red5_or_better.get('hit_top_10000', False)}",
        f"- Best red overlap: {overlap.get('best_overlap', 0)}/6 at "
        f"#{overlap.get('best_overlap_rank') or 'none'}",
    ]
    examples = overlap.get("best_overlap_examples") or []
    if examples:
        lines.extend(["", "## Best Overlap Examples", ""])
        for example in examples:
            numbers = " ".join(f"{number:02d}" for number in example.get("red_numbers") or [])
            lines.append(
                f"- #{example.get('rank')}: {numbers} "
                f"(overlap={example.get('overlap')}, score={example.get('score')})"
            )
    if warnings:
        lines.extend(["", "## Guardrails", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    return "\n".join(lines)


def write_prediction_evaluation_report(
    payload: dict[str, Any],
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, str]:
    issue = safe_filename_component(payload.get("issue"), fallback="unknown-issue")
    metadata = ((payload.get("prediction_snapshot") or {}).get("metadata") or {})
    snapshot_key = safe_filename_component(metadata.get("snapshot_key"), fallback="no-snapshot")
    stem = f"prediction-evaluation-{issue}-{snapshot_key}"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    atomic_write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n")
    atomic_write_text(markdown_path, render_prediction_evaluation_report(payload))
    return {"json_path": str(json_path), "report_path": str(markdown_path)}
