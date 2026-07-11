from __future__ import annotations

from contextlib import nullcontext

import scripts.plan_synced_prediction_evaluations as planner


class FakeResult:
    def __init__(self, *, one=None, rows=None):
        self.one = one
        self.rows = rows or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, *, table_exists: bool = True):
        self.table_exists = table_exists
        self.issues = []

    def execute(self, query, params=None):
        if "to_regclass" in query:
            return FakeResult(
                one=(
                    "training_prediction_evaluations"
                    if self.table_exists
                    else None,
                )
            )
        self.issues.append(params[0])
        return FakeResult(
            rows=[
                (
                    "static_100",
                    params[0],
                    "snapshot-static",
                    "evaluated",
                    10000,
                    {"leakage_passed": True},
                )
            ]
        )


def test_load_accepted_evaluations_preserves_exact_acceptance_fields(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(planner, "get_connection", lambda: nullcontext(conn))

    rows = planner.load_accepted_evaluations(
        [
            {
                "line_key": "static_100",
                "next_issue": "2026079",
            }
        ]
    )

    assert conn.issues == ["2026079"]
    assert rows == [
        {
            "line_key": "static_100",
            "predicted_issue": "2026079",
            "snapshot_key": "snapshot-static",
            "status": "evaluated",
            "candidate_count": 10000,
            "summary": {"leakage_passed": True},
        }
    ]


def test_load_accepted_evaluations_handles_missing_table(monkeypatch):
    conn = FakeConnection(table_exists=False)
    monkeypatch.setattr(planner, "get_connection", lambda: nullcontext(conn))

    assert planner.load_accepted_evaluations([]) == []
    assert conn.issues == []
