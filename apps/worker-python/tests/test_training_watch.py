from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import scripts.watch_training_progress as watch
from scripts.watch_training_progress import (
    advisor_summary,
    gate_summary,
    recommendation_summary,
    render_markdown,
    safe_float,
    safe_filename_component,
    safe_int,
    summarize_watch,
)


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


def test_gate_summary_surfaces_frozen_primary_blockers_in_recommendation_and_markdown():
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    prefilter = {
        "promotion_gate": {
            "passed": False,
            "reason": "frozen_validation_not_better",
            "tail_passed": True,
            "objective_passed": False,
            "primary_hit_passed": False,
            "candidate_primary_score": [0, 0, 0],
            "incumbent_primary_score": [0, 0, 0],
        },
        "eval_slice_overfit_guardrail": {
            "active": True,
            "reason": "eval_slice_overfit_no_frozen_primary_lift",
            "force_primary_gate": True,
            "rank_homogeneity_active": True,
            "rank_homogeneity_unique_signature_count": 1,
            "round_best_eval_primary_score": [3, 3, 3],
            "round_best_frozen_primary_score": [0, 0, 0],
            "incumbent_frozen_primary_score": [0, 0, 0],
            "suspicious_candidate_count": 4,
            "issue_counts": {"2026025": 4},
            "source_counts": {"unknown": 3, "stagnation_restart": 1},
        },
        "stale_round_best_search_base_gate": {
            "active": True,
            "reason": "eval_slice_overfit_no_frozen_primary_lift",
            "require_frozen_primary_challenger": True,
            "allow_unpromoted_round_best": False,
            "threshold": 64,
        },
        "rank_homogeneity_guardrail": {
            "active": True,
            "reason": "stale_rank_signature_cycle",
            "window": 12,
            "observed": 12,
            "unique_signature_count": 1,
            "max_unique_signatures": 4,
        },
        "decision_round_best": {
            "source": "incumbent",
            "reason": "incumbent_due_to_required_frozen_primary_lift",
            "frozen_primary_lift_required": True,
            "selected_frozen_primary_score": [0, 0, 0],
            "frozen_primary_lift_baseline_score": [0, 0, 0],
            "blocked_candidates": [{"source": "rank_homogeneity_restart"}],
        },
    }

    gates = gate_summary(prefilter)
    recommendation = recommendation_summary(
        rows=[
            {
                "round_index": index,
                "improved": False,
                "updated_at": now - timedelta(minutes=2),
            }
            for index in range(1, 35)
        ],
        lock={"active": True, "owner": "training-supervisor"},
        advisors={"neural_kdj_advisor": {"candidate_count": 0}},
        gates=gates,
        now=now,
        stale_minutes=30,
    )
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 34,
        "latest_round": 34,
        "last_improved_round": None,
        "stagnation_rounds": 34,
        "latest_metrics": {
            "phase": "large",
            "step": 0.15,
            "improved": False,
            "top_100_hits": 3,
            "top_1000_hits": 3,
            "top_10000_hits": 3,
            "red5_top_10000_hits": 28,
            "best_rank": 39,
            "median_rank": 557702,
            "worst_rank": 1079121,
            "objective_score": 5085.35383,
            "best_objective_seen": 5085.35383,
        },
        "advisor_summary": {},
        "gate_summary": gates,
        "heavy_job_lock": {"active": True},
        "recommendation": recommendation,
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert gates["promotion_gate"]["reason"] == "frozen_validation_not_better"
    assert gates["eval_slice_overfit_guardrail"]["round_best_eval_primary_score"] == [3, 3, 3]
    assert gates["decision_round_best"]["blocked_candidate_count"] == 1
    assert any("Promotion gate blocked" in note for note in recommendation["notes"])
    assert any("Eval-slice overfit guardrail is active" in note for note in recommendation["notes"])
    assert any("sources=unknown=3, stagnation_restart=1" in note for note in recommendation["notes"])
    assert any("issues=2026025=4" in note for note in recommendation["notes"])
    assert "## Gate Snapshot" in markdown
    assert "frozen_primary=[0, 0, 0]" in markdown
    assert "sources=unknown=3, stagnation_restart=1" in markdown
    assert "issues=2026025=4" in markdown
    assert "blocked_sources=[rank_homogeneity_restart]" in markdown


