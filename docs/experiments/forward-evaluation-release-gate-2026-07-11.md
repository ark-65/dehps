# Forward Evaluation Release Gate — 2026-07-11

## Primary Goal

Fail closed when a newly synced issue cannot be evaluated against a complete, pre-sync static/dynamic/near snapshot set, before advisor refresh or fresh-supervisor startup.

## Non-Goals

- No model, advisor, source budget, objective, candidate, or promotion change.
- No restart while issue `2026079` remains unsynced.
- No retroactive construction of missing predictions.
- No predictive-lift claim.

## Triggering Defect

The watchdog logged an individual prediction-evaluation failure but returned success from the batch and continued toward advisor refresh and supervisor startup. An unreadable, empty, incomplete, duplicate, or leaking snapshot plan could also produce no evaluation commands and still be treated as successful.

## Gauss-Inspired Verification Pass

- **Object:** the finite release set of prediction snapshots captured before history sync.
- **Known:** the forward protocol requires exactly three line keys: `static_100`, `dynamic_kdj`, and `dynamic_kdj_near`.
- **Invariant:** each eligible predicted issue has one unique snapshot per line; every line has exactly its declared `top_n` candidates; every `as_of_issue` is strictly earlier than its predicted issue and no later than the pre-sync history issue.
- **Boundary cases:** empty snapshots, one missing line, duplicate line, partial candidate set, malformed issue, history regression, snapshot mismatch, zero candidates, and leakage failure.
- **Proof obligation:** a history advance has at least one complete eligible three-line plan, and every CLI evaluation exits successfully before advisor refresh or supervisor launch.
- **Smallest justified conclusion:** the gate proves evaluation-plan completeness and failure propagation only; it does not prove forecast quality.

## Change

- Added a pure forward-evaluation planner with exact line completeness, candidate-set cardinality, uniqueness, issue-order, and pre-sync leakage checks.
- Replaced the unchecked process-substitution planner with an explicitly checked TSV plan artifact.
- Made the prediction-evaluation CLI return nonzero unless status is `evaluated`, leakage passed, and candidates are present.
- Made any plan or line-evaluation failure stop the watchdog before advisor refresh and supervisor startup.
- Added the release invariant to the autonomous self-iteration contract.

## Pre-Change Live Check

At `2026-07-11 16:40 CST`, history remained at `2026078`, the complete `2026079` snapshot remained pending, and the watchdog correctly stayed on the unchanged-history skip path without starting training.

## Validation Plan

- Pure planner boundary tests.
- Evaluation CLI acceptance tests.
- Watchdog ordering contract test and shell syntax check.
- Full Python worker test suite.
- Live unchanged-history watchdog replay, which must remain parked and must not start a supervisor.

## Validation Result

- Focused planner, CLI, watchdog-contract, prompt-contract, and evaluator tests: `24 passed`.
- Final full Python worker suite: `586 passed`.
- Shell syntax checks passed for the watchdog and autonomous self-iteration scripts.
- Updated watchdog live replay at `2026-07-11 16:47 CST`:
  - sync remained at `2026078` with zero inserted/updated draws;
  - evaluation correctly used the unchanged-history skip path;
  - the complete three-line `2026079` snapshot remained pending with exactly `10,000` candidates per line;
  - lifecycle remained `parked_waiting_for_forward_issue`;
  - no supervisor or self-iteration process started.
- Non-mutating live negative CLI check against the real `2026079` static snapshot returned `status=missing_actual_draw` and exit status `1`, proving that a non-accepted evaluation now propagates failure. Persistence and report writes were disabled for this check.

## Evidence Boundary

The legal red-ball universe remains `1,107,568`; historical search/frozen windows, null baseline, quarantine, selection, and promotion are unchanged. This gate protects forward-evidence integrity but cannot turn aggregate or historical evidence into predictive proof.
