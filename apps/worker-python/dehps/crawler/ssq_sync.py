from __future__ import annotations

from datetime import datetime
from typing import Any

from dehps.crawler.ssq_client import get_data_source
from dehps.crawler.ssq_parser import validate_ssq_draw
from dehps.db import get_connection
from dehps.storage.postgres_store import create_sync_run, finish_sync_run, upsert_ssq_draw


def sync_ssq(
    source: str,
    *,
    history: bool = False,
    from_issue: str | None = None,
    to_issue: str | None = None,
    csv_file: str | None = None,
    dry_run: bool = False,
    run_key: str | None = None,
) -> dict[str, Any]:
    run_key = run_key or f"sync-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    data_source = get_data_source(source, csv_file=csv_file)
    raw_draws = data_source.fetch_history(from_issue, to_issue) if history else [data_source.fetch_latest()]
    raw_draws = [draw for draw in raw_draws if draw]
    validated = sorted((validate_ssq_draw(draw) for draw in raw_draws), key=lambda draw: draw.issue)

    summary: dict[str, Any] = {
        "run_key": run_key,
        "source": source,
        "fetched_count": len(raw_draws),
        "inserted_count": 0,
        "updated_count": 0,
        "skipped_count": 0,
        "conflict_count": 0,
        "dry_run": dry_run,
        "latest_draw": max(validated, key=lambda draw: draw.issue).model_dump(mode="json") if validated else None,
    }
    if dry_run:
        summary["status"] = "dry_run"
        return summary

    with get_connection() as conn:
        create_sync_run(conn, run_key, source)
        try:
            for draw in validated:
                result = upsert_ssq_draw(conn, draw, source)
                summary[f"{result}_count"] = summary.get(f"{result}_count", 0) + 1
            summary["status"] = "success"
            finish_sync_run(conn, run_key, "success", summary)
        except Exception as exc:
            summary["status"] = "failed"
            summary["error_message"] = str(exc)
            finish_sync_run(conn, run_key, "failed", summary)
            raise
    return summary
