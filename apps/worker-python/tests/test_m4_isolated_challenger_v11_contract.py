from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)


def test_frozen_surface_has_exact_38_tasks_and_artifacts() -> None:
    assert len(contract.TASK_TEMPLATES) == 42
    assert len(contract.ARTIFACT_TYPES) == 43
    context = contract.render_context(source_max_issue="2026100")
    assert len(contract.rendered_task_keys(context)) == 42
    assert len(set(contract.rendered_task_keys(context))) == 42
    assert contract.WORKER_COUNT == 18
    assert contract.LEGAL_RED_COMBINATION_COUNT == 1_107_568


def test_schedule_is_tuesday_thursday_sunday_and_rolls_year() -> None:
    dates = contract.draw_dates(2026)
    assert dates
    assert {item.weekday() for item in dates} == {1, 3, 6}
    last = f"2026{len(dates):03d}"
    assert contract.next_official_issue(last) == "2027001"
    assert contract.issue_draw_date("2027001") == contract.draw_dates(2027)[0]
    schedule = contract.schedule_for_issue("2026001")
    assert schedule["selection_cutoff"].hour == 16
    assert schedule["selection_cutoff"].minute == 40
    assert schedule["freeze_deadline"].minute == 45
    assert schedule["predraw_send"].hour == 17


def test_target_projection_rejects_non_next_issue() -> None:
    with pytest.raises(contract.IsolatedChallengerContractError):
        contract.render_context(source_max_issue="2026100", target_issue="2026102")


def test_target_projection_deadline_boundary_and_year_rollover() -> None:
    candidate = contract.next_official_issue("2026100")
    deadline = datetime.combine(
        contract.issue_draw_date(candidate),
        contract.PREDRAW_SEND_TIME,
        contract.TIMEZONE,
    )
    at_deadline = contract.target_issue_projection(
        source_max_issue="2026100", projection_time=deadline
    )
    after_deadline = contract.target_issue_projection(
        source_max_issue="2026100", projection_time=deadline + timedelta(microseconds=1)
    )
    assert at_deadline["target_issue"] == candidate
    assert after_deadline["target_issue"] == contract.next_official_issue(candidate)

    last_2026 = f"2026{len(contract.draw_dates(2026)):03d}"
    first_2027 = contract.next_official_issue(last_2026)
    first_deadline = datetime.combine(
        contract.issue_draw_date(first_2027),
        contract.PREDRAW_SEND_TIME,
        contract.TIMEZONE,
    )
    rollover = contract.target_issue_projection(
        source_max_issue=last_2026,
        projection_time=first_deadline + timedelta(microseconds=1),
    )
    assert first_2027 == "2027001"
    assert rollover["target_issue"] == "2027002"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "QUIESCENT"),
        ({"ActiveState": "active", "SubState": "running"}, "PREEMPT"),
        ({"query_ok": False}, "PREEMPT"),
        ({"LoadState": "not-found"}, "PREEMPT"),
        ({"MainPID": 1}, "PREEMPT"),
    ],
)
def test_formal_p3_activity_function_is_total_and_fail_closed(
    overrides: dict[str, object], expected: str
) -> None:
    observation: dict[str, object] = {
        "query_ok": True,
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "SubState": "dead",
        "MainPID": 0,
        "ControlPID": 0,
        "observed_monotonic_ns": 1,
    }
    observation.update(overrides)
    assert contract.formal_p3_activity_state(observation) == expected


def test_draw_fixture_date_is_not_inferred_from_formal_p3() -> None:
    first = contract.draw_dates(2026)[0]
    assert isinstance(first, date)
    assert contract.issue_draw_date("2026001") == first
