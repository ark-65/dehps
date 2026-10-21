"""Preview the current M4 research report, or deliver its weekly copy."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.notifications.mail import QqMailConfig
from dehps.notifications.research_progress import RELEASE_ROOT, deliver_report, render_report


def _assert_reviewed_release() -> None:
    expected = os.environ.get("DEHPS_RESEARCH_PROGRESS_RELEASE_COMMIT", "").strip()
    if len(expected) != 40 or any(char not in "0123456789abcdef" for char in expected):
        raise RuntimeError("reviewed research progress release commit is not configured")
    actual = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=RELEASE_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if actual != expected:
        raise RuntimeError("research progress source differs from reviewed release")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=RELEASE_ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if dirty:
        raise RuntimeError("research progress release worktree is dirty")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deliver", action="store_true", help="send one copy for the current Shanghai week")
    args = parser.parse_args()
    report = render_report(now=datetime.now(UTC))
    if not args.deliver:
        print(report.text, end="")
        return
    _assert_reviewed_release()
    result = deliver_report(report, config=QqMailConfig.from_environment())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
