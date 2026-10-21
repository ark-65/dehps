# Research progress mail repair — 2026-10-21

## Scope and authorization

Primary goal: restore a weekly **current M4 research progress** email, including
an explicit wait or stale-state report when no training ran. The owner selected
this report kind on 2026-10-21. This is the report/status-consumer part of the
owner-authorized R0–R5 control-layer scope recorded in the
2026-09-09 checkpoint. It adds no algorithm, strategy, training dispatch,
scientific Evidence, P3 source change, or V11 scheduling.

The old `dehps-training-watch.timer` is deliberately disabled. It is not
reactivated. The old training mainline projects `FROZEN`; the current M4 status
projects `DEPENDENCY_WAIT` and no `next_ready_task`. A progress email must not
call these new completed training rounds.

## Task frame

| Item | Binding |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` status consumption |
| Ready | Matching manifest and snapshot identities in the M4 status and unified Research Evidence Supervisor state, or an explicit `UNAVAILABLE` report |
| Runner | Weekly `dehps-research-progress-mail.service` consumer, Monday 09:00 Asia/Shanghai |
| Upstream artifacts | `runtime/logs/m4-information-theory-status.json` and `runtime/logs/research-evidence-supervisor-state.json` |
| Downstream artifacts | Immutable weekly rendered report, delivery ledger with SMTP result and message ID |
| Status projection | The two canonical source projections; the consumer does not write research status |
| Evidence rule | Report only the existing projected progress and immutable execution identity; no new scientific Evidence or training-complete claim |
| Decision consumer | Owner's operational review of research progress |
| Next consumer | Next weekly report; any science task remains governed by the existing resolver and Ready Queue |

The exact consumer path is `Goal -> Resolver/Ready Queue -> unified Research
Evidence Supervisor -> status projection -> weekly report artifact -> delivery
ledger -> next weekly report`. The mail consumer is read-only with respect to
research state. It does not become a second training completion path.

## Before state and report impact

On 2026-10-21 the worktree was clean at `35480d8`. The last old training
supervisor watch log was 2026-07-23 17:50 Asia/Shanghai, and the last ordinary
training supervisor Markdown report was 2026-07-21 23:23. The training watch
timer was disabled/inactive and no training supervisor process was live. The M4
projection was written 2026-10-20 22:01 and matched the supervisor state's
manifest and snapshot digests. It showed `M4-P3`, `DEPENDENCY_WAIT`, no next
Ready task, and old training `FROZEN`; the last execution was a 2026121
pre-draw replay, not a training round.

The existing P3 pre-draw and post-draw mail timers were active. At the baseline
check, the pre-draw timer's next trigger was 2026-10-22 17:00 Asia/Shanghai;
the post-draw timer continued its 15-minute cadence. The latest P3 notification
status included 2026120 completion tasks; the M4 pre-draw replay referenced
2026121. This report consumer introduces no shared worker, schema, source,
ledger, timer, or report mutation in those P3 paths. It imports the existing
mail configuration/service but does not edit it or its frozen report consumer.

The expected new report identity is ISO week `2026-W43`, based on Shanghai
time. Its content reports the most recent M4 snapshot, not a claim about the
2026121 prediction outcome. The next regular report is Monday 2026-10-26
09:00 Asia/Shanghai. `Persistent=true` catches up a missed weekly trigger only
after an authorized deployment; the one-period ledger suppresses duplicates.

## Implementation and isolated validation

The new renderer checks both projection schemas, matching manifest/snapshot
identities, and a sane supervisor heartbeat. A source older than 48 hours is
marked `STALE`; a missing or inconsistent source is reported as `UNAVAILABLE`.
Neither state is shown as live training. The report states the frozen old
mainline, current phase/state, projected engineering/evidence percentages,
historical walk-forward count, wait dependencies, and last execution identity.

The delivery path runs from a dedicated fixed release worktree and reads the
existing research runtime through `DEHPS_RESEARCH_PROGRESS_STATE_ROOT`. It
requires an explicit recipient, a reviewed release commit, and a clean release
worktree. The shared project virtualenv is a declared runtime dependency; it
must be checked against the accepted worker dependency lock during release.
It writes the report artifact and a period ledger before SMTP; a returned SMTP
call records `smtp_returned` and message ID. An exception or interrupted send
cannot be retried automatically, because the outcome could be uncertain.
`smtp_returned` is transport completion, not proof of inbox receipt.

Isolated checks on the development branch:

- Three focused tests passed: matching/wait report, stale/mismatched source,
  once-per-period delivery and uncertain-result stop.
- Read-only preview against the current canonical files generated a W43 report
  with `DEPENDENCY_WAIT`, no Ready task, and explicit absence of new-round proof.
- `systemd-analyze verify` accepted both unit files.

## Release and acceptance boundary

Source implementation and isolated validation are complete. Production release
requires an independently approved Operator Request for the exact accepted
commit, unit files, environment binding, first send, and rollback. Do not enable
the new timer or send a test email as part of engineering acceptance. The
Operator package must identify the accepted release SHA, install it under
`/home/ark/releases/dehps-research-progress/current`, verify the read-only
source digests and recipient binding, set
`DEHPS_RESEARCH_PROGRESS_RELEASE_COMMIT` to that SHA, install the two units,
then enable the timer. Rollback disables the new timer and service only; the
weekly ledger and report artifact remain immutable for reconciliation.

Report-impact verdict before deployment: existing P3 path `NO_RUNTIME_IMPACT`
by changed-file/dependency audit; new progress mail `INTEGRATION_PENDING` and
`PENDING_DELIVERY`. A later runtime acceptance must check the actual deployment
week's artifact (W43 if deployed before 2026-10-26),
source identities, ledger status/message ID, timer next trigger, and recipient
receipt separately. The new consumer's mainline integration answer is **NO —
INTEGRATION_PENDING** until a fresh execution under the accepted release and
replay/consumer verification are recorded.

### Reviewed release package for the Operator

The release object is the accepted PR head SHA (recorded on the PR after final
review), with a dedicated detached worktree. The fixed path named `current`
must point to that worktree; its SHA must equal the configured value at every
send. The report reads only the existing runtime root. The sole new runtime
writes are the weekly report artifact and its delivery ledger/lock. The
service unit uses the existing worker virtualenv; the Operator must verify its
dependencies before enabling the timer.

After independent Operator approval for this exact package:

1. Fetch the accepted SHA and create
   `/home/ark/releases/dehps-research-progress/<accepted-sha>` as a detached
   worktree. Confirm that `git rev-parse HEAD` equals the accepted SHA and the
   release worktree is clean. Link `current` to that exact directory.
2. Confirm the M4 status and supervisor files are readable and their
   manifest/snapshot identities match. Confirm the QQ sender and recipient
   environment variables are present by name, without printing their values.
   Store only `DEHPS_RESEARCH_PROGRESS_RELEASE_COMMIT=<accepted-sha>` in
   `/home/ark/.config/dehps/research-progress.env` with mode `0600`.
3. Run the release script without `--deliver` and review the exact subject and
   body. Link both unit files from the accepted worktree into the user systemd
   manager, reload it, and enable/start the new timer. A `Persistent=true`
   catch-up may immediately send the current week's one copy; do not also run
   the service manually.
4. Verify the service result, weekly report artifact digest, ledger period and
   `smtp_returned` message ID or explicit uncertain failure, and next timer
   trigger. Check that existing P3 timers and their current-issue ledgers are
   unchanged. Recipient receipt is a separate acceptance fact.

Rollback: disable and stop only `dehps-research-progress-mail.timer` and its
service; retain the report artifact, ledger and any uncertain attempt. Do not
delete a sent record or automatically resend it. The old training watch stays
disabled and Formal P3 stays on its retained path.
