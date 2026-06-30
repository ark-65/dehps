from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.models.frequency_ranker import FrequencyRankerConfig, infer_next_ssq_draw_date
from dehps.optimization.regime import select_history
from dehps.optimization.walk_forward import (
    build_ranked_universe,
    config_hash,
    fingerprint_history,
    top_candidates_for_next,
)
from dehps.storage.postgres_store import (
    ensure_training_supervisor_best_schema,
    load_history_with_dates,
    replace_training_next_candidates_current,
)


def next_issue_hint(issue: str | None) -> str:
    if not issue or not issue.isdigit():
        return ""
    return str(int(issue) + 1)


def training_freshness_metadata(
    *,
    training_as_of_issue: str | None,
    latest_issue: str | None,
    training_history_fingerprint: str | None,
    current_history_fingerprint: str | None,
) -> dict[str, Any]:
    training_issue = str(training_as_of_issue or "")
    current_issue = str(latest_issue or "")
    issue_lag: int | None = None
    if training_issue.isdigit() and current_issue.isdigit():
        issue_lag = int(current_issue) - int(training_issue)
    issue_matches = bool(training_issue and current_issue and training_issue == current_issue)
    history_matches = bool(
        training_history_fingerprint
        and current_history_fingerprint
        and training_history_fingerprint == current_history_fingerprint
    )
    return {
        "status": "current" if issue_matches and history_matches else "stale",
        "training_issue_matches_current": issue_matches,
        "training_history_matches_current": history_matches,
        "training_issue_lag": issue_lag,
    }


