import subprocess
import sys
from pathlib import Path

from scripts.daily_pipeline import run_pipeline


def test_daily_pipeline_direct_script_help_starts_without_import_error():
    worker_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/daily_pipeline.py", "--help"],
        cwd=worker_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--skip-weight-kdj-signals" in result.stdout


def test_daily_pipeline_no_new_data_finishes(monkeypatch, tmp_path):
    finished = {}
    sync_calls = []

    monkeypatch.setattr("scripts.daily_pipeline.ROOT_DIR", tmp_path)
    monkeypatch.setattr("scripts.daily_pipeline._latest_local_issue", lambda: "2026067")

    def fake_sync(*args, **kwargs):
        sync_calls.append((args, kwargs))
        return {"run_key": "sync", "inserted_count": 0}

    monkeypatch.setattr("scripts.daily_pipeline.sync_ssq", fake_sync)

    class FakeConn:
        pass

    class FakeContext:
        def __enter__(self):
            return FakeConn()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scripts.daily_pipeline.get_connection", lambda: FakeContext())
    monkeypatch.setattr("scripts.daily_pipeline.create_pipeline_run", lambda conn, run_key: None)
    monkeypatch.setattr(
        "scripts.daily_pipeline.finish_pipeline_run",
        lambda conn, run_key, status, summary: finished.update({"status": status, "summary": summary}),
    )
    result = run_pipeline("baseline_v1", "zhcw")
    assert result["sync"]["inserted_count"] == 0
    assert sync_calls[0][0] == ("zhcw",)
    assert sync_calls[0][1]["history"] is True
    assert sync_calls[0][1]["from_issue"] == "2026067"
    assert finished["status"] == "success"


def test_daily_pipeline_runs_incremental_weight_kdj_after_sync_change(monkeypatch, tmp_path):
    finished = {}
    kdj_calls = []

    monkeypatch.setattr("scripts.daily_pipeline.ROOT_DIR", tmp_path)
    monkeypatch.setattr("scripts.daily_pipeline._latest_local_issue", lambda: "2026067")
    monkeypatch.setattr(
        "scripts.daily_pipeline.sync_ssq",
        lambda *a, **k: {
            "run_key": "sync",
            "inserted_count": 1,
            "updated_count": 0,
            "latest_draw": {"issue": "2026068"},
        },
    )
    monkeypatch.setattr("scripts.daily_pipeline.load_history", lambda conn: [("2026068", (1, 2, 3, 4, 5, 6))])
    monkeypatch.setattr("scripts.daily_pipeline.previous_experiment_metrics", lambda conn, strategy_key: None)
    monkeypatch.setattr("scripts.daily_pipeline.latest_draw", lambda conn: {"issue": "2026068"})
    monkeypatch.setattr("scripts.daily_pipeline.run_baseline_backtest", lambda history: {"history_draws": len(history)})
    monkeypatch.setattr("scripts.daily_pipeline.render_experiment_report", lambda *args: "# experiment")
    monkeypatch.setattr("scripts.daily_pipeline.render_daily_report", lambda *args: "# daily")
    monkeypatch.setattr("scripts.daily_pipeline.save_experiment", lambda *args: None)

    def fake_generate_signals(**kwargs):
        kdj_calls.append(kwargs)
        return {"status": "seed_missing", "signals": 0}

    monkeypatch.setattr("scripts.daily_pipeline.generate_signals", fake_generate_signals)

    class FakeConn:
        pass

    class FakeContext:
        def __enter__(self):
            return FakeConn()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scripts.daily_pipeline.get_connection", lambda: FakeContext())
    monkeypatch.setattr("scripts.daily_pipeline.create_pipeline_run", lambda conn, run_key: None)
    monkeypatch.setattr(
        "scripts.daily_pipeline.finish_pipeline_run",
        lambda conn, run_key, status, summary: finished.update({"status": status, "summary": summary}),
    )

    result = run_pipeline("baseline_v1", "zhcw")

    assert kdj_calls[0]["mode"] == "incremental"
    assert kdj_calls[0]["signal_run_id"] == "weight-kdj-recent-1000-v1"
    assert result["weight_kdj"]["status"] == "seed_missing"
    assert finished["summary"]["weight_kdj"]["signals"] == 0


def test_daily_pipeline_records_failed_status(monkeypatch, tmp_path):
    finished = {}

    monkeypatch.setattr("scripts.daily_pipeline.ROOT_DIR", tmp_path)
    monkeypatch.setattr("scripts.daily_pipeline._latest_local_issue", lambda: "2026067")

    def fail_sync(*args, **kwargs):
        raise RuntimeError("sync unavailable")

    class FakeConn:
        pass

    class FakeContext:
        def __enter__(self):
            return FakeConn()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scripts.daily_pipeline.sync_ssq", fail_sync)
    monkeypatch.setattr("scripts.daily_pipeline.get_connection", lambda: FakeContext())
    monkeypatch.setattr("scripts.daily_pipeline.create_pipeline_run", lambda conn, run_key: None)
    monkeypatch.setattr(
        "scripts.daily_pipeline.finish_pipeline_run",
        lambda conn, run_key, status, summary: finished.update({"status": status, "summary": summary}),
    )

    try:
        run_pipeline("baseline_v1", "zhcw")
    except RuntimeError as exc:
        assert str(exc) == "sync unavailable"
    else:
        raise AssertionError("pipeline failure was not raised")

    assert finished["status"] == "failed"
    assert finished["summary"]["error_message"] == "sync unavailable"


def test_daily_pipeline_preserves_sync_failure_when_lock_heartbeat_fails(monkeypatch, tmp_path):
    finished = {}
    released = {"called": False}

    monkeypatch.setattr("scripts.daily_pipeline.ROOT_DIR", tmp_path)
    monkeypatch.setattr("scripts.daily_pipeline._latest_local_issue", lambda: "2026067")

    class FailingHeartbeatLock:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def acquire(self):
            return self

        def heartbeat(self, **kwargs):
            raise RuntimeError("metadata write failed")

        def release(self):
            released["called"] = True

    def fail_sync(*args, **kwargs):
        raise RuntimeError("sync unavailable")

    class FakeConn:
        pass

    class FakeContext:
        def __enter__(self):
            return FakeConn()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scripts.daily_pipeline.HeavyJobLock", FailingHeartbeatLock)
    monkeypatch.setattr("scripts.daily_pipeline.sync_ssq", fail_sync)
    monkeypatch.setattr("scripts.daily_pipeline.get_connection", lambda: FakeContext())
    monkeypatch.setattr("scripts.daily_pipeline.create_pipeline_run", lambda conn, run_key: None)
    monkeypatch.setattr(
        "scripts.daily_pipeline.finish_pipeline_run",
        lambda conn, run_key, status, summary: finished.update({"status": status, "summary": summary}),
    )

    try:
        run_pipeline("baseline_v1", "zhcw")
    except RuntimeError as exc:
        assert str(exc) == "sync unavailable"
    else:
        raise AssertionError("pipeline failure was not raised")

    assert finished["status"] == "failed"
    assert finished["summary"]["error_message"] == "sync unavailable"
    assert released["called"] is True
