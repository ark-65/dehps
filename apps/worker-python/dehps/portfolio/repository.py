from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.portfolio.models import ScoredCandidate, reject
from dehps.ranking_contract import with_effective_ranking_contract


@dataclass(frozen=True)
class LoadedPortfolioRun:
    candidates: tuple[ScoredCandidate, ...]
    candidate_pool: tuple[ScoredCandidate, ...]
    source: dict[str, Any]


def load_forward_prediction_portfolio(
    conn: Connection,
    *,
    prediction_run_key: str,
    budget: int,
    pool_limit: int,
) -> LoadedPortfolioRun:
    if not prediction_run_key.strip():
        reject("portfolio_prediction_run_key_missing", "prediction_run_key is required")
    if budget < 1:
        reject("portfolio_budget_invalid", "budget must be at least 1")
    if pool_limit < budget:
        reject("portfolio_pool_limit_invalid", "pool_limit must be at least budget")
    conn.execute("SET TRANSACTION READ ONLY")
    with conn.cursor(row_factory=dict_row) as cur:
        run = cur.execute(
            """
            SELECT prediction_run_key, line_key, line_label, line_kind,
                   source_run_id, source_round_index, as_of_issue, target_issue,
                   train_mode, train_window, top_n, candidate_count, config_hash,
                   prediction_fingerprint, ranking_contract, metadata, status, generated_at
            FROM forward_prediction_runs
            WHERE prediction_run_key = %s
            """,
            (prediction_run_key,),
        ).fetchone()
        if run is None:
            reject(
                "portfolio_prediction_run_missing",
                "durable prediction run does not exist",
                prediction_run_key=prediction_run_key,
            )
        rows = cur.execute(
            """
            SELECT rank, red_numbers, score
            FROM forward_prediction_candidates
            WHERE prediction_run_key = %s
              AND rank <= %s
            ORDER BY rank ASC
            """,
            (prediction_run_key, pool_limit),
        ).fetchall()
    if len(rows) < budget:
        reject(
            "portfolio_prediction_rows_insufficient",
            "durable prediction run has fewer rows than budget",
            prediction_run_key=prediction_run_key,
            row_count=len(rows),
            budget=budget,
        )
    actual_ranks = [int(row["rank"]) for row in rows]
    if actual_ranks != list(range(1, len(rows) + 1)):
        reject(
            "portfolio_prediction_rank_sequence_invalid",
            "durable candidate pool must contain consecutive source ranks from one",
            prediction_run_key=prediction_run_key,
        )
    pool = tuple(
        ScoredCandidate.build(
            source_rank=row["rank"],
            red_numbers=row["red_numbers"],
            score=row["score"],
        )
        for row in rows
    )
    run_payload = with_effective_ranking_contract(
        dict(run),
        output_field="effective_ranking_contract",
    )
    metadata = run_payload.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    source = {
        "source_kind": "durable_forward_prediction_run",
        "source_key": str(run_payload["prediction_run_key"]),
        "line_key": str(run_payload["line_key"]),
        "line_label": str(run_payload["line_label"]),
        "line_kind": str(run_payload["line_kind"]),
        "source_run_id": str(run_payload.get("source_run_id") or ""),
        "source_round_index": run_payload.get("source_round_index"),
        "as_of_issue": str(run_payload["as_of_issue"]),
        "target_issue": str(run_payload["target_issue"]),
        "prediction_status": str(run_payload["status"]),
        "snapshot_generated_at": run_payload["generated_at"].isoformat(),
        "history_digest": str(metadata.get("history_fingerprint") or ""),
        "score_config_digest": str(run_payload.get("config_hash") or ""),
        "prediction_fingerprint": str(run_payload.get("prediction_fingerprint") or ""),
        "scoring_contract": str(metadata.get("scoring_contract") or ""),
        "ranking_contract": str(run_payload.get("effective_ranking_contract") or ""),
        "source_code_commit": str(metadata.get("git_commit") or ""),
        "declared_candidate_count": int(run_payload["candidate_count"]),
        "loaded_candidate_pool_count": len(pool),
        "pool_limit": pool_limit,
    }
    return LoadedPortfolioRun(
        candidates=pool[:budget],
        candidate_pool=pool,
        source=source,
    )
