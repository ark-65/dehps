from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import smtplib
import ssl
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_artifacts as artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)

TRANSPORT_EXTERNAL = "EXTERNAL_QQ_SMTP"
TRANSPORT_FAKE = "FAKE_EPHEMERAL"
TLS_IMPLICIT = "IMPLICIT_TLS"
LEDGER_RELATIVE_PATH = Path("runtime/isolated-24h-challenger-v11/delivery-ledger.json")


class IsolatedMailError(contract.IsolatedChallengerContractError):
    pass


@dataclass(frozen=True)
class MailRuntimeConfiguration:
    smtp_host: str
    smtp_port: int
    tls_mode: str
    sender: str
    recipients: tuple[str, ...]
    username: str
    password: str
    transport_mode: str = TRANSPORT_EXTERNAL

    @classmethod
    def from_environment(cls) -> MailRuntimeConfiguration:
        recipients = tuple(
            sorted(
                {
                    item.strip()
                    for item in os.environ.get("DEHPS_ISOLATED_V11_MAIL_TO", "").split(
                        ","
                    )
                    if item.strip()
                }
            )
        )
        return cls(
            smtp_host=os.environ.get("DEHPS_ISOLATED_V11_SMTP_HOST", "smtp.qq.com"),
            smtp_port=int(os.environ.get("DEHPS_ISOLATED_V11_SMTP_PORT", "465")),
            tls_mode=os.environ.get("DEHPS_ISOLATED_V11_SMTP_TLS", TLS_IMPLICIT),
            sender=os.environ.get("DEHPS_ISOLATED_V11_MAIL_FROM", ""),
            recipients=recipients,
            username=os.environ.get("DEHPS_ISOLATED_V11_SMTP_USERNAME", ""),
            password=os.environ.get("DEHPS_ISOLATED_V11_SMTP_PASSWORD", ""),
        )

    def validate(self, *, allow_fake: bool = False) -> None:
        if self.transport_mode == TRANSPORT_FAKE and allow_fake:
            if self.sender or self.recipients or self.username or self.password:
                raise IsolatedMailError(
                    "fake_transport_must_not_have_external_identity"
                )
            return
        if (
            self.transport_mode != TRANSPORT_EXTERNAL
            or self.smtp_host != "smtp.qq.com"
            or self.smtp_port != 465
            or self.tls_mode != TLS_IMPLICIT
            or not self.sender
            or not self.recipients
            or not self.username
            or not self.password
        ):
            raise IsolatedMailError("mail_configuration_invalid")
        if self.username != self.sender:
            raise IsolatedMailError("mail_sender_username_changed")

    @property
    def sender_address_digest(self) -> str:
        return hashlib.sha256(self.sender.strip().lower().encode("utf-8")).hexdigest()

    @property
    def recipient_set_digest(self) -> str:
        return contract.domain_digest(
            [item.strip().lower() for item in self.recipients],
            domain="dehps.m4.isolated-24h-challenger.recipient-set.v11",
        )

    @property
    def configuration_digest(self) -> str:
        return contract.domain_digest(
            {
                "transport_mode": self.transport_mode,
                "smtp_host": self.smtp_host,
                "smtp_port": self.smtp_port,
                "tls_mode": self.tls_mode,
                "sender_address_digest": self.sender_address_digest,
                "recipient_set_digest": self.recipient_set_digest,
                "credential_present": bool(self.username and self.password),
                "credential_secret_serialized": False,
            },
            domain="dehps.m4.isolated-24h-challenger.mail-configuration.v11",
        )


@dataclass(frozen=True)
class CompiledEnvelope:
    mail_kind: str
    target_identity: str
    delivery_key: str
    content_digest: str
    recipient_set_digest: str
    client_message_id: str
    subject: str
    body: str
    rfc5322_bytes: bytes

    def artifact_body(self) -> dict[str, Any]:
        return {
            "mail_kind": self.mail_kind,
            "target_identity": self.target_identity,
            "delivery_key": self.delivery_key,
            "content_digest": self.content_digest,
            "recipient_set_digest": self.recipient_set_digest,
            "client_message_id": self.client_message_id,
            "subject_utf8_sha256": hashlib.sha256(
                self.subject.encode("utf-8")
            ).hexdigest(),
            "body_utf8_sha256": hashlib.sha256(self.body.encode("utf-8")).hexdigest(),
            "rfc5322_sha256": hashlib.sha256(self.rfc5322_bytes).hexdigest(),
            "plaintext_recipients_serialized": False,
        }


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _reply_digest(reply: bytes | str | None) -> str | None:
    if reply is None:
        return None
    raw = reply.encode("utf-8") if isinstance(reply, str) else reply
    return hashlib.sha256(raw).hexdigest()


