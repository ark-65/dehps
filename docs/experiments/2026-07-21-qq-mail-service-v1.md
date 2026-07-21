# QQ Mail Service v1

Date: 2026-07-21

Engineering authorization: Agent Request `engineering-qq-mail-service-20260721-v1` (request `161`, execution `82`).

## Primary Goal

Provide one reusable, operator-controlled Python service that sends a plain-text message, with an optional HTML alternative, through QQ SMTP. The configured QQ account is both sender and default recipient, so self-addressed operational notifications require only one account.

## Contract

- transport: implicit TLS to `smtp.qq.com:465`;
- identity: full QQ email address;
- credential: QQ SMTP authorization code read from `DEHPS_QQ_MAIL_AUTHORIZATION_CODE`;
- default recipient: configured sender address;
- optional recipient: `DEHPS_QQ_MAIL_RECIPIENT` or the CLI `--to` option;
- failure behavior: validate before connecting and expose only a sanitized SMTP exception class;
- execution: manual `dehps mail send`; no scheduler or resident integration.

Tencent Cloud documents QQ SMTP as `smtp.qq.com` on port `465/587` and requires the generated authorization code after enabling SMTP. This implementation selects port `465` and Python's implicit TLS client to keep one transport mode.

## Security Boundary

- The authorization code is represented as `SecretStr` and excluded from receipts.
- The CLI has no credential option; local environment is the only credential source.
- SMTP server response text is not propagated because it may contain sensitive values.
- Sender, recipient, and subject reject newline-based header injection.
- Unit tests inject a fake SMTP factory and perform no network delivery.

## Non-goals

- automatic Research OS or scheduler notifications;
- production deployment or supervisor changes;
- credential storage or rotation;
- bulk email, attachments, retry queues, or delivery tracking;
- research, evaluation, Evidence, or Promotion changes.

## Validation

Commands:

```text
cd apps/worker-python && .venv/bin/python -m pytest -q tests/test_mail_service.py
cd apps/worker-python && .venv/bin/dehps mail --help
cd apps/worker-python && .venv/bin/dehps mail send --help
cd apps/worker-python && .venv/bin/python -m pytest -q
git diff --check
```

Results:

- mail unit/CLI tests: `10 passed`;
- full Worker suite: `1331 passed, 4 skipped`;
- existing Python 3.14 multiprocessing/fork deprecation warnings: `4`;
- CLI command discovery: passed;
- diff whitespace check: passed;
- live network calls during tests: `0`.

A real QQ SMTP smoke remains an explicit operator action after the user configures the ignored local `.env`; no credential is included in source evidence.

## References

- [Tencent Cloud Email connector documentation](https://cloud.tencent.com/document/product/1270/55456)
- [Microsoft: add a QQMail account to Outlook](https://support.microsoft.com/zh-tw/outlook/add-a-qqmail-account-to-outlook)
