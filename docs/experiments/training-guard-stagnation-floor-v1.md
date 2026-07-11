# Training Guard Stagnation Floor V1

## Round frame

Primary goal: preserve the monotonic same-history stagnation position and deterministic restart-catalog position across supervisor handoffs even after the bounded 80-record navigation window is saturated.

Non-goals:

- no new model, advisor, candidate source, objective, weight, threshold, or promotion rule;
- no expansion of the bounded rank-signature history window;
- no use of an uncommitted partial round as training evidence;
- no claim that continued catalog coverage is predictive lift.

## Task Frame

The object is supervisor guard state under same-history, unpromoted training. Local rank geometry needs only a bounded recent window, but the global stagnation coordinate and restart batch must continue monotonically until formal `improved=true`.

Before the patch, the latest durable record for run `20260710-234151` was round 3 with persisted effective stagnation 82. That round was unpromoted, so an uninterrupted next round starts at 83. The recovery query returned 80 records and the old recovery function returned stagnation 80 solely because the query window was full.

## Historical Boundary

Gauss and Riemann below are historically inspired verification and structural lenses, not literal minds, trained replicas, or sources of authority.

## Gauss Pass: Verification

Strongest claim: `82 + one completed unpromoted round = 83`, while the old recovery result was 80. This is an exact state-continuity failure, not a model-performance interpretation.

Weakest assumption: the latest durable record's `guard_continuity.effective_stagnation_rounds` is the count at that round's start. The uninterrupted supervisor logs confirm this convention: completed rounds logged 80, 81, and 82 in sequence.

Verification test: with a saturated three-record test window whose latest record persists effective stagnation 82, recovery must keep three rank-signature records but expose stagnation 83. Restart batch under the existing threshold 4 and budget 5 must be 79 at offset 395.

Historical boundary note: persisted counters, database transactions, and deterministic catalogs are modern implementation methods under a Gauss-inspired verification lens.

## Riemann Pass: Structure

Strongest claim: the old implementation identified two different spaces—the finite recent-signature neighborhood and the global path coordinate. Saturating the finite neighborhood folded the global path back onto an earlier restart catalog region.

Weakest assumption: a monotonic counter remains meaningful across code revisions. It is conservative here because it only controls diagnostic pressure and deterministic coverage; it cannot promote a candidate or weaken frozen validation.

Structural test: preserve only the bounded recent records for rank-homogeneity geometry, preserve the global counter as a scalar floor, and verify that a handoff continues the first uncommitted catalog batch instead of returning to batch 76.

Historical boundary note: state-space and coordinate language is a modern structural analogy under a Riemann-inspired lens.

## Cross-Review

Gauss rejects inferring the global count from `len(records)` once the SQL `LIMIT` is saturated. Riemann rejects expanding the record window indefinitely merely to preserve one scalar. Both require a bounded local history plus a separately persisted monotonic position.

## Disagreement

- Evidence: a process log after `strategy_memory` is not proof that the database transaction committed.
- Scope: an interrupted partial round may legitimately repeat its restart batch after handoff.
- Risk: a corrupt persisted counter could be conservative and move coverage forward too far; it still cannot bypass promotion, but should remain observable.
- Method: formal improvement, not process identity or search-base change, remains the only reset event.

## Synthesis

Use the latest durable record's effective stagnation plus its completed unpromoted outcome as a floor, keep the 80-record signature history bounded, add current-run completed rounds on top of the floor, and reset to current-run post-improvement rounds only after formal `improved=true`.

## Implementation

- `recover_supervisor_guard_history` retains the bounded record list for rank signatures.
- It reads the latest durable `effective_stagnation_rounds`, derives `persisted_next_stagnation_rounds`, and applies it only when an unpromoted history record is recoverable.
- New metadata exposes `continuity_floor_applied` and `record_window_saturated` alongside observed and effective counts.
- `active_supervisor_stagnation_round_count` keeps the scalar carryover separate from the bounded signature list and clears carryover after a current-run formal improvement.
- The two-hour self-iteration prompt and project memory require monotonic floor review and define a completed handoff boundary as watcher `target_complete_round_recorded` plus a durable database row.

