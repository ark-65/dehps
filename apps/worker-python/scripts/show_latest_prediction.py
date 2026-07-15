from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.db import get_connection
from dehps.forward_runtime.latest_prediction import (
    build_latest_prediction_payload,
    load_latest_prediction_rows,
    render_latest_prediction,
    resolve_git_commit,
)


ROOT_DIR = Path(__file__).resolve().parents[3]


def show_latest_prediction(*, top_limit: int = 10) -> dict:
    with get_connection() as conn:
        runs, candidates = load_latest_prediction_rows(conn, top_limit=top_limit)
    return build_latest_prediction_payload(
        runs,
        candidates,
        git_commit=resolve_git_commit(ROOT_DIR),
        top_limit=top_limit,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show the latest durable three-line forward prediction snapshot."
    )
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be at least 1")
    payload = show_latest_prediction(top_limit=args.top)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_latest_prediction(payload))


if __name__ == "__main__":
    main()
