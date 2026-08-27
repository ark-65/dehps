from __future__ import annotations

import json
from itertools import combinations, islice
from pathlib import Path

import pytest
from dehps.notifications import isolated_challenger_v11 as mail
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_artifacts as artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_reporting as reporting,
)


def _fake_configuration() -> mail.MailRuntimeConfiguration:
    return mail.MailRuntimeConfiguration(
        smtp_host="fake.invalid",
        smtp_port=0,
        tls_mode="NONE",
        sender="",
        recipients=(),
        username="",
        password="",
        transport_mode=mail.TRANSPORT_FAKE,
    )


def _external_configuration() -> mail.MailRuntimeConfiguration:
    return mail.MailRuntimeConfiguration(
        smtp_host="smtp.qq.com",
        smtp_port=465,
        tls_mode=mail.TLS_IMPLICIT,
        sender="sender@qq.com",
        recipients=("receiver@example.com",),
        username="sender@qq.com",
        password="secret-never-serialized",
    )


def test_fake_transport_makes_no_external_sent_receipt() -> None:
    config = _fake_configuration()
    envelope = mail.compile_envelope(
        configuration=config,
        mail_kind="DAILY_24H_RESEARCH_SUMMARY",
        target_identity="20260827",
        subject="simulation",
        body="result blind",
        allow_fake=True,
    )
    receipt = mail.simulate_delivery(
        envelope=envelope,
        mail_envelope_digest="a" * 64,
        mail_replay_digest="b" * 64,
        mail_configuration_digest="c" * 64,
    )
    assert receipt["state"] == "SIMULATED"
    assert receipt["simulation"] is True
    assert receipt["attempt_count"] == 0
    assert receipt["smtp_final_reply_code"] is None


def test_mail_configuration_artifact_rejects_digest_valid_secret_drift() -> None:
    value = mail.build_configuration_artifact(
        task_key="m4-isolated-24h-challenger-v11-mail-configuration",
        git_commit="a" * 40,
        source_contract_digest="b" * 64,
        parent_digests=("c" * 64,),
        configuration_body=mail.fake_configuration_body(),
    )
    corrupted = json.loads(json.dumps(value))
    corrupted["body"]["credential_secret_serialized"] = True
    type_body = {
        key: item
        for key, item in corrupted["body"].items()
        if key not in artifacts.COMMON_BODY_KEYS
    }
    corrupted["body"]["output_digest"] = mail.contract.domain_digest(
        type_body,
        domain="dehps.m4.isolated-24h-challenger.output."
        "M4IsolatedMailConfigurationV11.v11",
    )
    envelope = dict(corrupted)
    envelope.pop("artifact_digest")
    corrupted["artifact_digest"] = mail.contract.domain_digest(
        envelope, domain=mail.contract.ARTIFACT_DOMAIN
    )
    with pytest.raises(artifacts.IsolatedArtifactError, match="secret_boundary"):
        artifacts.validate_artifact(corrupted)


def test_receipt_validator_rejects_fake_sent_and_bad_ack() -> None:
    body = mail.simulate_delivery(
        envelope=mail.compile_envelope(
            configuration=_fake_configuration(),
            mail_kind="PREDRAW_TOP100",
            target_identity="2026101",
            subject="s",
            body="b",
            allow_fake=True,
        ),
        mail_envelope_digest="a" * 64,
        mail_replay_digest="b" * 64,
        mail_configuration_digest="c" * 64,
    )
    body.update(
        {
            "state": "SENT",
            "simulation": False,
            "transport_mode": "EXTERNAL_QQ_SMTP",
            "attempt_count": 1,
            "smtp_transaction_started_at": "2026-08-27T00:00:00+00:00",
            "smtp_final_reply_code": 250,
            "smtp_data_accepted_at": "2026-08-27T00:00:01+00:00",
            "smtp_final_reply_bytes_digest": "d" * 64,
            "tls_peer_certificate_sha256": "e" * 64,
        }
    )
    artifacts.validate_delivery_receipt_body(body)
    body["smtp_final_reply_code"] = 2500
    with pytest.raises(artifacts.IsolatedArtifactError, match="sent_condition"):
        artifacts.validate_delivery_receipt_body(body)


def test_delivery_ledger_uncertain_is_terminal_and_not_retried(tmp_path: Path) -> None:
    ledger = mail.DeliveryLedger(tmp_path / "ledger.json")
    key = "a" * 64
    ledger.transition(key, expected=None, state="SENDING", evidence={})
    ledger.transition(key, expected="SENDING", state="UNCERTAIN", evidence={})
    with pytest.raises(mail.IsolatedMailError, match="not_retryable"):
        ledger.transition(key, expected=None, state="SENDING", evidence={})


def test_external_provider_ack_compiles_sent_without_serializing_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Socket:
        def getpeercert(self, *, binary_form: bool) -> bytes:
            assert binary_form is True
            return b"certificate"

    class SMTP:
        instances = 0

        def __init__(self, *args, **kwargs) -> None:
            SMTP.instances += 1
            self.sock = Socket()

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def ehlo(self):
            return 250, b"ok"

        def login(self, username: str, password: str):
            assert username == "sender@qq.com"
            assert password == "secret-never-serialized"
            return 235, b"ok"

        def mail(self, sender: str):
            return 250, b"ok"

        def rcpt(self, recipient: str):
            return 250, b"ok"

        def data(self, payload: bytes):
            assert b"X-DEHPS-Delivery-Key" in payload
            return 250, b"queued as QQ-123"

    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", SMTP)
    config = _external_configuration()
    envelope = mail.compile_envelope(
        configuration=config,
        mail_kind="POSTDRAW_SETTLEMENT",
        target_identity="2026101",
        subject="post",
        body="gross, tax, net and ROI",
    )
    receipt = mail.send_external_once(
        configuration=config,
        envelope=envelope,
        mail_envelope_digest="a" * 64,
        mail_replay_digest="b" * 64,
        mail_configuration_digest="c" * 64,
        ledger=mail.DeliveryLedger(tmp_path / "ledger.json"),
    )
    assert SMTP.instances == 1
    assert receipt["state"] == "SENT"
    assert receipt["smtp_final_reply_code"] == 250
    serialized = json.dumps(receipt)
    assert "secret-never-serialized" not in serialized
    assert "receiver@example.com" not in serialized
    replayed = mail.send_external_once(
        configuration=config,
        envelope=envelope,
        mail_envelope_digest="a" * 64,
        mail_replay_digest="b" * 64,
        mail_configuration_digest="c" * 64,
        ledger=mail.DeliveryLedger(tmp_path / "ledger.json"),
    )
    assert replayed == receipt
    assert SMTP.instances == 1