def training_summary_sort_key(summary: dict[str, Any]) -> tuple:
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    reward = summary.get("reward") if isinstance(summary.get("reward"), dict) else {}
    rank_quality = summary.get("rank_quality") if isinstance(summary.get("rank_quality"), dict) else {}
    baseline_overlap = summary.get("baseline_overlap") if isinstance(summary.get("baseline_overlap"), dict) else {}
    baseline_bands = baseline_overlap.get("bands") if isinstance(baseline_overlap.get("bands"), dict) else {}
    top_10000_overlap = baseline_bands.get("top_10000") if isinstance(baseline_bands.get("top_10000"), dict) else {}
    top_1000_overlap = baseline_bands.get("top_1000") if isinstance(baseline_bands.get("top_1000"), dict) else {}
    return (
        int(summary.get("top_100_hits") or 0),
        int(summary.get("top_1000_hits") or 0),
        int(top_1000_overlap.get("unique_hit_count") or 0),
        float(reward.get("objectiveScore") or 0),
        -int(rank_quality.get("tail_over_1000000_count") or 0),
        -int(rank_quality.get("tail_over_900000_count") or 0),
        -int(rank_quality.get("tail_over_750000_count") or 0),
        int(top_10000_overlap.get("unique_hit_count") or 0),
        -int(top_10000_overlap.get("overlap_hit_count") or 0),
        int(summary.get("top_10000_hits") or 0),
        int(rank_quality.get("top_50000_hits") or 0),
        int(rank_quality.get("top_100000_hits") or 0),
        int(rank_quality.get("top_250000_hits") or 0),
        int(rank_quality.get("top_500000_hits") or 0),
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


def training_best_candidate_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    summary = row.get("best_summary") if isinstance(row.get("best_summary"), dict) else {}
    config = summary.get("config") if isinstance(summary.get("config"), dict) else row.get("best_config")
    if not isinstance(config, dict) or not config:
        return None
    return {
        "run_id": str(row["run_id"]),
        "source_round_index": int(row["round_index"]),
        "train_mode": str(row["train_mode"]),
        "train_window": int(row["train_window"]),
        "eval_window": int(row["eval_window"]),
        "top_n": int(row["top_n"]),
        "training_as_of_issue": str(row["as_of_issue"]),
        "training_history_fingerprint": str(row["history_fingerprint"]),
        "history_scope": str(row.get("history_scope") or ""),
        "regime_years": int(row.get("regime_years") or 0),
        "training_regime_start_date": row.get("regime_start_date").isoformat()
        if row.get("regime_start_date")
        else "",
        "summary": summary,
        "config": {key: float(value) for key, value in config.items() if isinstance(value, int | float)},
    }


def load_training_supervisor_best_summary(conn: Connection, run_id: str | None = None) -> dict[str, Any] | None:
    ensure_training_supervisor_best_schema(conn)
    if run_id:
        query = """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   as_of_issue, history_fingerprint, history_scope, regime_years, regime_start_date,
                   best_summary, best_config, updated_at
            FROM training_supervisor_best
            WHERE run_id = %s
            ORDER BY round_index DESC, updated_at DESC
            LIMIT 1
        """
        params: tuple[Any, ...] = (run_id,)
    else:
        query = """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   as_of_issue, history_fingerprint, history_scope, regime_years, regime_start_date,
                   best_summary, best_config, updated_at
            FROM training_supervisor_best
            ORDER BY updated_at DESC
            LIMIT 1
        """
        params = ()
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(query, params).fetchone()
    if not row:
        return None
    return training_best_candidate_from_row(row)


def load_best_training_summary(conn: Connection, run_id: str | None = None) -> dict[str, Any] | None:
    checkpoint_best = load_training_supervisor_best_summary(conn, run_id)
    if checkpoint_best is not None:
        return checkpoint_best
    resolved_run_id = resolve_latest_training_run_id(conn, run_id)
    if not resolved_run_id:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   as_of_issue, history_fingerprint, history_scope, regime_years, regime_start_date,
                   best_summary, best_config, updated_at
            FROM training_round_results
            WHERE run_id = %s
            ORDER BY round_index ASC
            """,
            (resolved_run_id,),
        ).fetchall()
    best: dict[str, Any] | None = None
    for row in rows:
        candidate = training_best_candidate_from_row(row)
        if candidate is None:
            continue
        if best is None or training_summary_sort_key(candidate["summary"]) > training_summary_sort_key(best["summary"]):
            best = candidate
    return best


def load_current_history_for_training_scope(conn: Connection, best: dict[str, Any]) -> tuple[list, dict[str, Any]]:
    scope = str(best.get("history_scope") or "")
    regime_years = int(best.get("regime_years") or 0)
    if scope in {"full_history_audit", "current_regime_default"} and regime_years >= 1:
        selection = select_history(conn, scope=scope, regime_years=regime_years)
        return selection.dated_history, {
            "history_scope": selection.scope,
            "regime_years": selection.regime_years,
            "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
            "freshness_mode": "training_scope",
        }
    return load_history_with_dates(conn), {
        "history_scope": scope,
        "regime_years": regime_years,
        "regime_start_date": "",
        "freshness_mode": "legacy_full_history",
    }


def build_training_next_candidate_snapshot(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
) -> dict[str, Any]:
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    best = load_best_training_summary(conn, run_id)
    if best is None:
        raise RuntimeError("no training_round_results best config is available")
    history, history_context = load_current_history_for_training_scope(conn, best)
    if not history:
        raise RuntimeError("ssq_history is empty")
    latest_issue = str(history[-1][0])
    target_draw_date = infer_next_ssq_draw_date(history)
    current_history_fingerprint = fingerprint_history(history)
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
        "history_fingerprint": current_history_fingerprint,
        "training_as_of_issue": best["training_as_of_issue"],
        "training_history_fingerprint": best["training_history_fingerprint"],
        "history_scope": history_context["history_scope"],
        "regime_years": history_context["regime_years"],
        "regime_start_date": history_context["regime_start_date"],
        "training_regime_start_date": best.get("training_regime_start_date") or "",
        "freshness_mode": history_context["freshness_mode"],
        "training_freshness": training_freshness_metadata(
            training_as_of_issue=best["training_as_of_issue"],
            latest_issue=latest_issue,
            training_history_fingerprint=best["training_history_fingerprint"],
            current_history_fingerprint=current_history_fingerprint,
        ),
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
