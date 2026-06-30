from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

import dehps.optimization.next_candidates as next_candidates
from dehps.optimization.next_candidates import (
    build_training_next_candidate_snapshot,
    load_best_training_summary,
    next_issue_hint,
    training_freshness_metadata,
    training_summary_sort_key,
)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def execute(self, sql, params=None):
        self.conn.queries.append((sql, params))
        return self

    def fetchone(self):
        return self.conn.row


class FakeConn:
    def __init__(self, row):
        self.row = row
        self.queries = []

    def cursor(self, row_factory=None):
        self.row_factory = row_factory
        return FakeCursor(self)


def test_next_issue_hint_increments_numeric_issue():
    assert next_issue_hint("2026068") == "2026069"
    assert next_issue_hint("bad") == ""


def test_load_best_training_summary_prefers_supervisor_best_checkpoint(monkeypatch):
    checkpoint_row = {
        "run_id": "run-1",
        "round_index": 9,
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "as_of_issue": "2026073",
        "history_fingerprint": "history-current",
        "history_scope": "current_regime_default",
        "regime_years": 10,
        "regime_start_date": date(2016, 6, 28),
        "best_summary": {
            "config_hash": "checkpoint-best",
            "config": {"structural_weight": 0.7, "frequency_weight": 0.8, "omission_weight": 0.05},
            "top_100_hits": 3,
            "top_1000_hits": 3,
            "top_10000_hits": 3,
        },
        "best_config": {"frequency_weight": 0.1},
    }
    conn = FakeConn(checkpoint_row)
    monkeypatch.setattr(next_candidates, "ensure_training_supervisor_best_schema", lambda _conn: None)

    best = load_best_training_summary(conn)

    assert best is not None
    assert best["source_round_index"] == 9
    assert best["training_regime_start_date"] == "2016-06-28"
    assert best["summary"]["config_hash"] == "checkpoint-best"
    assert best["config"]["frequency_weight"] == 0.8
    assert len(conn.queries) == 1
    assert "FROM training_supervisor_best" in conn.queries[0][0]


def test_training_freshness_metadata_marks_stale_history():
    metadata = training_freshness_metadata(
        training_as_of_issue="2026067",
        latest_issue="2026069",
        training_history_fingerprint="history-old",
        current_history_fingerprint="history-current",
    )

    assert metadata == {
        "status": "stale",
        "training_issue_matches_current": False,
        "training_history_matches_current": False,
        "training_issue_lag": 2,
    }


def test_training_next_candidate_snapshot_rejects_nonpositive_top_n():
    with pytest.raises(ValueError, match="top_n must be at least 1"):
        build_training_next_candidate_snapshot(object(), top_n=0)


def test_training_next_candidate_snapshot_reports_training_freshness(monkeypatch):
    history = [
        ("2026067", None, (1, 2, 3, 4, 5, 6)),
        ("2026068", None, (2, 3, 4, 5, 6, 7)),
    ]
    best = {
        "run_id": "run-1",
        "source_round_index": 5,
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "training_as_of_issue": "2026067",
        "training_history_fingerprint": "history-old",
        "summary": {},
        "config": {},
    }
    monkeypatch.setattr(next_candidates, "load_best_training_summary", lambda _conn, _run_id: best)
    monkeypatch.setattr(next_candidates, "load_history_with_dates", lambda _conn: history)
    monkeypatch.setattr(
        next_candidates,
        "top_candidates_for_next",
        lambda **_kwargs: [(1, (1, 2, 3, 4, 5, 6), 0.75)],
    )

    snapshot = build_training_next_candidate_snapshot(object(), top_n=10, ranked_universe=[object(), object()])

    metadata = snapshot["metadata"]
    assert metadata["history_fingerprint"] == next_candidates.fingerprint_history(history)
    assert metadata["freshness_mode"] == "legacy_full_history"
    assert metadata["training_freshness"] == {
        "status": "stale",
        "training_issue_matches_current": False,
        "training_history_matches_current": False,
        "training_issue_lag": 1,
    }


