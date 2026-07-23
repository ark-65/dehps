# Post-draw Mail Draw-sync Recovery v1

Date: 2026-07-23

Engineering authorization: Agent Request `engineering-post-draw-mail-draw-sync-recovery-v1` (request `187`, execution `108`).

## Primary Goal

Restore post-draw analysis delivery on the active systemd draw-sync path and make a missed current-issue report recoverable without duplicate SMTP delivery.

## Incident Evidence

- `draw-sync-20260721-135137-630422` synchronized issue `2026083` at 21:51 Asia/Shanghai on 2026-07-21.
- The three accepted forward evaluations completed by 21:54.
- The delivery ledger contained only issue `2026082`; it had no `2026083` entry.
- The active systemd unit executes `scripts/run_draw_sync_watch.py`. That watcher evaluated pending predictions but never invoked the post-draw notifier. Notification orchestration existed only in the legacy daily pipeline.

## Fix Contract

- After a successful forward-evaluation batch, attempt the current latest issue through the existing report compiler and digest/recipient delivery ledger.
- Run the same check on no-change polls so an omitted current issue can recover.
- Preserve existing `sent`/`already_sent` idempotency and fail-closed `uncertain` behavior.
- Record notification result or failure in `draw-sync-watch.json` without replacing successful sync and evaluation status.
- Withhold notification when the evaluation batch reports failures.

## Non-goals

- No report-content, SMTP, evidence-validation, scoring, ranking, candidate, training, promotion, or betting change.
- No retry of an ambiguous `uncertain` SMTP delivery.

## Validation

```text
python -m pytest -q tests/test_draw_sync_scheduler.py tests/test_draw_sync_systemd_deployment.py tests/test_draw_sync_supervisor_ownership.py tests/test_forward_wait_sync_decoupling.py tests/test_post_draw_evaluation_mail.py tests/test_daily_pipeline.py tests/test_mail_service.py
58 passed

python -m pytest -q
1536 passed, 4 skipped, 4 existing Python 3.14 fork warnings

dehps mail post-draw-evaluation --issue 2026083 --preview
status=preview
line_count=3
report_digest=d3e6f86674c357041db73aaeb2c1e0aaa663ef293065772cc699d5bb365849c9

git diff --check
passed
```

Production deployment and the idempotent recovery receipt are recorded after merge under a separately reviewed Operator Request.