def _tls_peer_digest(smtp: smtplib.SMTP_SSL) -> str:
    sock = smtp.sock
    if sock is None:
        raise IsolatedMailError("smtp_tls_socket_missing")
    certificate = sock.getpeercert(binary_form=True)
    if not certificate:
        raise IsolatedMailError("smtp_tls_peer_certificate_missing")
    return hashlib.sha256(certificate).hexdigest()


def probe_external_configuration(
    configuration: MailRuntimeConfiguration,
    *,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    configuration.validate()
    started = _utc_now()
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        configuration.smtp_host,
        configuration.smtp_port,
        timeout=timeout_seconds,
        context=context,
    ) as smtp:
        code, _ = smtp.ehlo()
        if code != 250:
            raise IsolatedMailError("smtp_ehlo_not_accepted")
        login_code, _ = smtp.login(configuration.username, configuration.password)
        if login_code not in {235, 503}:
            raise IsolatedMailError("smtp_auth_not_accepted")
        noop_code, noop_reply = smtp.noop()
        peer_digest = _tls_peer_digest(smtp)
    completed = _utc_now()
    if noop_code != 250:
        raise IsolatedMailError("smtp_noop_not_accepted")
    return {
        "transport_mode": TRANSPORT_EXTERNAL,
        "smtp_host": configuration.smtp_host,
        "smtp_port": configuration.smtp_port,
        "tls_mode": configuration.tls_mode,
        "sender_address_digest": configuration.sender_address_digest,
        "recipient_set_digest": configuration.recipient_set_digest,
        "credential_present": True,
        "credential_secret_serialized": False,
        "auth_probe_started_at": started,
        "auth_probe_completed_at": completed,
        "auth_probe_result": "TLS_AUTH_NOOP_VERIFIED",
        "smtp_noop_reply_code": noop_code,
        "smtp_noop_reply_bytes_digest": _reply_digest(noop_reply),
        "tls_peer_certificate_sha256": peer_digest,
        "configuration_digest": configuration.configuration_digest,
    }


def fake_configuration_body() -> dict[str, Any]:
    return {
        "transport_mode": TRANSPORT_FAKE,
        "smtp_host": "fake.invalid",
        "smtp_port": 0,
        "tls_mode": "NONE",
        "sender_address_digest": hashlib.sha256(b"").hexdigest(),
        "recipient_set_digest": contract.domain_digest(
            [], domain="dehps.m4.isolated-24h-challenger.recipient-set.v11"
        ),
        "credential_present": False,
        "credential_secret_serialized": False,
        "auth_probe_started_at": None,
        "auth_probe_completed_at": None,
        "auth_probe_result": "FAKE_EPHEMERAL_ONLY",
        "smtp_noop_reply_code": None,
        "smtp_noop_reply_bytes_digest": None,
        "tls_peer_certificate_sha256": None,
        "configuration_digest": contract.domain_digest(
            {"transport_mode": TRANSPORT_FAKE, "simulation": True},
            domain="dehps.m4.isolated-24h-challenger.mail-configuration.v11",
        ),
    }