def test_render_markdown_escapes_untrusted_inline_text():
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run`id\nwith-line",
        "round_count": 1,
        "latest_round": 1,
        "last_improved_round": None,
        "stagnation_rounds": 1,
        "latest_metrics": {
            "phase": "micro|phase\nretry",
            "step": 0.01,
            "improved": False,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": 0,
            "red5_top_10000_hits": 0,
            "best_rank": None,
            "median_rank": None,
            "worst_rank": None,
            "objective_score": None,
            "best_objective_seen": None,
        },
        "advisor_summary": {
            "custom|advisor": {
                "candidate_count": 1,
                "selected_count": 1,
                "rejected_count": 0,
                "selected_fields": ["weight|field", "line\nfield"],
            }
        },
        "heavy_job_lock": {},
        "recommendation": {
            "severity": "warn",
            "action": "inspect|log",
            "notes": ["first line\nsecond line | detail"],
        },
        "guardrail": "Historical response-surface monitoring only.",
    }

    markdown = render_markdown(payload)

    assert "- Run id: ``run`id with-line``" in markdown
    assert "- Phase/step: micro\\|phase retry / 0.01" in markdown
    assert "| custom\\|advisor | 1 | 1 | 0 | weight\\|field, line field |" in markdown
    assert "- first line second line \\| detail" in markdown
    assert "first line\nsecond line" not in markdown


def test_write_outputs_sanitizes_run_id_filename(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "utc_stamp", lambda: "20260618-100000")
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": " ../run:bad/..//escape ",
        "round_count": 0,
        "latest_round": None,
        "last_improved_round": None,
        "stagnation_rounds": 0,
        "latest_metrics": {},
        "advisor_summary": {},
        "heavy_job_lock": {},
        "recommendation": {"severity": "ok", "action": "continue_current_run", "notes": []},
        "guardrail": "Historical response-surface monitoring only.",
    }

    json_path, md_path = watch.write_outputs(payload, tmp_path)

    assert safe_filename_component(payload["run_id"]) == "run_bad_escape"
    assert safe_filename_component(None) == "none"
    assert safe_filename_component(" / ") == "none"
    assert safe_filename_component(0) == "0"
    assert json_path == tmp_path / "training-watch-run_bad_escape-20260618-100000.json"
    assert md_path == tmp_path / "training-watch-run_bad_escape-20260618-100000.md"
    assert (tmp_path / "training-watch-latest.json").exists()
    assert (tmp_path / "training-watch-latest.md").exists()


def test_write_outputs_uses_atomic_writer(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "utc_stamp", lambda: "20260618-100000")
    writes = []

    def fake_atomic_write_text(path, text):
        writes.append((path.name, text))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    monkeypatch.setattr(watch, "atomic_write_text", fake_atomic_write_text)
    payload = {
        "generated_at": "2026-06-18T10:00:00Z",
        "run_id": "run-1",
        "round_count": 0,
        "latest_round": None,
        "last_improved_round": None,
        "stagnation_rounds": 0,
        "latest_metrics": {},
        "advisor_summary": {},
        "heavy_job_lock": {},
        "recommendation": {"severity": "ok", "action": "continue_current_run", "notes": []},
        "guardrail": "Historical response-surface monitoring only.",
    }

    watch.write_outputs(payload, tmp_path)

    assert [name for name, _ in writes] == [
        "training-watch-run-1-20260618-100000.json",
        "training-watch-run-1-20260618-100000.md",
        "training-watch-latest.json",
        "training-watch-latest.md",
    ]


