from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import comb
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.crawler.ssq_parser import ValidatedSsqDraw


TOTAL_SSQ_RED_COMBINATIONS = comb(33, 6)
CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID = "weight-kdj-recent-1000-v1"


@dataclass(frozen=True)
class SsqDrawSite:
    site_key: str
    name: str
    address: str
    latitude: Decimal
    longitude: Decimal
    coordinate_system: str
    accuracy_note: str
    address_source_url: str
    draw_location_source_url: str
    effective_from_issue: str | None = None
    effective_to_issue: str | None = None
    is_active: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "site_key": self.site_key,
            "name": self.name,
            "address": self.address,
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "coordinate_system": self.coordinate_system,
            "accuracy_note": self.accuracy_note,
            "address_source_url": self.address_source_url,
            "draw_location_source_url": self.draw_location_source_url,
            "effective_from_issue": self.effective_from_issue,
            "effective_to_issue": self.effective_to_issue,
            "is_active": self.is_active,
        }


DEFAULT_SSQ_DRAW_SITE = SsqDrawSite(
    site_key="cwl_beijing_n4ring_v0",
    name="China Welfare Lottery Issuance Management Center",
    address="Beijing, Chaoyang District, North 4th Ring East Road 73",
    latitude=Decimal("39.990000"),
    longitude=Decimal("116.430000"),
    coordinate_system="WGS84",
    accuracy_note=(
        "Approximate site coordinate for external physics experiments; the address is sourced, "
        "while coordinates are rounded and should not be treated as survey-grade."
    ),
    address_source_url="https://www.cwl.gov.cn/c/2020-02-01/463075.shtml",
    draw_location_source_url="https://www.thepaper.cn/newsDetail_forward_11540335",
)


def init_schema(conn: Connection, sql_path) -> None:
    conn.execute(sql_path.read_text())


