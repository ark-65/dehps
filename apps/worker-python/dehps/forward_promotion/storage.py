from __future__ import annotations

import hashlib
import json
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.storage.postgres_store import upsert_training_supervisor_best


FORWARD_PROMOTION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS forward_promotion_cohorts (
  cohort_key TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('accumulating', 'invalid', 'rejected', 'promoted')),
  activation_issue TEXT NOT NULL,
  incumbent_config_hash TEXT NOT NULL,
  incumbent_config JSONB NOT NULL,
  incumbent_summary JSONB NOT NULL,
  challenger_config_hash TEXT NOT NULL,
  challenger_config JSONB NOT NULL,
  challenger_summary JSONB NOT NULL,
  source_run_id TEXT NOT NULL,
  source_round_index INTEGER NOT NULL,
  source_train_mode TEXT NOT NULL,
  source_train_window INTEGER NOT NULL,
  source_eval_window INTEGER NOT NULL,
  source_top_n INTEGER NOT NULL,
  source_history_scope TEXT NOT NULL DEFAULT '',
  source_regime_years INTEGER NOT NULL DEFAULT 0,
  source_regime_start_date DATE,
  historical_gate_passed BOOLEAN NOT NULL,
  min_paired_issues INTEGER NOT NULL DEFAULT 20,
  max_losing_streak INTEGER NOT NULL DEFAULT 3,
  paired_issue_count INTEGER NOT NULL DEFAULT 0,
  decision JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  decided_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_forward_promotion_one_accumulating
  ON forward_promotion_cohorts ((status)) WHERE status = 'accumulating';
CREATE TABLE IF NOT EXISTS forward_champion_state (
  champion_key TEXT PRIMARY KEY,
  cohort_key TEXT NOT NULL REFERENCES forward_promotion_cohorts(cohort_key) ON DELETE RESTRICT,
  config_hash TEXT NOT NULL,
  config JSONB NOT NULL,
  source_summary JSONB NOT NULL,
  promoted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def ensure_forward_promotion_schema(conn: Connection) -> None:
    conn.execute(FORWARD_PROMOTION_SCHEMA_SQL)


def load_active_forward_promotion_cohort(conn: Connection) -> dict[str, Any] | None:
    ensure_forward_promotion_schema(conn)
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "SELECT * FROM forward_promotion_cohorts WHERE status = 'accumulating' ORDER BY created_at LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def load_forward_champion(conn: Connection) -> dict[str, Any] | None:
    ensure_forward_promotion_schema(conn)
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "SELECT * FROM forward_champion_state WHERE champion_key = 'production'"
        ).fetchone()
    return dict(row) if row else None


def invalidate_active_forward_promotion_cohort(
    conn: Connection,
    *,
    cohort_key: str,
    reason: str,
) -> None:
    decision = {
        "protocol": "config_bound_forward_promotion_v1",
        "status": "invalid",
        "promote": False,
        "blockers": [reason],
    }
    conn.execute(
        """
        UPDATE forward_promotion_cohorts
        SET status = 'invalid', decision = %s::jsonb,
            decided_at = now(), updated_at = now()
        WHERE cohort_key = %s AND status = 'accumulating'
        """,
        (json.dumps(decision), cohort_key),
    )


def ensure_active_forward_promotion_cohort(
    conn: Connection,
    *,
    activation_issue: str,
) -> dict[str, Any] | None:
    active = load_active_forward_promotion_cohort(conn)
    if active is not None:
        return active
    champion = load_forward_champion(conn)
    with conn.cursor(row_factory=dict_row) as cur:
        incumbent = None
        if champion is None:
            incumbent = cur.execute(
                """
                SELECT config_hash, best_config AS config, best_summary AS summary
                FROM training_supervisor_best
                ORDER BY updated_at DESC LIMIT 1
                """
            ).fetchone()
        incumbent_hash = str((champion or incumbent or {}).get("config_hash") or "")
        incumbent_config = (champion or incumbent or {}).get("config") or {}
        incumbent_summary = (champion or incumbent or {}).get("source_summary") or (incumbent or {}).get("summary") or {}
        if not incumbent_hash or not incumbent_config or not incumbent_summary:
            return None
        challenger = cur.execute(
            """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   history_scope, regime_years, regime_start_date,
                   best_summary->>'config_hash' AS config_hash,
                   best_config AS config, best_summary AS summary
            FROM training_round_results
            WHERE prefilter->'promotion_gate'->>'pre_quarantine_passed' = 'true'
              AND best_summary->>'config_hash' <> %s
              AND prefilter->'promotion_gate'->>'incumbent_config_hash' = %s
              AND NOT EXISTS (
                    SELECT 1 FROM forward_promotion_cohorts prior
                    WHERE prior.challenger_config_hash = best_summary->>'config_hash'
                      AND prior.status IN ('invalid', 'rejected')
              )
            ORDER BY objective_score DESC NULLS LAST, created_at ASC
            LIMIT 1
            """,
            (incumbent_hash, incumbent_hash),
        ).fetchone()
        if not challenger:
            return None
        challenger_hash = str(challenger["config_hash"] or "")
        key_material = f"{activation_issue}|{incumbent_hash}|{challenger_hash}"
        cohort_key = "forward-promotion:" + hashlib.sha256(key_material.encode()).hexdigest()[:24]
        row = cur.execute(
            """
            INSERT INTO forward_promotion_cohorts (
              cohort_key, status, activation_issue,
              incumbent_config_hash, incumbent_config, incumbent_summary,
              challenger_config_hash, challenger_config, challenger_summary,
              source_run_id, source_round_index,
              source_train_mode, source_train_window, source_eval_window, source_top_n,
              source_history_scope, source_regime_years, source_regime_start_date,
              historical_gate_passed
            ) VALUES (%s, 'accumulating', %s, %s, %s::jsonb, %s::jsonb,
                      %s, %s::jsonb, %s::jsonb, %s, %s,
                      %s, %s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (cohort_key) DO NOTHING
            RETURNING *
            """,
            (
                cohort_key,
                activation_issue,
                incumbent_hash,
                json.dumps(incumbent_config),
                json.dumps(incumbent_summary),
                challenger_hash,
                json.dumps(challenger["config"]),
                json.dumps(challenger["summary"]),
                challenger["run_id"],
                int(challenger["round_index"]),
                challenger["train_mode"],
                int(challenger["train_window"]),
                int(challenger["eval_window"]),
                int(challenger["top_n"]),
                challenger.get("history_scope") or "",
                int(challenger.get("regime_years") or 0),
                challenger.get("regime_start_date"),
            ),
        ).fetchone()
    return dict(row) if row else load_active_forward_promotion_cohort(conn)


