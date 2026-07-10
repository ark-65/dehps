# Training Strict Primary Gate Continuity V1

## Round frame

Primary goal: close two supervisor-lifecycle routes that could weaken the frozen-primary search gate—tail/secondary-only experimental navigation under a strict primary gate, and same-history supervisor restarts that reset stagnation/overfit guard state to zero.

Non-goals:

- no new model, advisor, candidate family, objective, weight, or score threshold;
- no change to formal promotion or frozen-validation ordering;
- no deletion of restart, exploration, tail-risk, or source-frontier diagnostics;
- no automatic promotion or search-base reservation by source;
- no claim that blocking a route makes the incumbent predictively stronger.

## Task Frame

The object is search-navigation acceptance under same-history stagnation. Progress requires every route that runs while `require_frozen_primary_challenger=true` to require a strict candidate-primary score above its baseline, and requires the same guard state to survive a process handoff until formal `improved=true` resets it.

Run `20260710-205704` round 17 exposed the first contradiction:

- eval-slice overfit active with eval primary `[3,3,3]`, frozen primary `[0,0,0]`, and four suspicious candidates;
- stale search-base gate active with `require_frozen_primary_challenger=true`;
- restart candidate frozen primary `[0,0,0]`, baseline `[0,0,0]`, tail-over-1,000,000 delta `-2`;
- broad navigation quality passed and persisted `experimental_navigation_eligible=true` despite no primary lift.

The candidate did not win that round because a strict-primary challenger existed, but the fallback route could have selected it when no challenger existed.

## Historical Boundary

Gauss and Riemann below are historically inspired verification and structural lenses, not literal minds, trained replicas, or sources of authority.

## Gauss Pass: Verification

Strongest claim: persisted round-17 metadata simultaneously asserted that strict frozen-primary lift was required and that a candidate equal to the primary baseline was eligible. This is an exact logical contradiction, independent of future performance.

Weakest assumption: primary-score tuples and same-history fingerprints are the correct invariants. They are already the formal search-gate inputs and are reused without a new threshold.

Verification test: a zero-primary candidate with tail delta `-1` or secondary-frontier improvement may retain broad `quality=passed`, but must persist `primary_lift_passed=false`, `primary_lift_blocked=true`, `eligible=false`, and must not become next search base. A strict-primary candidate remains allowed. Across a handoff, current-run round count may reset, but effective stagnation must not reset unless a formal improvement exists.

Historical boundary note: exact tuple comparisons and persisted-process invariants are modern implementation methods under a Gauss-inspired verification lens.

## Riemann Pass: Structure

Strongest claim: broad navigation quality and strict-primary acceptance are different boundaries. Using the broad boundary inside the strict region creates a false continuation path. Process run id is also only a coordinate; same-history, same-incumbent unresolved stagnation is the invariant state.

Weakest assumption: carrying same-history stagnation across multiple algorithm revisions is conservative rather than misleading. It only tightens a safety gate and never promotes a candidate, so the error direction is fail-closed.

Structural test: preserve current-run reporting separately from effective guard history, then confirm the first new-run round activates the same rank-homogeneity/overfit geometry and uses the next deterministic restart batch rather than returning to the early broad state.

Historical boundary note: state-space and coordinate language is a modern structural analogy under a Riemann-inspired lens.

## Cross-Review

Gauss rejects `quality=passed` as sufficient when the active gate explicitly demands primary lift. Riemann rejects using process identity as a discontinuity when history fingerprint, incumbent, evaluation protocol, and lack of formal improvement are unchanged. Both require formal improvement—not restart—as the reset event.

## Disagreement

- Evidence: carried stagnation proves unresolved same-history search, not model deterioration.
- Scope: guard history is capped at 80 recent records; this is sufficient to preserve the existing 64-round gate but is not an unbounded lifetime count.
- Risk: cross-run records may span code revisions; carryover is conservative because it only strengthens validation requirements.
- Method: tail and secondary-frontier improvements remain recorded and can support diagnostics, but cannot satisfy a strict-primary gate.

## Synthesis

Smallest shared conclusion: make strict primary lift an explicit conjunct for experimental navigation, persist pass/block metadata, recover recent same-history unpromoted guard rounds across process handoffs, clear them only after current-run formal improvement, and show current-run versus effective stagnation separately in watcher output.

## Implementation

