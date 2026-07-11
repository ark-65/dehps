from collections import namedtuple

import dehps.runtime.storage_capacity as capacity


DiskUsage = namedtuple("DiskUsage", "total used free")


def test_storage_capacity_reports_healthy_and_observed_logs(monkeypatch, tmp_path):
    log_dir = tmp_path / "runtime/logs"
    log_dir.mkdir(parents=True)
    (log_dir / "hourly_self_iterate.log").write_bytes(b"a" * 11)
    (log_dir / "training-supervisor-watchdog.log").write_bytes(b"b" * 7)
    monkeypatch.setattr(
        capacity.shutil,
        "disk_usage",
        lambda _path: DiskUsage(total=1000, used=100, free=900),
    )

    summary = capacity.runtime_storage_capacity_summary(
        tmp_path,
        warning_free_ratio=0.05,
        warning_free_bytes=50,
        critical_free_ratio=0.01,
        critical_free_bytes=10,
    )

    assert summary["status"] == "healthy"
    assert summary["action"] == "continue_storage_monitoring"
    assert summary["free_ratio"] == 0.9
    assert summary["observed_append_log_bytes"] == 18
    assert [row["exists"] for row in summary["observed_append_logs"]] == [
        True,
        True,
        False,
    ]
    assert summary["automatic_cleanup_allowed"] is False
    assert summary["selection_changed"] is False
    assert summary["promotion_allowed"] is False


def test_storage_capacity_uses_stricter_ratio_or_absolute_threshold(monkeypatch, tmp_path):
    monkeypatch.setattr(
        capacity.shutil,
        "disk_usage",
        lambda _path: DiskUsage(total=1000, used=930, free=70),
    )

    summary = capacity.runtime_storage_capacity_summary(
        tmp_path,
        warning_free_ratio=0.05,
        warning_free_bytes=80,
        critical_free_ratio=0.01,
        critical_free_bytes=20,
    )

    assert summary["warning_threshold_bytes"] == 80
    assert summary["critical_threshold_bytes"] == 20
    assert summary["status"] == "warning"
    assert summary["action"] == "review_runtime_evidence_retention"


def test_storage_capacity_marks_critical_without_automatic_cleanup(monkeypatch, tmp_path):
    monkeypatch.setattr(
        capacity.shutil,
        "disk_usage",
        lambda _path: DiskUsage(total=1000, used=985, free=15),
    )

    summary = capacity.runtime_storage_capacity_summary(
        tmp_path,
        warning_free_ratio=0.05,
        warning_free_bytes=80,
        critical_free_ratio=0.01,
        critical_free_bytes=20,
    )

    assert summary["status"] == "critical"
    assert summary["blockers"] == ["disk_free_below_critical_threshold"]
    assert summary["automatic_cleanup_allowed"] is False


def test_storage_capacity_fails_closed_when_disk_usage_is_unavailable(
    monkeypatch, tmp_path
):
    def fail(_path):
        raise OSError("statvfs failed")

    monkeypatch.setattr(capacity.shutil, "disk_usage", fail)

    summary = capacity.runtime_storage_capacity_summary(tmp_path)

    assert summary["status"] == "unavailable"
    assert summary["action"] == "inspect_runtime_storage"
    assert summary["automatic_cleanup_allowed"] is False
