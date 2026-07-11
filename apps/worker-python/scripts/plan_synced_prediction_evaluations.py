from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.db import get_connection
from dehps.optimization.forward_evaluation_plan import (
    FORWARD_EVALUATION_LINE_KEYS,
    ForwardEvaluationPlanError,
    build_forward_evaluation_plan,
)


def load_snapshots(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForwardEvaluationPlanError(
            f"snapshot_file_unreadable:{path}:{type(exc).__name__}"
        ) from exc
    if not isinstance(payload, list):
        raise ForwardEvaluationPlanError("snapshot_file_root_not_list")
    if not all(isinstance(row, dict) for row in payload):
        raise ForwardEvaluationPlanError("snapshot_file_contains_non_object_row")
    return payload


def load_available_history_issues(snapshots: list[dict]) -> set[str]:
    candidate_issues = sorted(
        {
            str(row.get("next_issue") or "").strip()
            for row in snapshots
            if str(row.get("line_key") or "").strip()
            in FORWARD_EVALUATION_LINE_KEYS
            and str(row.get("next_issue") or "").strip()
        }
    )
    available: set[str] = set()
    with get_connection() as conn:
        for issue in candidate_issues:
            row = conn.execute(
                "SELECT 1 FROM ssq_history WHERE issue = %s LIMIT 1",
                (issue,),
            ).fetchone()
            if row:
                available.add(issue)
    return available


def load_accepted_evaluations(snapshots: list[dict]) -> list[dict]:
    candidate_issues = sorted(
        {
            str(row.get("next_issue") or "").strip()
            for row in snapshots
            if str(row.get("line_key") or "").strip()
            in FORWARD_EVALUATION_LINE_KEYS
            and str(row.get("next_issue") or "").strip()
        }
    )
    accepted: list[dict] = []
    with get_connection() as conn:
        table = conn.execute(
            "SELECT to_regclass('public.training_prediction_evaluations')"
        ).fetchone()
        if not table or not table[0]:
            return accepted
        for issue in candidate_issues:
            rows = conn.execute(
                """
                SELECT line_key, predicted_issue, snapshot_key, status,
                       candidate_count, summary
                FROM training_prediction_evaluations
                WHERE predicted_issue = %s
                """,
                (issue,),
            ).fetchall()
            accepted.extend(
                {
                    "line_key": str(row[0]),
                    "predicted_issue": str(row[1]),
                    "snapshot_key": str(row[2] or ""),
                    "status": str(row[3]),
                    "candidate_count": int(row[4] or 0),
                    "summary": row[5] if isinstance(row[5], dict) else {},
                }
                for row in rows
            )
    return accepted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a complete, pre-sync three-line forward prediction evaluation plan."
        )
    )
    parser.add_argument("--snapshot-file", type=Path, required=True)
    parser.add_argument("--previous-issue", default="")
    parser.add_argument("--current-issue", required=True)
    args = parser.parse_args(argv)

    try:
        snapshots = load_snapshots(args.snapshot_file)
        plan = build_forward_evaluation_plan(
            snapshots,
            history_issues=load_available_history_issues(snapshots),
            previous_issue=args.previous_issue,
            current_issue=args.current_issue,
            accepted_evaluations=load_accepted_evaluations(snapshots),
        )
    except ForwardEvaluationPlanError as exc:
        print(f"forward_evaluation_plan_invalid:{exc}", file=sys.stderr)
        return 1

    for row in plan:
        print(
            "\t".join(
                (
                    row["line_key"],
                    row["next_issue"],
                    row["snapshot_key"],
                    row["as_of_issue"],
                )
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
