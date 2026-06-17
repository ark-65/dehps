from __future__ import annotations

import json
from datetime import date
from math import comb
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.crawler.ssq_parser import ValidatedSsqDraw


TOTAL_SSQ_RED_COMBINATIONS = comb(33, 6)


def init_schema(conn: Connection, sql_path) -> None:
    conn.execute(sql_path.read_text())


def upsert_ssq_draw(conn: Connection, draw: ValidatedSsqDraw, source: str) -> str:
    existing = conn.execute(
        "SELECT red_numbers, blue_number, source FROM ssq_history WHERE issue = %s",
        (draw.issue,),
    ).fetchone()
    if existing:
        existing_red = list(existing[0])
        existing_blue = existing[1]
        existing_source = existing[2]
        if existing_red != list(draw.red_numbers) or existing_blue != draw.blue_number:
            if source == "zhcw" and existing_source == "csv":
                conn.execute(
                    """
                    UPDATE ssq_history
                    SET draw_date = %s,
                        red_numbers = %s,
                        r1 = %s,
                        r2 = %s,
                        r3 = %s,
                        r4 = %s,
                        r5 = %s,
                        r6 = %s,
                        blue_number = %s,
                        source = %s
                    WHERE issue = %s
                    """,
                    (
                        draw.draw_date,
                        list(draw.red_numbers),
                        *draw.red_numbers,
                        draw.blue_number,
                        source,
                        draw.issue,
                    ),
                )
                return "updated"
            record_conflict(
                conn,
                issue=draw.issue,
                existing_red_numbers=existing_red,
                incoming_red_numbers=list(draw.red_numbers),
                existing_blue_number=existing_blue,
                incoming_blue_number=draw.blue_number,
                source=source,
                reason="same issue has different numbers",
                raw_payload=draw.raw_payload,
            )
            return "conflict"
        return "skipped"

    conn.execute(
        """
        INSERT INTO ssq_history (
          issue, draw_date, red_numbers, r1, r2, r3, r4, r5, r6, blue_number, source
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            draw.issue,
            draw.draw_date,
            list(draw.red_numbers),
            *draw.red_numbers,
            draw.blue_number,
            source,
        ),
    )
    return "inserted"


def record_conflict(
    conn: Connection,
    issue: str,
    existing_red_numbers: list[int] | None,
    incoming_red_numbers: list[int],
    existing_blue_number: int | None,
    incoming_blue_number: int | None,
    source: str,
    reason: str,
    raw_payload: dict[str, Any] | None,
) -> None:
    conn.execute(
        """
        INSERT INTO ssq_data_conflicts (
          issue, existing_red_numbers, incoming_red_numbers, existing_blue_number,
          incoming_blue_number, source, conflict_reason, raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            issue,
            existing_red_numbers,
            incoming_red_numbers,
            existing_blue_number,
            incoming_blue_number,
            source,
            reason,
            json.dumps(raw_payload or {}),
        ),
    )


def create_sync_run(conn: Connection, run_key: str, source: str, status: str = "running") -> None:
    conn.execute(
        """
        INSERT INTO ssq_sync_runs (run_key, source, status)
        VALUES (%s, %s, %s)
        ON CONFLICT (run_key) DO NOTHING
        """,
        (run_key, source, status),
    )


def finish_sync_run(conn: Connection, run_key: str, status: str, summary: dict[str, Any]) -> None:
    conn.execute(
        """
        UPDATE ssq_sync_runs
        SET status = %s,
            finished_at = now(),
            fetched_count = %s,
            inserted_count = %s,
            updated_count = %s,
            skipped_count = %s,
            conflict_count = %s,
            error_message = %s,
            raw_meta = %s::jsonb
        WHERE run_key = %s
        """,
        (
            status,
            summary.get("fetched_count", 0),
            summary.get("inserted_count", 0),
            summary.get("updated_count", 0),
            summary.get("skipped_count", 0),
            summary.get("conflict_count", 0),
            summary.get("error_message"),
            json.dumps(summary.get("raw_meta", {})),
            run_key,
        ),
    )


def load_history(conn: Connection) -> list[tuple[str, tuple[int, ...]]]:
    rows = conn.execute(
        "SELECT issue, red_numbers FROM ssq_history ORDER BY issue",
    ).fetchall()
    return [(row[0], tuple(row[1])) for row in rows]


def load_history_with_dates(conn: Connection) -> list[tuple[str, date | None, tuple[int, ...]]]:
    rows = conn.execute(
        "SELECT issue, draw_date, red_numbers FROM ssq_history ORDER BY issue",
    ).fetchall()
    return [(row[0], row[1], tuple(row[2])) for row in rows]


