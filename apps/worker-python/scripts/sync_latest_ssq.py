from __future__ import annotations

import argparse
import json

from dehps.crawler.ssq_sync import sync_ssq


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="zhcw", choices=["zhcw", "csv"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--from-issue")
    parser.add_argument("--to-issue")
    args = parser.parse_args()
    summary = sync_ssq(
        args.source,
        history=args.history,
        from_issue=args.from_issue,
        to_issue=args.to_issue,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