def load_forward_promotion_pairs(conn: Connection, cohort: dict[str, Any]) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT e.line_key, e.predicted_issue AS target_issue, e.status,
                   e.candidate_count, e.red5_rank, e.summary,
                   r.config_hash, r.top_n, r.as_of_issue
            FROM training_prediction_evaluations e
            JOIN forward_prediction_runs r USING (prediction_run_key)
            WHERE e.predicted_issue >= %s
              AND e.line_key IN ('static_100', 'forward_challenger')
            ORDER BY e.predicted_issue, e.line_key
            """,
            (cohort["activation_issue"],),
        ).fetchall()
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for raw in rows:
        row = dict(raw)
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        audit = summary.get("ranking_audit") if isinstance(summary.get("ranking_audit"), dict) else {}
        normalized = {
            "target_issue": str(row["target_issue"]),
            "status": row["status"],
            "candidate_count": int(row.get("candidate_count") or 0),
            "top_n": int(row.get("top_n") or 0),
            "config_hash": str(row.get("config_hash") or ""),
            "leakage_passed": summary.get("leakage_passed") is True,
            "model_rank": int(audit["model_score_rank"]) if isinstance(audit.get("model_score_rank"), int | float) else None,
            "red5_rank": int(row["red5_rank"]) if isinstance(row.get("red5_rank"), int | float) else None,
            "as_of_issue": str(row.get("as_of_issue") or ""),
        }
        grouped.setdefault(str(row["target_issue"]), {}).setdefault(str(row["line_key"]), []).append(normalized)
    pairs = []
    for issue, lines in sorted(grouped.items()):
        if "static_100" not in lines or "forward_challenger" not in lines:
            continue
        duplicates = sorted(line_key for line_key, values in lines.items() if len(values) != 1)
        pairs.append(
            {
                "target_issue": issue,
                "incumbent": lines["static_100"][0],
                "challenger": lines["forward_challenger"][0],
                "duplicate_line_keys": duplicates,
            }
        )
    return pairs


def persist_forward_promotion_decision(
    conn: Connection,
    *,
    cohort: dict[str, Any],
    decision: dict[str, Any],
) -> None:
    terminal = decision.get("status") in {"invalid", "rejected", "promoted"}
    updated = conn.execute(
        """
        UPDATE forward_promotion_cohorts
        SET status = %s, paired_issue_count = %s, decision = %s::jsonb,
            decided_at = CASE WHEN %s THEN now() ELSE decided_at END,
            updated_at = now()
        WHERE cohort_key = %s AND status = 'accumulating'
        """,
        (
            decision["status"],
            int(decision.get("paired_issue_count") or 0),
            json.dumps(decision),
            terminal,
            cohort["cohort_key"],
        ),
    )
    if not decision.get("promote") or updated.rowcount != 1:
        return
    conn.execute(
        """
        INSERT INTO forward_champion_state (
          champion_key, cohort_key, config_hash, config, source_summary
        ) VALUES ('production', %s, %s, %s::jsonb, %s::jsonb)
        ON CONFLICT (champion_key) DO UPDATE
        SET cohort_key = EXCLUDED.cohort_key,
            config_hash = EXCLUDED.config_hash,
            config = EXCLUDED.config,
            source_summary = EXCLUDED.source_summary,
            promoted_at = now(), updated_at = now()
        """,
        (
            cohort["cohort_key"],
            cohort["challenger_config_hash"],
            json.dumps(cohort["challenger_config"]),
            json.dumps(cohort["challenger_summary"]),
        ),
    )
    summary = dict(cohort["challenger_summary"])
    summary["forward_promotion"] = decision
    upsert_training_supervisor_best(
        conn,
        run_id=f"forward-promotion:{cohort['cohort_key']}",
        round_index=0,
        best_summary=summary,
        status={
            "train_mode": cohort["source_train_mode"],
            "train_window": cohort["source_train_window"],
            "eval_window": cohort["source_eval_window"],
            "top_n": cohort["source_top_n"],
            "as_of_issue": summary.get("as_of_issue") or "",
            "history_scope": cohort.get("source_history_scope") or "",
            "regime_years": cohort.get("source_regime_years") or 0,
            "regime_start_date": cohort.get("source_regime_start_date"),
        },
    )
