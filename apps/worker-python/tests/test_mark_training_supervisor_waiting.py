from __future__ import annotations

import json

import pytest

from scripts.mark_training_supervisor_waiting import (
    find_status_path,
    waiting_status_payload,
)


def running_status(pid: int = 12345) -> dict:
    return {
        "run_id": "run-1",
        "pid": pid,
        "status": "running",
        "latest_progress": {
            "round": 8,
            "target_index": 100,
            "target_total": 100,
        },
    }


def test_waiting_status_payload_marks_explicit_resume_boundary():
    payload = waiting_status_payload(
        running_status(),
        expected_pid=12345,
        history_issue="2026078",
        pending_issue="2026079",
    )

    assert payload["status"] == "waiting_for_forward_issue"
    assert payload["forward_wait"] == {
        "protocol": "dehps-forward-evidence-wait-v1",
        "status": "awaiting_new_forward_issue",
        "history_latest_issue": "2026078",
        "next_pending_issue": "2026079",
        "resume_condition": "history_latest_issue_reaches_pending_issue",
        "process_active": False,
        "selection_changed": False,
        "promotion_allowed": False,
    }


def test_waiting_status_payload_rejects_partial_round_and_nonfuture_issue():
    partial = running_status()
    partial["latest_progress"]["target_index"] = 99

    with pytest.raises(ValueError, match="durable_target_boundary"):
        waiting_status_payload(
            partial,
            expected_pid=12345,
            history_issue="2026078",
            pending_issue="2026079",
        )
    with pytest.raises(ValueError, match="pending_issue_not_future"):
        waiting_status_payload(
            running_status(),
            expected_pid=12345,
            history_issue="2026079",
            pending_issue="2026079",
        )


def test_find_status_path_uses_matching_pid(tmp_path):
    wrong = tmp_path / "training-supervisor-wrong.json"
    right = tmp_path / "training-supervisor-right.json"
    wrong.write_text(json.dumps(running_status(99999)), encoding="utf-8")
    right.write_text(json.dumps(running_status(12345)), encoding="utf-8")

    assert find_status_path(output_dir=tmp_path, expected_pid=12345) == right
