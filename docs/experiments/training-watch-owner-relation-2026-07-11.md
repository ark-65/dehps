# Training Watch Heavy-Job Owner Relation — 2026-07-11

## Primary Goal

Make the relationship between the current training supervisor PID and global heavy-job metadata explicit, so a later inactive owner is not mistaken for the parked supervisor.

## Non-Goals

- No model, advisor, candidate source, budget, objective, or promotion change.
- No restart of same-history training while forward issue `2026079` is pending.
- No rewrite of preserved heavy-job audit metadata.

## Triggering Observation

The parked supervisor status identifies PID `3579268`, while the preserved heavy-job metadata identifies later inactive PID `3647004` with status `interrupted`. Both records were individually correct, but the watcher did not state their relationship.

## Change

The watcher now emits `heavy_job_supervisor_relation` with a fixed protocol and one of these ownership states:

- `same_supervisor_pid`
- `different_active_pid`
- `different_inactive_pid`
- `heavy_job_pid_missing`
- `supervisor_unavailable`

The field is read-only evidence. It explicitly keeps `selection_changed=false` and `promotion_allowed=false`. The autonomous self-iteration contract now requires PID-based interpretation: a different active owner fails closed, while a different inactive owner is preserved as audit history and is not reported as the current parked supervisor.

## Pre-Change Live Check

At `2026-07-11 16:20 CST`, the watchdog synchronized issue `2026078`, found no prediction evaluation change, retained pending issue `2026079`, and kept the supervisor parked. No training or self-iteration process was started.

## Validation Plan

- Focused watcher and self-iteration prompt-contract tests.
- Full Python worker test suite.
- Live watcher replay against the parked supervisor and preserved heavy-job metadata.

## Validation Result

- Focused tests: `93 passed`.
- Final full Python worker suite: `565 passed`.
- Live watcher replay emitted:
  - `status=different_inactive_pid`
  - `supervisor_pid=3579268`
  - `heavy_job_pid=3647004`
  - `heavy_job_status=interrupted`
  - `same_pid=false`
  - `different_active_owner=false`
  - `selection_changed=false`
  - `promotion_allowed=false`
- The replay retained `action=await_new_forward_issue`, history issue `2026078`, pending issue `2026079`, passed prediction-input boundaries, and the previously rejected GPU probe. No training or self-iteration process was started.

## Evidence Boundary

This change improves operational ownership observability only. It is not evidence of predictive lift and does not alter the legal sample space, historical windows, null model, frozen-validation quarantine, leakage checks, or forward-evidence threshold.
