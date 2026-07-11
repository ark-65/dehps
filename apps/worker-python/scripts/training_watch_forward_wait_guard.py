from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any


FORWARD_WAIT_ACTION = "await_new_forward_issue"


@dataclass(frozen=True)
class ForwardWaitDecision:
    should_wait: bool
    reason: str


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def forward_wait_decision_from_watch_summary(
    summary: dict[str, Any],
    *,
    expected_pid: int | None = None,
    require_durable_boundary: bool = True,
) -> ForwardWaitDecision:
    forward_wait = summary.get("forward_wait")
    if (
        summary.get("action") != FORWARD_WAIT_ACTION
        or not isinstance(forward_wait, dict)
    ):
        return ForwardWaitDecision(False, "watch_forward_wait_not_requested")

    history_issue = _as_int(forward_wait.get("history_latest_issue"))
    pending_issue = _as_int(forward_wait.get("next_pending_issue"))
    round_boundary = (
        summary.get("supervisor_round_boundary")
        if isinstance(summary.get("supervisor_round_boundary"), dict)
        else {}
    )
    checks = {
        "wait_ready": forward_wait.get("ready") is True,
        "wait_status": forward_wait.get("status") == "awaiting_new_forward_issue",
        "wait_action": forward_wait.get("action") == "park_same_history_training",
        "future_issue": (
            history_issue is not None
            and pending_issue is not None
            and pending_issue > history_issue
        ),
        "selection_unchanged": forward_wait.get("selection_changed") is False,
        "promotion_disabled": forward_wait.get("promotion_allowed") is False,
        "adaptive_risk_explicit": (
            forward_wait.get("adaptive_hypothesis_generation_counted") is False
        ),
        "sequential_risk_explicit": (
            forward_wait.get("sequential_search_multiplicity_counted") is False
        ),
        "db_reads_clean": not bool(summary.get("db_read_errors")),
    }
    if require_durable_boundary:
        checks["durable_round_boundary"] = (
            round_boundary.get("status") == "target_complete_round_recorded"
        )

    if expected_pid is not None:
        supervisor = (
            summary.get("supervisor_status")
            if isinstance(summary.get("supervisor_status"), dict)
            else {}
        )
        lock = (
            summary.get("heavy_job_lock")
            if isinstance(summary.get("heavy_job_lock"), dict)
            else {}
        )
        progress = (
            supervisor.get("latest_progress")
            if isinstance(supervisor.get("latest_progress"), dict)
            else {}
        )
        checks.update(
            {
                "supervisor_available": supervisor.get("available") is True,
                "supervisor_pid": _as_int(supervisor.get("pid")) == expected_pid,
                "supervisor_progress_fresh": progress.get("fresh") is True,
                "lock_owner": lock.get("owner") == "training-supervisor",
                "lock_pid": _as_int(lock.get("pid")) == expected_pid,
            }
        )

    missing = [name for name, passed in checks.items() if not passed]
    if missing:
        return ForwardWaitDecision(
            False,
            "watch_forward_wait_not_ready:" + ",".join(missing),
        )
    return ForwardWaitDecision(
        True,
        f"watch_forward_wait_ready:{history_issue}->{pending_issue}",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Decide whether a training-watch summary permits parking until a new issue."
    )
    parser.add_argument("--expected-pid", type=int)
    parser.add_argument(
        "--request-only",
        action="store_true",
        help="Validate the wait request without requiring the instantaneous durable boundary.",
    )
    args = parser.parse_args(argv)

    try:
        summary = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"watch_forward_wait_invalid_json:{exc.msg}", file=sys.stderr)
        return 2
    if not isinstance(summary, dict):
        print("watch_forward_wait_invalid_json:not_object", file=sys.stderr)
        return 2

    decision = forward_wait_decision_from_watch_summary(
        summary,
        expected_pid=args.expected_pid,
        require_durable_boundary=not args.request_only,
    )
    print(decision.reason)
    return 0 if decision.should_wait else 1


if __name__ == "__main__":
    raise SystemExit(main())
