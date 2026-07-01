from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_COAUTHOR_TRAILER = (
    "Co-authored-by: give me a 98K <240642031+inhuman-0@users.noreply.github.com>"
)
ALLOWED_TYPES = ("fix", "feat", "chore", "docs", "test", "refactor")
BRANCH_RE = re.compile(rf"^({'|'.join(ALLOWED_TYPES)})/[a-z0-9][a-z0-9._-]*[a-z0-9]$")
TITLE_RE = re.compile(rf"^({'|'.join(ALLOWED_TYPES)})(\([a-z0-9._-]+\))?: .+")


def run(cmd: list[str], cwd: Path | str = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def command_error(completed: subprocess.CompletedProcess) -> str:
    return completed.stderr.strip() or completed.stdout.strip()


def current_branch() -> tuple[str | None, str | None]:
    branch = run(["git", "branch", "--show-current"])
    if branch.returncode != 0:
        return None, command_error(branch) or "unable to resolve current branch"
    value = branch.stdout.strip()
    if not value:
        return None, "detached HEAD is not a valid self-iteration branch"
    return value, None


def title_type(title: str) -> str | None:
    match = TITLE_RE.match(title)
    return match.group(1) if match else None


def validate_branch_and_title(branch: str, title: str) -> dict | None:
    if branch in {"main", "master"}:
        return {"status": "invalid_branch", "error": "self-iteration PRs must not publish from main/master"}
    branch_match = BRANCH_RE.match(branch)
    if not branch_match:
        return {
            "status": "invalid_branch",
            "error": f"branch must start with one of: {', '.join(ALLOWED_TYPES)}",
            "branch": branch,
        }
    parsed_title_type = title_type(title)
    if parsed_title_type is None:
        return {
            "status": "invalid_title",
            "error": f"PR title must use one of these prefixes: {', '.join(ALLOWED_TYPES)}",
            "title": title,
        }
    branch_type = branch_match.group(1)
    if branch_type != parsed_title_type:
        return {
            "status": "invalid_title",
            "error": "PR title type must match the branch prefix",
            "branch": branch,
            "title": title,
        }
    return None


def clean_worktree_error() -> str | None:
    status = run(["git", "status", "--porcelain"])
    if status.returncode != 0:
        return command_error(status) or "unable to inspect working tree"
    if status.stdout.strip():
        return status.stdout.strip()
    return None


def last_commit_message() -> tuple[str | None, str | None]:
    message = run(["git", "log", "-1", "--format=%B"])
    if message.returncode != 0:
        return None, command_error(message) or "unable to read last commit message"
    return message.stdout, None


def head_sha() -> tuple[str | None, str | None]:
    sha = run(["git", "rev-parse", "HEAD"])
    if sha.returncode != 0:
        return None, command_error(sha) or "unable to resolve HEAD"
    value = sha.stdout.strip()
    if not value:
        return None, "unable to resolve HEAD"
    return value, None


def merge_body_from(body_file: Path, coauthor_trailer: str) -> str:
    body = body_file.read_text().rstrip()
    if coauthor_trailer in body:
        return body + "\n"
    if body:
        return f"{body}\n\n{coauthor_trailer}\n"
    return f"{coauthor_trailer}\n"


def publish_self_iteration_pr(
    *,
    title: str,
    body_file: Path,
    base: str = "main",
    remote: str = "origin",
    coauthor_trailer: str | None = None,
) -> dict:
    coauthor_trailer = coauthor_trailer or os.environ.get(
        "DEHPS_SELF_ITERATE_GIT_COAUTHOR_TRAILER", DEFAULT_COAUTHOR_TRAILER
    )
    branch, branch_error = current_branch()
    if branch_error or branch is None:
        return {"status": "invalid_branch", "error": branch_error}

    validation_error = validate_branch_and_title(branch, title)
    if validation_error is not None:
        return validation_error

    if not body_file.exists():
        return {"status": "missing_body_file", "error": f"PR body file does not exist: {body_file}"}

    dirty = clean_worktree_error()
    if dirty is not None:
        return {"status": "dirty_worktree", "error": dirty}

    auth = run(["gh", "auth", "status"])
    if auth.returncode != 0:
        return {"status": "gh_auth_failed", "error": command_error(auth) or "gh auth status failed"}

    commit_message, commit_error = last_commit_message()
    if commit_error or commit_message is None:
        return {"status": "failed", "error": commit_error}
    if coauthor_trailer not in commit_message:
        return {
            "status": "missing_coauthor_trailer",
            "error": "last commit message does not include the required co-author trailer",
        }

    sha, sha_error = head_sha()
    if sha_error or sha is None:
        return {"status": "failed", "error": sha_error}

    pushed = run(["git", "push", "-u", remote, branch])
    if pushed.returncode != 0:
        return {"status": "push_failed", "error": command_error(pushed), "branch": branch, "head_sha": sha}

    pr = run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            base,
            "--head",
            branch,
            "--title",
            title,
            "--body-file",
            str(body_file),
        ]
    )
    if pr.returncode != 0:
        return {"status": "pr_create_failed", "error": command_error(pr), "branch": branch, "head_sha": sha}
    pr_url = pr.stdout.strip().splitlines()[-1] if pr.stdout.strip() else ""

    merge_body = merge_body_from(body_file, coauthor_trailer)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=True) as merge_body_file:
        merge_body_file.write(merge_body)
        merge_body_file.flush()
        merged = run(
            [
                "gh",
                "pr",
                "merge",
                pr_url,
                "--auto",
                "--squash",
                "--delete-branch",
                "--match-head-commit",
                sha,
                "--subject",
                title,
                "--body-file",
                merge_body_file.name,
            ]
        )
    if merged.returncode != 0:
        return {
            "status": "auto_merge_failed",
            "error": command_error(merged),
            "branch": branch,
            "head_sha": sha,
            "pr_url": pr_url,
        }

    return {
        "status": "auto_merge_enabled",
        "branch": branch,
        "base": base,
        "head_sha": sha,
        "pr_url": pr_url,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--body-file", required=True, type=Path)
    parser.add_argument("--base", default="main")
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args()

    result = publish_self_iteration_pr(
        title=args.title,
        body_file=args.body_file,
        base=args.base,
        remote=args.remote,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result.get("status") != "auto_merge_enabled":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
