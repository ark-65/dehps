# Training Restart Navigation Quality Gate V1

## Round frame

Primary goal: make search-base routing honor the existing experimental-navigation quality decision when a restart champion re-enters the same function through the standard `round_best`, challenger, or replay branches.

Non-goals:

- no change to restart generation, rotation, budget, prefilter, full evaluation, or champion diagnostics;
- no change to incumbent promotion, frozen validation, objective, model, advisor, or candidate family;
- no new quality threshold: reuse the existing frozen-primary/tail/source-frontier diagnostic;
- no deletion of failed restart evidence;
- no claim that blocking a poor search base makes the model predictively stronger.

## Task frame

Final rotation run `20260710-195125` exposed an exact routing inconsistency:

- round 6 restart `106e8166...`: frozen-primary `[0,0,0]`, tail-over-1,000,000 delta `+2`, no source-frontier lift;
- round 7 restart `9ea23209...`: frozen-primary `[0,0,0]`, tail delta `+1`, no source-frontier lift;
- in both rounds the watcher classified experimental navigation as `zero_frozen_primary_without_tail_or_frontier_lift` and `eligible=false`;
- the same config hash was nevertheless selected as `decision_round_best` and became search base through the standard `round_best` branch;
- formal promotion failed with `frozen_validation_not_better` and was not bypassed.

Progress means the restart candidate remains fully evaluated and auditable, but a hash that fails the existing navigation-quality function cannot become search base through any alias branch. A quality-passed restart and a formally improved candidate must remain allowed.

## Historical boundary

The Gauss and Riemann names below denote historically inspired reasoning lenses, not literal minds, trained replicas, or sources of authority.

## Gauss pass: verification

Strongest claim: persisted metadata for two consecutive rounds simultaneously records `experimental_navigation_eligible=false`, a failing quality reason, `search_base.source=round_best`, and `search_base.config_hash` equal to the failed restart hash. This is an exact branch inconsistency.

Weakest assumption: the existing experimental-navigation quality function is the correct navigation boundary. It is already used to judge the same candidate and requires frozen-primary lift, reduced tail risk, or source-frontier improvement; this round reuses it rather than selecting a new post-hoc threshold.

Verification test: reproduce the alias with the restart object passed as both `round_best` and experimental navigation candidate. Assert that a failed hash is excluded from round-best, challenger, fallback, and replay paths; assert an alternative challenger is selected or the current base remains unchanged; assert quality-passed and formally improved candidates remain allowed.

## Riemann pass: structure

Strongest claim: one candidate object was represented in two coordinate systems—experimental recovery and standard round-best—and the quality boundary applied to only one representation. Hash identity is the invariant that should carry the boundary across branches.

Weakest assumption: preventing the poor candidate from becoming search base will improve the global search trajectory. It only removes a known-inconsistent transition; the selected alternative may still fail frozen validation.

Structural test: keep the failed restart candidate in generated, prefilter, full-eval, champion, and source-survival evidence while confirming the next search base uses a different hash. Observe subsequent rank diversity and frozen results without claiming lift from the routing correction alone.

## Cross-review

Gauss rejects discarding the restart candidate before evaluation because that would hide evidence and confound the rotation experiment. Riemann rejects a branch-local fix that blocks only the explicit experimental fallback while allowing the identical hash through standard aliases. Both accept a hash-level exclusion applied only inside search-base selection after quality evaluation.

## Disagreement

- Evidence: a different search base is operational correctness, not proof of model improvement.
- Scope: `decision_round_best` may still feed diagnostics or advisors; this round gates only search-base movement.
- Risk: an eval-slice candidate with no frozen or frontier evidence remains susceptible to repeated-search overfit even when it reaches Top5.
- Method: formally improved candidates bypass this navigation block because they have already passed the existing promotion decision supplied to the function.

## Synthesis

Smallest shared conclusion: compute the existing navigation quality before selecting challengers, exclude a failed experimental candidate hash from standard round-best, challenger, fallback, and replay routes, persist explicit block metadata, and leave evaluation and promotion untouched.

## Implementation

- `select_next_search_base` now computes quality-blocked hashes before challenger selection.
- A failed hash is excluded from primary challenger and fallback challenger searches.
- The standard round-best and current-base-replay branches cannot select the same failed hash.
- `improved=true` is explicitly exempt from the navigation-quality block.
- Search-base metadata records `round_best_quality_blocked`, `round_best_quality_reason`, `quality_blocked_config_hashes`, and `exploration_navigation_quality_blocked`.
- Watcher gate, recommendation, evidence-context, and operator summaries expose the quality block.

## Static validation

- focused next-search-base/experimental-navigation tests: `17 passed`;
- watcher suite: `54 passed`;
- full worker suite: `451 passed`;
- `git diff --check` passed.

## Fresh supervisor

- run id: `20260710-205704`;
- PID: `2551736`;
- issue: `2026078`;
- Weight KDJ share: baseline `0.22`;
- rounds 1–4 completed normally without improvement; round 5 preserved batch-0 restart compatibility;
- round 6 activated exact-repeat recovery with `restart_batch_index=1` and `restart_catalog_offset=5`;
- restart champion `106e8166...` remained fully evaluated at rank 12 and changed all 100 target ranks;
- its frozen-primary score was `[0,0,0]`, tail-over-1,000,000 delta was `+2`, and neither source-frontier score improved;
- the existing quality function returned `zero_frozen_primary_without_tail_or_frontier_lift`;
- persisted search-base metadata records `round_best_quality_blocked=true`, `exploration_navigation_quality_blocked=true`, and the blocked hash `106e8166...`;
- the next search base was the distinct challenger `fb567900...`, so the failed restart hash did not re-enter through round-best, challenger, fallback, or replay aliases;
- restart generation and evidence remained auditable: 5 candidates were generated, 2 survived prefilter, and the champion remained in the full-evaluation report;
- frozen validation ran and blocked promotion with `frozen_validation_not_better`; it was not bypassed;
- the watcher reported `severity=ok`, `action=continue_current_run`, all four advisors current at issue `2026078`, and no parser, sync, duplicate, or legal-universe error;
- the supervisor remained active after the validated round and continued into round 7.

Live requirement passed: the first quality-failing rotated restart remained evaluated but was not selected as search base.

## Predeclared falsification

- If a quality-failed restart hash still equals the next search-base hash through any branch, the fix fails.
- If the restart candidate disappears before full evaluation or champion/source-survival reporting, auditability regresses and the fix fails.
- If a quality-passed restart or formally improved candidate is blocked solely by this change, the scope is too broad and the fix fails.
- If promotion bypasses frozen validation, scientific acceptance fails.
- If routing changes but frozen validation does not improve, do not describe the model as stronger.

## Guardrail

This is a navigation consistency correction. Legal sample space, history window, ranked-uniform null context, advisor freshness, parser/sync/duplicate checks, and frozen promotion remain the evidence boundaries.

The run still had no frozen-primary lift and repeated static round metrics. The alternative search base is evidence that the routing loop is now internally consistent, not evidence that the prediction model is stronger. A later round must separately test whether the new trajectory improves diversity or frozen validation.