def load_history_until(conn: Connection, as_of_issue: str | None) -> list[tuple[str, tuple[int, ...]]]:
    if not as_of_issue:
        return load_history(conn)
    rows = conn.execute(
        "SELECT issue, red_numbers FROM ssq_history WHERE issue <= %s ORDER BY issue",
        (as_of_issue,),
    ).fetchall()
    return [(row[0], tuple(row[1])) for row in rows]


def load_history_until_with_dates(
    conn: Connection,
    as_of_issue: str | None,
) -> list[tuple[str, date | None, tuple[int, ...]]]:
    if not as_of_issue:
        return load_history_with_dates(conn)
    rows = conn.execute(
        "SELECT issue, draw_date, red_numbers FROM ssq_history WHERE issue <= %s ORDER BY issue",
        (as_of_issue,),
    ).fetchall()
    return [(row[0], row[1], tuple(row[2])) for row in rows]


def load_history_since_date(
    conn: Connection,
    *,
    start_date: date,
    as_of_issue: str | None = None,
) -> list[tuple[str, tuple[int, ...]]]:
    if as_of_issue:
        rows = conn.execute(
            """
            SELECT issue, red_numbers
            FROM ssq_history
            WHERE draw_date >= %s AND issue <= %s
            ORDER BY issue
            """,
            (start_date, as_of_issue),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT issue, red_numbers
            FROM ssq_history
            WHERE draw_date >= %s
            ORDER BY issue
            """,
            (start_date,),
        ).fetchall()
    return [(row[0], tuple(row[1])) for row in rows]


def load_history_since_date_with_dates(
    conn: Connection,
    *,
    start_date: date,
    as_of_issue: str | None = None,
) -> list[tuple[str, date | None, tuple[int, ...]]]:
    if as_of_issue:
        rows = conn.execute(
            """
            SELECT issue, draw_date, red_numbers
            FROM ssq_history
            WHERE draw_date >= %s AND issue <= %s
            ORDER BY issue
            """,
            (start_date, as_of_issue),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT issue, draw_date, red_numbers
            FROM ssq_history
            WHERE draw_date >= %s
            ORDER BY issue
            """,
            (start_date,),
        ).fetchall()
    return [(row[0], row[1], tuple(row[2])) for row in rows]


def latest_draw_date_until(conn: Connection, as_of_issue: str | None = None) -> date | None:
    if as_of_issue:
        row = conn.execute(
            "SELECT max(draw_date) FROM ssq_history WHERE issue <= %s",
            (as_of_issue,),
        ).fetchone()
    else:
        row = conn.execute("SELECT max(draw_date) FROM ssq_history").fetchone()
    return row[0] if row and row[0] else None


def latest_draw(conn: Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "SELECT issue, draw_date, red_numbers, blue_number, source FROM ssq_history ORDER BY issue DESC LIMIT 1",
        ).fetchone()
    if not row:
        return None
    row["red_numbers"] = list(row["red_numbers"])
    if row["draw_date"]:
        row["draw_date"] = row["draw_date"].isoformat()
    return dict(row)


def audit_ssq_history(conn: Connection) -> dict[str, Any]:
    summary = conn.execute(
        """
        SELECT
          count(*) AS total_draws,
          min(issue) AS min_issue,
          max(issue) AS max_issue,
          min(draw_date) AS min_draw_date,
          max(draw_date) AS max_draw_date
        FROM ssq_history
        """,
    ).fetchone()
    duplicate_rows = conn.execute(
        """
        SELECT issue, count(*) AS row_count
        FROM ssq_history
        GROUP BY issue
        HAVING count(*) > 1
        ORDER BY issue
        """,
    ).fetchall()
    monotonic_rows = conn.execute(
        """
        WITH ordered AS (
          SELECT
            id,
            issue,
            lag(issue) OVER (ORDER BY id) AS previous_issue
          FROM ssq_history
        )
        SELECT id, issue, previous_issue
        FROM ordered
        WHERE previous_issue IS NOT NULL AND issue < previous_issue
        ORDER BY id
        LIMIT 20
        """,
    ).fetchall()
    id_asc = conn.execute(
        """
        SELECT id, issue, draw_date
        FROM ssq_history
        ORDER BY id ASC
        LIMIT 10
        """,
    ).fetchall()
    issue_asc = conn.execute(
        """
        SELECT id, issue, draw_date
        FROM ssq_history
        ORDER BY issue ASC
        LIMIT 10
        """,
    ).fetchall()
    issue_desc = conn.execute(
        """
        SELECT id, issue, draw_date
        FROM ssq_history
        ORDER BY issue DESC
        LIMIT 10
        """,
    ).fetchall()
    issue_years = conn.execute(
        """
        SELECT left(issue, 4) AS issue_year, count(*) AS draw_count
        FROM ssq_history
        GROUP BY left(issue, 4)
        ORDER BY issue_year
        """,
    ).fetchall()

    return {
        "total_draws": summary[0],
        "min_issue": summary[1],
        "max_issue": summary[2],
        "min_draw_date": summary[3].isoformat() if summary[3] else None,
        "max_draw_date": summary[4].isoformat() if summary[4] else None,
        "duplicate_issues": [{"issue": row[0], "row_count": row[1]} for row in duplicate_rows],
        "id_issue_monotonic": len(monotonic_rows) == 0,
        "id_issue_monotonic_violations": [
            {"id": row[0], "issue": row[1], "previous_issue": row[2]} for row in monotonic_rows
        ],
        "first_10_by_id": [_audit_row(row) for row in id_asc],
        "first_10_by_issue": [_audit_row(row) for row in issue_asc],
        "latest_10_by_issue": [_audit_row(row) for row in issue_desc],
        "draws_by_issue_year": [{"issue_year": row[0], "draw_count": row[1]} for row in issue_years],
    }