def compile_envelope(
    *,
    configuration: MailRuntimeConfiguration,
    mail_kind: str,
    target_identity: str,
    subject: str,
    body: str,
    allow_fake: bool = False,
) -> CompiledEnvelope:
    configuration.validate(allow_fake=allow_fake)
    if mail_kind not in {
        "PREDRAW_TOP100",
        "POSTDRAW_SETTLEMENT",
        "DAILY_24H_RESEARCH_SUMMARY",
        "IMMEDIATE_FAIL_CLOSED_INCIDENT",
    }:
        raise IsolatedMailError("mail_kind_not_frozen")
    if not subject or not body:
        raise IsolatedMailError("mail_content_empty")
    content_digest = contract.domain_digest(
        {"subject": subject, "body": body},
        domain="dehps.m4.isolated-24h-challenger.mail-content.v11",
    )
    delivery_key = contract.domain_digest(
        [
            mail_kind,
            target_identity,
            content_digest,
            configuration.recipient_set_digest,
        ],
        domain="dehps.m4.isolated-24h-challenger.delivery-key.v11",
    )
    sender_domain = configuration.sender.rpartition("@")[2] or "simulation.invalid"
    message_id = f"<{delivery_key}@{sender_domain}>"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = configuration.sender or "simulation@simulation.invalid"
    message["To"] = (
        ", ".join(configuration.recipients) or "simulation@simulation.invalid"
    )
    message["Message-ID"] = message_id
    message["X-DEHPS-Lineage"] = contract.LINEAGE_ID
    message["X-DEHPS-Delivery-Key"] = delivery_key
    message.set_content(body, charset="utf-8")
    return CompiledEnvelope(
        mail_kind=mail_kind,
        target_identity=target_identity,
        delivery_key=delivery_key,
        content_digest=content_digest,
        recipient_set_digest=configuration.recipient_set_digest,
        client_message_id=message_id,
        subject=subject,
        body=body,
        rfc5322_bytes=message.as_bytes(),
    )


def validate_envelope(
    envelope: CompiledEnvelope,
    *,
    configuration: MailRuntimeConfiguration,
) -> None:
    expected = compile_envelope(
        configuration=configuration,
        mail_kind=envelope.mail_kind,
        target_identity=envelope.target_identity,
        subject=envelope.subject,
        body=envelope.body,
        allow_fake=configuration.transport_mode == TRANSPORT_FAKE,
    )
    if expected != envelope:
        raise IsolatedMailError("mail_envelope_replay_changed")


class DeliveryLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": "dehps-isolated-v11-delivery-ledger.v1",
                "deliveries": {},
            }
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != "dehps-isolated-v11-delivery-ledger.v1"
            or not isinstance(payload.get("deliveries"), dict)
        ):
            raise IsolatedMailError("delivery_ledger_corrupt")
        return payload

    def _write(self, payload: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = (
            json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n"
        )
        descriptor, temporary = tempfile.mkstemp(
            prefix=self.path.name + ".", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def transition(
        self,
        delivery_key: str,
        *,
        expected: str | None,
        state: str,
        evidence: Mapping[str, Any],
    ) -> None:
        contract.require_digest(delivery_key, field="delivery_key")
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            payload = self._read()
            current = payload["deliveries"].get(delivery_key)
            current_state = None if current is None else current.get("state")
            if current_state != expected:
                raise IsolatedMailError(
                    f"delivery_state_not_retryable:{current_state or 'UNSENT'}"
                )
            payload["deliveries"][delivery_key] = {
                "state": state,
                "updated_at": _utc_now(),
                **dict(evidence),
            }
            self._write(payload)

    def get(self, delivery_key: str) -> Mapping[str, Any] | None:
        return self._read()["deliveries"].get(delivery_key)


def _receipt_body(
    *,
    envelope: CompiledEnvelope,
    mail_envelope_digest: str,
    mail_replay_digest: str,
    mail_configuration_digest: str,
    configuration: MailRuntimeConfiguration,
    state: str,
    simulation: bool,
    attempt_count: int,
    started_at: str | None,
    accepted_at: str | None,
    reply_code: int | None,
    reply_digest: str | None,
    tls_peer_digest: str | None,
    provider_message_id: str | None,
    error_code: str | None,
) -> dict[str, Any]:
    return {
        "mail_kind": envelope.mail_kind,
        "delivery_key": envelope.delivery_key,
        "mail_envelope_digest": contract.require_digest(
            mail_envelope_digest, field="mail_envelope_digest"
        ),
        "mail_replay_digest": contract.require_digest(
            mail_replay_digest, field="mail_replay_digest"
        ),
        "content_digest": envelope.content_digest,
        "recipient_set_digest": envelope.recipient_set_digest,
        "mail_configuration_digest": contract.require_digest(
            mail_configuration_digest, field="mail_configuration_digest"
        ),
        "transport_mode": configuration.transport_mode,
        "simulation": simulation,
        "attempt_count": attempt_count,
        "client_message_id": envelope.client_message_id,
        "smtp_transaction_started_at": started_at,
        "smtp_data_accepted_at": accepted_at,
        "smtp_final_reply_code": reply_code,
        "smtp_final_reply_bytes_digest": reply_digest,
        "tls_peer_certificate_sha256": tls_peer_digest,
        "provider_message_id_or_null": provider_message_id,
        "state": state,
        "error_code_or_null": error_code,
    }


def simulate_delivery(
    *,
    envelope: CompiledEnvelope,
    mail_envelope_digest: str,
    mail_replay_digest: str,
    mail_configuration_digest: str,
) -> dict[str, Any]:
    configuration = MailRuntimeConfiguration(
        smtp_host="fake.invalid",
        smtp_port=0,
        tls_mode="NONE",
        sender="",
        recipients=(),
        username="",
        password="",
        transport_mode=TRANSPORT_FAKE,
    )
    validate_envelope(envelope, configuration=configuration)
    return _receipt_body(
        envelope=envelope,
        mail_envelope_digest=mail_envelope_digest,
        mail_replay_digest=mail_replay_digest,
        mail_configuration_digest=mail_configuration_digest,
        configuration=configuration,
        state="SIMULATED",
        simulation=True,
        attempt_count=0,
        started_at=None,
        accepted_at=None,
        reply_code=None,
        reply_digest=None,
        tls_peer_digest=None,
        provider_message_id=None,
        error_code=None,
    )


def send_external_once(
    *,
    configuration: MailRuntimeConfiguration,
    envelope: CompiledEnvelope,
    mail_envelope_digest: str,
    mail_replay_digest: str,
    mail_configuration_digest: str,
    ledger: DeliveryLedger,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    configuration.validate()
    validate_envelope(envelope, configuration=configuration)
    if envelope.recipient_set_digest != configuration.recipient_set_digest:
        raise IsolatedMailError("recipient_set_digest_changed")
    existing = ledger.get(envelope.delivery_key)
    if existing is not None:
        state = existing.get("state")
        stored_receipt = existing.get("receipt_body")
        if state == "SENT" and isinstance(stored_receipt, dict):
            artifacts.validate_delivery_receipt_body(stored_receipt)
            if (
                stored_receipt.get("delivery_key") != envelope.delivery_key
                or stored_receipt.get("content_digest") != envelope.content_digest
                or stored_receipt.get("recipient_set_digest")
                != envelope.recipient_set_digest
                or stored_receipt.get("mail_envelope_digest") != mail_envelope_digest
                or stored_receipt.get("mail_replay_digest") != mail_replay_digest
                or stored_receipt.get("mail_configuration_digest")
                != mail_configuration_digest
            ):
                raise IsolatedMailError("stored_sent_receipt_identity_changed")
            return dict(stored_receipt)
        if state == "SENDING":
            started = str(existing.get("smtp_transaction_started_at") or "")
            if not started:
                raise IsolatedMailError("sending_ledger_started_at_missing")
            body = _receipt_body(
                envelope=envelope,
                mail_envelope_digest=mail_envelope_digest,
                mail_replay_digest=mail_replay_digest,
                mail_configuration_digest=mail_configuration_digest,
                configuration=configuration,
                state="UNCERTAIN",
                simulation=False,
                attempt_count=1,
                started_at=started,
                accepted_at=None,
                reply_code=None,
                reply_digest=None,
                tls_peer_digest=None,
                provider_message_id=None,
                error_code="CRASH_AFTER_NETWORK_INTENT",
            )
            ledger.transition(
                envelope.delivery_key,
                expected="SENDING",
                state="UNCERTAIN",
                evidence={
                    "error_code": "CRASH_AFTER_NETWORK_INTENT",
                    "receipt_body": body,
                },
            )
            return body
        raise IsolatedMailError(f"delivery_state_not_retryable:{state}")
    started = _utc_now()
    ledger.transition(
        envelope.delivery_key,
        expected=None,
        state="SENDING",
        evidence={
            "content_digest": envelope.content_digest,
            "recipient_set_digest": envelope.recipient_set_digest,
            "attempt_count": 1,
            "smtp_transaction_started_at": started,
        },
    )
    peer_digest: str | None = None
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            configuration.smtp_host,
            configuration.smtp_port,
            timeout=timeout_seconds,
            context=context,
        ) as smtp:
            peer_digest = _tls_peer_digest(smtp)
            code, _ = smtp.ehlo()
            if code != 250:
                raise IsolatedMailError("smtp_ehlo_not_accepted")
            login_code, _ = smtp.login(
                configuration.username, configuration.password
            )
            if login_code not in {235, 503}:
                raise IsolatedMailError("smtp_auth_not_accepted")
            mail_code, _ = smtp.mail(configuration.sender)
            if mail_code != 250:
                raise IsolatedMailError("smtp_mail_from_not_accepted")
            for recipient in configuration.recipients:
                recipient_code, _ = smtp.rcpt(recipient)
                if recipient_code not in {250, 251}:
                    raise IsolatedMailError("smtp_recipient_not_accepted")
            reply_code, reply_bytes = smtp.data(envelope.rfc5322_bytes)
        accepted = _utc_now() if reply_code == 250 else None
        if reply_code != 250 or accepted is None:
            raise IsolatedMailError("smtp_data_not_accepted")
        reply_digest = _reply_digest(reply_bytes)
        provider_message_id = None
        match = re.search(
            rb"(?:queued as|id[ =])\s*([A-Za-z0-9._-]+)", reply_bytes, re.IGNORECASE
        )
        if match is not None:
            provider_message_id = match.group(1).decode("ascii", errors="strict")
        body = _receipt_body(
            envelope=envelope,
            mail_envelope_digest=mail_envelope_digest,
            mail_replay_digest=mail_replay_digest,
            mail_configuration_digest=mail_configuration_digest,
            configuration=configuration,
            state="SENT",
            simulation=False,
            attempt_count=1,
            started_at=started,
            accepted_at=accepted,
            reply_code=reply_code,
            reply_digest=reply_digest,
            tls_peer_digest=peer_digest,
            provider_message_id=provider_message_id,
            error_code=None,
        )
        ledger.transition(
            envelope.delivery_key,
            expected="SENDING",
            state="SENT",
            evidence={
                "content_digest": envelope.content_digest,
                "receipt_body_digest": contract.domain_digest(
                    body,
                    domain="dehps.m4.isolated-24h-challenger.delivery-receipt-body.v11",
                ),
                "receipt_body": body,
            },
        )
        return body
    except Exception as exc:  # noqa: BLE001 - any post-call failure is UNCERTAIN
        error_code = type(exc).__name__.upper()
        body = _receipt_body(
            envelope=envelope,
            mail_envelope_digest=mail_envelope_digest,
            mail_replay_digest=mail_replay_digest,
            mail_configuration_digest=mail_configuration_digest,
            configuration=configuration,
            state="UNCERTAIN",
            simulation=False,
            attempt_count=1,
            started_at=started,
            accepted_at=None,
            reply_code=None,
            reply_digest=None,
            tls_peer_digest=peer_digest,
            provider_message_id=None,
            error_code=error_code,
        )
        ledger.transition(
            envelope.delivery_key,
            expected="SENDING",
            state="UNCERTAIN",
            evidence={"error_code": error_code, "receipt_body": body},
        )
        return body


def build_configuration_artifact(
    *,
    task_key: str,
    git_commit: str,
    source_contract_digest: str,
    parent_digests: Sequence[str],
    configuration_body: Mapping[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    return artifacts.build_artifact(
        artifact_type="M4IsolatedMailConfigurationV11",
        task_key=task_key,
        target_issue=None,
        git_commit=git_commit,
        source_contract_digest=source_contract_digest,
        config_digest=str(configuration_body["configuration_digest"]),
        parent_digests=parent_digests,
        type_body=configuration_body,
        created_at=created_at,
    )


def build_receipt_artifact(
    *,
    task_key: str,
    target_issue: str | None,
    git_commit: str,
    source_contract_digest: str,
    receipt_body: Mapping[str, Any],
    parent_digests: Sequence[str],
    created_at: str | None = None,
) -> dict[str, Any]:
    return artifacts.build_artifact(
        artifact_type="M4IsolatedDeliveryReceiptV11",
        task_key=task_key,
        target_issue=target_issue,
        git_commit=git_commit,
        source_contract_digest=source_contract_digest,
        config_digest=str(receipt_body["mail_configuration_digest"]),
        parent_digests=parent_digests,
        type_body=receipt_body,
        created_at=created_at,
    )
