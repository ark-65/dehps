from __future__ import annotations

import os
import smtplib
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


QQ_SMTP_HOST = "smtp.qq.com"
QQ_SMTP_SSL_PORT = 465
DEFAULT_TIMEOUT_SECONDS = 15.0
MAIL_ADDRESS_ENV = "DEHPS_QQ_MAIL_ADDRESS"
MAIL_AUTHORIZATION_CODE_ENV = "DEHPS_QQ_MAIL_AUTHORIZATION_CODE"
MAIL_RECIPIENT_ENV = "DEHPS_QQ_MAIL_RECIPIENT"


class MailConfigurationError(ValueError):
    """Raised before connecting when the local mail configuration is invalid."""


class MailDeliveryError(RuntimeError):
    """Raised with a credential-free message when SMTP delivery fails."""


def _validated_address(value: str, *, field_name: str) -> str:
    candidate = value.strip()
    parsed_name, parsed_address = parseaddr(candidate)
    local_part, separator, domain = candidate.rpartition("@")
    if (
        not candidate
        or parsed_name
        or parsed_address != candidate
        or separator != "@"
        or not local_part
        or not domain
        or any(character.isspace() for character in candidate)
    ):
        raise ValueError(f"{field_name} must be one plain email address")
    return candidate


class QqMailConfig(BaseModel):
    """QQ SMTP settings whose authorization code remains masked in representations."""

    model_config = ConfigDict(frozen=True)

    address: str
    authorization_code: SecretStr
    recipient: str | None = None
    timeout_seconds: float = Field(DEFAULT_TIMEOUT_SECONDS, gt=0, le=120)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        return _validated_address(value, field_name="address")

    @field_validator("recipient")
    @classmethod
    def validate_recipient(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validated_address(value, field_name="recipient")

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> QqMailConfig:
        values = os.environ if environment is None else environment
        address = str(values.get(MAIL_ADDRESS_ENV) or "").strip()
        authorization_code = str(values.get(MAIL_AUTHORIZATION_CODE_ENV) or "").strip()
        recipient = str(values.get(MAIL_RECIPIENT_ENV) or "").strip() or None
        missing = [
            name
            for name, value in (
                (MAIL_ADDRESS_ENV, address),
                (MAIL_AUTHORIZATION_CODE_ENV, authorization_code),
            )
            if not value
        ]
        if missing:
            raise MailConfigurationError(
                "missing required mail environment variables: " + ", ".join(missing)
            )
        try:
            return cls(
                address=address,
                authorization_code=authorization_code,
                recipient=recipient,
            )
        except ValueError:
            raise MailConfigurationError("invalid QQ mail configuration") from None

    @property
    def destination(self) -> str:
        return self.recipient or self.address


@dataclass(frozen=True)
class MailDeliveryReceipt:
    message_id: str
    sender: str
    recipient: str


SmtpFactory = Callable[..., Any]


class QqMailService:
    """Send one operator-authored message through QQ SMTP over implicit TLS."""

    def __init__(
        self,
        config: QqMailConfig,
        *,
        smtp_factory: SmtpFactory | None = None,
        ssl_context_factory: Callable[[], ssl.SSLContext] = ssl.create_default_context,
    ) -> None:
        self.config = config
        self._smtp_factory = smtp_factory or smtplib.SMTP_SSL
        self._ssl_context_factory = ssl_context_factory

    def send(
        self,
        *,
        subject: str,
        text: str,
        html: str | None = None,
        recipient: str | None = None,
    ) -> MailDeliveryReceipt:
        message = self._build_message(
            subject=subject,
            text=text,
            html=html,
            recipient=recipient,
        )
        try:
            with self._smtp_factory(
                QQ_SMTP_HOST,
                QQ_SMTP_SSL_PORT,
                timeout=self.config.timeout_seconds,
                context=self._ssl_context_factory(),
            ) as client:
                client.login(
                    self.config.address,
                    self.config.authorization_code.get_secret_value(),
                )
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise MailDeliveryError(
                f"QQ SMTP delivery failed ({type(exc).__name__})"
            ) from None
        return MailDeliveryReceipt(
            message_id=str(message["Message-ID"]),
            sender=self.config.address,
            recipient=str(message["To"]),
        )

    def _build_message(
        self,
        *,
        subject: str,
        text: str,
        html: str | None,
        recipient: str | None,
    ) -> EmailMessage:
        clean_subject = subject.strip()
        if not clean_subject:
            raise MailConfigurationError("mail subject must not be empty")
        if any(character in clean_subject for character in "\r\n"):
            raise MailConfigurationError("mail subject must not contain line breaks")
        if not text and not html:
            raise MailConfigurationError("mail must contain text or HTML content")
        try:
            destination = (
                self.config.destination
                if recipient is None
                else _validated_address(recipient, field_name="recipient")
            )
        except ValueError:
            raise MailConfigurationError("invalid mail recipient") from None

        message = EmailMessage()
        message["From"] = self.config.address
        message["To"] = destination
        message["Subject"] = clean_subject
        message["Message-ID"] = make_msgid(domain=self.config.address.rsplit("@", 1)[1])
        message.set_content(text or "This message contains an HTML alternative.")
        if html is not None:
            message.add_alternative(html, subtype="html")
        return message
