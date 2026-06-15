from scripts.daily_pipeline import run_pipeline


def test_daily_pipeline_no_new_data_finishes(monkeypatch, tmp_path):
    finished = {}

    monkeypatch.setattr("scripts.daily_pipeline.ROOT_DIR", tmp_path)
    monkeypatch.setattr("scripts.daily_pipeline.sync_ssq", lambda *a, **k: {"run_key": "sync", "inserted_count": 0})

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
    result = run_pipeline("baseline_v1", "csv")
    assert result["sync"]["inserted_count"] == 0
    assert finished["status"] == "success"
