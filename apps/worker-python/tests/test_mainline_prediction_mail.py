from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import islice, combinations
from pathlib import Path

import pytest

from dehps.notifications.mail import MailDeliveryError, MailDeliveryReceipt, QqMailConfig
from dehps.notifications.mainline_prediction import (
    MainlinePredictionMailError,
    MainlinePredictionNotificationService,
    PredictionDeliveryStateError,
    PredictionMailDeliveryLedger,
    compile_mainline_prediction_email,
    require_pre_draw_delivery_window,
)


RECIPIENT = "receiver@vip.qq.com"
AUTHORIZATION_CODE = "abcdefghijklmnop"


def _payload() -> dict:
    candidate_numbers = list(islice(combinations(range(1, 34), 6), 100))
    return {
        "status": "waiting_draw",
        "issue": "2026083",
        "as_of_issue": "2026082",
        "generated_at": "2026-07-20T09:52:13+08:00",
        "lines": [
            {
                "line_key": "static_100",
                "status": "pending",
                "prediction_run_key": "static_100:2026083:snapshot",
                "prediction_fingerprint": "a" * 64,
                "model_version": "static-v1",
                "parameter_version": "config-1",
                "ranking_contract": "score_desc_combination_asc",
                "candidate_count": 10000,
                "top_candidates": [
                    {
                        "rank": rank,
                        "red_numbers": list(numbers),
                        "score": 1.0 - rank / 1000,
                    }
                    for rank, numbers in enumerate(candidate_numbers, start=1)
                ],
            },
            {
                "line_key": "dynamic_kdj",
                "status": "pending",
                "top_candidates": [
                    {"rank": 1, "red_numbers": [28, 29, 30, 31, 32, 33], "score": 9.0}
                ],
            },
        ],
    }


class RecordingMailService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    def send(self, **kwargs) -> MailDeliveryReceipt:
        self.calls.append(kwargs)
        if self.fail:
            raise MailDeliveryError("sanitized SMTP failure")
        return MailDeliveryReceipt(
            message_id="<message@example.com>",
            sender="sender@qq.com",
            recipient=kwargs["recipient"],
        )


def _config() -> QqMailConfig:
    return QqMailConfig(
        address="sender@qq.com",
        authorization_code=AUTHORIZATION_CODE,
        recipient=RECIPIENT,
    )


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 7, 21, 10, 15, tzinfo=timezone.utc),  # Tuesday 18:15 Beijing
        datetime(2026, 7, 23, 12, 30, tzinfo=timezone.utc),  # Thursday 20:30 Beijing
        datetime(2026, 7, 26, 10, 15, tzinfo=timezone.utc),  # Sunday 18:15 Beijing
    ],
)
def test_pre_draw_delivery_window_accepts_draw_days(now: datetime) -> None:
    assert require_pre_draw_delivery_window(now).tzinfo is not None


@pytest.mark.parametrize(
    "now, message",
    [
        (datetime(2026, 7, 21, 10, 14, tzinfo=timezone.utc), "has not opened"),
        (datetime(2026, 7, 21, 13, 15, tzinfo=timezone.utc), "closed"),
        (datetime(2026, 7, 20, 10, 15, tzinfo=timezone.utc), "Tuesday"),
    ],
)
def test_pre_draw_delivery_window_fails_closed(now: datetime, message: str) -> None:
    with pytest.raises(MainlinePredictionMailError, match=message):
        require_pre_draw_delivery_window(now)


