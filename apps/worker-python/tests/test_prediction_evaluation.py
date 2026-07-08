from __future__ import annotations

from dehps.optimization.prediction_evaluation import (
    build_prediction_evaluation,
    evaluate_prediction_candidates,
    render_prediction_evaluation_report,
)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rows = []
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def execute(self, sql, params=None):
        self.conn.queries.append((sql, params))
        if "FROM ssq_history" in sql and "WHERE issue" in sql:
            self.row = self.conn.actual_draw
            self.rows = []
        elif "FROM training_next_candidates_current" in sql and "WHERE next_issue" in sql:
            issue = params[0]
            self.rows = self.conn.prediction_rows if issue == self.conn.prediction_issue else []
            self.row = None
        elif "FROM training_next_candidates_current" in sql:
            self.row = self.conn.current_prediction_row
            self.rows = []
        else:
            self.row = None
            self.rows = []
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, *, actual_draw=None, prediction_issue="2026002", prediction_rows=None, current_prediction_row=None):
        self.actual_draw = actual_draw
        self.prediction_issue = prediction_issue
        self.prediction_rows = prediction_rows or []
        self.current_prediction_row = current_prediction_row
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append((sql, params))
        return FakeResult([])

    def cursor(self, row_factory=None):
        self.row_factory = row_factory
        return FakeCursor(self)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


def prediction_row(rank, red_numbers, *, next_issue="2026002", as_of_issue="2026001"):
    return {
        "snapshot_key": "training-next-2026001-test",
        "run_id": "run-1",
        "source_round_index": 2,
        "as_of_issue": as_of_issue,
        "next_issue": next_issue,
        "next_draw_date": "2026-01-03",
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "history_fingerprint": "history-1",
        "config_hash": "config-1",
        "config": {},
        "rank": rank,
        "red_numbers": red_numbers,
        "score": 0.9,
        "generated_at": "2026-01-01T00:00:00Z",
    }


def test_evaluate_prediction_candidates_reports_exact_hit_bands():
    result = evaluate_prediction_candidates(
        [1, 2, 3, 4, 5, 6],
        [
            {"rank": 1, "red_numbers": [1, 2, 3, 4, 5, 6], "score": 0.9},
            {"rank": 101, "red_numbers": [1, 2, 3, 4, 5, 7], "score": 0.8},
        ],
    )

    assert result["exact_red6"]["rank"] == 1
    assert result["exact_red6"]["hit_top_100"] is True
    assert result["exact_red6"]["hit_top_10000"] is True
    assert result["red5"]["rank"] == 101
    assert result["red5_or_better"]["rank"] == 1
    assert result["red_overlap"]["best_overlap"] == 6


def test_evaluate_prediction_candidates_reports_red5_near_miss():
    result = evaluate_prediction_candidates(
        [1, 2, 3, 4, 5, 6],
        [
            {"rank": 3, "red_numbers": [8, 9, 10, 11, 12, 13], "score": 0.9},
            {"rank": 42, "red_numbers": [1, 2, 3, 4, 5, 7], "score": 0.8},
        ],
    )

    assert result["exact_red6"]["rank"] is None
    assert result["red5"]["rank"] == 42
    assert result["red5"]["hit_top_100"] is True
    assert result["red5_or_better"]["rank"] == 42
    assert result["red_overlap"]["best_overlap"] == 5


def test_build_prediction_evaluation_blocks_same_issue_snapshot():
    conn = FakeConn(
        actual_draw={
            "issue": "2026002",
            "draw_date": "2026-01-03",
            "red_numbers": [1, 2, 3, 4, 5, 6],
            "blue_number": 7,
            "source": "zhcw",
        },
        prediction_rows=[prediction_row(1, [1, 2, 3, 4, 5, 6], as_of_issue="2026002")],
    )

    payload = build_prediction_evaluation(conn, issue="2026002")

    assert payload["status"] == "leakage_guard_failed"
    assert payload["evaluable"] is False
    assert payload["result"] is None


def test_build_prediction_evaluation_marks_snapshot_mismatch():
    current_row = prediction_row(1, [1, 2, 3, 4, 5, 6], next_issue="2026003")
    conn = FakeConn(
        actual_draw={
            "issue": "2026002",
            "draw_date": "2026-01-03",
            "red_numbers": [1, 2, 3, 4, 5, 6],
            "blue_number": 7,
            "source": "zhcw",
        },
        prediction_issue="2026003",
        prediction_rows=[current_row],
        current_prediction_row=current_row,
    )

    payload = build_prediction_evaluation(conn, issue="2026002")

    assert payload["status"] == "prediction_snapshot_mismatch"
    assert payload["prediction_snapshot"]["metadata"]["next_issue"] == "2026003"


def test_render_prediction_evaluation_report_includes_hit_summary():
    result = evaluate_prediction_candidates(
        [1, 2, 3, 4, 5, 6],
        [{"rank": 1, "red_numbers": [1, 2, 3, 4, 5, 6], "score": 0.9}],
    )
    report = render_prediction_evaluation_report(
        {
            "issue": "2026002",
            "status": "evaluated",
            "evaluable": True,
            "evaluated_at": "2026-01-03T14:00:00Z",
            "actual_draw": {
                "issue": "2026002",
                "draw_date": "2026-01-03",
                "red_numbers": [1, 2, 3, 4, 5, 6],
                "blue_number": 7,
                "source": "zhcw",
            },
            "prediction_snapshot": {
                "status": "loaded",
                "metadata": {"snapshot_key": "training-next-2026001-test", "as_of_issue": "2026001"},
                "candidate_count": 1,
            },
            "result": result,
            "warnings": [],
        }
    )

    assert "Exact red6 rank: #1" in report
    assert "Red5 first rank: not in snapshot" in report
    assert "Red5-or-better first rank: #1" in report
