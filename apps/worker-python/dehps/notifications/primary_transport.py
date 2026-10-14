"""Additive SMTP receipts for the retained primary notification consumer.

The legacy report, ledger protocol and source contracts are not modified.
DATA acceptance is durable before QUIT. An old unknown attempt cannot be
retried merely because the sender or recipient did not find a message.
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from dehps.notifications.mail import (
    QQ_SMTP_HOST,
    QQ_SMTP_SSL_PORT,
    MailDeliveryError,
    MailDeliveryReceipt,
    QqMailService,
)


def digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def identity(email: Any) -> dict[str, str]:
    return {
        name: str(getattr(email, name))
        for name in (
            "issue",
            "kind",
            "delivery_key",
            "artifact_digest",
            "replay_digest",
            "recipient_digest",
        )
    } | {
        "content_digest": digest(
            {"subject": email.subject, "text": email.text, "html": email.html}
        )
    }


class Journal:
    def __init__(self, root: Path, email: Any) -> None:
        self.identity = identity(email)
        self.path = root / self.identity["delivery_key"]
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.attempt = uuid4().hex

    def append(self, phase: str, **facts: Any) -> dict[str, Any]:
        value = {
            "schema": "primary-smtp-receipt.v1",
            "identity": self.identity,
            "attempt": self.attempt,
            "at": datetime.now(UTC).isoformat(),
            "phase": phase,
            **facts,
        }
        raw = (json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n").encode()
        target = self.path / (sha256(raw).hexdigest() + ".json")
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        directory = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return value

    def records(self) -> list[dict[str, Any]]:
        values = []
        for path in self.path.glob("*.json"):
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != path.stem:
                raise ValueError("transport receipt digest differs")
            value = json.loads(raw)
            if (
                value.get("schema") != "primary-smtp-receipt.v1"
                or value.get("identity") != self.identity
            ):
                raise ValueError("transport receipt identity differs")
            values.append(value)
        return values

    def accepted(self) -> dict[str, Any] | None:
        values = []
        for value in self.records():
            if value.get("phase") == "DATA_ACCEPTED":
                if value.get("smtp_code") != 250 or not value.get("message_id"):
                    raise ValueError("transport acceptance receipt incomplete")
                values.append(value)
        if len(values) > 1:
            raise ValueError("multiple accepted primary SMTP attempts")
        return values[0] if values else None

    def safe_retry(self) -> bool:
        records = self.records()
        if any(
            r["phase"] in ("DATA_STARTED", "UNCERTAIN", "DATA_ACCEPTED")
            for r in records
        ):
            return False
        failures = [r for r in records if r["phase"] == "NOT_SUBMITTED"]
        transient = {
            "SSLError",
            "SSLEOFError",
            "SMTPServerDisconnected",
            "TimeoutError",
            "ConnectionResetError",
            "ConnectionRefusedError",
            "OSError",
        }
        prepared = {r["attempt"] for r in records if r["phase"] == "PREPARED"}
        failed = {r["attempt"] for r in failures}
        # At most six connections across timer invocations for this exact issue.
        return (
            bool(failures)
            and len(failures) <= 4
            and prepared == failed
            and all(r.get("error_type") in transient for r in failures)
        )


class Transport(QqMailService):
    def __init__(
        self, config: Any, *, journal: Journal, smtp_factory: Any = None
    ) -> None:
        super().__init__(config)
        self.journal = journal
        self.smtp_factory = smtp_factory

    def send(
        self,
        *,
        subject: str,
        text: str,
        html: str | None = None,
        recipient: str | None = None,
    ) -> MailDeliveryReceipt:
        message = self._build_message(
            subject=subject, text=text, html=html, recipient=recipient
        )
        message_id = str(message["Message-ID"])
        journal = self.journal
        # This record is fsynced before any connection or DATA transmission.
        journal.append("PREPARED", message_id=message_id)
        for connection_attempt in (1, 2):
            client = None
            data_started = False
            accepted = False
            stage = "CONNECT"

            def before_data(ordinal: int = connection_attempt) -> None:
                nonlocal data_started, stage
                stage = "DATA"
                journal.append(
                    "DATA_STARTED",
                    message_id=message_id,
                    connection_attempt=ordinal,
                )
                data_started = True

            def after_data(
                code: int, response: bytes, ordinal: int = connection_attempt
            ) -> None:
                nonlocal accepted
                if code == 250:
                    # Record acceptance before send_message returns and QUIT.
                    journal.append(
                        "DATA_ACCEPTED",
                        message_id=message_id,
                        smtp_code=code,
                        reply_sha256=sha256(response).hexdigest(),
                        connection_attempt=ordinal,
                    )
                    accepted = True

            class Smtp(smtplib.SMTP_SSL):
                def data(self, msg: Any) -> tuple[int, bytes]:
                    before_data()
                    code, response = super().data(msg)
                    after_data(code, response)
                    return code, response

            try:
                factory = self.smtp_factory or Smtp
                client = factory(
                    QQ_SMTP_HOST,
                    QQ_SMTP_SSL_PORT,
                    timeout=self.config.timeout_seconds,
                    context=ssl.create_default_context(),
                )
                # Injectable factories use these hooks for isolated reproductions.
                if self.smtp_factory is not None:
                    client.before_data = before_data
                    client.after_data = after_data
                stage = "LOGIN"
                client.login(
                    self.config.address,
                    self.config.authorization_code.get_secret_value(),
                )
                stage = "ENVELOPE"
                refused = client.send_message(message)
                if refused:
                    raise MailDeliveryError("primary SMTP recipient refused")
                if not accepted:
                    raise MailDeliveryError("primary SMTP acceptance unobserved")
            except (OSError, smtplib.SMTPException, MailDeliveryError) as exc:
                if accepted:
                    # An exception after observed DATA250 cannot undo acceptance.
                    journal.append(
                        "AFTER_ACCEPTANCE_ERROR",
                        message_id=message_id,
                        error_type=type(exc).__name__,
                    )
                else:
                    journal.append(
                        "UNCERTAIN" if data_started else "NOT_SUBMITTED",
                        message_id=message_id,
                        stage=stage,
                        connection_attempt=connection_attempt,
                        error_type=type(exc).__name__,
                    )
                    retry = (
                        not data_started
                        and connection_attempt == 1
                        and isinstance(exc, (OSError, smtplib.SMTPServerDisconnected))
                    )
                    if not retry:
                        raise MailDeliveryError(
                            "primary SMTP "
                            + stage
                            + " failed ("
                            + type(exc).__name__
                            + ")"
                        ) from None
                    continue
            finally:
                if client is not None:
                    try:
                        # Explicit cleanup: QQ EOF/SSL errors on QUIT are not DATA failures.
                        client.quit()
                    except (OSError, smtplib.SMTPException) as exc:
                        journal.append(
                            "CLEANUP_ERROR",
                            message_id=message_id,
                            accepted=accepted,
                            error_type=type(exc).__name__,
                        )
                    finally:
                        try:
                            client.close()
                        except OSError as exc:
                            journal.append(
                                "CLOSE_ERROR",
                                message_id=message_id,
                                accepted=accepted,
                                error_type=type(exc).__name__,
                            )
            if accepted:
                return MailDeliveryReceipt(
                    message_id=message_id,
                    sender=self.config.address,
                    recipient=str(message["To"]),
                )
        raise MailDeliveryError("primary SMTP bounded pre-DATA attempts exhausted")


def delivery_service(
    original: Any, *, journal_root: Path, reconciliation: dict[str, Any] | None = None
) -> type:
    """Bind a single reviewed mail entry; leave the frozen delivery code intact."""
    resolutions = reconciliation or {}

    class Delivery(original.P3Top100NotificationDeliveryService):
        def deliver(self, email: Any) -> dict[str, Any]:
            if (
                original._recipient_digest(self.config.destination)
                != email.recipient_digest
            ):
                raise ValueError("primary transport recipient differs")
            with self.ledger.exclusive():
                row = self.ledger._load()["deliveries"].get(email.delivery_key)
                if row is not None and any(
                    row.get(name) != getattr(email, name)
                    for name in (
                        "issue",
                        "kind",
                        "artifact_digest",
                        "replay_digest",
                        "recipient_digest",
                    )
                ):
                    raise ValueError(
                        "primary transport original ledger identity differs"
                    )
                if row is not None and row.get("status") == "sent":
                    return {
                        "status": "ALREADY_SENT",
                        "delivery_key": email.delivery_key,
                    }
                journal = Journal(journal_root, email)
                receipt = journal.accepted()
                if receipt is not None:
                    if row is None:
                        raise ValueError(
                            "primary transport accepted receipt lacks original ledger"
                        )
                    return {
                        "status": "ALREADY_SENT_TRANSPORT_RECEIPT",
                        "delivery_key": email.delivery_key,
                        "message_id": receipt["message_id"],
                    }
                if row is not None:
                    resolution = resolutions.get(email.delivery_key)
                    safe_retry = journal.safe_retry()
                    if not resolution and not safe_retry:
                        return {
                            "status": "WAITING_TRANSPORT_RECONCILIATION",
                            "delivery_key": email.delivery_key,
                        }
                    if resolution and (
                        resolution.get("identity") != journal.identity
                        or resolution.get("original_row_digest") != digest(row)
                        or resolution.get("outcome") != "NOT_SUBMITTED"
                        or resolution.get("evidence_kind")
                        != "PROVIDER_CONFIRMED_NOT_SUBMITTED"
                        or len(resolution.get("evidence_sha256", "")) != 64
                    ):
                        raise ValueError("primary transport reconciliation differs")
                    journal.append(
                        "RECONCILIATION",
                        resolution=resolution,
                        definitive_pre_data_receipts=safe_retry,
                    )
                    # The old uncertain row is retained, not converted or deleted.
                else:
                    self.ledger.begin(email)
                transport = Transport(self.config, journal=journal)
                try:
                    receipt = transport.send(
                        subject=email.subject,
                        text=email.text,
                        html=email.html,
                        recipient=self.config.destination,
                    )
                except Exception:
                    if row is None:
                        self.ledger.finish(
                            email.delivery_key, status="uncertain", receipt=None
                        )
                    raise
                if row is None:
                    self.ledger.finish(
                        email.delivery_key, status="sent", receipt=receipt
                    )
                return {
                    "status": "SENT",
                    "delivery_key": email.delivery_key,
                    "message_id": receipt.message_id,
                }

    return Delivery
