from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from dehps.optimization.next_candidates import (
    DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_LINE_KEY,
    STATIC_100_LINE_KEY,
)


FORWARD_EVALUATION_LINE_KEYS = (
    STATIC_100_LINE_KEY,
    DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_LINE_KEY,
)


class ForwardEvaluationPlanError(ValueError):
    """Raised when pre-sync prediction snapshots cannot form a safe evaluation plan."""


def parse_issue(value: object, *, field: str, allow_empty: bool = False) -> int | None:
    text = str(value or "").strip()
    if not text and allow_empty:
        return None
    if not text.isdigit():
        raise ForwardEvaluationPlanError(f"invalid_{field}:{text or 'missing'}")
    return int(text)


def build_forward_evaluation_plan(
    snapshots: Sequence[Mapping[str, Any]],
    *,
    history_issues: Iterable[object],
    previous_issue: object,
    current_issue: object,
) -> list[dict[str, str]]:
    previous_number = parse_issue(
        previous_issue,
        field="previous_issue",
        allow_empty=True,
    )
    current_number = parse_issue(current_issue, field="current_issue")
    if previous_number is not None and current_number < previous_number:
        raise ForwardEvaluationPlanError(
            f"history_issue_regressed:{previous_number}->{current_number}"
        )
    history_advanced = previous_number is not None and current_number > previous_number
    available_history = {str(issue).strip() for issue in history_issues}
    grouped: dict[str, dict[str, dict[str, str]]] = {}

    for index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, Mapping):
            raise ForwardEvaluationPlanError(f"invalid_snapshot_row:{index}")
        line_key = str(snapshot.get("line_key") or "").strip()
        if line_key not in FORWARD_EVALUATION_LINE_KEYS:
            continue
        next_issue = str(snapshot.get("next_issue") or "").strip()
        snapshot_key = str(snapshot.get("snapshot_key") or "").strip()
        as_of_issue = str(snapshot.get("as_of_issue") or "").strip()
        top_n = parse_issue(snapshot.get("top_n"), field="snapshot_top_n")
        candidate_count = parse_issue(
            snapshot.get("candidate_count"),
            field="snapshot_candidate_count",
        )
        next_number = parse_issue(next_issue, field="snapshot_next_issue")
        as_of_number = parse_issue(as_of_issue, field="snapshot_as_of_issue")
        if not snapshot_key:
            raise ForwardEvaluationPlanError(
                f"missing_snapshot_key:{line_key}:{next_issue}"
            )
        if top_n <= 0 or candidate_count != top_n:
            raise ForwardEvaluationPlanError(
                "incomplete_snapshot_candidates:"
                f"{line_key}:{next_issue}:count={candidate_count}:top_n={top_n}"
            )
        if as_of_number >= next_number:
            raise ForwardEvaluationPlanError(
                f"snapshot_leakage_boundary:{line_key}:{as_of_issue}>={next_issue}"
            )
        if (
            history_advanced
            and previous_number is not None
            and as_of_number > previous_number
        ):
            raise ForwardEvaluationPlanError(
                "snapshot_not_frozen_before_sync:"
                f"{line_key}:{as_of_issue}>{previous_number}"
            )
        if next_number > current_number or next_issue not in available_history:
            continue

        issue_lines = grouped.setdefault(next_issue, {})
        if line_key in issue_lines:
            raise ForwardEvaluationPlanError(
                f"duplicate_snapshot_line:{next_issue}:{line_key}"
            )
        issue_lines[line_key] = {
            "line_key": line_key,
            "next_issue": next_issue,
            "snapshot_key": snapshot_key,
            "as_of_issue": as_of_issue,
        }

    plan: list[dict[str, str]] = []
    for next_issue in sorted(grouped, key=int):
        issue_lines = grouped[next_issue]
        missing_lines = [
            line_key
            for line_key in FORWARD_EVALUATION_LINE_KEYS
            if line_key not in issue_lines
        ]
        if missing_lines:
            raise ForwardEvaluationPlanError(
                f"incomplete_forward_line_set:{next_issue}:{','.join(missing_lines)}"
            )
        plan.extend(issue_lines[line_key] for line_key in FORWARD_EVALUATION_LINE_KEYS)

    if history_advanced and not plan:
        raise ForwardEvaluationPlanError(
            f"missing_complete_forward_snapshot_after_history_advance:"
            f"{previous_number}->{current_number}"
        )
    return plan