def test_cny200_accounting_and_cny10000_tax_boundary_are_explicit() -> None:
    winning_reds = (1, 2, 3, 4, 5, 6)
    winning_blue = 16
    losing = tuple(
        (tuple(values), 1)
        for values in islice(combinations(range(7, 34), 6), 99)
    )
    tickets = ((winning_reds, winning_blue), *losing)
    exempt = reporting.settle_portfolio(
        tickets,
        winning_reds=winning_reds,
        winning_blue=winning_blue,
        first_prize_cny="10000.00",
        second_prize_cny="0.00",
    )
    assert exempt["cost_cny"] == "200.00"
    assert exempt["gross_prize_cny"] == "10000.00"
    assert exempt["estimated_tax_cny"] == "0.00"
    assert exempt["estimated_after_tax_cny"] == "10000.00"
    assert exempt["net_cny"] == "9800.00"
    assert exempt["roi"] == "49.000000"
    report = reporting.postdraw_body(
        target_issue="2026101",
        settlement=exempt,
        baseline_percentile="1.000000",
        formal_p3_comparison="PENDING_LEGAL_COMPARISON",
        prediction_digest="1" * 64,
        settlement_digest="2" * 64,
        report_digest="3" * 64,
    )
    for label in (
        "固定假设投入：人民币 200.00 元",
        "中奖毛收益：人民币 10000.00 元",
        "预计税额：人民币 0.00 元",
        "预计税后到账：人民币 10000.00 元",
        "净收益（税后到账-200）：人民币 9800.00 元",
        "ROI：49.000000",
        "实际代扣与到账金额以彩票机构和税务机关为准",
    ):
        assert label in report

    taxable = reporting.settle_portfolio(
        tickets,
        winning_reds=winning_reds,
        winning_blue=winning_blue,
        first_prize_cny="10000.01",
        second_prize_cny="0.00",
    )
    assert taxable["estimated_tax_cny"] == "2000.00"
    assert taxable["estimated_after_tax_cny"] == "8000.01"
    assert taxable["net_cny"] == "7800.01"


def test_crash_after_network_intent_becomes_uncertain_without_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ForbiddenSMTP:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("crash recovery must not call SMTP")

    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", ForbiddenSMTP)
    config = _external_configuration()
    envelope = mail.compile_envelope(
        configuration=config,
        mail_kind="DAILY_24H_RESEARCH_SUMMARY",
        target_identity="20260827",
        subject="daily",
        body="health and replay",
    )
    ledger = mail.DeliveryLedger(tmp_path / "ledger.json")
    ledger.transition(
        envelope.delivery_key,
        expected=None,
        state="SENDING",
        evidence={
            "attempt_count": 1,
            "smtp_transaction_started_at": "2026-08-27T00:00:00+00:00",
        },
    )
    receipt = mail.send_external_once(
        configuration=config,
        envelope=envelope,
        mail_envelope_digest="a" * 64,
        mail_replay_digest="b" * 64,
        mail_configuration_digest="c" * 64,
        ledger=ledger,
    )
    assert receipt["state"] == "UNCERTAIN"
    assert receipt["error_code_or_null"] == "CRASH_AFTER_NETWORK_INTENT"


def test_post_call_failure_becomes_uncertain_without_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Socket:
        def getpeercert(self, *, binary_form: bool) -> bytes:
            return b"certificate"

    class SMTP:
        def __init__(self, *args, **kwargs) -> None:
            self.sock = Socket()

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def ehlo(self):
            return 250, b"ok"

        def login(self, username: str, password: str):
            return 235, b"ok"

        def mail(self, sender: str):
            return 250, b"ok"

        def rcpt(self, recipient: str):
            return 250, b"ok"

        def data(self, payload: bytes):
            raise TimeoutError("ambiguous after call")

    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", SMTP)
    config = _external_configuration()
    envelope = mail.compile_envelope(
        configuration=config,
        mail_kind="PREDRAW_TOP100",
        target_identity="2026101",
        subject="pre",
        body="top100",
    )
    ledger = mail.DeliveryLedger(tmp_path / "ledger.json")
    receipt = mail.send_external_once(
        configuration=config,
        envelope=envelope,
        mail_envelope_digest="a" * 64,
        mail_replay_digest="b" * 64,
        mail_configuration_digest="c" * 64,
        ledger=ledger,
    )
    assert receipt["state"] == "UNCERTAIN"
    assert ledger.get(envelope.delivery_key)["state"] == "UNCERTAIN"
    with pytest.raises(mail.IsolatedMailError, match="not_retryable"):
        mail.send_external_once(
            configuration=config,
            envelope=envelope,
            mail_envelope_digest="a" * 64,
            mail_replay_digest="b" * 64,
            mail_configuration_digest="c" * 64,
            ledger=ledger,
        )