def test_safe_filename_component_bounds_long_run_ids():
    first = safe_filename_component("run-" + ("a" * 240), max_length=48)
    second = safe_filename_component("run-" + ("b" * 240), max_length=48)

    assert len(first) == 48
    assert len(second) == 48
    assert first.startswith("run")
    assert second.startswith("run")
    assert first != second


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
        captured["rounds_run_id"] = run_id
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

    def fake_load_round_stats(run_id):
        captured["stats_run_id"] = run_id
        return {
            "round_count": 1,
            "latest_round": 1,
            "last_improved_round": None,
            "stagnation_rounds": 1,
            "improvement_count": 0,
            "best_objective_seen": 1.0,
        }

    monkeypatch.setattr(watch, "utc_now", lambda: now)
    monkeypatch.setattr(watch, "resolve_run_id", lambda run_id: "run-1")
    monkeypatch.setattr(watch, "load_rounds", fake_load_rounds)
    monkeypatch.setattr(watch, "load_round_stats", fake_load_round_stats)
    monkeypatch.setattr(watch, "heavy_lock_summary", lambda: {"active": True, "owner": "training-supervisor"})

    payload = summarize_watch(None, limit=0, stale_minutes=-10)

    assert captured == {
        "rounds_run_id": "run-1",
        "stats_run_id": "run-1",
        "limit": watch.DEFAULT_ROUND_LIMIT,
    }
    assert payload["round_limit"] == watch.DEFAULT_ROUND_LIMIT
    assert payload["stale_minutes"] == watch.DEFAULT_STALE_MINUTES
    assert payload["recommendation"]["severity"] == "ok"


def test_summarize_watch_uses_full_stats_beyond_recent_limit(monkeypatch):
    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    captured = {}

    def fake_load_rounds(run_id, *, limit):
        captured["rounds"] = (run_id, limit)
        return [
            {
                "round_index": 11,
                "improved": False,
                "updated_at": now - timedelta(minutes=2),
                "objective_score": 1.0,
                "prefilter": {},
            },
            {
                "round_index": 12,
                "improved": False,
                "updated_at": now - timedelta(minutes=1),
                "objective_score": 2.0,
                "prefilter": {},
            },
        ]

    def fake_load_round_stats(run_id):
        captured["stats"] = run_id
        return {
            "round_count": 12,
            "latest_round": 12,
            "last_improved_round": 10,
            "stagnation_rounds": 2,
            "improvement_count": 4,
            "best_objective_seen": 99.0,
        }

    monkeypatch.setattr(watch, "utc_now", lambda: now)
    monkeypatch.setattr(watch, "resolve_run_id", lambda run_id: "run-1")
    monkeypatch.setattr(watch, "load_rounds", fake_load_rounds)
    monkeypatch.setattr(watch, "load_round_stats", fake_load_round_stats)
    monkeypatch.setattr(watch, "heavy_lock_summary", lambda: {"active": True, "owner": "training-supervisor"})

    payload = summarize_watch("input-run", limit=2, stale_minutes=30)

    assert captured == {"rounds": ("run-1", 2), "stats": "run-1"}
    assert payload["round_count"] == 12
    assert payload["round_window_count"] == 2
    assert payload["last_improved_round"] == 10
    assert payload["stagnation_rounds"] == 2
    assert payload["latest_metrics"]["best_objective_seen"] == 99.0
    assert payload["recommendation"]["severity"] == "ok"


def test_safe_numeric_helpers_reject_bool_and_non_finite_values():
    assert safe_float("3.5") == 3.5
    assert safe_float(True) is None
    assert safe_float("nan") is None
    assert safe_float(float("inf")) is None

    assert safe_int("3") == 3
    assert safe_int(" 003 ") == 3
    assert safe_int(3.0) == 3
    assert safe_int(3.5) is None
    assert safe_int(False) is None
    assert safe_int(float("inf")) is None


def test_safe_int_rejects_non_decimal_string_forms():
    for value in ("+3", "-1", "1_000", "0x10", "1e3", "3.0", "", "\uff13"):
        assert safe_int(value) is None


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
