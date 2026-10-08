# Primary P3 pre-mail duplicate-timer recovery — 2026-10-08

## Round boundary

- Role: Engineering Agent, following the user's direct instruction to repair and restart the mail timer.
- Goal: let an already-sent, exactly registered pre-mail skip a later timer invocation without reaching the frozen draw-window check or SMTP.
- Non-goals: change prediction rankings, report content, source contracts, deadlines, recipients, historical records, post-mail, or send a test/resend message.
- Current issue and deadline: 2026115, official draw time 2026-10-08 21:15 Asia/Shanghai; pre-mail timer next trigger 17:00. The prediction was sealed on 2026-10-06 21:57 and its registered replay is verified. Pre-mail delivery is pending.

## Before state and cause

- The 2026114 checkpoint records an official time of 2026-10-01 21:15, while the audited draw and settlement occurred on 2026-10-06. The 2026114 pre-mail ledger already recorded `sent` on 2026-10-01 17:08 Asia/Shanghai; its post-mail ledger recorded `sent` on 2026-10-06 22:24.
- The fixed Tue/Thu/Sun 17:00 timer selected the latest completed pre-draw replay on 2026-10-04 and 2026-10-06. The canonical runner checked the old checkpoint's draw window before reaching delivery deduplication, so both invocations failed with `notification_predraw_window_closed`.
- The canonical runner is itself covered by the frozen source contract. Editing it failed the source-byte validation in the notification test suite and was reverted.
- The report chain for 2026114 has settlement and report replay; current 2026115 has pre-draw seal and replay. No 2026115 pre-mail delivery entry exists yet.

## Change

- Add a read-only `ExecCondition` before the existing frozen mail `ExecStart`. It resolves the same latest completed pre-draw issue and recipient binding. If there is no ledger record for that issue, it exits 0 and the canonical runner continues.
- For an existing pre-mail record, it requires exactly one `sent` entry, identical recipient digest, and the same delivery key, artifact digest, and replay digest reconstructed from registered artifacts. It exits 1 only for that exact already-sent identity, which systemd treats as a skipped condition. Ambiguous, uncertain, or changed evidence exits 255 and leaves a visible failure.
- The condition does not write to the ledger or connect to SMTP. The frozen source and installed presentation release remain unchanged. The original failed journal records remain available after `reset-failed` cleared the unit's active failure flag.

## Validation and deployment

- Read-only live probe: 2026115 returned `UNSENT_RUN_CANONICAL` (exit 0); forced 2026114 selection returned `ALREADY_SENT_EXACT_REGISTERED_PRE_MAIL` (exit 1).
- In-memory uncertain-ledger probe raised `pre_mail_ledger_requires_review`; no delivery was attempted.
- The installed command ran as a transient user systemd unit with the production mail environment and returned `UNSENT_RUN_CANONICAL` / exit 0 for 2026115. The transient unit did not start the mail service.
- Focused validation after restoring the frozen CLI: `ruff check` passed, and the notification plus primary presentation suites passed (45 tests).
- Ledger SHA256 before and after: `ab0d5b1e78c702c299aa015a20e255244f47b2a321a103ab96b40c76c1bf14ef`. Frozen CLI SHA256 before and after: `92a387d0ec74039111d38e2886f2dde1b6736ee9d79285d88efdef9e59e73506`.
- Installed only the new service drop-in, ran `systemctl --user daemon-reload`, cleared the old failure flag, and restarted the pre-mail timer. The loaded unit shows the new `ExecCondition` and the next trigger remains 2026-10-08 17:00. The pre-mail service was not started before its 17:00 window.
- `git diff --check` passed. The old notification-suite failures were produced by the discarded frozen-CLI edit, not by this additive condition.

## Report integrity and integration

| Link | Current evidence |
| --- | --- |
| Goal / resolver / Ready Queue | 2026115 pre-draw issue and replay already completed; notification pre-envelope remains for the timer |
| Supervisor / capability / artifacts | Frozen canonical mail path retained; pre-mail artifacts will be produced by its scheduled execution |
| Status / next consumer | `ExecCondition` is loaded; unsent 2026115 continues to the original service and presentation consumer |
| Replay / delivery | 2026115 pre-draw replay verified; pre-mail and presentation replay plus delivery remain pending until 17:00 |

Report-impact verdict: **PENDING_DELIVERY** for 2026115. This round did not change source lineage, sealed ranking, report content, ledger, or post-mail. A fresh 17:00 canonical execution, readable presentation, registered replay, and exact `sent` ledger entry are required before delivery acceptance. The 2026114 historical checkpoint-date discrepancy remains explicit and is not rewritten.
