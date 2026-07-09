from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any

RESTART_ACTION = "prepare_restart_with_more_exploration"
TARGET_BOUNDARY_STOP_ACTION = (
    "operator_review_then_stop_continuous_training_supervisor_before_restart"
)


@dataclass(frozen=True)
class RestartDecision:
    should_restart: bool
    reason: str


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _positive_int(value: Any) -> bool:
    parsed = _as_int(value)
    return parsed is not None and parsed > 0


def _navigation_distance_ready(readiness: dict[str, Any]) -> bool:
    distance = _as_float(readiness.get("experimental_navigation_config_distance"))
    minimum = _as_float(readiness.get("experimental_navigation_min_config_distance"))
    return distance is not None and minimum is not None and distance >= minimum


def restart_decision_from_watch_summary(
    summary: dict[str, Any],
    *,
    expected_pid: int,
) -> RestartDecision:
    readiness = summary.get("restart_readiness")
    if not isinstance(readiness, dict):
        return RestartDecision(False, "watch_restart_not_requested")
    if readiness.get("requested") is False or readiness.get("status") == "not_requested":
        round_boundary = summary.get("supervisor_round_boundary")
        if (
            isinstance(round_boundary, dict)
            and round_boundary.get("status") == "target_complete_waiting_round_result"
        ):
            return RestartDecision(
                False,
                "watch_restart_not_requested:target_complete_waiting_round_result",
            )
        return RestartDecision(False, "watch_restart_not_requested")

    restart_rank_changed = readiness.get("restart_candidate_rank_vector_changed") is True
    restart_primary_improved = (
        readiness.get("restart_candidate_primary_score_improved") is True
    )
    restart_secondary_improved = (
        readiness.get("restart_candidate_secondary_score_improved") is True
    )
    navigation_rank_changed = (
        readiness.get("experimental_navigation_rank_vector_changed") is True
    )
    checks = {
        "action": summary.get("action") == RESTART_ACTION,
        "status": readiness.get("status") == "blocked_by_active_training_supervisor_lock",
        "operator_action": readiness.get("operator_action") == TARGET_BOUNDARY_STOP_ACTION,
        "owner": readiness.get("owner") == "training-supervisor",
        "pid": _as_int(readiness.get("pid")) == expected_pid,
        "supervisor_pid": _as_int(readiness.get("supervisor_pid")) == expected_pid,
        "supervisor_run_id": bool(readiness.get("supervisor_run_id"))
        and readiness.get("supervisor_run_id") == summary.get("run_id"),
        "run_mode": readiness.get("supervisor_run_mode") == "continuous",
        "progress_fresh": readiness.get("supervisor_progress_fresh") is True,
        "target_complete": readiness.get("supervisor_target_complete") is True,
        "restart_candidate": readiness.get("restart_candidate_active") is True,
        "restart_rank_vector_changed": restart_rank_changed,
        "restart_changed_targets": _positive_int(
            readiness.get("restart_candidate_changed_target_count")
        ),
        "restart_full_eval_rank": _positive_int(
            readiness.get("restart_candidate_full_eval_rank")
        ),
        "restart_frontier_improved": (
            restart_primary_improved or restart_secondary_improved
        ),
        "restart_improvement_basis": readiness.get("restart_candidate_improvement_basis")
        in {"primary", "secondary"},
        "navigation_eligible": readiness.get("experimental_navigation_eligible") is True,
        "navigation_quality": readiness.get("experimental_navigation_quality_reason")
        == "passed",
        "navigation_rank_vector_changed": navigation_rank_changed,
        "navigation_distance": _navigation_distance_ready(readiness),
    }
    missing = [name for name, passed in checks.items() if not passed]
    if missing:
        return RestartDecision(False, "watch_restart_not_ready:" + ",".join(missing))
    return RestartDecision(True, "watch_restart_ready_target_boundary")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Decide whether a training-watch summary permits a supervisor restart."
    )
    parser.add_argument("--expected-pid", type=int, required=True)
    args = parser.parse_args(argv)

    try:
        summary = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"watch_restart_invalid_json:{exc.msg}", file=sys.stderr)
        return 2
    if not isinstance(summary, dict):
        print("watch_restart_invalid_json:not_object", file=sys.stderr)
        return 2

    decision = restart_decision_from_watch_summary(summary, expected_pid=args.expected_pid)
    print(decision.reason)
    return 0 if decision.should_restart else 1


if __name__ == "__main__":
    raise SystemExit(main())
