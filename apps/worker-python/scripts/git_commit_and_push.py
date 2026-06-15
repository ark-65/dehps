from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ALLOWED_PATHS = ["data/raw", "data/processed", "data/output", "docs/experiments"]
REPO_ROOT = Path(__file__).resolve().parents[3]


def run(cmd: list[str], cwd: Path | str = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def git_commit_and_push(message: str, push: bool = False, remote: str = "origin", branch: str = "main") -> dict:
    status = run(["git", "status", "--short"])
    if status.returncode != 0:
        return {"status": "failed", "error": status.stderr.strip()}
    if not status.stdout.strip():
        return {"status": "no_changes"}

    add = run(["git", "add", *ALLOWED_PATHS])
    if add.returncode != 0:
        return {"status": "failed", "error": add.stderr.strip()}

    staged = run(["git", "diff", "--cached", "--quiet"])
    if staged.returncode == 0:
        return {"status": "no_allowed_changes"}

    commit = run(["git", "commit", "-m", message])
    if commit.returncode != 0:
        return {"status": "failed", "error": commit.stderr.strip() or commit.stdout.strip()}

    sha = run(["git", "rev-parse", "HEAD"])
    result = {"status": "committed", "sha": sha.stdout.strip()}
    if push:
        pushed = run(["git", "push", remote, branch])
        if pushed.returncode != 0:
            return {**result, "status": "push_failed", "error": pushed.stderr.strip()}
        result["status"] = "pushed"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", required=True)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()
    print(git_commit_and_push(args.message, args.push, args.remote, args.branch))


if __name__ == "__main__":
    main()