def test_training_next_candidate_snapshot_uses_training_regime_for_freshness(monkeypatch):
    history = [
        ("2026067", date(2026, 6, 20), (1, 2, 3, 4, 5, 6)),
        ("2026068", date(2026, 6, 22), (2, 3, 4, 5, 6, 7)),
    ]
    best = {
        "run_id": "run-1",
        "source_round_index": 5,
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "training_as_of_issue": "2026068",
        "training_history_fingerprint": next_candidates.fingerprint_history(history),
        "history_scope": "current_regime_default",
        "regime_years": 10,
        "training_regime_start_date": "2016-06-22",
        "summary": {},
        "config": {},
    }
    seen = {}
    selection = SimpleNamespace(
        dated_history=history,
        scope="current_regime_default",
        regime_years=10,
        start_date=date(2016, 6, 22),
    )
    monkeypatch.setattr(next_candidates, "load_best_training_summary", lambda _conn, _run_id: best)
    monkeypatch.setattr(next_candidates, "select_history", lambda *_args, **_kwargs: selection)

    def fake_top_candidates_for_next(**kwargs):
        seen["history"] = kwargs["history"]
        return [(1, (1, 2, 3, 4, 5, 6), 0.75)]

    monkeypatch.setattr(next_candidates, "top_candidates_for_next", fake_top_candidates_for_next)

    snapshot = build_training_next_candidate_snapshot(object(), top_n=10, ranked_universe=[object(), object()])

    metadata = snapshot["metadata"]
    assert seen["history"] == history
    assert metadata["freshness_mode"] == "training_scope"
    assert metadata["history_scope"] == "current_regime_default"
    assert metadata["regime_start_date"] == "2016-06-22"
    assert metadata["training_freshness"] == {
        "status": "current",
        "training_issue_matches_current": True,
        "training_history_matches_current": True,
        "training_issue_lag": 0,
    }


def test_training_next_candidate_snapshot_marks_regime_fingerprint_mismatch_stale(monkeypatch):
    history = [
        ("2026068", date(2026, 6, 22), (2, 3, 4, 5, 6, 7)),
    ]
    best = {
        "run_id": "run-1",
        "source_round_index": 5,
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "training_as_of_issue": "2026068",
        "training_history_fingerprint": "old-regime-fingerprint",
        "history_scope": "current_regime_default",
        "regime_years": 10,
        "summary": {},
        "config": {},
    }
    selection = SimpleNamespace(
        dated_history=history,
        scope="current_regime_default",
        regime_years=10,
        start_date=date(2016, 6, 22),
    )
    monkeypatch.setattr(next_candidates, "load_best_training_summary", lambda _conn, _run_id: best)
    monkeypatch.setattr(next_candidates, "select_history", lambda *_args, **_kwargs: selection)
    monkeypatch.setattr(
        next_candidates,
        "top_candidates_for_next",
        lambda **_kwargs: [(1, (1, 2, 3, 4, 5, 6), 0.75)],
    )

    snapshot = build_training_next_candidate_snapshot(object(), top_n=10, ranked_universe=[object(), object()])

    assert snapshot["metadata"]["training_freshness"] == {
        "status": "stale",
        "training_issue_matches_current": True,
        "training_history_matches_current": False,
        "training_issue_lag": 0,
    }


def test_training_summary_sort_key_prefers_historical_hits_before_reward():
    stronger_hits = {
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "reward": {"objectiveScore": 1},
        "rank_quality": {},
        "red5": {},
    }
    stronger_reward = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 3,
        "reward": {"objectiveScore": 99},
        "rank_quality": {},
        "red5": {},
    }

    assert training_summary_sort_key(stronger_hits) > training_summary_sort_key(stronger_reward)


def test_training_summary_sort_key_prefers_unique_baseline_hits_with_same_top10000():
    unique_hits = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 3,
        "reward": {"objectiveScore": 12},
        "rank_quality": {},
        "red5": {},
        "baseline_overlap": {
            "bands": {
                "top_1000": {"unique_hit_count": 0},
                "top_10000": {"unique_hit_count": 3, "overlap_hit_count": 0},
            }
        },
    }
    overlapped_hits = {
        **unique_hits,
        "reward": {"objectiveScore": 3},
        "baseline_overlap": {
            "bands": {
                "top_1000": {"unique_hit_count": 0},
                "top_10000": {"unique_hit_count": 0, "overlap_hit_count": 3},
            }
        },
    }

    assert training_summary_sort_key(unique_hits) > training_summary_sort_key(overlapped_hits)
