# Parked Supervisor And Heavy-Job Status Consistency

Date: 2026-07-11

## Round scope

- Primary goal: keep a supervisor that has reached the forward-evidence wait
  boundary durably parked, while preserving truthful heavy-job audit metadata.
- Non-goals: no strategy, weight, advisor budget, candidate source, promotion
  threshold, or prediction output changes.

## Initial evidence

Run `20260711-132111` had completed eight durable rounds against history issue
`2026078` and was intentionally stopped pending the complete three-line snapshot
for issue `2026079`.  Its supervisor status correctly reported
`waiting_for_forward_issue`, but `runtime/logs/dehps-heavy-job.lock.json` still
reported the stopped PID `3579268` as `running`.

The stale metadata did not hold the OS lock, but it made the operator view
internally contradictory: `active=false`, `pid_active=false`, and
`status=running`.

## Change

`dehps.runtime.heavy_job.mark_inactive_heavy_job_owner` now performs a
fail-closed metadata transition while holding the heavy-job lock file
non-blocking.  It only writes when:

- the lock is not held by another process;
- the stored PID and optional owner exactly match the expected values;
- the PID is known to have stopped; and
- the requested status is an explicitly inactive status.

The transition preserves command and context evidence, adds a finish timestamp,
and atomically records `waiting_for_forward_issue`.  The supervisor waiting
marker now applies the same transition and records the forward-wait contract in
the lock context before writing the supervisor waiting status.

The training watcher now treats stale progress and an inactive lock as expected
when both the persisted supervisor status and the recomputed forward-wait gate
confirm a valid parked state.  Its primary action therefore remains
`await_new_forward_issue` after the ordinary 30-minute freshness threshold.

## Live falsification and correction

The first manual watchdog validation exposed a second bug.  At 14:27 local time,
the supervisor progress age crossed 30 minutes, so `inspect_training_log` was
placed ahead of `await_new_forward_issue`.  The forward-wait guard rejected the
summary and watchdog started PID `3647004` against unchanged history issue
`2026078`.

That process was stopped immediately during static-universe initialization,
before it completed or persisted a training round.  Its last heavy-job metadata
was retained as `interrupted` with the reason
`watchdog_restarted_parked_same_history_run`.  The watcher action-priority bug
was then fixed and covered by a stale parked-supervisor regression test.

## Validation

- Focused tests:
  `tests/test_heavy_job.py`, `tests/test_mark_training_supervisor_waiting.py`,
  `tests/test_training_watch_forward_wait_guard.py`, and
  `tests/test_training_watch.py` passed (`104 passed`).
- Full worker regression passed (`544 passed`); shell syntax and Python compile
  checks also passed.
- The live watcher returned `action=await_new_forward_issue`, supervisor status
  `waiting_for_forward_issue`, history `2026078`, pending issue `2026079`,
  `selection_changed=false`, and `promotion_allowed=false` after the progress
  freshness threshold had expired.
- The live forward-wait guard returned
  `watch_forward_wait_ready:2026078->2026079`.
- A subsequent manual `scripts/ensure_training_supervisor.sh` sync found no new
  draw, logged `training supervisor remains parked`, exited successfully, and
  left no `run_training_supervisor.py` process active.

## Interpretation

This is an operational consistency fix.  It prevents repeated computation on an
unchanged historical surface and makes the wait boundary auditable.  It does not
add predictive evidence, change candidate selection, or relax the frozen
validation, null-model, multiplicity, or leakage guardrails.
