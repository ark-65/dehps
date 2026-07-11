from __future__ import annotations

import json
from datetime import datetime, timezone

from dehps.db import get_connection
from dehps.runtime.remote_sync_schedule import ssq_remote_sync_poll_plan


def main() -> None:
    with get_connection() as conn:
        table = conn.execute("SELECT to_regclass('public.ssq_sync_runs')").fetchone()
        row = (
            conn.execute(
                """
                SELECT status, started_at
                FROM ssq_sync_runs
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            if table and table[0]
            else None
        )
    plan = ssq_remote_sync_poll_plan(
        now=datetime.now(timezone.utc),
        last_status=str(row[0]) if row else None,
        last_attempt_at=row[1] if row else None,
    )
    print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
    if plan.get("due") is not True:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
