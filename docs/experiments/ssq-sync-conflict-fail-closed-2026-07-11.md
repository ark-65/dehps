# SSQ Sync Conflict Fail-Closed — 2026-07-11

## Primary Goal

Prevent forward evaluation, advisor refresh, and supervisor startup whenever synced draw numbers conflict with stored history or unresolved conflict evidence exists.

## Non-Goals

- No automatic deletion or resolution of conflict evidence.
- No model, advisor, budget, candidate, objective, selection, or promotion change.
- No claim that a successful HTTP/sync status proves draw-number agreement.

## Triggering Defect

The watcher considered the latest sync safe whenever status was not `failed` or `error`, even if `conflict_count > 0`. The cumulative `ssq_data_conflicts` count was displayed but did not affect `ok`. The watchdog itself had no conflict gate before evaluation, advisor refresh, or supervisor startup.

## Gauss-Inspired Integrity Invariant

- **Object:** canonical history `H`, latest sync conflicts `C_latest`, and recorded unresolved conflict evidence `C_recorded`.
- **Release condition:** `C_latest = 0` and `C_recorded = 0`, with both counts parseable.
- **Failure condition:** any positive or unknown conflict count stops release before derived evaluations or training state can consume ambiguous labels.
- **Boundary:** this proves label consistency is not knowingly ambiguous; it does not prove source truth or predictive quality.

## Change

- Added parseable latest-sync and cumulative-conflict checks to the watchdog.
- Conflict or unreadable count exits before forward evaluation.
- Watcher `ok` now requires zero latest and recorded conflicts.
- Recommendation becomes alert with `inspect_parser_sync_conflicts`.
- Autonomous self-iteration must preserve conflict evidence and cannot restart around it.

## Validation Plan

- Focused recommendation, orchestration-contract, and prompt-contract tests.
- Full Python worker suite.
- Live zero-conflict replay must evaluate no due rows, remain parked, and start no supervisor.

## Validation Result

- Focused watcher recommendation, watchdog-contract, and prompt-contract tests: `108 passed`.
- Final full Python worker suite: `599 passed`.
- Watchdog and autonomous self-iteration shell syntax checks passed.
- Live zero-conflict replay at `2026-07-11 17:12 CST`:
  - latest sync status was success with `conflict_count=0`;
  - `latest_sync_ok=true`, `data_conflicts_ok=true`, and recorded conflict count was zero;
  - no due evaluation rows were emitted;
  - lifecycle remained parked and no supervisor or self-iteration process started.

## Evidence Boundary

Legal universe, historical/frozen windows, null baseline, quarantine, leakage rules, prediction inputs, and promotion remain unchanged. The gate prevents known ambiguous draw labels from entering the release path.
