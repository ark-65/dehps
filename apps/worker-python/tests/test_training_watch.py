from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import scripts.watch_training_progress as watch
from scripts.watch_training_progress import advisor_summary, recommendation_summary, render_markdown, summarize_watch


def test_recommendation_continues_healthy_active_training_run():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    rows = [
        {
            "round_index": 1,
            "improved": True,
            "updated_at": now - timedelta(minutes=5),
        },
        {
            "round_index": 2,
            "improved": False,
            "updated_at": now - timedelta(minutes=1),
        },
    ]
    lock = {"active": True, "owner": "training-supervisor"}
    advisors = {
        "neural_kdj_advisor": {
            "candidate_count": 1,
            "top_advice": [{"confidence": 0.02}],
        },
        "ridge_kdj_advisor": {"candidate_count": 1},
    }

    recommendation = recommendation_summary(
        rows=rows,
        lock=lock,
        advisors=advisors,
        now=now,
        stale_minutes=30,
    )

    assert recommendation["severity"] == "ok"
    assert recommendation["action"] == "continue_current_run"
    assert any("confidence is low" in note for note in recommendation["notes"])
    assert any("Ridge advisor remains" in note for note in recommendation["notes"])


def test_recommendation_flags_high_stagnation_for_restart_preparation():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    rows = [
        {
            "round_index": index,
            "improved": index == 1,
            "updated_at": now - timedelta(minutes=2),
        }
        for index in range(1, 35)
    ]

    recommendation = recommendation_summary(
        rows=rows,
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        now=now,
        stale_minutes=30,
    )

    assert recommendation["severity"] == "alert"
    assert recommendation["action"] == "prepare_restart_with_more_exploration"
    assert "prepare_restart_with_more_exploration" in recommendation["actions"]


def test_advisor_summary_and_markdown_include_guardrails():
    prefilter = {
        "candidate_budget": {"neural_kdj": 1},
        "neural_kdj_advisor": {
            "enabled": True,
            "budget": 1,
            "candidate_count": 1,
            "selected_count": 1,
            "rejected_count": 2,
            "latest_signal_issue": "2026068",
            "selected_fields": ["consecutive_trend_weight"],
            "advice": [
                {
                    "weight_name": "consecutive_trend_weight",
                    "decision": "selected",
                    "suggested_offset": 0.02,
                    "confidence": 0.03,
                    "validation_metric": 0.01,
                    "baseline_metric": 0.02,
                }
            ],
        },
    }

    advisors = advisor_summary(prefilter)
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 2,
        "latest_round": 2,
        "last_improved_round": 1,
        "stagnation_rounds": 1,
        "latest_metrics": {
            "phase": "micro",
            "step": 0.01,
            "improved": False,
            "top_100_hits": 0,
            "top_1000_hits": 1,
            "top_10000_hits": 3,
            "red5_top_10000_hits": 12,
            "best_rank": 100,
            "median_rank": 1000,
            "worst_rank": 9000,
            "objective_score": 1.0,
            "best_objective_seen": 2.0,
        },
        "advisor_summary": advisors,
        "heavy_job_lock": {"active": True},
        "recommendation": {
            "severity": "ok",
            "action": "continue_current_run",
            "notes": ["Training process is active under the heavy-job lock."],
        },
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert advisors["neural_kdj_advisor"]["candidate_count"] == 1
    assert advisors["neural_kdj_advisor"]["top_advice"][0]["confidence"] == 0.03
    assert "Neural" not in markdown  # Machine-readable key is used in the table.
    assert "Historical response-surface monitoring only" in markdown


def test_heavy_lock_summary_reports_unreadable_metadata_error(monkeypatch):
    monkeypatch.setattr(
        watch,
        "describe_heavy_job_owner",
        lambda: SimpleNamespace(
            active=False,
            pid_active=None,
            reason="metadata_unreadable",
            error="Unable to read heavy-job metadata",
            metadata=None,
        ),
    )

    summary = watch.heavy_lock_summary()

    assert summary["active"] is False
    assert summary["reason"] == "metadata_unreadable"
    assert summary["error"] == "Unable to read heavy-job metadata"


def test_summarize_watch_normalizes_non_positive_windows(monkeypatch):
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    captured = {}

    def fake_load_rounds(run_id, *, limit):
        captured["run_id"] = run_id
        captured["limit"] = limit
        return [
            {
                "round_index": 1,
                "improved": False,
                "updated_at": now,
                "objective_score": 1.0,
                "prefilter": {},
            }
        ]

    monkeypatch.setattr(watch, "utc_now", lambda: now)
    monkeypatch.setattr(watch, "resolve_run_id", lambda run_id: "run-1")
    monkeypatch.setattr(watch, "load_rounds", fake_load_rounds)
    monkeypatch.setattr(watch, "heavy_lock_summary", lambda: {"active": True, "owner": "training-supervisor"})

    payload = summarize_watch(None, limit=0, stale_minutes=-10)

    assert captured == {"run_id": "run-1", "limit": watch.DEFAULT_ROUND_LIMIT}
    assert payload["round_limit"] == watch.DEFAULT_ROUND_LIMIT
    assert payload["stale_minutes"] == watch.DEFAULT_STALE_MINUTES
    assert payload["recommendation"]["severity"] == "ok"


def test_load_rounds_queries_recent_window_before_chronological_sort(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.sql = ""
            self.params = ()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params):
            self.sql = " ".join(sql.split())
            self.params = params
            return self

        def fetchall(self):
            return [{"round_index": 12}, {"round_index": 13}]

    class FakeConnection:
        def __init__(self, cursor):
            self.cursor_instance = cursor

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self, **_kwargs):
            return self.cursor_instance

    cursor = FakeCursor()
    monkeypatch.setattr(watch, "get_connection", lambda: FakeConnection(cursor))

    rows = watch.load_rounds("run-1", limit=2)

    assert rows == [{"round_index": 12}, {"round_index": 13}]
    assert cursor.params == ("run-1", 2)
    assert "ORDER BY round_index DESC LIMIT %s ) recent_rounds ORDER BY round_index ASC" in cursor.sql
