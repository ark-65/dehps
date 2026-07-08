from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.optimization.prediction_evaluation import (
    DEFAULT_OUTPUT_DIR,
    build_prediction_evaluation,
    json_default,
    write_prediction_evaluation_report,
)
from dehps.db import get_connection


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the current training prediction snapshot against an actual SSQ draw.")
    parser.add_argument("--issue", help="Actual issue to evaluate. Defaults to the latest issue in ssq_history.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()

    with get_connection() as conn:
        payload = build_prediction_evaluation(conn, issue=args.issue)

    if not args.no_write_report:
        payload["artifact_paths"] = write_prediction_evaluation_report(payload, output_dir=args.output_dir)

    summary = {
        "status": payload["status"],
        "evaluable": payload["evaluable"],
        "issue": payload["issue"],
        "exact_red6_rank": (payload.get("result") or {}).get("exact_red6", {}).get("rank"),
        "red5_rank": (payload.get("result") or {}).get("red5", {}).get("rank"),
        "red5_or_better_rank": (payload.get("result") or {}).get("red5_or_better", {}).get("rank"),
        "artifact_paths": payload.get("artifact_paths"),
        "warnings": payload.get("warnings") or [],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=json_default))


if __name__ == "__main__":
    main()
