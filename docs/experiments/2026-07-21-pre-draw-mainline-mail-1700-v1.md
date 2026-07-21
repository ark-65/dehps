# Pre-draw Mainline Mail 17:00 Schedule v1

Date: 2026-07-21

Engineering authorization: Agent Request `engineering-mainline-mail-1700-schedule-20260721-v1` (request `166`, execution `87`).

## Primary Goal

Replace the accepted 18:15 pre-draw mail schedule with 17:00 Asia/Shanghai on Tuesday, Thursday, and Sunday, as explicitly requested by the operator.

The official SSQ draw remains 21:15, so the revised notification occurs four hours and fifteen minutes before the draw:

```text
OnCalendar=Tue,Thu,Sun *-*-* 17:00:00 Asia/Shanghai
```

## Changed Contract

- earliest allowed send time: `17:00` instead of `18:15`;
- checked-in systemd timer: `17:00`;
- production user crontab target after separate Operator approval: `0 17 * * 2,4,0`;
- existing pre-draw cutoff remains strictly before `21:15`.

## Preserved Boundaries

- draw weekdays remain Tuesday, Thursday, and Sunday;
- durable source remains `static_100` ranks `1..100`;
- recipient, SMTP identity, authorization code, email content, delivery key, and ledger protocol are unchanged;
- no training, scoring, ranking, Evaluation, Promotion, or prediction-row mutation;
- historical 18:15 evidence remains historical and is not rewritten.

## Acceptance

- Tuesday at 16:59 Beijing time fails closed;
- Tuesday at 17:00 Beijing time is accepted;
- 21:15 and later fail closed;
- the systemd calendar resolves the next occurrence to 17:00 CST;
- the active production cron must contain one marked mail block at 17:00 and zero mail entries at 18:15.

## Validation

Commands and results:

```text
python -m pytest -q tests/test_mainline_prediction_mail.py tests/test_mail_service.py tests/test_latest_prediction.py
30 passed

python -m pytest -q
1347 passed, 4 skipped, 4 existing Python 3.14 fork warnings

systemd-analyze calendar 'Tue,Thu,Sun *-*-* 17:00:00 Asia/Shanghai'
Next elapse: Tue 2026-07-21 17:00:00 CST
(in UTC): Tue 2026-07-21 09:00:00 UTC

systemd-analyze verify infra/systemd/dehps-mainline-prediction-mail.service infra/systemd/dehps-mainline-prediction-mail.timer
passed

git diff --check
passed
```

Production cron replacement remains a separate Operator action.
