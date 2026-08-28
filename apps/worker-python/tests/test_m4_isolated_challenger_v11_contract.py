from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)


def test_frozen_surface_has_exact_v5_tasks_and_artifacts() -> None:
    assert len(contract.TASK_TEMPLATES) == 43
    assert len(contract.ARTIFACT_TYPES) == 45
    context = contract.render_context(
        source_max_issue="2026100", source_max_draw_date="2026-08-30"
    )
    assert len(contract.rendered_task_keys(context)) == 43
    assert len(set(contract.rendered_task_keys(context))) == 43
    resolution_templates = [
        item for item in contract.TASK_TEMPLATES if item.name == "incident_resolution"
    ]
    assert len(resolution_templates) == 1
    assert resolution_templates[0].capability == (
        "M4IsolatedIncidentResolutionCapabilityV11"
    )
    assert resolution_templates[0].artifact_types == (
        "M4IsolatedIncidentResolutionV11",
        "M4IsolatedIncidentLedgerHeadV11",
    )
    assert contract.WORKER_COUNT == 18
    assert contract.LEGAL_RED_COMBINATION_COUNT == 1_107_568


def test_schedule_is_tuesday_thursday_sunday_and_rolls_year() -> None:
    dates = contract.draw_dates(2026)
    assert dates
    assert {item.weekday() for item in dates} == {1, 3, 6}
    next_date = contract.next_ssq_draw_date(date(2026, 12, 31))
    assert next_date == date(2027, 1, 3)
    assert (
        contract.next_official_issue("2026152", candidate_draw_date=next_date)
        == "2027001"
    )
    schedule = contract.schedule_for_issue("2026100", target_draw_date="2026-08-30")
    assert schedule["selection_cutoff"].hour == 16
    assert schedule["selection_cutoff"].minute == 40
    assert schedule["freeze_deadline"].minute == 45
    assert schedule["predraw_send"].hour == 17


def test_target_projection_rejects_non_next_issue() -> None:
    with pytest.raises(contract.IsolatedChallengerContractError):
        contract.render_context(
            source_max_issue="2026100",
            source_max_draw_date="2026-08-30",
            target_issue="2026102",
        )
    with pytest.raises(
        contract.IsolatedChallengerContractError,
        match="target_draw_date_not_scheduled_draw_day",
    ):
        contract.render_context(
            source_max_issue="2026099",
            source_max_draw_date="2026-08-27",
            target_issue="2026100",
            target_draw_date="2026-08-31",
            projection_time="2026-08-27T23:30:00+08:00",
        )


def test_target_projection_deadline_boundary_and_year_rollover() -> None:
    source_date = date(2026, 8, 27)
    candidate_date = date(2026, 8, 30)
    candidate = contract.next_official_issue(
        "2026099", candidate_draw_date=candidate_date
    )
    deadline = datetime.combine(
        candidate_date,
        contract.PREDRAW_SEND_TIME,
        contract.TIMEZONE,
    )
    at_deadline = contract.target_issue_projection(
        source_max_issue="2026099",
        source_max_draw_date=source_date,
        projection_time=deadline,
    )
    after_deadline = contract.target_issue_projection(
        source_max_issue="2026099",
        source_max_draw_date=source_date,
        projection_time=deadline + timedelta(microseconds=1),
    )
    assert at_deadline == {
        "source_max_issue": "2026099",
        "source_max_draw_date": "2026-08-27",
        "target_issue": "2026100",
        "target_draw_date": "2026-08-30",
        "deadline": "2026-08-30T17:00:00+08:00",
        "official_draw_time": "2026-08-30T21:15:00+08:00",
        "projection_time": "2026-08-30T17:00:00+08:00",
    }
    assert candidate == "2026100"
    assert after_deadline["target_issue"] == "2026101"
    assert after_deadline["target_draw_date"] == "2026-09-01"

    first_2027 = "2027001"
    first_deadline = datetime.combine(
        date(2027, 1, 3),
        contract.PREDRAW_SEND_TIME,
        contract.TIMEZONE,
    )
    rollover = contract.target_issue_projection(
        source_max_issue="2026152",
        source_max_draw_date="2026-12-31",
        projection_time=first_deadline + timedelta(microseconds=1),
    )
    assert first_2027 == "2027001"
    assert rollover["target_issue"] == "2027002"
    assert rollover["target_draw_date"] == "2027-01-05"


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


def test_draw_fixture_is_anchored_to_audited_history_not_annual_ordinal() -> None:
    projected = contract.target_issue_projection(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        projection_time=datetime(2026, 8, 27, 23, 30, tzinfo=contract.TIMEZONE),
    )
    assert projected["target_issue"] == "2026100"
    assert projected["target_draw_date"] == "2026-08-30"
    assert projected["target_issue"] != "2026104"
