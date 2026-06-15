from __future__ import annotations

import json
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.crawler.ssq_parser import ValidatedSsqDraw


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
