import json
import smtplib
import ssl

import pytest
from dehps.notifications import p3_top100 as original
from dehps.notifications.mail import MailDeliveryError, QqMailConfig
from dehps.notifications.primary_transport import Journal, Transport, delivery_service


def email():
    return original.NotificationEmail(
        kind="post",
        issue="2026117",
        artifact_digest="a" * 64,
        replay_digest="b" * 64,
        recipient_digest=original._recipient_digest("recipient@example.test"),
        subject="registered subject",
        text="registered text",
        html="<p>registered</p>",
    )


def config():
    return QqMailConfig(
        address="sender@qq.com",
        authorization_code="synthetic-secret",
        recipient="recipient@example.test",
    )


class Smtp:
    def __init__(self, *args, failure=None, **kwargs):
        self.failure = failure
        self.sent = False
        self.closed = False

    def login(self, *args):
        if self.failure == "login":
            raise ssl.SSLError("synthetic-secret must not escape")

    def send_message(self, message):
        self.before_data()
        self.sent = True
        if self.failure == "data":
            raise smtplib.SMTPServerDisconnected("lost final DATA reply")
        self.after_data(250, b"queued synthetic transaction")
        if self.failure == "after":
            raise smtplib.SMTPServerDisconnected("accepted then disconnected")
        return {}

    def quit(self):
        if self.failure == "quit":
            raise ssl.SSLError("cleanup EOF")

    def close(self):
        self.closed = True


@pytest.mark.parametrize("failure", [None, "quit", "after"])
def test_data_acceptance_survives_cleanup_or_post_acceptance_error(tmp_path, failure):
    clients = []

    def factory(*args, **kwargs):
        clients.append(Smtp(*args, failure=failure, **kwargs))
        return clients[-1]

    journal = Journal(tmp_path, email())
    receipt = Transport(config(), journal=journal, smtp_factory=factory).send(
        subject=email().subject, text=email().text, html=email().html
    )
    assert journal.accepted()["message_id"] == receipt.message_id
    assert len(clients) == 1 and clients[0].closed
    assert not journal.safe_retry()


def test_retry_only_before_data_and_preserve_message_id(tmp_path):
    clients = []

    def factory(*args, **kwargs):
        clients.append(Smtp(*args, failure="login" if not clients else None, **kwargs))
        return clients[-1]

    journal = Journal(tmp_path, email())
    receipt = Transport(config(), journal=journal, smtp_factory=factory).send(
        subject=email().subject, text=email().text, html=email().html
    )
    records = journal.records()
    assert len(clients) == 2
    assert not clients[0].sent and clients[1].sent
    assert {r["message_id"] for r in records} == {receipt.message_id}
    assert sum(r["phase"] == "DATA_ACCEPTED" for r in records) == 1
    assert "synthetic-secret" not in json.dumps(records)


def test_data_ambiguity_never_retries(tmp_path):
    clients = []

    def factory(*args, **kwargs):
        clients.append(Smtp(*args, failure="data", **kwargs))
        return clients[-1]

    journal = Journal(tmp_path, email())
    with pytest.raises(MailDeliveryError, match="DATA failed"):
        Transport(config(), journal=journal, smtp_factory=factory).send(
            subject=email().subject, text=email().text
        )
    assert len(clients) == 1
    assert journal.accepted() is None and not journal.safe_retry()
    assert any(r["phase"] == "UNCERTAIN" for r in journal.records())


def test_safe_retry_requires_persisted_pre_data_failure_and_is_bounded(tmp_path):
    journal = Journal(tmp_path, email())
    assert not journal.safe_retry()
    journal.append("PREPARED", message_id="synthetic")
    assert not journal.safe_retry()
    for count in range(1, 7):
        journal.append("NOT_SUBMITTED", error_type="SSLError", connection_attempt=count)
        assert journal.safe_retry() == (count <= 4)


def test_old_uncertain_row_waits_without_smtp_or_mutation(tmp_path, monkeypatch):
    ledger = original.P3Top100DeliveryLedger(tmp_path / "ledger.json")
    ledger.begin(email())
    ledger.finish(email().delivery_key, status="uncertain", receipt=None)
    before = ledger.path.read_bytes()
    monkeypatch.setattr(
        Transport, "send", lambda *a, **kw: pytest.fail("SMTP forbidden")
    )
    service = delivery_service(original, journal_root=tmp_path / "receipts")(
        config(), ledger=ledger
    )
    assert service.deliver(email())["status"] == "WAITING_TRANSPORT_RECONCILIATION"
    assert ledger.path.read_bytes() == before


def test_accepted_receipt_recovers_lost_ledger_ack_without_resend(
    tmp_path, monkeypatch
):
    ledger = original.P3Top100DeliveryLedger(tmp_path / "ledger.json")
    ledger.begin(email())
    ledger.finish(email().delivery_key, status="uncertain", receipt=None)
    before = ledger.path.read_bytes()
    Journal(tmp_path / "receipts", email()).append(
        "DATA_ACCEPTED", smtp_code=250, message_id="synthetic"
    )
    monkeypatch.setattr(
        Transport, "send", lambda *a, **kw: pytest.fail("SMTP forbidden")
    )
    service = delivery_service(original, journal_root=tmp_path / "receipts")(
        config(), ledger=ledger
    )
    assert service.deliver(email())["status"] == "ALREADY_SENT_TRANSPORT_RECEIPT"
    assert ledger.path.read_bytes() == before


def test_corrupt_receipt_fails_closed(tmp_path):
    journal = Journal(tmp_path, email())
    journal.append("DATA_ACCEPTED", smtp_code=250, message_id="synthetic")
    path = next(journal.path.glob("*.json"))
    path.write_text("{}")
    with pytest.raises(ValueError, match="digest differs"):
        journal.accepted()
