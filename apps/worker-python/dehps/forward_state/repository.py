from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.draw_sync.audit import DrawDatabaseAuditor
from dehps.forward_state.models import WaitingSupervisorState
from dehps.runtime.heavy_job import describe_heavy_job_owner, is_pid_active
from dehps.storage.postgres_store import ensure_draw_sync_schema


ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]
DEFAULT_TRAINING_WATCH_LATEST = ROOT_DIR / "data/output/optimization/training-watch/training-watch-latest.json"


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


class ForwardStateRepository:
    def __init__(
        self,
        connection_factory: ConnectionFactory = get_connection,
        *,
        watch_latest_path: Path = DEFAULT_TRAINING_WATCH_LATEST,
    ) -> None:
        self.connection_factory = connection_factory
        self.watch_latest_path = watch_latest_path
        self.auditor = DrawDatabaseAuditor()

    def ensure_schema(self) -> None:
        with self.connection_factory() as conn:
            ensure_draw_sync_schema(conn)

    def latest_issue(self) -> str | None:
        with self.connection_factory() as conn:
            row = conn.execute("SELECT max(issue) FROM ssq_history").fetchone()
        return str(row[0]) if row and row[0] is not None else None

    def current_history_fingerprint(self) -> str | None:
        with self.connection_factory() as conn:
            rows = conn.execute(
                "SELECT issue, red_numbers, blue_number FROM ssq_history ORDER BY issue"
            ).fetchall()
        report = self.auditor.audit(tuple((str(row[0]), tuple(row[1]), row[2]) for row in rows))
        return report.history_fingerprint if report.passed else None

    def waiting_supervisor_state(self) -> WaitingSupervisorState:
        try:
            payload = json.loads(self.watch_latest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        supervisor = payload.get("supervisor_status") if isinstance(payload.get("supervisor_status"), dict) else {}
        forward_wait = payload.get("forward_wait") if isinstance(payload.get("forward_wait"), dict) else {}
        pid = _safe_int(supervisor.get("pid"))
        status = str(supervisor.get("status") or payload.get("status") or "")
        return WaitingSupervisorState(
            status=status,
            old_run_id=str(supervisor.get("run_id") or payload.get("run_id") or "") or None,
            history_latest_issue=str(forward_wait.get("history_latest_issue") or "") or None,
            pending_issue=str(forward_wait.get("next_pending_issue") or "") or None,
            pid=pid,
            process_active=bool(pid and is_pid_active(pid)),
            history_fingerprint=None,
            source=payload,
        )

    def event_by_key(self, event_key: str) -> dict[str, Any] | None:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute("SELECT * FROM draw_issue_events WHERE event_key = %s", (event_key,)).fetchone()
        return dict(row) if row else None

    def latest_pending_event(self) -> dict[str, Any] | None:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                SELECT * FROM draw_issue_events
                WHERE status IN ('pending', 'failed')
                ORDER BY created_at, id
                LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None

    def consumed_forward_count(self) -> int:
        with self.connection_factory() as conn:
            row = conn.execute(
                "SELECT count(*) FROM draw_issue_events WHERE status = 'consumed'"
            ).fetchone()
        return int(row[0] if row else 0)

    def heavy_job_active(self) -> bool:
        return describe_heavy_job_owner().active

    def current_main_allowed(self) -> bool:
        if os.getenv("DEHPS_TRAINING_RESUME_ALLOW_CURRENT_REF") == "1":
            return True
        allowed = {
            item.strip()
            for item in os.getenv("DEHPS_TRAINING_RESUME_ALLOWED_REFS", "main,master").split(",")
            if item.strip()
        }
        try:
            current = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=ROOT_DIR,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return False
        return current in allowed