def _audit_row(row) -> dict[str, Any]:
    return {"id": row[0], "issue": row[1], "draw_date": row[2].isoformat() if row[2] else None}


def count_red_combination_universe(conn: Connection) -> int:
    row = conn.execute("SELECT count(*) FROM ssq_red_combinations").fetchone()
    return int(row[0])


def load_red_combination_universe(conn: Connection) -> list[tuple[int, ...]]:
    rows = conn.execute(
        """
        SELECT numbers
        FROM ssq_red_combinations
        ORDER BY n1, n2, n3, n4, n5, n6
        """,
    ).fetchall()
    combinations = [tuple(row[0]) for row in rows]
    if len(combinations) != TOTAL_SSQ_RED_COMBINATIONS:
        raise ValueError(
            "ssq_red_combinations must contain the full C(33,6) universe "
            f"({TOTAL_SSQ_RED_COMBINATIONS} rows); found {len(combinations)}"
        )
    return combinations


def previous_experiment_metrics(conn: Connection, strategy_key: str) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            """
            SELECT keep_rate, coverage_rate, lift
            FROM dehps_experiments
            WHERE strategy_key = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (strategy_key,),
        ).fetchone()
    return dict(row) if row else None


def save_experiment(conn: Connection, experiment_key: str, strategy_key: str, metrics: dict, report: str) -> None:
    conn.execute(
        """
        INSERT INTO dehps_experiments (
          experiment_key, strategy_key, hypothesis, total_combinations, kept_combinations,
          keep_rate, history_draws, covered_draws, coverage_rate, lift, config, summary
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '{}'::jsonb, %s)
        ON CONFLICT (experiment_key) DO NOTHING
        """,
        (
            experiment_key,
            strategy_key,
            "baseline structural naturalness filter",
            metrics["total_combinations"],
            metrics["kept_combinations"],
            metrics["keep_rate"],
            metrics["history_draws"],
            metrics["covered_draws"],
            metrics["coverage_rate"],
            metrics["lift"],
            json.dumps(metrics, ensure_ascii=False),
        ),
    )
    conn.execute(
        """
        INSERT INTO dehps_experiment_reports (experiment_key, report_markdown)
        VALUES (%s, %s)
        """,
        (experiment_key, report),
    )


def create_pipeline_run(conn: Connection, run_key: str) -> None:
    conn.execute(
        "INSERT INTO pipeline_runs (run_key, status) VALUES (%s, 'running') ON CONFLICT (run_key) DO NOTHING",
        (run_key,),
    )


def finish_pipeline_run(conn: Connection, run_key: str, status: str, summary: dict[str, Any]) -> None:
    conn.execute(
        """
        UPDATE pipeline_runs
        SET status = %s,
            finished_at = now(),
            sync_run_key = %s,
            experiment_key = %s,
            git_commit_sha = %s,
            error_message = %s,
            summary = %s::jsonb
        WHERE run_key = %s
        """,
        (
            status,
            summary.get("sync_run_key"),
            summary.get("experiment_key"),
            summary.get("git_commit_sha"),
            summary.get("error_message"),
            json.dumps(summary, ensure_ascii=False),
            run_key,
        ),
    )
