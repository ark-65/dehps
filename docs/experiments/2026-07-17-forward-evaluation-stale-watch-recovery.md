# Forward evaluation stale-watch recovery

## Incident state

Read-only inspection after issue `2026081` entered history found:

- history: 3,478 rows, latest issue `2026081`;
- forward `2026081`: three runs, 30,000 candidates, all still `pending`;
- forward evaluation runs: zero;
- forward `2026082`: three newer runs, 30,000 candidates, all `pending`.

This violated the required sequence: sync draw, evaluate the matching prediction,
then release the next prediction.

## Root cause evidence

The evaluation service and current `DrawSyncWatch` source already call
`evaluate_pending()` on every poll, including `no_change`. The running watcher,
however, was PID `2655006`, started on 2026-07-14 and never restarted after the
evaluation code was deployed. Its state payload had no `forward_evaluation` or
code-identity field. `ensure_draw_sync_watch.sh` treated any matching live PID as
healthy and could not distinguish loaded code from current code.

There was a second independent bypass. The 21:45 cron invokes
`daily_pipeline.py`, whose old order was sync, feature/signal refresh, then next
prediction generation. It did not call forward evaluation at all.

Finally, the continuous watcher synchronized issue `2026081` at 21:32, before
the requested delayed update boundary of 21:45. Its old hot window began at
20:45 and had no 21:15–21:45 deferral gate.

## Fix

1. The watcher captures its loaded Git commit once at startup, writes it to a
   version file, and includes it plus `watch_started_at` in success and error
   state payloads.
2. The ensure script compares the loaded commit with clean-worktree `HEAD`.
   Missing or stale identity triggers graceful `SIGTERM`, bounded wait, and a
   non-overlapping restart. Failure to stop or a wrong startup identity fails
   closed.
3. The packaged systemd service is now timer-driven `Type=oneshot --once`, not
   a `Restart=always` resident interpreter. Every scheduled poll loads the
   deployed code afresh.
4. Draw-day synchronization is deferred from 21:15 until 21:45. Pending
   evaluation still runs during the deferral, and the next interval lands on
   21:45.
5. `daily_pipeline.py` now evaluates pending forward runs immediately after
   sync and before backtests, signal refresh, or prediction generation.
   Evaluation failure fails the pipeline and blocks downstream prediction.
6. Because evaluation runs on `no_change`, restarting current code after a draw
   was already synchronized safely compensates the missed batch without needing
   another history mutation.

## Safety boundary

This engineering round does not itself restart the production watcher or write
evaluation rows. The existing 2026081/2026082 runs remain unchanged until an
approved Operator execution restarts the watcher. The recovery operation must
record the old/new PID and code commit, three completed 2026081 evaluations,
idempotent second-pass count zero, and unchanged 2026081 candidate identity.

## Verification contract

Tests cover:

- evaluation on both new-issue and no-change polls;
- evaluation during the 21:15–21:45 sync deferral;
- exact 21:45 update boundary and hot interval;
- code identity in success and exception state;
- version-aware stale-process launcher guards;
- daily pipeline evaluation before signals and prediction generation;
- downstream blocking when any evaluation fails;
- existing evaluation idempotency and retry behavior.
