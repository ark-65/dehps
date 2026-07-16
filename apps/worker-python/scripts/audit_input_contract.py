from __future__ import annotations

import argparse
import json

from dehps.input_contracts import WindowMode, WindowSpec
from dehps.research_runtime.snapshot import HistorySnapshotManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize and audit History Snapshot + Window Contract v1")
    parser.add_argument("--as-of-issue", required=True)
    parser.add_argument("--target-issue")
    parser.add_argument("--mode", choices=[mode.value for mode in WindowMode], default=WindowMode.ROLLING.value)
    parser.add_argument("--size", type=int)
    parser.add_argument("--minimum-size", type=int, default=1)
    parser.add_argument("--exclude-as-of", action="store_true")
    parser.add_argument("--include-records", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mode = WindowMode(args.mode)
    size = args.size
    if mode is WindowMode.ROLLING and size is None:
        raise SystemExit("--size is required for rolling windows")
    if mode is WindowMode.EXPANDING and size is not None:
        raise SystemExit("--size is forbidden for expanding windows")
    snapshot = HistorySnapshotManager().contract_current()
    spec = WindowSpec(
        mode=mode,
        size=size,
        minimum_size=args.minimum_size,
        as_of_issue=args.as_of_issue,
        include_as_of=not args.exclude_as_of,
        target_issue=args.target_issue,
    )
    window = spec.materialize(snapshot)
    print(
        json.dumps(
            {
                "status": "valid",
                "history_snapshot": snapshot.as_dict(include_records=args.include_records),
                "window": window.as_dict(include_records=args.include_records),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
