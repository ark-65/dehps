from __future__ import annotations

from decimal import Decimal

import pytest

from dehps.storage.postgres_store import DEFAULT_SSQ_DRAW_SITE
from dehps.storage.postgres_store import load_training_round_candidate_summaries
from dehps.storage.postgres_store import load_red_combination_universe
from dehps.storage.postgres_store import upsert_training_round_result
from dehps.storage.postgres_store import upsert_ssq_draw_site


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        return FakeResult(self.rows)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        return FakeResult(self.conn.rows)


class FakeCursorConn(FakeConn):
    def cursor(self, row_factory=None):
        self.row_factory = row_factory
        return FakeCursor(self)


def test_load_red_combination_universe_rejects_incomplete_table():
    with pytest.raises(ValueError, match="full C\\(33,6\\) universe"):
        load_red_combination_universe(FakeConn([([1, 2, 3, 4, 5, 6],)]))


def test_default_ssq_draw_site_is_sourced_approximate_wgs84_coordinate():
    assert DEFAULT_SSQ_DRAW_SITE.site_key == "cwl_beijing_n4ring_v0"
    assert DEFAULT_SSQ_DRAW_SITE.coordinate_system == "WGS84"
    assert DEFAULT_SSQ_DRAW_SITE.latitude == Decimal("39.990000")
    assert DEFAULT_SSQ_DRAW_SITE.longitude == Decimal("116.430000")
    assert DEFAULT_SSQ_DRAW_SITE.address_source_url.startswith("https://www.cwl.gov.cn/")
    assert DEFAULT_SSQ_DRAW_SITE.draw_location_source_url.startswith("https://www.thepaper.cn/")
    assert "survey-grade" in DEFAULT_SSQ_DRAW_SITE.accuracy_note


def test_upsert_ssq_draw_site_uses_stable_conflict_key():
    conn = FakeConn([])

    upsert_ssq_draw_site(conn, DEFAULT_SSQ_DRAW_SITE)

    sql, params = conn.executed[-1]
    assert "ON CONFLICT (site_key) DO UPDATE" in sql
    assert params[0] == "cwl_beijing_n4ring_v0"
    assert params[3] == DEFAULT_SSQ_DRAW_SITE.latitude
    assert params[4] == DEFAULT_SSQ_DRAW_SITE.longitude


def test_upsert_training_round_result_uses_run_round_conflict_key():
    conn = FakeConn([])
    best = {
        "as_of_issue": "2026067",
        "history_fingerprint": "history-1",
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 12345.5,
        "best_rank": 88,
        "worst_rank": 900000,
        "config": {"frequency_weight": 0.4},
        "reward": {"objectiveScore": 29.5},
        "red5": {"top_100_hits": 2, "top_1000_hits": 4, "top_10000_hits": 6},
        "target_results": [{"issue": "2026001", "red_numbers": [1, 2, 3, 4, 5, 6]}],
    }

    upsert_training_round_result(
        conn,
        run_id="run-1",
        round_info={
            "round": 1,
            "phase": "micro",
            "step": 0.01,
            "improved": True,
            "best": best,
            "top_results": [best],
            "prefilter": {"target_count": 25},
        },
        status={"train_mode": "expanding", "train_window": 900, "eval_window": 100, "top_n": 10000},
    )

    sql, params = conn.executed[-1]
    assert "ON CONFLICT (run_id, round_index) DO UPDATE" in sql
    assert params[:4] == ("run-1", 1, "micro", 0.01)
    assert params[10] is True
    assert '"frequency_weight": 0.4' in params[-5]
    assert '"target_count": 25' in params[-1]


def test_load_training_round_candidate_summaries_returns_best_and_top_results():
    conn = FakeCursorConn(
        [
            {
                "best_summary": {"config_hash": "best-1"},
                "top_results": [{"config_hash": "top-1"}, "skip-me"],
            },
            {
                "best_summary": None,
                "top_results": [{"config_hash": "top-2"}],
            },
        ]
    )

    candidates = load_training_round_candidate_summaries(
        conn,
        as_of_issue="2026067",
        history_fingerprint="history-1",
        train_window=900,
        train_mode="expanding",
        eval_window=100,
        top_n=10000,
        limit=12,
    )

    sql, params = conn.executed[-1]
    assert "FROM training_round_results" in sql
    assert "ORDER BY objective_score DESC NULLS LAST" in sql
    assert params == ("2026067", "history-1", 900, "expanding", 100, 10000, 12)
    assert [candidate.get("config_hash") for candidate in candidates] == ["best-1", "top-1", "top-2"]
