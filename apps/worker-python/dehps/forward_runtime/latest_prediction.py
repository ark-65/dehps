from __future__ import annotations

from collections import Counter
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.source_version import resolve_git_commit


EXPECTED_LINE_KEYS = ("static_100", "dynamic_kdj", "dynamic_kdj_near")


def load_latest_prediction_rows(
    conn: Connection,
    *,
    top_limit: int = 10,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with conn.cursor(row_factory=dict_row) as cur:
        runs = cur.execute(
            """
            WITH latest_target AS (
              SELECT target_issue
              FROM forward_prediction_runs
              ORDER BY generated_at DESC, target_issue DESC
              LIMIT 1
            ), latest_lines AS (
              SELECT DISTINCT ON (line_key)
                     prediction_run_key, line_key, line_label, line_kind,
                     source_run_id, source_round_index, as_of_issue,
                     target_issue, status, generated_at, candidate_count,
                     config_hash, metadata
              FROM forward_prediction_runs
              WHERE target_issue = (SELECT target_issue FROM latest_target)
                AND status <> 'superseded'
              ORDER BY line_key, generated_at DESC
            )
            SELECT * FROM latest_lines
            """
        ).fetchall()
        run_rows = [dict(row) for row in runs]
        if not run_rows:
            return [], []
        run_keys = [str(row["prediction_run_key"]) for row in run_rows]
        candidates = cur.execute(
            """
            SELECT prediction_run_key, rank, red_numbers, score
            FROM forward_prediction_candidates
            WHERE prediction_run_key = ANY(%s::text[])
              AND rank <= %s
            ORDER BY prediction_run_key, rank
            """,
            (run_keys, max(1, int(top_limit))),
        ).fetchall()
    return run_rows, [dict(row) for row in candidates]


def prediction_display_status(statuses: list[str], *, complete_line_set: bool) -> str:
    if not complete_line_set:
        return "incomplete_lines"
    if statuses and all(status == "evaluated" for status in statuses):
        return "evaluated"
    if any(status == "evaluation_failed" for status in statuses):
        return "evaluation_failed"
    if any(status == "evaluating" for status in statuses):
        return "evaluating"
    return "waiting_draw"


def build_latest_prediction_payload(
    run_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    *,
    git_commit: str,
    top_limit: int = 10,
) -> dict[str, Any]:
    if not run_rows:
        return {
            "status": "no_prediction",
            "issue": None,
            "as_of_issue": None,
            "generated_at": None,
            "git_commit": "not_applicable",
            "viewer_git_commit": git_commit,
            "lines": [],
            "consensus_numbers": [],
            "missing_lines": list(EXPECTED_LINE_KEYS),
        }

    candidates_by_run: dict[str, list[dict[str, Any]]] = {}
    for row in candidate_rows:
        key = str(row["prediction_run_key"])
        candidates_by_run.setdefault(key, []).append(row)

    runs_by_line = {str(row["line_key"]): row for row in run_rows}
    missing_lines = [key for key in EXPECTED_LINE_KEYS if key not in runs_by_line]
    line_payloads: list[dict[str, Any]] = []
    number_line_presence: Counter[int] = Counter()
    number_candidate_occurrences: Counter[int] = Counter()
    for line_key in EXPECTED_LINE_KEYS:
        run = runs_by_line.get(line_key)
        if run is None:
            continue
        rows = candidates_by_run.get(str(run["prediction_run_key"]), [])[:top_limit]
        top_candidates = [
            {
                "rank": int(row["rank"]),
                "red_numbers": [int(value) for value in row["red_numbers"]],
                "score": float(row["score"]),
            }
            for row in rows
        ]
        present_in_line: set[int] = set()
        for candidate in top_candidates:
            numbers = candidate["red_numbers"]
            present_in_line.update(numbers)
            number_candidate_occurrences.update(numbers)
        number_line_presence.update(present_in_line)
        line_payloads.append(
            {
                "line_key": line_key,
                "line_label": str(run["line_label"]),
                "status": str(run["status"]),
                "source_run_id": str(run["source_run_id"]),
                "source_round_index": run.get("source_round_index"),
                "config_hash": str(run["config_hash"]),
                "candidate_count": int(run["candidate_count"]),
                "top_candidates": top_candidates,
            }
        )

    line_count = len(line_payloads)
    consensus_numbers = [
        {
            "number": number,
            "line_count": number_line_presence[number],
            "candidate_occurrences": number_candidate_occurrences[number],
        }
        for number in sorted(
            number_line_presence,
            key=lambda value: (
                -number_line_presence[value],
                -number_candidate_occurrences[value],
                value,
            ),
        )
        if line_count > 0 and number_line_presence[number] == line_count
    ]
    generated_at = max(row["generated_at"] for row in run_rows)
    first = run_rows[0]
    statuses = [str(row["status"]) for row in run_rows]
    source_git_commits = {
        str(metadata["git_commit"])
        for row in run_rows
        if isinstance((metadata := row.get("metadata")), dict)
        and metadata.get("git_commit")
    }
    source_git_commit = (
        next(iter(source_git_commits))
        if len(source_git_commits) == 1
        else "mixed" if source_git_commits else "not_recorded"
    )
    return {
        "status": prediction_display_status(statuses, complete_line_set=not missing_lines),
        "issue": str(first["target_issue"]),
        "as_of_issue": str(first["as_of_issue"]),
        "generated_at": generated_at.isoformat() if hasattr(generated_at, "isoformat") else str(generated_at),
        "git_commit": source_git_commit,
        "viewer_git_commit": git_commit,
        "lines": line_payloads,
        "consensus_definition": f"red numbers present in Top {top_limit} of every available line",
        "consensus_numbers": consensus_numbers,
        "missing_lines": missing_lines,
    }


def render_latest_prediction(payload: dict[str, Any]) -> str:
    if payload["status"] == "no_prediction":
        return "No forward prediction is available."
    lines = [
        f"Issue: {payload['issue']}",
        f"As of: {payload['as_of_issue']}",
        f"Generated: {payload['generated_at']}",
        f"Status: {payload['status']}",
        f"Git (prediction source): {payload['git_commit']}",
        f"Git (viewer): {payload['viewer_git_commit']}",
    ]
    for line in payload["lines"]:
        lines.append("")
        lines.append(
            f"[{line['line_key']}] {line['line_label']} "
            f"run={line['source_run_id']} round={line['source_round_index']} "
            f"status={line['status']}"
        )
        for candidate in line["top_candidates"]:
            numbers = " ".join(f"{number:02d}" for number in candidate["red_numbers"])
            lines.append(f"  {candidate['rank']:>2}. {numbers}  score={candidate['score']:.8f}")
    consensus = " ".join(
        f"{item['number']:02d}({item['candidate_occurrences']})"
        for item in payload["consensus_numbers"]
    )
    lines.extend(("", f"Consensus across all lines: {consensus or 'none'}"))
    if payload["missing_lines"]:
        lines.append(f"Missing lines: {', '.join(payload['missing_lines'])}")
    return "\n".join(lines)
