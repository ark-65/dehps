from pathlib import Path

from scripts import git_commit_and_push


class FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_git_helper_uses_repo_root(monkeypatch):
    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append({"cmd": cmd, "cwd": cwd})
        if cmd == ["git", "status", "--short"]:
            return FakeCompleted(stdout=" M data/output/daily/report.md\n")
        if cmd == ["git", "diff", "--cached", "--quiet"]:
            return FakeCompleted(returncode=1)
        if cmd == ["git", "rev-parse", "HEAD"]:
            return FakeCompleted(stdout="abc123\n")
        return FakeCompleted()

    monkeypatch.setattr(git_commit_and_push.subprocess, "run", fake_run)

    result = git_commit_and_push.git_commit_and_push("test commit")

    assert result == {"status": "committed", "sha": "abc123"}
    assert calls
    assert all(call["cwd"] == git_commit_and_push.REPO_ROOT for call in calls)
    assert git_commit_and_push.REPO_ROOT == Path(__file__).resolve().parents[3]


def test_git_helper_skips_missing_allowed_paths(monkeypatch):
    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append({"cmd": cmd, "cwd": cwd})
        if cmd == ["git", "status", "--short"]:
            return FakeCompleted(stdout=" M docs/experiments/report.md\n")
        if cmd == ["git", "diff", "--cached", "--quiet"]:
            return FakeCompleted(returncode=1)
        if cmd == ["git", "rev-parse", "HEAD"]:
            return FakeCompleted(stdout="abc123\n")
        return FakeCompleted()

    monkeypatch.setattr(git_commit_and_push, "ALLOWED_PATHS", ["missing-data-dir", "docs/experiments"])
    monkeypatch.setattr(git_commit_and_push.subprocess, "run", fake_run)

    result = git_commit_and_push.git_commit_and_push("test commit")

    assert result == {"status": "committed", "sha": "abc123"}
    assert ["git", "add", "docs/experiments"] in [call["cmd"] for call in calls]
    assert ["git", "add", "missing-data-dir", "docs/experiments"] not in [call["cmd"] for call in calls]


def test_git_helper_reports_no_allowed_changes_when_allowed_paths_are_absent(monkeypatch):
    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append(cmd)
        if cmd == ["git", "status", "--short"]:
            return FakeCompleted(stdout=" M apps/api/src/main.ts\n")
        return FakeCompleted()

    monkeypatch.setattr(git_commit_and_push, "ALLOWED_PATHS", ["missing-data-dir"])
    monkeypatch.setattr(git_commit_and_push.subprocess, "run", fake_run)

    result = git_commit_and_push.git_commit_and_push("test commit")

    assert result == {"status": "no_allowed_changes"}
    assert not any(call[:2] == ["git", "add"] for call in calls)
