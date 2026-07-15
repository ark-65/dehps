from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from dehps.config import ROOT_DIR


@lru_cache(maxsize=4)
def resolve_git_commit(repo_root: Path = ROOT_DIR) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"
