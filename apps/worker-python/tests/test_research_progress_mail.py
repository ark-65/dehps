from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from dehps.notifications.mail import MailDeliveryReceipt, QqMailConfig
from dehps.notifications.research_progress import deliver_report, render_report


NOW = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)


def _sources(tmp_path, *, heartbeat=NOW, matching=True):
    status_path = tmp_path / "status.json"
    supervisor_path = tmp_path / "supervisor.json"
    status_path.write_text(
        json.dumps(
            {
                "schema_version": "dehps-m4-information-theory-status.v1",
                "manifest_digest": "a" * 64,
                "snapshot_digest": "b" * 64,
                "goal": "M4_INFORMATION_THEORY_EVIDENCE",
                "current_phase": "M4-P3",
                "current_state": "DEPENDENCY_WAIT",
                "old_training_mainline": "FROZEN",
                "next_ready_task": None,
                "progress": {
                    "engineering_percent": 43,
                    "evidence_percent": 25,
                    "historical_walk_forward": {"completed": 0, "total": None},
                },
                "blocked_by": [{"target_key": "needed:FACT", "required_status": "available"}],
            }
        )
    )
    supervisor_path.write_text(
        json.dumps(
            {
                "schema_version": "dehps-research-evidence-supervisor-state.v1",
                "manifest_digest": "a" * 64,
                "snapshot_digest": ("b" if matching else "c") * 64,
                "heartbeat_at": heartbeat.isoformat(),
                "task_key": "last-task",
                "execution_id": "execution-1",
            }
        )
    )
    return status_path, supervisor_path


def test_report_uses_matching_projection_and_labels_wait(tmp_path):
    status, supervisor = _sources(tmp_path)
    report = render_report(now=NOW, status_path=status, supervisor_path=supervisor)
    assert report.source_status == "CURRENT"
    assert "当前无可执行的下一训练任务" in report.text
    assert "旧训练主线：FROZEN" in report.text
    assert "历史逐期评估投影：0/未定" in report.text


def test_mismatch_or_stale_projection_cannot_look_like_fresh_training(tmp_path):
    status, supervisor = _sources(tmp_path, matching=False)
    report = render_report(now=NOW, status_path=status, supervisor_path=supervisor)
    assert report.source_status == "UNAVAILABLE"
    assert "无法核实研究进度" in report.text
    status, supervisor = _sources(tmp_path, heartbeat=NOW - timedelta(days=3))
    report = render_report(now=NOW, status_path=status, supervisor_path=supervisor)
    assert report.source_status == "STALE"
    assert "不代表当前训练仍在运行" in report.text


class _Mail:
    def __init__(self, *, fails=False):
        self.calls = 0
        self.fails = fails

    def send(self, **kwargs):
        self.calls += 1
        if self.fails:
            raise OSError("simulated uncertain SMTP result")
        return MailDeliveryReceipt(
            message_id="<isolated@example.test>", sender="from@example.test", recipient=kwargs["recipient"]
        )


def test_one_delivery_per_period_and_uncertain_send_requires_reconciliation(tmp_path):
    status, supervisor = _sources(tmp_path)
    report = render_report(now=NOW, status_path=status, supervisor_path=supervisor)
    config = QqMailConfig(address="from@example.test", authorization_code="isolated", recipient="to@example.test")
    ledger = tmp_path / "notifications" / "ledger.json"
    artifacts = tmp_path / "reports"
    mail = _Mail()
    first = deliver_report(report, config=config, ledger_path=ledger, report_dir=artifacts, mail_service=mail)
    second = deliver_report(report, config=config, ledger_path=ledger, report_dir=artifacts, mail_service=mail)
    assert first["status"] == "SMTP_RETURNED"
    assert second["status"] == "ALREADY_SENT"
    assert mail.calls == 1
    entry = json.loads(ledger.read_text())["periods"][report.period]
    assert entry["status"] == "smtp_returned"
    assert len(list(artifacts.glob("*.json"))) == 1

    failed_ledger = tmp_path / "failed" / "ledger.json"
    failed_mail = _Mail(fails=True)
    with pytest.raises(OSError):
        deliver_report(report, config=config, ledger_path=failed_ledger, report_dir=artifacts, mail_service=failed_mail)
    with pytest.raises(ValueError, match="manual reconciliation"):
        deliver_report(report, config=config, ledger_path=failed_ledger, report_dir=artifacts, mail_service=failed_mail)
    assert failed_mail.calls == 1
