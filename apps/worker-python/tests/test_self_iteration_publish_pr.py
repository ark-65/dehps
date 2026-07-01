from pathlib import Path

from scripts import self_iteration_publish_pr


class FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def write_body(tmp_path: Path) -> Path:
    body_file = tmp_path / "pr-body.md"
    body_file.write_text("## Summary\n\n- test body\n")
    return body_file


def test_publish_pr_pushes_creates_pr_and_enables_auto_merge(monkeypatch, tmp_path):
    body_file = write_body(tmp_path)
    calls = []
    title = "chore: self-iterate PR auto-merge flow"
    trailer = self_iteration_publish_pr.DEFAULT_COAUTHOR_TRAILER

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append(cmd)
        if cmd == ["git", "branch", "--show-current"]:
            return FakeCompleted(stdout="chore/self-iterate-20260701-1500-pr-flow\n")
        if cmd == ["git", "status", "--porcelain"]:
            return FakeCompleted(stdout="")
        if cmd == ["gh", "auth", "status"]:
            return FakeCompleted(stdout="logged in\n")
        if cmd == ["git", "log", "-1", "--format=%B"]:
            return FakeCompleted(stdout=f"{title}\n\n{trailer}\n")
        if cmd == ["git", "rev-parse", "HEAD"]:
            return FakeCompleted(stdout="abc123\n")
        if cmd == ["git", "push", "-u", "origin", "chore/self-iterate-20260701-1500-pr-flow"]:
            return FakeCompleted()
        if cmd[:3] == ["gh", "pr", "create"]:
            return FakeCompleted(stdout="https://github.com/ark-65/dehps/pull/123\n")
        if cmd[:3] == ["gh", "pr", "merge"]:
            body_arg = cmd[cmd.index("--body-file") + 1]
            assert trailer in Path(body_arg).read_text()
            return FakeCompleted()
        return FakeCompleted(returncode=99, stderr=f"unexpected command: {cmd}")

    monkeypatch.setattr(self_iteration_publish_pr.subprocess, "run", fake_run)

    result = self_iteration_publish_pr.publish_self_iteration_pr(title=title, body_file=body_file)

    assert result == {
        "status": "auto_merge_enabled",
        "branch": "chore/self-iterate-20260701-1500-pr-flow",
        "base": "main",
        "head_sha": "abc123",
        "pr_url": "https://github.com/ark-65/dehps/pull/123",
    }
    assert ["git", "push", "-u", "origin", "chore/self-iterate-20260701-1500-pr-flow"] in calls
    assert [
        "gh",
        "pr",
        "create",
        "--base",
        "main",
        "--head",
        "chore/self-iterate-20260701-1500-pr-flow",
        "--title",
        title,
        "--body-file",
        str(body_file),
    ] in calls
    assert any(
        call[:10]
        == [
            "gh",
            "pr",
            "merge",
            "https://github.com/ark-65/dehps/pull/123",
            "--auto",
            "--squash",
            "--delete-branch",
            "--match-head-commit",
            "abc123",
            "--subject",
        ]
        for call in calls
    )


def test_publish_pr_rejects_main_branch(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append(cmd)
        if cmd == ["git", "branch", "--show-current"]:
            return FakeCompleted(stdout="main\n")
        return FakeCompleted()

    monkeypatch.setattr(self_iteration_publish_pr.subprocess, "run", fake_run)

    result = self_iteration_publish_pr.publish_self_iteration_pr(
        title="chore: self-iterate PR auto-merge flow",
        body_file=write_body(tmp_path),
    )

    assert result["status"] == "invalid_branch"
    assert not any(call[:2] == ["git", "push"] for call in calls)


def test_publish_pr_rejects_invalid_branch_prefix(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append(cmd)
        if cmd == ["git", "branch", "--show-current"]:
            return FakeCompleted(stdout="self-iterate/topic\n")
        return FakeCompleted()

    monkeypatch.setattr(self_iteration_publish_pr.subprocess, "run", fake_run)

    result = self_iteration_publish_pr.publish_self_iteration_pr(
        title="chore: self-iterate PR auto-merge flow",
        body_file=write_body(tmp_path),
    )

    assert result["status"] == "invalid_branch"
    assert not any(call[:2] == ["git", "push"] for call in calls)


def test_publish_pr_rejects_invalid_title_prefix(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append(cmd)
        if cmd == ["git", "branch", "--show-current"]:
            return FakeCompleted(stdout="chore/self-iterate-20260701-1500-pr-flow\n")
        return FakeCompleted()

    monkeypatch.setattr(self_iteration_publish_pr.subprocess, "run", fake_run)

    result = self_iteration_publish_pr.publish_self_iteration_pr(
        title="self-iterate PR auto-merge flow",
        body_file=write_body(tmp_path),
    )

    assert result["status"] == "invalid_title"
    assert not any(call[:2] == ["git", "push"] for call in calls)


def test_publish_pr_rejects_dirty_worktree(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append(cmd)
        if cmd == ["git", "branch", "--show-current"]:
            return FakeCompleted(stdout="chore/self-iterate-20260701-1500-pr-flow\n")
        if cmd == ["git", "status", "--porcelain"]:
            return FakeCompleted(stdout=" M scripts/hourly_self_iterate.sh\n")
        return FakeCompleted()

    monkeypatch.setattr(self_iteration_publish_pr.subprocess, "run", fake_run)

    result = self_iteration_publish_pr.publish_self_iteration_pr(
        title="chore: self-iterate PR auto-merge flow",
        body_file=write_body(tmp_path),
    )

    assert result == {"status": "dirty_worktree", "error": "M scripts/hourly_self_iterate.sh"}
    assert ["gh", "auth", "status"] not in calls
    assert not any(call[:2] == ["git", "push"] for call in calls)


def test_publish_pr_rejects_missing_coauthor_trailer(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append(cmd)
        if cmd == ["git", "branch", "--show-current"]:
            return FakeCompleted(stdout="chore/self-iterate-20260701-1500-pr-flow\n")
        if cmd == ["git", "status", "--porcelain"]:
            return FakeCompleted(stdout="")
        if cmd == ["gh", "auth", "status"]:
            return FakeCompleted(stdout="logged in\n")
        if cmd == ["git", "log", "-1", "--format=%B"]:
            return FakeCompleted(stdout="chore: self-iterate PR auto-merge flow\n")
        return FakeCompleted()

    monkeypatch.setattr(self_iteration_publish_pr.subprocess, "run", fake_run)

    result = self_iteration_publish_pr.publish_self_iteration_pr(
        title="chore: self-iterate PR auto-merge flow",
        body_file=write_body(tmp_path),
    )

    assert result["status"] == "missing_coauthor_trailer"
    assert not any(call[:2] == ["git", "push"] for call in calls)


def test_publish_pr_rejects_failed_gh_auth_without_push(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append(cmd)
        if cmd == ["git", "branch", "--show-current"]:
            return FakeCompleted(stdout="chore/self-iterate-20260701-1500-pr-flow\n")
        if cmd == ["git", "status", "--porcelain"]:
            return FakeCompleted(stdout="")
        if cmd == ["gh", "auth", "status"]:
            return FakeCompleted(returncode=1, stderr="not logged in\n")
        return FakeCompleted()

    monkeypatch.setattr(self_iteration_publish_pr.subprocess, "run", fake_run)

    result = self_iteration_publish_pr.publish_self_iteration_pr(
        title="chore: self-iterate PR auto-merge flow",
        body_file=write_body(tmp_path),
    )

    assert result == {"status": "gh_auth_failed", "error": "not logged in"}
    assert not any(call[:2] == ["git", "push"] for call in calls)
