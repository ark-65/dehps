from __future__ import annotations

import json
import sys

import pytest

from scripts.mark_training_supervisor_waiting import (
    find_status_path,
    main,
    update_waiting_report,
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


def test_update_waiting_report_syncs_lifecycle_fields(tmp_path):
    report_path = tmp_path / "training-supervisor-run-1.md"
    report_path.write_text(
        "# DEHPS 24h Training Supervisor Report\n\n"
        "- Updated at: 2026-07-11T13:58:50\n"
        "- Status: running\n"
        "- Train mode: `expanding`\n",
        encoding="utf-8",
    )

    updated_path = update_waiting_report(
        {
            "report_path": str(report_path),
            "updated_at": "2026-07-11T14:26:35",
            "status": "waiting_for_forward_issue",
        }
    )

    assert updated_path == report_path
    assert report_path.read_text(encoding="utf-8") == (
        "# DEHPS 24h Training Supervisor Report\n\n"
        "- Updated at: 2026-07-11T14:26:35\n"
        "- Status: waiting_for_forward_issue\n"
        "- Train mode: `expanding`\n"
    )


def test_main_marks_supervisor_and_stopped_heavy_job_waiting(tmp_path, monkeypatch, capsys):
    dead_pid = 999_999_999
    output_dir = tmp_path / "optimization"
    output_dir.mkdir()
    status_path = output_dir / "training-supervisor-run-1.json"
    report_path = output_dir / "training-supervisor-run-1.md"
    report_path.write_text(
        "# DEHPS 24h Training Supervisor Report\n\n"
        "- Updated at: 2026-07-11T13:58:50\n"
        "- Status: running\n",
        encoding="utf-8",
    )
    initial_status = running_status(dead_pid)
    initial_status["report_path"] = str(report_path)
    status_path.write_text(json.dumps(initial_status), encoding="utf-8")
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = lock_path.with_name(f"{lock_path.name}.json")
    metadata_path.write_text(
        json.dumps(
            {
                "owner": "training-supervisor",
                "pid": dead_pid,
                "status": "running",
                "context": {"train_window": 900},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mark_training_supervisor_waiting.py",
            "--expected-pid",
            str(dead_pid),
            "--history-issue",
            "2026078",
            "--pending-issue",
            "2026079",
            "--output-dir",
            str(output_dir),
            "--heavy-job-lock-path",
            str(lock_path),
        ],
    )

    main()

    supervisor = json.loads(status_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    emitted = json.loads(capsys.readouterr().out)
    assert supervisor["status"] == "waiting_for_forward_issue"
    assert metadata["status"] == "waiting_for_forward_issue"
    assert metadata["context"]["forward_wait"]["next_pending_issue"] == "2026079"
    assert emitted["heavy_job_metadata_status"] == "waiting_for_forward_issue"
    assert emitted["report_path"] == str(report_path)
    report = report_path.read_text(encoding="utf-8")
    assert "- Updated at: " + supervisor["updated_at"] in report
    assert "- Status: waiting_for_forward_issue" in report
