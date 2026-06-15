from dehps.crawler.ssq_parser import validate_ssq_draw
from dehps.crawler.ssq_sync import sync_ssq
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


def test_history_dry_run_reports_latest_issue(monkeypatch):
    class FakeSource:
        def fetch_history(self, start_issue=None, end_issue=None):
            return [
                {"issue": "2026002", "red_numbers": [1, 2, 3, 4, 5, 6], "blue_number": 8},
                {"issue": "2026001", "red_numbers": [2, 3, 4, 5, 6, 7], "blue_number": 9},
            ]

    monkeypatch.setattr("dehps.crawler.ssq_sync.get_data_source", lambda *a, **k: FakeSource())

    summary = sync_ssq("fake", history=True, dry_run=True)

    assert summary["latest_draw"]["issue"] == "2026002"


def test_sync_records_failed_status(monkeypatch):
    finished = {}

    class FakeSource:
        def fetch_latest(self):
            return {"issue": "2026001", "red_numbers": [1, 2, 3, 4, 5, 6], "blue_number": 8}

    class FakeContext:
        def __enter__(self):
            return FakeConn()

        def __exit__(self, exc_type, exc, tb):
            return False

    def fail_upsert(conn, draw, source):
        raise RuntimeError("write failed")

    monkeypatch.setattr("dehps.crawler.ssq_sync.get_data_source", lambda *a, **k: FakeSource())
    monkeypatch.setattr("dehps.crawler.ssq_sync.get_connection", lambda: FakeContext())
    monkeypatch.setattr("dehps.crawler.ssq_sync.create_sync_run", lambda conn, run_key, source: None)
    monkeypatch.setattr("dehps.crawler.ssq_sync.upsert_ssq_draw", fail_upsert)
    monkeypatch.setattr(
        "dehps.crawler.ssq_sync.finish_sync_run",
        lambda conn, run_key, status, summary: finished.update({"status": status, "summary": summary}),
    )

    try:
        sync_ssq("fake", run_key="sync-test")
    except RuntimeError as exc:
        assert str(exc) == "write failed"
    else:
        raise AssertionError("sync failure was not raised")

    assert finished["status"] == "failed"
    assert finished["summary"]["status"] == "failed"
    assert finished["summary"]["error_message"] == "write failed"
