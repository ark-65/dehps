# Forward Line Completion v1

## Problem

A production target contains independent named lines. Exactly-once identity is
`line_key + target_issue`; it is not an all-lines batch identity.

Previously, `refresh_training_prediction_lines_current` built every requested
line and persisted them in fixed order. If `static_100` already had an active
run, storage raised `active_forward_prediction_exists` before a later missing
`dynamic_kdj_near` line could be written. Repeating training could never complete
the target, even though creating the missing line would not conflict with an
existing production identity.

## Contract

The default single-line storage API remains fail-closed. A caller must explicitly
set `reuse_active=True` to use completion semantics.

For each line in a multi-line refresh:

1. acquire a transaction-scoped advisory lock for `line_key + target_issue`;
2. look up an active `pending`, `evaluating`, or `evaluation_failed` run;
3. if present, return its immutable identity as `reused_active` without writing
   candidates, metadata, dashboard rows, or status;
4. if absent, create the run and candidates through the normal strict-v1 path;
5. return `created` with the new production identity.

The refresh result includes `line_persistence`, `created_lines`, and
`reused_active_lines`. This makes partial completion observable and prevents an
expected production lock from being reported as a generic training error.

## Invariants

- Existing active runs are never silently superseded.
- Candidate rows belonging to a reused run are never deleted or rewritten.
- A missing line uses current history, an explicit ranking contract, and the
  normal simultaneous shadow-capture path.
- Repeating the same refresh reuses all active lines.
- Concurrent completion attempts serialize per line inside the database
  transaction.

## Non-goals

- No automatic backfill of a live target.
- No change to line selection, training policy, score, rank, or evaluation.
- No relaxation of the one-active-run-per-line database constraint.
