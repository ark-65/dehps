from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from typing import Any

import pytest
from typer.testing import CliRunner

from dehps.cli import app
from dehps.notifications.mail import (
    MAIL_ADDRESS_ENV,
    MAIL_AUTHORIZATION_CODE_ENV,
    MAIL_RECIPIENT_ENV,
    QQ_SMTP_HOST,
    QQ_SMTP_SSL_PORT,
    MailConfigurationError,
    MailDeliveryError,
    QqMailConfig,
    QqMailService,
)


AUTHORIZATION_CODE = "abcdefghijklmnop"


class RecordingSmtp:
    def __init__(self, host: str, port: int, **kwargs: Any) -> None:
        self.host = host
        self.port = port
        self.kwargs = kwargs
        self.login_call: tuple[str, str] | None = None
        self.message: EmailMessage | None = None

    def __enter__(self) -> RecordingSmtp:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def login(self, address: str, authorization_code: str) -> None:
        self.login_call = (address, authorization_code)

    def send_message(self, message: EmailMessage) -> None:
        self.message = message


class RecordingFactory:
    def __init__(self, smtp_type: type[RecordingSmtp] = RecordingSmtp) -> None:
        self.smtp_type = smtp_type
        self.connections: list[RecordingSmtp] = []

    def __call__(self, host: str, port: int, **kwargs: Any) -> RecordingSmtp:
        connection = self.smtp_type(host, port, **kwargs)
        self.connections.append(connection)
        return connection


def test_config_defaults_recipient_to_same_qq_account_and_masks_secret() -> None:
    config = QqMailConfig.from_environment(
        {
            MAIL_ADDRESS_ENV: "123456@qq.com",
            MAIL_AUTHORIZATION_CODE_ENV: AUTHORIZATION_CODE,
        }
    )

    assert config.destination == "123456@qq.com"
    assert AUTHORIZATION_CODE not in repr(config)
    assert "**********" in repr(config)


def test_environment_recipient_can_override_same_account_default() -> None:
    config = QqMailConfig.from_environment(
        {
            MAIL_ADDRESS_ENV: "123456@qq.com",
            MAIL_AUTHORIZATION_CODE_ENV: AUTHORIZATION_CODE,
            MAIL_RECIPIENT_ENV: "receiver@qq.com",
        }
    )

    assert config.destination == "receiver@qq.com"


def test_missing_environment_fails_before_smtp_connection() -> None:
    with pytest.raises(MailConfigurationError) as error:
        QqMailConfig.from_environment({})

    message = str(error.value)
    assert MAIL_ADDRESS_ENV in message
    assert MAIL_AUTHORIZATION_CODE_ENV in message


@pytest.mark.parametrize(
    "address",
    ["not-an-address", "a b@qq.com", "a@qq.com\nBcc: attacker@example.com"],
)
def test_invalid_sender_address_fails_closed(address: str) -> None:
    with pytest.raises(MailConfigurationError, match="invalid QQ mail configuration"):
        QqMailConfig.from_environment(
            {
                MAIL_ADDRESS_ENV: address,
                MAIL_AUTHORIZATION_CODE_ENV: AUTHORIZATION_CODE,
            }
        )


def test_send_uses_qq_implicit_tls_and_builds_multipart_message() -> None:
    factory = RecordingFactory()
    tls_context = object()
    config = QqMailConfig(
        address="123456@qq.com",
        authorization_code=AUTHORIZATION_CODE,
    )

    receipt = QqMailService(
        config,
        smtp_factory=factory,
        ssl_context_factory=lambda: tls_context,  # type: ignore[return-value]
    ).send(
        subject="DEHPS notification",
        text="plain body",
        html="<strong>HTML body</strong>",
    )

    connection = factory.connections[0]
    assert (connection.host, connection.port) == (QQ_SMTP_HOST, QQ_SMTP_SSL_PORT)
    assert connection.kwargs == {"timeout": 15.0, "context": tls_context}
    assert connection.login_call == ("123456@qq.com", AUTHORIZATION_CODE)
    assert connection.message is not None
    assert connection.message["From"] == "123456@qq.com"
    assert connection.message["To"] == "123456@qq.com"
    assert connection.message["Subject"] == "DEHPS notification"
    assert connection.message.get_body(preferencelist=("plain",)).get_content().strip() == "plain body"
    assert "<strong>HTML body</strong>" in connection.message.get_body(
        preferencelist=("html",)
    ).get_content()
    assert receipt.sender == receipt.recipient == "123456@qq.com"
    assert receipt.message_id == connection.message["Message-ID"]


def test_header_injection_fails_before_smtp_connection() -> None:
    factory = RecordingFactory()
    service = QqMailService(
        QqMailConfig(address="123456@qq.com", authorization_code=AUTHORIZATION_CODE),
        smtp_factory=factory,
    )

    with pytest.raises(MailConfigurationError, match="line breaks"):
        service.send(subject="safe\nBcc: attacker@example.com", text="body")

    assert factory.connections == []


def test_smtp_failure_does_not_expose_authorization_code_or_server_message() -> None:
    class FailingSmtp(RecordingSmtp):
        def login(self, address: str, authorization_code: str) -> None:
            raise smtplib.SMTPAuthenticationError(
                535,
                f"bad credential {authorization_code}".encode(),
            )

    service = QqMailService(
        QqMailConfig(address="123456@qq.com", authorization_code=AUTHORIZATION_CODE),
        smtp_factory=RecordingFactory(FailingSmtp),
    )

    with pytest.raises(MailDeliveryError) as error:
        service.send(subject="subject", text="body")

    assert str(error.value) == "QQ SMTP delivery failed (SMTPAuthenticationError)"
    assert AUTHORIZATION_CODE not in str(error.value)
    assert error.value.__cause__ is None


def test_mail_cli_sends_without_accepting_credentials_as_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = RecordingFactory()
    monkeypatch.setenv(MAIL_ADDRESS_ENV, "123456@qq.com")
    monkeypatch.setenv(MAIL_AUTHORIZATION_CODE_ENV, AUTHORIZATION_CODE)
    monkeypatch.delenv(MAIL_RECIPIENT_ENV, raising=False)
    monkeypatch.setattr("dehps.notifications.mail.smtplib.SMTP_SSL", factory)

    result = CliRunner().invoke(
        app,
        ["mail", "send", "--subject", "CLI test", "--text", "hello"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["sent"] is True
    assert payload["receipt"]["sender"] == "123456@qq.com"
    assert payload["receipt"]["recipient"] == "123456@qq.com"
    assert AUTHORIZATION_CODE not in result.stdout
    assert factory.connections[0].message is not None
