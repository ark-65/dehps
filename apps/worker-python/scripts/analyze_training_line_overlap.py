from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.db import get_connection
from dehps.optimization.line_overlap_audit import default_output_dir, write_line_overlap_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a three-line per-target overlap audit report.")
    parser.add_argument("--run-id", default=None, help="Training supervisor run id. Defaults to latest line round.")
    parser.add_argument("--round-index", type=int, default=None, help="Training round index. Defaults to latest round.")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    args = parser.parse_args()

    with get_connection() as conn:
        payload = write_line_overlap_audit(
            conn,
            run_id=args.run_id,
            round_index=args.round_index,
            output_dir=args.output_dir,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