def ensure_ssq_draw_site_schema(conn: Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ssq_draw_sites (
          id BIGSERIAL PRIMARY KEY,
          site_key TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          address TEXT NOT NULL,
          latitude NUMERIC(9,6) NOT NULL,
          longitude NUMERIC(9,6) NOT NULL,
          coordinate_system TEXT NOT NULL DEFAULT 'WGS84',
          accuracy_note TEXT,
          address_source_url TEXT,
          draw_location_source_url TEXT,
          effective_from_issue TEXT,
          effective_to_issue TEXT,
          is_active BOOLEAN NOT NULL DEFAULT true,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def ensure_training_round_results_schema(conn: Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS training_round_results (
          id BIGSERIAL PRIMARY KEY,
          run_id TEXT NOT NULL,
          round_index INTEGER NOT NULL,
          phase TEXT NOT NULL,
          step NUMERIC(10,6) NOT NULL,
          train_mode TEXT NOT NULL,
          train_window INTEGER NOT NULL,
          eval_window INTEGER NOT NULL,
          top_n INTEGER NOT NULL,
          as_of_issue TEXT NOT NULL,
          history_fingerprint TEXT NOT NULL,
          improved BOOLEAN NOT NULL DEFAULT false,
          top_100_hits INTEGER NOT NULL DEFAULT 0,
          top_1000_hits INTEGER NOT NULL DEFAULT 0,
          top_10000_hits INTEGER NOT NULL DEFAULT 0,
          red5_top_100_hits INTEGER NOT NULL DEFAULT 0,
          red5_top_1000_hits INTEGER NOT NULL DEFAULT 0,
          red5_top_10000_hits INTEGER NOT NULL DEFAULT 0,
          median_rank NUMERIC(12,2),
          best_rank INTEGER,
          worst_rank INTEGER,
          objective_score NUMERIC(14,6),
          best_config JSONB NOT NULL DEFAULT '{}'::jsonb,
          best_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
          top_results JSONB NOT NULL DEFAULT '[]'::jsonb,
          target_results JSONB NOT NULL DEFAULT '[]'::jsonb,
          prefilter JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (run_id, round_index)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_training_round_results_created_at
          ON training_round_results (created_at DESC, round_index DESC)
        """
    )


def ensure_training_weight_signals_schema(conn: Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS training_weight_signals (
          id BIGSERIAL PRIMARY KEY,
          signal_run_id TEXT NOT NULL,
          issue TEXT NOT NULL,
          draw_date DATE,
          weight_name TEXT NOT NULL,
          train_mode TEXT NOT NULL,
          train_window INTEGER NOT NULL,
          eval_window INTEGER NOT NULL,
          top_n INTEGER NOT NULL,
          history_fingerprint TEXT NOT NULL,
          source TEXT NOT NULL,
          base_value NUMERIC(12,6) NOT NULL,
          close_value NUMERIC(12,6) NOT NULL,
          issue_low_value NUMERIC(12,6) NOT NULL,
          issue_high_value NUMERIC(12,6) NOT NULL,
          rolling_low_value NUMERIC(12,6) NOT NULL,
          rolling_high_value NUMERIC(12,6) NOT NULL,
          rsv NUMERIC(12,6) NOT NULL,
          k_value NUMERIC(12,6) NOT NULL,
          d_value NUMERIC(12,6) NOT NULL,
          j_value NUMERIC(12,6) NOT NULL,
          recommended_offset NUMERIC(12,6) NOT NULL,
          best_objective_score NUMERIC(14,6) NOT NULL,
          objective_delta NUMERIC(14,6) NOT NULL,
          sample_count INTEGER NOT NULL,
          probe_results JSONB NOT NULL DEFAULT '[]'::jsonb,
          advisor_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (signal_run_id, issue, weight_name)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_training_weight_signals_weight_issue
          ON training_weight_signals (weight_name, issue)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_training_weight_signals_run_issue
          ON training_weight_signals (signal_run_id, issue)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_training_weight_signals_run_weight_issue
          ON training_weight_signals (signal_run_id, weight_name, issue)
        """
    )


def upsert_training_weight_signal(conn: Connection, signal: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO training_weight_signals (
          signal_run_id, issue, draw_date, weight_name, train_mode, train_window, eval_window, top_n,
          history_fingerprint, source, base_value, close_value, issue_low_value, issue_high_value,
          rolling_low_value, rolling_high_value, rsv, k_value, d_value, j_value, recommended_offset,
          best_objective_score, objective_delta, sample_count, probe_results, advisor_metadata
        )
        VALUES (
          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
          %s::jsonb, %s::jsonb
        )
        ON CONFLICT (signal_run_id, issue, weight_name) DO UPDATE
        SET draw_date = EXCLUDED.draw_date,
            train_mode = EXCLUDED.train_mode,
            train_window = EXCLUDED.train_window,
            eval_window = EXCLUDED.eval_window,
            top_n = EXCLUDED.top_n,
            history_fingerprint = EXCLUDED.history_fingerprint,
            source = EXCLUDED.source,
            base_value = EXCLUDED.base_value,
            close_value = EXCLUDED.close_value,
            issue_low_value = EXCLUDED.issue_low_value,
            issue_high_value = EXCLUDED.issue_high_value,
            rolling_low_value = EXCLUDED.rolling_low_value,
            rolling_high_value = EXCLUDED.rolling_high_value,
            rsv = EXCLUDED.rsv,
            k_value = EXCLUDED.k_value,
            d_value = EXCLUDED.d_value,
            j_value = EXCLUDED.j_value,
            recommended_offset = EXCLUDED.recommended_offset,
            best_objective_score = EXCLUDED.best_objective_score,
            objective_delta = EXCLUDED.objective_delta,
            sample_count = EXCLUDED.sample_count,
            probe_results = EXCLUDED.probe_results,
            advisor_metadata = EXCLUDED.advisor_metadata,
            updated_at = now()
        """,
        (
            signal["signal_run_id"],
            signal["issue"],
            signal.get("draw_date"),
            signal["weight_name"],
            signal["train_mode"],
            int(signal["train_window"]),
            int(signal["eval_window"]),
            int(signal["top_n"]),
            signal["history_fingerprint"],
            signal["source"],
            float(signal["base_value"]),
            float(signal["close_value"]),
            float(signal["issue_low_value"]),
            float(signal["issue_high_value"]),
            float(signal["rolling_low_value"]),
            float(signal["rolling_high_value"]),
            float(signal["rsv"]),
            float(signal["k_value"]),
            float(signal["d_value"]),
            float(signal["j_value"]),
            float(signal["recommended_offset"]),
            float(signal["best_objective_score"]),
            float(signal["objective_delta"]),
            int(signal["sample_count"]),
            json.dumps(signal.get("probe_results") or []),
            json.dumps(signal.get("advisor_metadata") or {}),
        ),
    )


def load_recent_training_weight_signals(
    conn: Connection,
    *,
    signal_run_id: str | None = None,
    as_of_issue: str | None = None,
    train_mode: str | None = None,
    train_window: int | None = None,
    top_n: int | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    exists = conn.execute("SELECT to_regclass('public.training_weight_signals')").fetchone()
    if not exists or not exists[0]:
        return []
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            WITH eligible_signals AS (
              SELECT *
              FROM training_weight_signals
              WHERE (%s::text IS NULL OR issue <= %s::text)
                AND (%s::text IS NULL OR train_mode = %s::text)
                AND (%s::integer IS NULL OR train_window = %s::integer)
                AND (%s::integer IS NULL OR top_n = %s::integer)
            ),
            selected_run AS (
              SELECT COALESCE(
                %s::text,
                (
                  SELECT signal_run_id
                  FROM eligible_signals
                  WHERE signal_run_id = %s::text
                  LIMIT 1
                ),
                (
                  SELECT signal_run_id
                  FROM eligible_signals
                  ORDER BY created_at DESC, issue DESC
                  LIMIT 1
                )
              ) AS signal_run_id
            ),
            ranked_points AS (
              SELECT s.*,
                     row_number() OVER (PARTITION BY s.weight_name ORDER BY s.issue DESC) AS row_number
              FROM eligible_signals s
              JOIN selected_run r ON r.signal_run_id = s.signal_run_id
              WHERE r.signal_run_id IS NOT NULL
            )
            SELECT signal_run_id, issue, draw_date, weight_name, train_mode, train_window, eval_window, top_n,
                   base_value, close_value, rsv, k_value, d_value, j_value, recommended_offset, objective_delta,
                   best_objective_score, sample_count, source
            FROM ranked_points
            WHERE row_number <= %s
            ORDER BY weight_name ASC, issue ASC
            """,
            (
                as_of_issue,
                as_of_issue,
                train_mode,
                train_mode,
                train_window,
                train_window,
                top_n,
                top_n,
                signal_run_id,
                CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,
                limit,
            ),
        ).fetchall()
    return [dict(row) for row in rows]


def has_training_weight_signal_run(conn: Connection, *, signal_run_id: str) -> bool:
    exists = conn.execute("SELECT to_regclass('public.training_weight_signals')").fetchone()
    if not exists or not exists[0]:
        return False
    row = conn.execute(
        """
        SELECT 1
        FROM training_weight_signals
        WHERE signal_run_id = %s
        LIMIT 1
        """,
        (signal_run_id,),
    ).fetchone()
    return bool(row)


def load_training_weight_signal_coverage(
    conn: Connection,
    *,
    signal_run_id: str,
    issues: tuple[str, ...],
    weights: tuple[str, ...],
) -> dict[str, set[str]]:
    if not issues or not weights:
        return {}
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT issue, weight_name
            FROM training_weight_signals
            WHERE signal_run_id = %s
              AND issue = ANY(%s::text[])
              AND weight_name = ANY(%s::text[])
            ORDER BY issue ASC, weight_name ASC
            """,
            (signal_run_id, list(issues), list(weights)),
        ).fetchall()
    coverage: dict[str, set[str]] = {}
    for row in rows:
        coverage.setdefault(str(row["issue"]), set()).add(str(row["weight_name"]))
    return coverage


def load_training_weight_signal_rows(
    conn: Connection,
    *,
    signal_run_id: str,
    issues: tuple[str, ...],
    weights: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not issues or not weights:
        return []
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT issue, weight_name, issue_low_value, issue_high_value,
                   rsv, k_value, d_value, j_value
            FROM training_weight_signals
            WHERE signal_run_id = %s
              AND issue = ANY(%s::text[])
              AND weight_name = ANY(%s::text[])
            ORDER BY issue ASC, weight_name ASC
            """,
            (signal_run_id, list(issues), list(weights)),
        ).fetchall()
    return [dict(row) for row in rows]


def load_training_weight_signal_tail(
    conn: Connection,
    *,
    signal_run_id: str,
    before_issue: str,
    weights: tuple[str, ...],
    limit_per_weight: int,
) -> list[dict[str, Any]]:
    if not weights or limit_per_weight < 1:
        return []
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            WITH ranked AS (
              SELECT issue, weight_name, issue_low_value, issue_high_value,
                     rsv, k_value, d_value, j_value,
                     row_number() OVER (PARTITION BY weight_name ORDER BY issue DESC) AS row_number
              FROM training_weight_signals
              WHERE signal_run_id = %s
                AND issue < %s
                AND weight_name = ANY(%s::text[])
            )
            SELECT issue, weight_name, issue_low_value, issue_high_value,
                   rsv, k_value, d_value, j_value
            FROM ranked
            WHERE row_number <= %s
            ORDER BY issue ASC, weight_name ASC
            """,
            (signal_run_id, before_issue, list(weights), limit_per_weight),
        ).fetchall()
    return [dict(row) for row in rows]


def prune_stale_training_weight_signals(
    conn: Connection,
    *,
    signal_run_id: str,
    keep_issues: tuple[str, ...],
) -> int:
    if signal_run_id != CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID:
        return 0
    row = conn.execute(
        """
        WITH deleted AS (
          DELETE FROM training_weight_signals
          WHERE signal_run_id = %s
            AND NOT (issue = ANY(%s::text[]))
          RETURNING 1
        )
        SELECT count(*) FROM deleted
        """,
        (signal_run_id, list(keep_issues)),
    ).fetchone()
    return int(row[0]) if row else 0


def upsert_training_round_result(conn: Connection, *, run_id: str, round_info: dict[str, Any], status: dict[str, Any]) -> None:
    best = round_info.get("best") if isinstance(round_info.get("best"), dict) else {}
    red5 = best.get("red5") if isinstance(best.get("red5"), dict) else {}
    reward = best.get("reward") if isinstance(best.get("reward"), dict) else {}
    conn.execute(
        """
        INSERT INTO training_round_results (
          run_id, round_index, phase, step, train_mode, train_window, eval_window, top_n,
          as_of_issue, history_fingerprint, improved, top_100_hits, top_1000_hits, top_10000_hits,
          red5_top_100_hits, red5_top_1000_hits, red5_top_10000_hits, median_rank, best_rank,
          worst_rank, objective_score, best_config, best_summary, top_results, target_results, prefilter
        )
        VALUES (
          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
          %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb
        )
        ON CONFLICT (run_id, round_index) DO UPDATE
        SET phase = EXCLUDED.phase,
            step = EXCLUDED.step,
            train_mode = EXCLUDED.train_mode,
            train_window = EXCLUDED.train_window,
            eval_window = EXCLUDED.eval_window,
            top_n = EXCLUDED.top_n,
            as_of_issue = EXCLUDED.as_of_issue,
            history_fingerprint = EXCLUDED.history_fingerprint,
            improved = EXCLUDED.improved,
            top_100_hits = EXCLUDED.top_100_hits,
            top_1000_hits = EXCLUDED.top_1000_hits,
            top_10000_hits = EXCLUDED.top_10000_hits,
            red5_top_100_hits = EXCLUDED.red5_top_100_hits,
            red5_top_1000_hits = EXCLUDED.red5_top_1000_hits,
            red5_top_10000_hits = EXCLUDED.red5_top_10000_hits,
            median_rank = EXCLUDED.median_rank,
            best_rank = EXCLUDED.best_rank,
            worst_rank = EXCLUDED.worst_rank,
            objective_score = EXCLUDED.objective_score,
            best_config = EXCLUDED.best_config,
            best_summary = EXCLUDED.best_summary,
            top_results = EXCLUDED.top_results,
            target_results = EXCLUDED.target_results,
            prefilter = EXCLUDED.prefilter,
            updated_at = now()
        """,
        (
            run_id,
            int(round_info["round"]),
            str(round_info["phase"]),
            float(round_info["step"]),
            str(status["train_mode"]),
            int(status["train_window"]),
            int(status["eval_window"]),
            int(status["top_n"]),
            str(best.get("as_of_issue") or status.get("as_of_issue") or ""),
            str(best.get("history_fingerprint") or ""),
            bool(round_info.get("improved")),
            int(best.get("top_100_hits") or 0),
            int(best.get("top_1000_hits") or 0),
            int(best.get("top_10000_hits") or 0),
            int(red5.get("top_100_hits") or 0),
            int(red5.get("top_1000_hits") or 0),
            int(red5.get("top_10000_hits") or 0),
            best.get("median_rank"),
            best.get("best_rank"),
            best.get("worst_rank"),
            reward.get("objectiveScore"),
            json.dumps(best.get("config") or {}),
            json.dumps(best),
            json.dumps(round_info.get("top_results") or []),
            json.dumps(best.get("target_results") or []),
            json.dumps(round_info.get("prefilter") or {}),
        ),
    )


def load_training_round_candidate_summaries(
    conn: Connection,
    *,
    as_of_issue: str,
    history_fingerprint: str,
    train_window: int,
    train_mode: str,
    eval_window: int,
    top_n: int,
    limit: int = 80,
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT best_summary, top_results
            FROM training_round_results
            WHERE as_of_issue = %s
              AND history_fingerprint = %s
              AND train_window = %s
              AND train_mode = %s
              AND eval_window = %s
              AND top_n = %s
            ORDER BY objective_score DESC NULLS LAST, updated_at DESC
            LIMIT %s
            """,
            (as_of_issue, history_fingerprint, train_window, train_mode, eval_window, top_n, limit),
        ).fetchall()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        best_summary = row.get("best_summary")
        if isinstance(best_summary, dict):
            candidates.append(best_summary)
        top_results = row.get("top_results")
        if isinstance(top_results, list):
            candidates.extend(item for item in top_results if isinstance(item, dict))
    return candidates


def upsert_ssq_draw_site(conn: Connection, site: SsqDrawSite = DEFAULT_SSQ_DRAW_SITE) -> None:
    conn.execute(
        """
        INSERT INTO ssq_draw_sites (
          site_key, name, address, latitude, longitude, coordinate_system, accuracy_note,
          address_source_url, draw_location_source_url, effective_from_issue, effective_to_issue, is_active
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (site_key) DO UPDATE
        SET name = EXCLUDED.name,
            address = EXCLUDED.address,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            coordinate_system = EXCLUDED.coordinate_system,
            accuracy_note = EXCLUDED.accuracy_note,
            address_source_url = EXCLUDED.address_source_url,
            draw_location_source_url = EXCLUDED.draw_location_source_url,
            effective_from_issue = EXCLUDED.effective_from_issue,
            effective_to_issue = EXCLUDED.effective_to_issue,
            is_active = EXCLUDED.is_active,
            updated_at = now()
        """,
        (
            site.site_key,
            site.name,
            site.address,
            site.latitude,
            site.longitude,
            site.coordinate_system,
            site.accuracy_note,
            site.address_source_url,
            site.draw_location_source_url,
            site.effective_from_issue,
            site.effective_to_issue,
            site.is_active,
        ),
    )


def load_active_ssq_draw_site(conn: Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            """
            SELECT
              site_key, name, address, latitude, longitude, coordinate_system, accuracy_note,
              address_source_url, draw_location_source_url, effective_from_issue, effective_to_issue, is_active
            FROM ssq_draw_sites
            WHERE is_active = true
            ORDER BY site_key
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    site = dict(row)
    site["latitude"] = float(site["latitude"])
    site["longitude"] = float(site["longitude"])
    return site


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
