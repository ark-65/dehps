from pathlib import Path

from dehps.config import ROOT_DIR


def test_training_watchdog_no_longer_invokes_remote_draw_sync() -> None:
    script = (ROOT_DIR / "scripts/ensure_training_supervisor.sh").read_text(encoding="utf-8")

    assert "scripts/sync_latest_ssq.py" not in script
    assert "scripts/plan_ssq_remote_sync_poll.py" not in script
    assert "draw synchronization is decoupled from training watchdog" in script


def test_draw_sync_has_independent_watch_entrypoint() -> None:
    assert Path(ROOT_DIR / "scripts/run_draw_sync_watch.py").exists()
    assert Path(ROOT_DIR / "apps/worker-python/scripts/run_draw_sync_watch.py").exists()
    assert Path(ROOT_DIR / "scripts/ensure_draw_sync_watch.sh").exists()
