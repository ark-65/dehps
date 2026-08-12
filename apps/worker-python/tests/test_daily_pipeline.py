import os
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.daily_pipeline import run_pipeline


@pytest.fixture
def inactive_legacy_retirement(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "dehps.prediction.v2.retirement.DEFAULT_ACTIVATION_PATH",
        tmp_path / "legacy-retirement-not-activated.json",
    )


pytestmark = pytest.mark.usefixtures("inactive_legacy_retirement")


class ForwardEvaluator:
    def __init__(self, result=None, events=None):
        self.result = result or {
            "status": "ok",
            "pending_count": 0,
            "evaluated_count": 0,
            "missing_draw_count": 0,
            "failed_count": 0,
            "results": [],
        }
        self.events = events

    def evaluate_pending(self):
        if self.events is not None:
            self.events.append("evaluate")
        return self.result


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


def test_daily_pipeline_direct_script_help_starts_from_repository_root():
    worker_root = Path(__file__).resolve().parents[1]
    repository_root = worker_root.parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "apps/worker-python/scripts/daily_pipeline.py",
            "--help",
        ],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--skip-weight-kdj-signals" in result.stdout


def test_daily_pipeline_direct_script_resolves_sibling_import(tmp_path):
    worker_root = Path(__file__).resolve().parents[1]
    (tmp_path / "dehps").symlink_to(worker_root / "dehps", target_is_directory=True)
    runner = """
import os
import runpy
import sys
from pathlib import Path

root = Path(os.environ["DEHPS_TEST_WORKER_ROOT"]).resolve()
sys.path = [path for path in sys.path if Path(path or ".").resolve() != root]
sys.path[:0] = [str(root / "scripts"), os.environ["DEHPS_TEST_PACKAGE_ROOT"]]
sys.argv = [str(root / "scripts/daily_pipeline.py"), "--help"]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
    env = os.environ.copy()
    env["DEHPS_TEST_WORKER_ROOT"] = str(worker_root)
    env["DEHPS_TEST_PACKAGE_ROOT"] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, "-c", runner],
        cwd=worker_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage: daily_pipeline.py" in result.stdout


def test_daily_pipeline_no_new_data_finishes(monkeypatch, tmp_path):
    finished = {}
    sync_calls = []
    report_calls = []

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
    result = run_pipeline(
        "baseline_v1",
        "zhcw",
        forward_evaluator=ForwardEvaluator(),
        post_draw_report_notifier=lambda issue: report_calls.append(issue) or {"status": "sent"},
    )
    assert result["sync"]["inserted_count"] == 0
    assert sync_calls[0][0] == ("zhcw",)
    assert sync_calls[0][1]["history"] is True
    assert sync_calls[0][1]["from_issue"] == "2026067"
    assert finished["status"] == "success"
    assert report_calls == []


def test_daily_pipeline_runs_incremental_weight_kdj_after_sync_change(monkeypatch, tmp_path):
    finished = {}
    kdj_calls = []
    events = []

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
        events.append("signals")
        kdj_calls.append(kwargs)
        return {"status": "seed_missing", "signals": 0}

    monkeypatch.setattr("scripts.daily_pipeline.generate_signals", fake_generate_signals)
    monkeypatch.setattr(
        "scripts.daily_pipeline.refresh_training_prediction_lines_current",
        lambda conn, top_n: events.append("prediction") or {"status": "ready"},
    )

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

    result = run_pipeline(
        "baseline_v1",
        "zhcw",
        forward_evaluator=ForwardEvaluator(events=events),
        post_draw_report_notifier=lambda issue: events.append("report")
        or {"status": "sent", "issue": issue},
    )

    assert kdj_calls[0]["mode"] == "incremental"
    assert kdj_calls[0]["signal_run_id"] == "weight-kdj-recent-1000-v1"
    assert result["weight_kdj"]["status"] == "seed_missing"
    assert finished["summary"]["weight_kdj"]["signals"] == 0
    assert result["forward_evaluation"]["status"] == "ok"
    assert result["post_draw_evaluation_mail"] == {"status": "sent", "issue": "2026068"}
    assert events == ["evaluate", "report", "signals", "prediction"]


def test_daily_pipeline_records_mail_failure_without_blocking_next_prediction(monkeypatch, tmp_path):
    events = []
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
    monkeypatch.setattr("scripts.daily_pipeline.load_history", lambda conn: [])
    monkeypatch.setattr("scripts.daily_pipeline.previous_experiment_metrics", lambda conn, key: None)
    monkeypatch.setattr("scripts.daily_pipeline.latest_draw", lambda conn: {"issue": "2026068"})
    monkeypatch.setattr("scripts.daily_pipeline.run_baseline_backtest", lambda history: {})
    monkeypatch.setattr("scripts.daily_pipeline.render_experiment_report", lambda *args: "# experiment")
    monkeypatch.setattr("scripts.daily_pipeline.render_daily_report", lambda *args: "# daily")
    monkeypatch.setattr("scripts.daily_pipeline.save_experiment", lambda *args: None)
    monkeypatch.setattr(
        "scripts.daily_pipeline.generate_signals",
        lambda **kwargs: events.append("signals") or {"status": "ok"},
    )
    monkeypatch.setattr(
        "scripts.daily_pipeline.refresh_training_prediction_lines_current",
        lambda *args, **kwargs: events.append("prediction") or {"status": "ready"},
    )

    class FakeContext:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scripts.daily_pipeline.get_connection", lambda: FakeContext())
    monkeypatch.setattr("scripts.daily_pipeline.create_pipeline_run", lambda conn, run_key: None)
    monkeypatch.setattr("scripts.daily_pipeline.finish_pipeline_run", lambda *args: None)

    def fail_report(issue):
        events.append("report")
        raise RuntimeError("SMTP unavailable")

    result = run_pipeline(
        "baseline_v1",
        "zhcw",
        forward_evaluator=ForwardEvaluator(events=events),
        post_draw_report_notifier=fail_report,
    )

    assert result["post_draw_evaluation_mail"]["status"] == "failed"
    assert result["post_draw_evaluation_mail"]["error"]["type"] == "RuntimeError"
    assert events == ["evaluate", "report", "signals", "prediction"]


def test_daily_pipeline_blocks_next_prediction_when_forward_evaluation_fails(
    monkeypatch,
    tmp_path,
):
    finished = {}
    downstream_calls = []
    monkeypatch.setattr("scripts.daily_pipeline.ROOT_DIR", tmp_path)
    monkeypatch.setattr("scripts.daily_pipeline._latest_local_issue", lambda: "2026080")
    monkeypatch.setattr(
        "scripts.daily_pipeline.sync_ssq",
        lambda *a, **k: {
            "run_key": "sync",
            "inserted_count": 1,
            "updated_count": 0,
            "latest_draw": {"issue": "2026081"},
        },
    )
    monkeypatch.setattr(
        "scripts.daily_pipeline.generate_signals",
        lambda **kwargs: downstream_calls.append("signals"),
    )
    monkeypatch.setattr(
        "scripts.daily_pipeline.refresh_training_prediction_lines_current",
        lambda *args, **kwargs: downstream_calls.append("prediction"),
    )

    class FakeContext:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scripts.daily_pipeline.get_connection", lambda: FakeContext())
    monkeypatch.setattr("scripts.daily_pipeline.create_pipeline_run", lambda conn, run_key: None)
    monkeypatch.setattr(
        "scripts.daily_pipeline.finish_pipeline_run",
        lambda conn, run_key, status, summary: finished.update(
            {"status": status, "summary": summary}
        ),
    )
    evaluator = ForwardEvaluator(
        {
            "status": "failed",
            "pending_count": 3,
            "evaluated_count": 0,
            "missing_draw_count": 0,
            "failed_count": 1,
            "results": [{"status": "evaluation_failed"}],
        }
    )

    with pytest.raises(RuntimeError, match="forward_evaluation_batch_failed"):
        run_pipeline(
            "baseline_v1",
            "zhcw",
            forward_evaluator=evaluator,
        )

    assert downstream_calls == []
    assert finished["status"] == "failed"
    assert finished["summary"]["forward_evaluation"]["failed_count"] == 1


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
