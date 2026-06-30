from __future__ import annotations

from dehps.artifacts import atomic_write_text


def test_atomic_write_text_replaces_target_and_removes_temp_files(tmp_path):
    target = tmp_path / "status.json"
    target.write_text("old")

    atomic_write_text(target, "new")

    assert target.read_text() == "new"
    assert list(tmp_path.glob(".status.json.*.tmp")) == []


def test_atomic_write_text_preserves_existing_file_when_replace_fails(monkeypatch, tmp_path):
    target = tmp_path / "status.json"
    target.write_text("old")

    def fail_replace(temp_name: str, path: str) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("dehps.artifacts.os.replace", fail_replace)

    try:
        atomic_write_text(target, "new")
    except OSError as exc:
        assert str(exc) == "replace failed"
    else:
        raise AssertionError("atomic_write_text should raise when replace fails")

    assert target.read_text() == "old"
    assert list(tmp_path.glob(".status.json.*.tmp")) == []
