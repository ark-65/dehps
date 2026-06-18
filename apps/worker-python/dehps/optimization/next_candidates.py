from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.models.frequency_ranker import FrequencyRankerConfig, infer_next_ssq_draw_date
from dehps.optimization.walk_forward import (
    build_ranked_universe,
    config_hash,
    fingerprint_history,
    top_candidates_for_next,
)
from dehps.storage.postgres_store import (
    load_history_with_dates,
    replace_training_next_candidates_current,
)


def next_issue_hint(issue: str | None) -> str:
    if not issue or not issue.isdigit():
        return ""
    return str(int(issue) + 1)


def training_summary_sort_key(summary: dict[str, Any]) -> tuple:
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    reward = summary.get("reward") if isinstance(summary.get("reward"), dict) else {}
    rank_quality = summary.get("rank_quality") if isinstance(summary.get("rank_quality"), dict) else {}
    return (
        int(summary.get("top_100_hits") or 0),
        int(summary.get("top_1000_hits") or 0),
        int(summary.get("top_10000_hits") or 0),
        -int(rank_quality.get("tail_over_1000000_count") or 0),
        -int(rank_quality.get("tail_over_900000_count") or 0),
        -int(rank_quality.get("tail_over_750000_count") or 0),
        float(reward.get("objectiveScore") or 0),
        int(red5.get("top_100_hits") or 0),
        int(red5.get("top_1000_hits") or 0),
        int(red5.get("top_10000_hits") or 0),
        -float(summary.get("worst_rank") or 0),
        -float(summary.get("median_rank") or 0),
        -float(summary.get("best_rank") or 0),
    )


def resolve_latest_training_run_id(conn: Connection, run_id: str | None = None) -> str | None:
    if run_id:
        return run_id
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


def load_best_training_summary(conn: Connection, run_id: str | None = None) -> dict[str, Any] | None:
    resolved_run_id = resolve_latest_training_run_id(conn, run_id)
    if not resolved_run_id:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   as_of_issue, history_fingerprint, best_summary, best_config, updated_at
            FROM training_round_results
            WHERE run_id = %s
            ORDER BY round_index ASC
            """,
            (resolved_run_id,),
        ).fetchall()
    best: dict[str, Any] | None = None
    for row in rows:
        summary = row.get("best_summary") if isinstance(row.get("best_summary"), dict) else {}
        config = summary.get("config") if isinstance(summary.get("config"), dict) else row.get("best_config")
        if not isinstance(config, dict) or not config:
            continue
        candidate = {
            "run_id": str(row["run_id"]),
            "source_round_index": int(row["round_index"]),
            "train_mode": str(row["train_mode"]),
            "train_window": int(row["train_window"]),
            "eval_window": int(row["eval_window"]),
            "top_n": int(row["top_n"]),
            "training_as_of_issue": str(row["as_of_issue"]),
            "training_history_fingerprint": str(row["history_fingerprint"]),
            "summary": summary,
            "config": {key: float(value) for key, value in config.items() if isinstance(value, int | float)},
        }
        if best is None or training_summary_sort_key(candidate["summary"]) > training_summary_sort_key(best["summary"]):
            best = candidate
    return best


def build_training_next_candidate_snapshot(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
) -> dict[str, Any]:
    best = load_best_training_summary(conn, run_id)
    if best is None:
        raise RuntimeError("no training_round_results best config is available")
    history = load_history_with_dates(conn)
    if not history:
        raise RuntimeError("ssq_history is empty")
    latest_issue = str(history[-1][0])
    target_draw_date = infer_next_ssq_draw_date(history)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    config = FrequencyRankerConfig(**best["config"])
    matrix = ranked_universe or build_ranked_universe()
    resolved_top_n = min(top_n, len(matrix))
    candidates = top_candidates_for_next(
        history=history if best["train_mode"] == "expanding" else history[-best["train_window"] :],
        top_n=resolved_top_n,
        config=config,
        target_draw_date=target_draw_date,
        ranked_universe=matrix,
    )
    metadata = {
        "snapshot_key": f"training-next-{latest_issue}-{config_hash(config)[:12]}",
        "run_id": best["run_id"],
        "source_round_index": best["source_round_index"],
        "as_of_issue": latest_issue,
        "next_issue": next_issue_hint(latest_issue),
        "next_draw_date": target_draw_date.isoformat() if target_draw_date else None,
        "train_mode": best["train_mode"],
        "train_window": best["train_window"],
        "eval_window": best["eval_window"],
        "top_n": resolved_top_n,
        "history_fingerprint": fingerprint_history(history),
        "training_as_of_issue": best["training_as_of_issue"],
        "training_history_fingerprint": best["training_history_fingerprint"],
        "config_hash": config_hash(config),
        "config": best["config"],
        "generated_at": generated_at,
        "candidate_count": len(candidates),
    }
    return {"metadata": metadata, "candidates": candidates}


def refresh_training_next_candidates_current(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
) -> dict[str, Any]:
    snapshot = build_training_next_candidate_snapshot(conn, run_id=run_id, top_n=top_n, ranked_universe=ranked_universe)
    replace_training_next_candidates_current(
        conn,
        metadata=snapshot["metadata"],
        candidates=snapshot["candidates"],
    )
    return snapshot["metadata"]
