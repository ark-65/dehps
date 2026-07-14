#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = REPO_ROOT / "apps/worker-python"
sys.path.insert(0, str(WORKER_DIR))

from dehps.draw_sync.scheduler import main  # noqa: E402


if __name__ == "__main__":
    main()
