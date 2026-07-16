from __future__ import annotations

import json

from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.storage.postgres_store import (
    ensure_forward_prediction_evaluation_schema,
    ensure_training_next_candidates_current_schema,
)


def main() -> None:
    with get_connection() as conn:
        ensure_training_next_candidates_current_schema(conn)
        ensure_forward_prediction_evaluation_schema(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            summary = cur.execute(
                """
                SELECT
                  (SELECT count(*)::int FROM forward_prediction_runs) AS prediction_run_count,
                  (SELECT count(*)::int FROM forward_prediction_runs
                   WHERE ranking_contract IS NULL) AS legacy_prediction_run_count,
                  (SELECT count(*)::int FROM forward_prediction_runs
                   WHERE ranking_contract IS NOT NULL) AS explicit_prediction_run_count,
                  (SELECT count(*)::int FROM forward_prediction_candidates) AS candidate_count,
                  (SELECT count(*)::int FROM forward_evaluation_runs) AS evaluation_run_count
                """
            ).fetchone()
    print(
        json.dumps(
            {
                "status": "ranking_contract_provenance_schema_ready",
                "historical_backfill_performed": False,
                **dict(summary or {}),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
