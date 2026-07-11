# Self-Iteration Evidence Audit Contract

Date: 2026-07-11

## Round scope

- Primary goal: require scheduled self-iteration to consume the newly available
  candidate-budget evidence geometry and sequential-null coverage audit.
- Non-goals: no training, advisor, strategy, source budget, objective, search,
  selection, promotion, or prediction changes.

## Initial evidence

The live watcher already exposed two stronger diagnostics:

- candidate-source budget geometry with eight distinct conversion signatures,
  one history surface, one final-performance signature, and
  `automatic_budget_change_allowed=false`; and
- sequential-null coverage with `23/317` reconstructable rounds, a `294/317`
  legacy gap, arithmetic invariants, incomplete adaptive/sequential
  multiplicity, `candidate_signal_interpretable=false`, and
  `automatic_promotion_allowed=false`.

The scheduled prompt still referenced only the older raw budget-review window
and nested ledger fields.  A future automated turn could therefore see
`budget_review_ready=true` without being explicitly required to distinguish
operational conversion variety from repeated performance, or could discuss a
small observed-family p-value without reporting the 92.7% legacy gap.

## Change

`scripts/hourly_self_iterate.sh` now requires every scheduled agent to:

- read source-conversion, history-surface, and final-performance signature
  counts, evidence geometry, experiment-candidate readiness, limitations, and
  the automatic budget-change flag;
- treat eight raw rounds only as permission to propose one predeclared,
  single-variable budget experiment, never as eight independent performance
  observations;
- keep automatic budget changes disabled and never reduce multiple source
  budgets together;
- read the dedicated sequential-null audit coverage, legacy gap, arithmetic
  invariants, three p-value levels, completeness, signal interpretability, and
  automatic-promotion flag;
- fix invalid ledger arithmetic first and keep incomplete observed lower bounds
  at `noise_risk` regardless of a small local p-value.

The project self-iteration memory records the same durable rules.  A new prompt
contract test fails if the critical fields or prohibitions are removed in a
future edit.

## Validation

- `bash -n scripts/hourly_self_iterate.sh`: passed.
- Prompt-contract and PR-publish focused tests: `10 passed`.
- Full worker regression: `551 passed`.
- Live watcher remained `await_new_forward_issue`; advisor signals remained
  current; budget geometry remained
  `distinct_source_conversion_same_performance`; automatic budget change and
  automatic promotion remained false.

## Interpretation

This change makes the scheduler consume existing scientific guardrails; it does
not create new evidence or alter the model.  The next scheduled iteration must
continue waiting for issue `2026079` unless a genuine runtime or data-boundary
failure appears.
