from __future__ import annotations

import pytest

from dehps.optimization.forward_evaluation_plan import (
    FORWARD_EVALUATION_LINE_KEYS,
    ForwardEvaluationPlanError,
    build_forward_evaluation_plan,
)


def snapshots(
    *,
    next_issue: str = "2026079",
    as_of_issue: str = "2026078",
) -> list[dict[str, str]]:
    return [
        {
            "line_key": line_key,
            "next_issue": next_issue,
            "snapshot_key": f"snapshot-{line_key}",
            "as_of_issue": as_of_issue,
            "top_n": 10000,
            "candidate_count": 10000,
        }
        for line_key in FORWARD_EVALUATION_LINE_KEYS
    ]


def accepted_evaluation(
    line_key: str,
    *,
    status: str = "evaluated",
    leakage_passed: bool = True,
    candidate_count: int = 10000,
) -> dict:
    return {
        "line_key": line_key,
        "predicted_issue": "2026079",
        "snapshot_key": f"snapshot-{line_key}",
        "status": status,
        "candidate_count": candidate_count,
        "summary": {"leakage_passed": leakage_passed},
    }


def test_plan_requires_complete_pre_sync_three_line_snapshot():
    plan = build_forward_evaluation_plan(
        snapshots(),
        history_issues={"2026079"},
        previous_issue="2026078",
        current_issue="2026079",
    )

    assert [row["line_key"] for row in plan] == list(FORWARD_EVALUATION_LINE_KEYS)
    assert {row["next_issue"] for row in plan} == {"2026079"}
    assert {row["as_of_issue"] for row in plan} == {"2026078"}


def test_plan_rejects_missing_line_after_history_advance():
    with pytest.raises(
        ForwardEvaluationPlanError,
        match="incomplete_forward_line_set:2026079:dynamic_kdj_near",
    ):
        build_forward_evaluation_plan(
            snapshots()[:-1],
            history_issues={"2026079"},
            previous_issue="2026078",
            current_issue="2026079",
        )


def test_plan_rejects_empty_snapshot_after_history_advance():
    with pytest.raises(
        ForwardEvaluationPlanError,
        match="missing_complete_forward_snapshot_after_history_advance",
    ):
        build_forward_evaluation_plan(
            [],
            history_issues={"2026079"},
            previous_issue="2026078",
            current_issue="2026079",
        )


@pytest.mark.parametrize("as_of_issue", ["2026079", "2026080"])
def test_plan_rejects_snapshot_at_or_after_predicted_issue(as_of_issue):
    with pytest.raises(ForwardEvaluationPlanError, match="snapshot_leakage_boundary"):
        build_forward_evaluation_plan(
            snapshots(as_of_issue=as_of_issue),
            history_issues={"2026079"},
            previous_issue="2026078",
            current_issue="2026079",
        )


def test_plan_rejects_snapshot_not_frozen_before_sync():
    with pytest.raises(
        ForwardEvaluationPlanError,
        match="snapshot_not_frozen_before_sync",
    ):
        build_forward_evaluation_plan(
            snapshots(next_issue="2026081", as_of_issue="2026079"),
            history_issues={"2026081"},
            previous_issue="2026078",
            current_issue="2026081",
        )


def test_plan_rejects_duplicate_line_snapshot():
    duplicate = {**snapshots()[0], "snapshot_key": "duplicate-static"}
    with pytest.raises(ForwardEvaluationPlanError, match="duplicate_snapshot_line"):
        build_forward_evaluation_plan(
            [*snapshots(), duplicate],
            history_issues={"2026079"},
            previous_issue="2026078",
            current_issue="2026079",
        )


def test_plan_rejects_incomplete_candidate_set():
    incomplete = snapshots()
    incomplete[1]["candidate_count"] = 9999

    with pytest.raises(
        ForwardEvaluationPlanError,
        match=(
            "incomplete_snapshot_candidates:dynamic_kdj:2026079:"
            "count=9999:top_n=10000"
        ),
    ):
        build_forward_evaluation_plan(
            incomplete,
            history_issues={"2026079"},
            previous_issue="2026078",
            current_issue="2026079",
        )


def test_plan_allows_empty_work_when_history_did_not_advance():
    plan = build_forward_evaluation_plan(
        snapshots(),
        history_issues=set(),
        previous_issue="2026078",
        current_issue="2026078",
    )

    assert plan == []


def test_plan_retries_due_snapshot_when_history_is_unchanged_after_failure():
    plan = build_forward_evaluation_plan(
        snapshots(),
        history_issues={"2026079"},
        previous_issue="2026079",
        current_issue="2026079",
    )

    assert [row["line_key"] for row in plan] == list(FORWARD_EVALUATION_LINE_KEYS)


def test_plan_skips_only_fully_accepted_snapshot_rows():
    accepted = [accepted_evaluation(line_key) for line_key in FORWARD_EVALUATION_LINE_KEYS]

    plan = build_forward_evaluation_plan(
        snapshots(),
        history_issues={"2026079"},
        previous_issue="2026078",
        current_issue="2026079",
        accepted_evaluations=accepted,
    )

    assert plan == []


def test_plan_retries_only_unaccepted_line_after_partial_batch_failure():
    accepted = [
        accepted_evaluation("static_100"),
        accepted_evaluation("dynamic_kdj"),
        accepted_evaluation("dynamic_kdj_near", status="leakage_guard_failed"),
    ]

    plan = build_forward_evaluation_plan(
        snapshots(),
        history_issues={"2026079"},
        previous_issue="2026079",
        current_issue="2026079",
        accepted_evaluations=accepted,
    )

    assert [row["line_key"] for row in plan] == ["dynamic_kdj_near"]


def test_plan_does_not_accept_partial_ranked_evaluation():
    accepted = [
        accepted_evaluation("static_100", candidate_count=9999),
        accepted_evaluation("dynamic_kdj"),
        accepted_evaluation("dynamic_kdj_near"),
    ]

    plan = build_forward_evaluation_plan(
        snapshots(),
        history_issues={"2026079"},
        previous_issue="2026079",
        current_issue="2026079",
        accepted_evaluations=accepted,
    )

    assert [row["line_key"] for row in plan] == ["static_100"]


def test_plan_forces_re_evaluation_after_current_issue_sync_change():
    accepted = [accepted_evaluation(line_key) for line_key in FORWARD_EVALUATION_LINE_KEYS]

    plan = build_forward_evaluation_plan(
        snapshots(),
        history_issues={"2026079"},
        previous_issue="2026079",
        current_issue="2026079",
        accepted_evaluations=accepted,
        force_evaluation_issues={"2026079"},
    )

    assert [row["line_key"] for row in plan] == list(FORWARD_EVALUATION_LINE_KEYS)


def test_plan_does_not_force_unrelated_issue():
    accepted = [accepted_evaluation(line_key) for line_key in FORWARD_EVALUATION_LINE_KEYS]

    plan = build_forward_evaluation_plan(
        snapshots(),
        history_issues={"2026079"},
        previous_issue="2026079",
        current_issue="2026079",
        accepted_evaluations=accepted,
        force_evaluation_issues={"2026080"},
    )

    assert plan == []