- Experimental navigation now records `exploration_navigation_primary_lift_passed` and `exploration_navigation_primary_lift_blocked`.
- Strict-gate eligibility requires candidate primary score strictly greater than the baseline in addition to broad quality, distance, and rank-vector checks.
- The watcher reports `frozen_primary_lift_required` as the eligibility reason even when broad tail/secondary quality passed.
- Same-history navigation records now include formal `improved` state.
- The supervisor recovers up to 80 consecutive unpromoted guard rounds across run ids without adding them to current-run round reporting.
- A current-run formal improvement clears carryover guard history; a process restart does not.
- Rank homogeneity, restart catalog position, eval-slice overfit, near-miss recovery, and stale search-base gates use effective guard history.
- The watcher exposes current-run and effective stagnation separately.
- A newly restored high-stagnation run receives the existing four-round observation window before another restart request, preventing watchdog restart loops.
- The two-hour self-iteration prompt and project memory require `guard_continuity` review after handoff.

## Live verification

Intermediate run `20260710-232445` demonstrated the old lifecycle defect after the first routing-only patch: rounds 1 and 2 logged `stagnation=0` and `stagnation=1` despite the prior same-history run having 19 unresolved rounds.

Final run `20260710-234151`, PID `2712576`:

- revalidated continuity search base `6e670c97...` with frozen primary `[0,0,1]` versus baseline `[0,0,0]`;
- recovered 80 capped unpromoted records from 10 same-history runs;
- round 1 started at effective `stagnation=80`, rank-homogeneity batch 76/catalog offset 380, rather than zero;
- eval-slice overfit and stale search-base gates were active immediately;
- restart `c6deb344...` remained fully evaluated at rank 5 and changed all 100 target ranks;
- restart primary `[0,0,0]` equaled baseline, so metadata persisted `primary_lift_passed=false`, `primary_lift_blocked=true`, and `eligible=false`;
- decision stayed on the incumbent and next search base remained unchanged;
- promotion was evaluated and blocked by `frozen_validation_not_better` without bypass;
- watcher reported current-run stagnation 1 and effective stagnation 80 separately;
- watcher action became `watch_stagnation_recovery`, with restart not requested during the four-round post-handoff observation window;
- all advisors were current at issue `2026078`; null, parser, sync, duplicate, legal-universe, and leakage checks passed.

Round 2 completed without a runtime error:

- effective stagnation advanced from 80 to 81 while current-run reporting advanced independently to round 2;
- rank-homogeneity restart advanced from batch 76/catalog offset 380 to batch 77/offset 385;
- eval-slice overfit remained active with eval primary `[3,3,3]`, frozen primary `[0,0,0]`, and five suspicious candidates;
- the source-frontier/restart candidate changed all 100 target ranks, but the search base still remained `6e670c97...` and no formal improvement was recorded;
- dynamic KDJ scored `[1,1,2]` versus the static `[3,3,3]`, so this round provides no model-strength claim;
- watcher recorded `round_lag=0`, effective stagnation 81, current-run stagnation 2, current advisor signals, and `watch_stagnation_recovery` without requesting a restart.

## Validation

- focused strict-navigation/guard-continuity supervisor tests: `20 passed`;
- watcher suite: `61 passed`;
- PostgreSQL storage suite: `23 passed`;
- full worker suite: `462 passed`;
- `bash -n scripts/hourly_self_iterate.sh` and `git diff --check` passed.

## Predeclared falsification

- If a zero-primary candidate becomes experimental-navigation eligible while strict primary is required, the routing fix fails.
- If a same-history, unpromoted handoff starts effective stagnation at zero, guard continuity fails.
- If current-run round count is inflated by carryover records, reporting isolation fails.
- If formal improvement cannot clear carried guard history, the reset rule is too strict.
- If the watchdog immediately requests another restart before the four-round observation window, lifecycle stabilization fails.
- If promotion bypasses frozen validation, scientific acceptance fails.
- If static best and frozen promotion remain unchanged, do not claim model-strength improvement.

## Next Verification

- Continue observing later rounds to confirm effective stagnation and strict-primary enforcement remain stable beyond the two-round live acceptance window.
- After four current-run rounds, allow restart readiness only when the existing candidate-evidence checks pass; do not restart merely from the carried count.
- Continue seeking formal frozen promotion or a new static rank signature as separate evidence from guard correctness.

## Guardrail

Legal sample space, ten-year current-regime history, ranked-uniform null context, advisor freshness, parser/sync/duplicate checks, and frozen promotion remain unchanged evidence boundaries.
