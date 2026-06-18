from __future__ import annotations

from dehps.optimization.next_candidates import next_issue_hint, training_summary_sort_key


def test_next_issue_hint_increments_numeric_issue():
    assert next_issue_hint("2026068") == "2026069"
    assert next_issue_hint("bad") == ""


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
