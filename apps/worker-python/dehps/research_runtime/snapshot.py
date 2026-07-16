from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from psycopg import Connection

from dehps.db import get_connection
from dehps.input_contracts import HistorySnapshotArtifact
from dehps.research_runtime.models import (
    ROUND30_SCHEMA_VERSION,
    HistorySnapshot,
    SnapshotRotationDecision,
    stable_hash,
)


ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]


class HistorySnapshotManager:
    """Create immutable research snapshots from the current history table."""

    def __init__(self, connection_factory: ConnectionFactory = get_connection) -> None:
        self.connection_factory = connection_factory

    def current(self) -> HistorySnapshot:
        """Return the legacy runtime summary without changing historical fingerprints."""

        rows = self._load_history()
        latest_issue = rows[-1][0] if rows else None
        fingerprint = stable_hash(
            {
                "schema": ROUND30_SCHEMA_VERSION,
                "history": rows,
            }
        )
        key = f"history-snapshot-{latest_issue or 'empty'}-{fingerprint[:16]}"
        return HistorySnapshot(
            snapshot_key=key,
            latest_issue=latest_issue,
            issue_count=len(rows),
            history_fingerprint=fingerprint,
        )

    def contract_current(self) -> HistorySnapshotArtifact:
        """Materialize the opt-in v1 scoring history artifact.

        This does not replace ``current`` yet: existing runtime fingerprints and
        persisted production evidence remain byte-for-byte compatible.
        """

        return HistorySnapshotArtifact.from_history(
            self._load_contract_history(),
            source="ssq_history",
        )

    def rotation_decision(
        self,
        *,
        active_snapshot: HistorySnapshot | None,
        cycle_running: bool,
    ) -> SnapshotRotationDecision:
        candidate = self.current()
        if active_snapshot is None:
            return SnapshotRotationDecision(
                rotate=True,
                reason_code="no_active_snapshot",
                active_snapshot_key=None,
                candidate_snapshot_key=candidate.snapshot_key,
                active_latest_issue=None,
                candidate_latest_issue=candidate.latest_issue,
                defer_until_cycle_complete=False,
            )
        changed = active_snapshot.history_fingerprint != candidate.history_fingerprint
        return SnapshotRotationDecision(
            rotate=changed and not cycle_running,
            reason_code=(
                "snapshot_changed_defer_until_cycle_complete"
                if changed and cycle_running
                else "snapshot_changed_rotate_next_cycle"
                if changed
                else "snapshot_unchanged"
            ),
            active_snapshot_key=active_snapshot.snapshot_key,
            candidate_snapshot_key=candidate.snapshot_key,
            active_latest_issue=active_snapshot.latest_issue,
            candidate_latest_issue=candidate.latest_issue,
            defer_until_cycle_complete=changed and cycle_running,
        )

    def _load_history(self) -> tuple[tuple[str, tuple[int, ...]], ...]:
        with self.connection_factory() as conn:
            rows = conn.execute("SELECT issue, red_numbers FROM ssq_history ORDER BY issue").fetchall()
        return tuple((str(row[0]), tuple(int(number) for number in row[1])) for row in rows)

    def _load_contract_history(self) -> tuple[tuple[str, object, tuple[int, ...]], ...]:
        with self.connection_factory() as conn:
            rows = conn.execute(
                "SELECT issue, draw_date, red_numbers FROM ssq_history ORDER BY issue"
            ).fetchall()
        return tuple(
            (str(row[0]), row[1], tuple(int(number) for number in row[2]))
            for row in rows
        )
