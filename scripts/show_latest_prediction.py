#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = REPO_ROOT / "apps/worker-python"
sys.path.insert(0, str(WORKER_ROOT))

from dehps.db import get_connection  # noqa: E402
from dehps.forward_runtime.latest_prediction import (  # noqa: E402
    build_latest_prediction_payload,
    load_latest_prediction_rows,
    render_latest_prediction,
    resolve_git_commit,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show the latest durable three-line forward prediction snapshot."
    )
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be at least 1")
    with get_connection() as conn:
        runs, candidates = load_latest_prediction_rows(conn, top_limit=args.top)
    payload = build_latest_prediction_payload(
        runs,
        candidates,
        git_commit=resolve_git_commit(REPO_ROOT),
        top_limit=args.top,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_latest_prediction(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
