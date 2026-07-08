from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.db import get_connection
from dehps.optimization.prediction_evaluation import (
    default_output_dir,
    evaluate_prediction_snapshot,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a current training prediction snapshot after SSQ sync.")
    parser.add_argument("--issue", required=True, help="Actual issue to evaluate after it exists in ssq_history.")
    parser.add_argument("--line-key", choices=["static_100", "dynamic_kdj"], default="static_100")
    parser.add_argument("--snapshot-key", help="Optional pre-sync snapshot key guard.")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--no-write-report", action="store_true")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    with get_connection() as conn:
        payload = evaluate_prediction_snapshot(
            conn,
            line_key=args.line_key,
            predicted_issue=args.issue,
            snapshot_key=args.snapshot_key,
            output_dir=args.output_dir,
            write_report=not args.no_write_report,
            persist=not args.no_persist,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