def test_compiler_emits_only_static_top100_with_risk_language() -> None:
    email = compile_mainline_prediction_email(_payload(), recipient=RECIPIENT)

    assert email.issue == "2026083"
    assert email.as_of_issue == "2026082"
    assert email.candidate_count == 100
    assert email.subject == "[DEHPS][实验性] 双色球 2026083 主线预测 Top 100"
    assert email.text.count("\n0") >= 99
    assert "dynamic_kdj" not in email.text
    assert "不保证中奖" in email.text
    assert "历史表现不能证明未来结果" in email.text
    assert "禁止未成年人购彩" in email.text
    assert email.html.count("<tr>") == 101


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda payload: payload["lines"][0].update(status="evaluated"), "pending"),
        (lambda payload: payload["lines"][0]["top_candidates"].pop(), "ranks 1 through 100"),
        (
            lambda payload: payload["lines"][0]["top_candidates"][1].update(
                red_numbers=payload["lines"][0]["top_candidates"][0]["red_numbers"]
            ),
            "duplicate combinations",
        ),
        (
            lambda payload: payload["lines"][0].update(prediction_fingerprint=""),
            "fingerprint",
        ),
    ],
)
def test_compiler_rejects_incomplete_or_untrusted_mainline(mutation, message: str) -> None:
    payload = _payload()
    mutation(payload)

    with pytest.raises(MainlinePredictionMailError, match=message):
        compile_mainline_prediction_email(payload, recipient=RECIPIENT)


def test_delivery_is_idempotent_after_sent_ledger_state(tmp_path: Path) -> None:
    mail = RecordingMailService()
    ledger = PredictionMailDeliveryLedger(tmp_path / "ledger.json")
    service = MainlinePredictionNotificationService(
        _config(),
        mail_service=mail,  # type: ignore[arg-type]
        ledger=ledger,
    )
    now = datetime(2026, 7, 21, 10, 15, tzinfo=timezone.utc)

    first = service.deliver(_payload(), now=now)
    second = service.deliver(_payload(), now=now)

    assert first.status == "sent"
    assert second.status == "already_sent"
    assert len(mail.calls) == 1
    assert mail.calls[0]["recipient"] == RECIPIENT
    state = json.loads((tmp_path / "ledger.json").read_text())
    assert state["deliveries"][first.delivery_key]["status"] == "sent"
    assert state["deliveries"][first.delivery_key]["candidate_count"] == 100


def test_ambiguous_smtp_failure_is_not_retried_automatically(tmp_path: Path) -> None:
    mail = RecordingMailService(fail=True)
    ledger = PredictionMailDeliveryLedger(tmp_path / "ledger.json")
    service = MainlinePredictionNotificationService(
        _config(),
        mail_service=mail,  # type: ignore[arg-type]
        ledger=ledger,
    )
    now = datetime(2026, 7, 21, 10, 15, tzinfo=timezone.utc)

    with pytest.raises(MailDeliveryError, match="sanitized"):
        service.deliver(_payload(), now=now)
    with pytest.raises(PredictionDeliveryStateError, match="uncertain"):
        service.deliver(_payload(), now=now)

    assert len(mail.calls) == 1


def test_corrupt_delivery_ledger_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text('{"protocol":"unknown","deliveries":{}}')

    with pytest.raises(PredictionDeliveryStateError, match="schema"):
        PredictionMailDeliveryLedger(path).status("delivery-key")


def test_scheduled_delivery_requires_explicit_recipient() -> None:
    config = QqMailConfig(
        address="sender@qq.com",
        authorization_code=AUTHORIZATION_CODE,
    )

    with pytest.raises(MainlinePredictionMailError, match="RECIPIENT"):
        MainlinePredictionNotificationService(config)


def test_systemd_timer_is_exactly_three_hours_before_official_draw() -> None:
    root = Path(__file__).resolve().parents[3]
    timer = (root / "infra/systemd/dehps-mainline-prediction-mail.timer").read_text()
    service = (root / "infra/systemd/dehps-mainline-prediction-mail.service").read_text()

    assert "OnCalendar=Tue,Thu,Sun *-*-* 18:15:00 Asia/Shanghai" in timer
    assert "Persistent=true" in timer
    assert "mail mainline-prediction --send" in service
    assert "EnvironmentFile=/home/ark/workspace/dehps/.env" in service
