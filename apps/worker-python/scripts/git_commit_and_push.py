from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ALLOWED_PATHS = ["data/raw", "data/processed", "data/output", "docs/experiments"]
REPO_ROOT = Path(__file__).resolve().parents[3]


def run(cmd: list[str], cwd: Path | str = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def existing_allowed_paths() -> list[str]:
    return [path for path in ALLOWED_PATHS if (REPO_ROOT / path).exists()]


def staged_paths() -> subprocess.CompletedProcess:
    return run(["git", "diff", "--cached", "--name-only", "-z"])


def resolve_push_branch(remote: str, branch: str | None) -> tuple[str | None, str | None]:
    if branch:
        return branch, None

    upstream = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    upstream_ref = upstream.stdout.strip()
    remote_prefix = f"{remote}/"
    if upstream.returncode == 0 and upstream_ref.startswith(remote_prefix):
        return upstream_ref[len(remote_prefix) :], None

    current = run(["git", "branch", "--show-current"])
    current_branch = current.stdout.strip()
    if current.returncode == 0 and current_branch:
        return current_branch, None

    error = upstream.stderr.strip() or current.stderr.strip() or "unable to resolve current branch for push"
    return None, error


def split_null_paths(value: str) -> list[str]:
    return [path for path in value.split("\0") if path]


def path_is_allowed(path: str, allowed_paths: list[str]) -> bool:
    return any(path == allowed_path or path.startswith(f"{allowed_path}/") for allowed_path in allowed_paths)


def git_commit_and_push(message: str, push: bool = False, remote: str = "origin", branch: str | None = None) -> dict:
    status = run(["git", "status", "--short"])
    if status.returncode != 0:
        return {"status": "failed", "error": status.stderr.strip()}
    if not status.stdout.strip():
        return {"status": "no_changes"}

    allowed_paths = existing_allowed_paths()
    if not allowed_paths:
        return {"status": "no_allowed_changes"}

    pre_staged = staged_paths()
    if pre_staged.returncode != 0:
        return {"status": "failed", "error": pre_staged.stderr.strip() or pre_staged.stdout.strip()}
    disallowed_staged_paths = [
        path for path in split_null_paths(pre_staged.stdout) if not path_is_allowed(path, allowed_paths)
    ]
    if disallowed_staged_paths:
        return {
            "status": "blocked_disallowed_staged_changes",
            "paths": disallowed_staged_paths,
            "error": "staged changes outside allowed auto-git paths",
        }

    add = run(["git", "add", *allowed_paths])
    if add.returncode != 0:
        return {"status": "failed", "error": add.stderr.strip()}

    post_staged = staged_paths()
    if post_staged.returncode != 0:
        return {"status": "failed", "error": post_staged.stderr.strip() or post_staged.stdout.strip()}
    staged_allowed_paths = [
        path for path in split_null_paths(post_staged.stdout) if path_is_allowed(path, allowed_paths)
    ]
    if not staged_allowed_paths:
        return {"status": "no_allowed_changes"}

    commit = run(["git", "commit", "-m", message])
    if commit.returncode != 0:
        return {"status": "failed", "error": commit.stderr.strip() or commit.stdout.strip()}

    sha = run(["git", "rev-parse", "HEAD"])
    result = {"status": "committed", "sha": sha.stdout.strip()}
    if push:
        push_branch, push_error = resolve_push_branch(remote, branch)
        if push_branch is None:
            return {**result, "status": "push_failed", "error": push_error or "unable to resolve push branch"}
        pushed = run(["git", "push", remote, f"HEAD:{push_branch}"])
        if pushed.returncode != 0:
            return {**result, "status": "push_failed", "error": pushed.stderr.strip()}
        result["status"] = "pushed"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", required=True)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default=None)
    args = parser.parse_args()
    print(git_commit_and_push(args.message, args.push, args.remote, args.branch))


if __name__ == "__main__":
    main()