## Live verification

Pre-patch real-database replay:

- records loaded: 80;
- latest durable run/round: `20260710-234151` round 3;
- latest persisted effective stagnation: 82;
- uninterrupted next stagnation: 83;
- old recovered stagnation: 80.

Post-patch real-database replay returned:

- `recovered_round_count=80`;
- `stagnation_rounds=83`;
- `persisted_effective_stagnation_rounds=82`;
- `persisted_next_stagnation_rounds=83`;
- `continuity_floor_applied=true`;
- `record_window_saturated=true`.

The old process logged round 4 calculations through `strategy_memory`, but its round-4 database transaction had not committed before the controlled termination. Its latest durable round therefore remained round 3. This is a useful failure case: repeating batch 79 is correct, while claiming round 4 complete would be incorrect.

Fresh run `20260711-001405`, PID `2747049`:

- revalidated a same-history navigation search base with frozen primary `[0,0,1]` versus baseline `[0,0,0]`;
- startup logged `seeded_guard_continuity=stagnation=83 signatures=6/80`;
- round 1 started at effective stagnation 83 rather than the saturated-window length 80;
- round 1 used restart batch 79/catalog offset 395, exactly following the last durable batch 78;
- the restart champion changed all 100 target ranks but had frozen primary `[0,0,0]`, so strict-primary metadata blocked it from navigation;
- decision evidence still found a separate source-frontier candidate at `[0,0,1]`, while formal promotion remained blocked by `frozen_validation_not_better` without bypass;
- dynamic KDJ `[0,1,2]` and near-dynamic `[0,0,1]` both remained below static `[3,3,3]`;
- the watcher exposed the saturated 80-record window, persisted effective 82, persisted-next/effective 83, and `continuity_floor_applied=true`;
- round 2 started at effective stagnation 84, proving round 1 was durably committed before current-run continuation;
- round 2 used batch 80/catalog offset 400 and was durably recorded with watcher `round_lag=0`;
- its restart champion again changed all 100 target ranks but remained frozen-primary `[0,0,0]` and was blocked from navigation;
- near-miss inversion supplied separate recovery evidence at strict frozen primary `[0,0,1]`, without receiving promotion or bypass;
- dynamic KDJ remained `[0,1,2]`, near-dynamic remained `[0,0,1]`, and static remained `[3,3,3]`;
- watcher reported effective stagnation 84 versus current-run stagnation 2, `watch_stagnation_recovery`, and no immediate restart request;
- all advisor families were current at issue `2026078`; legal-universe, ranked-uniform null, parser, sync, duplicate, and leakage checks passed.

## Validation

- focused guard/restart tests: `7 passed`;
- full worker suite: `465 passed`;
- shell syntax and `git diff --check`: passed.

## Predeclared falsification

- If a handoff starts below the latest durable persisted effective count plus its completed unpromoted round, the floor fix fails.
- If a partial, uncommitted round advances the counter, the durability boundary fails.
- If the bounded rank-signature list grows to the scalar stagnation count, bounded-memory separation fails.
- If restart batch/catalog offset returns below the latest durable batch, catalog continuity fails.
- If current-run round reporting includes carryover rounds, reporting isolation fails.
- If formal improvement cannot reset carryover, the counter is too strict.
- If promotion bypasses frozen validation, scientific acceptance fails.
- If static/frozen metrics remain unchanged, do not claim model-strength improvement.

## Next Verification

- At the next natural handoff, verify latest durable round 2 derives startup floor 85 rather than the 80-record window length.
- Continue monitoring for formal frozen promotion or a new rank signature as evidence distinct from counter correctness.
- Keep using watcher `target_complete_round_recorded` rather than a pre-transaction log line as the durable handoff boundary.

## Guardrail

Legal sample space, ten-year current-regime history, ranked-uniform null context, advisor freshness, frozen promotion, strict-primary navigation, and leakage boundaries remain unchanged.
