from dehps.crawler.ssq_parser import validate_ssq_draw
from dehps.storage.postgres_store import upsert_ssq_draw


class FakeConn:
    def __init__(self, existing=None):
        self.existing = existing
        self.conflicts = []
        self.inserted = []

    def execute(self, sql, params=None):
        if sql.strip().startswith("SELECT red_numbers"):
            return FakeResult(self.existing)
        if "INSERT INTO ssq_data_conflicts" in sql:
            self.conflicts.append(params)
            return FakeResult(None)
        if "INSERT INTO ssq_history" in sql:
            self.inserted.append(params)
            return FakeResult(None)
        return FakeResult(None)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value


def test_same_issue_same_data_skips_without_conflict():
    draw = validate_ssq_draw({"issue": "2026001", "red_numbers": [1, 2, 3, 4, 5, 6], "blue_number": 8})
    conn = FakeConn(existing=([1, 2, 3, 4, 5, 6], 8, "test"))
    assert upsert_ssq_draw(conn, draw, "test") == "skipped"
    assert conn.conflicts == []


def test_same_issue_different_data_records_conflict():
    draw = validate_ssq_draw({"issue": "2026001", "red_numbers": [1, 2, 3, 4, 5, 7], "blue_number": 8})
    conn = FakeConn(existing=([1, 2, 3, 4, 5, 6], 8, "test"))
    assert upsert_ssq_draw(conn, draw, "test") == "conflict"
    assert len(conn.conflicts) == 1


def test_zhcw_replaces_csv_sample_conflict():
    draw = validate_ssq_draw({"issue": "2026001", "red_numbers": [1, 2, 3, 4, 5, 7], "blue_number": 8})
    conn = FakeConn(existing=([1, 2, 3, 4, 5, 6], 8, "csv"))
    assert upsert_ssq_draw(conn, draw, "zhcw") == "updated"
    assert len(conn.conflicts) == 0
