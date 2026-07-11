# Forward Evaluation Idempotent Retry — 2026-07-11

## Primary Goal

Guarantee that a failed forward-evaluation release is retried on later watchdog runs even when history no longer changes, while already accepted line evaluations are not repeated.

## Non-Goals

- No model, advisor, source budget, objective, candidate, or promotion change.
- No live supervisor start before issue `2026079` is synced and fully evaluated.
- No acceptance of failed, leaking, mismatched, or partial-ranked-set evaluations.

## Triggering Defect

PR #63 made the first new-issue evaluation failure stop fail closed. On the next cron, however, `previous_issue == current_issue` and `changed_count == 0`, so the old early return could skip the still-due failed snapshot and continue the release path. Removing the early return alone would repeatedly evaluate successful snapshots every ten minutes.

## Gauss-Inspired State Invariant

- **Object:** the finite complete set `S` of due static/dynamic/near snapshot rows.
- **Accepted subset `A`:** rows with the identical line, predicted issue, and snapshot key whose persisted result is `evaluated`, has `leakage_passed=true`, and has `candidate_count == top_n`.
- **Pending set:** `P = S - A`.
- **Transition:** evaluate every row in `P`; any failed row remains in `P` for the next cron, while a newly accepted row moves into `A`.
- **Fixed point:** when `P` is empty, the planner emits no work and the release path may proceed without duplicate evaluation.
- **Boundary:** this proves retry/idempotence only, not forecast quality.

## Change

- Removed the unchanged-history early return from the evaluation batch.
- Loaded persisted evaluations for the exact due snapshots.
- Validated the full three-line snapshot set before subtracting accepted rows.
- Planned only rows without an exact fully accepted persisted evaluation.
- Added tests for unchanged-history retry, partial-batch retry, full idempotent skip, and partial-ranked-set rejection.
- Added the retry invariant to autonomous self-iteration.

## Validation Plan

- Focused planner, watchdog-contract, and prompt-contract tests.
- Full Python worker suite.
- Live pre-draw watchdog replay: with `2026079` absent, the planner must emit zero work, remain parked, and start no supervisor.

## Validation Result

- Focused planner, database-loader, watchdog-contract, prompt-contract, CLI, and evaluator tests: `31 passed`.
- Final full Python worker suite: `593 passed`.
- Watchdog and autonomous self-iteration shell syntax checks passed.
- Final live replay at `2026-07-11 16:56 CST`:
  - history remained at `2026078`;
  - the planner ran despite unchanged history and emitted `count=0` because `2026079` is not yet due;
  - the complete `2026079` three-line snapshot remained pending at `10,000` candidates per line;
  - lifecycle remained `parked_waiting_for_forward_issue` and consistent;
  - no supervisor or self-iteration process started.

## Evidence Boundary

The legal universe, historical/frozen windows, null baseline, quarantine, prediction inputs, selection, and promotion remain unchanged. Accepted-evaluation state is used only to make the release gate retry-safe and idempotent.
