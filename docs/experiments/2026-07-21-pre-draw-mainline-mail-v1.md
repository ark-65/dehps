# Pre-draw Mainline Top-100 Mail v1

Date: 2026-07-21

Engineering authorization: Agent Request `engineering-pre-draw-mainline-mail-20260721-v1` (request `162`, execution `83`).

## Primary Goal

Send the existing durable `static_100` Top-100 prediction to one explicitly configured recipient at 18:15 Asia/Shanghai on every official SSQ draw day, three hours before the 21:15 draw.

The [China Welfare Lottery official draw page](https://www.cwl.gov.cn/ygkj/wqkjgg/) states that SSQ draws occur Tuesday, Thursday, and Sunday at 21:15. The timer therefore uses:

```text
OnCalendar=Tue,Thu,Sun *-*-* 18:15:00 Asia/Shanghai
```

## Data Boundary

The notification command reuses the read-only latest-prediction query and selects exactly one `static_100` line. It requires:

- a target issue strictly after the as-of issue;
- line status `pending`;
- a non-empty prediction run key and fingerprint;
- contiguous ranks `1..100`;
- six unique, sorted red balls in `1..33` per candidate;
- no duplicate combinations and only finite scores.

It does not generate, score, rerank, evaluate, promote, or write prediction rows.

## Delivery Boundary

- Preview is the CLI default and never opens SMTP.
- `--send` is accepted only Tuesday, Thursday, and Sunday from 18:15 until before 21:15 Beijing time.
- The scheduled path requires `DEHPS_QQ_MAIL_RECIPIENT`; it never silently defaults to the sender.
- The email includes issue identity, runtime identity, model/parameter versions, ranking contract, all 100 candidates, and experimental-risk language.
- The local ledger transitions `absent -> sending -> sent`.
- An SMTP exception transitions `sending -> uncertain`; automatic retry then fails closed because the server may already have accepted the message.
- A second invocation after `sent` returns `already_sent` without opening SMTP.

## Live Read-only Preview

The current durable state was read with placeholder SMTP credentials and no network delivery:

```text
status=preview
issue=2026083
as_of_issue=2026082
line=static_100
candidate_count=100
prediction_run_key=static_100:2026083:training-next-2026082-450864491180
```

## Non-goals

- prediction, feature, scoring, ranking, Evaluation, or Promotion changes;
- dynamic or near-line email content;
- bulk delivery, attachments, or marketing email;
- automatic retry of ambiguous SMTP outcomes;
- source-controlled credentials;
- timer installation before a separate approved Operator Request.

## Validation

Commands and results:

```text
python -m pytest -q tests/test_mainline_prediction_mail.py tests/test_mail_service.py tests/test_latest_prediction.py
30 passed

python -m pytest -q
1347 passed, 4 skipped, 4 existing Python 3.14 fork warnings

systemd-analyze calendar 'Tue,Thu,Sun *-*-* 18:15:00 Asia/Shanghai'
Next elapse: Tue 2026-07-21 18:15:00 CST
(in UTC): Tue 2026-07-21 10:15:00 UTC

systemd-analyze verify infra/systemd/dehps-mainline-prediction-mail.service infra/systemd/dehps-mainline-prediction-mail.timer
passed

git diff --check
passed
```

Automated tests injected a fake SMTP service and made zero external deliveries. Production activation and real external delivery remain separate Operator actions.
