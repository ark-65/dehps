from __future__ import annotations

import dehps.optimization.next_candidates as next_candidates
from dehps.optimization.next_candidates import (
    build_training_next_candidate_snapshot,
    next_issue_hint,
    training_freshness_metadata,
    training_summary_sort_key,
)


def test_next_issue_hint_increments_numeric_issue():
    assert next_issue_hint("2026068") == "2026069"
    assert next_issue_hint("bad") == ""


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
    assert metadata["training_freshness"] == {
        "status": "stale",
        "training_issue_matches_current": False,
        "training_history_matches_current": False,
        "training_issue_lag": 1,
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
