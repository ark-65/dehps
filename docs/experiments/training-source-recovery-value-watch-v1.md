# Training Source Recovery Value Watch V1

## Round frame

Primary goal: prevent mature candidate-source budget review from labeling a source unproductive when that source has produced an explicitly verified frozen-primary frontier or an actually selected guarded-navigation recovery.

Non-goals:

- no candidate-budget, prefilter, model, advisor, search, restart, objective, or promotion change;
- no source reservation or automatic budget increase;
- no conversion of navigation evidence into promotion or predictive evidence;
- no new score threshold: require the existing strict frozen-primary tuple comparison;
- no claim that a frozen-window recovery candidate proves future lift.

## Task Frame

The object of study is the nine-round current-run source-survival window for supervisor `20260710-205704`. Progress requires source-budget diagnostics to distinguish eval-slice Top5 productivity from guarded recovery productivity while preserving the same frozen-promotion and null/leakage boundaries.

At the eight-round maturity boundary, the old watcher reported:

- `stagnation_restart`: generated 20, prefilter-selected 6, full-eval Top5 0, round-best 0;
- `budget_review_sources=[stagnation_restart,target_weight_inversion,weight_kdj]`;
- in the same round, restart `bc77ceed...` was full-eval rank 11, changed all 100 target ranks, improved frozen-primary `[0,0,0] -> [0,0,1]`, became the active source-frontier champion, and became the next search base.

The old scalar definition therefore contradicted the persisted recovery evidence.

## Historical Boundary

Gauss and Riemann below are historically inspired verification and structural lenses, not literal minds, trained replicas, or sources of authority.

## Gauss Pass: Verification

Strongest claim: the same authoritative round record placed `stagnation_restart` in the mature unproductive-budget list while recording a strict frozen-primary lift and source-frontier navigation from that source.

Weakest assumption: one verified recovery event is sufficient to prevent the label `persistently_unproductive`. It is not sufficient to increase the source budget, promote the candidate, or claim predictive lift.

Verification test: require `source_frontier_champion.active=true`, a non-empty source/hash, and an exact lexicographic primary score improvement before counting a frozen-frontier round. Count guarded navigation only when decision and next-search-base hashes equal that frontier hash. Equal or missing primary scores must not count.

Historical boundary note: exact tuple comparison and residual-style accounting are modern implementation choices under a Gauss-inspired verification lens.

## Riemann Pass: Structure

Strongest claim: candidate-source value has at least two coordinates—eval-slice leaderboard conversion and frozen-guarded recovery. Collapsing both to Top5 produces a coordinate artifact: a source can be useless for Top5 competition but useful for escaping a local search chart.

Weakest assumption: the current frozen window represents a meaningful local continuation direction. It may still be a one-window fluctuation.

Structural test: retain separate `productive` and `productive_recovery` states, then observe whether future recovered search bases lead to new rank signatures or formal promotion without using the recovery window to select promotion winners.

Historical boundary note: the state-space and coordinate language is a modern structural analogy under a Riemann-inspired lens.

## Cross-Review

Gauss rejects counting any active flag without verifying candidate-primary strictly exceeds baseline-primary. Riemann rejects preserving a Top5-only scalar because it erases the operational purpose of recovery sources. Both reject treating recovery evidence as promotion evidence.

## Disagreement

- Evidence: a single frozen-frontier round prevents an `unproductive` label but does not establish an optimal budget.
- Scope: a source may be `productive_recovery` with zero Top5 and zero round-best rounds.
- Risk: repeated candidate search makes frozen-window discoveries vulnerable to selection effects; formal promotion remains separate.
- Method: guarded navigation is counted only for exact hash continuity, while frozen-frontier discovery is counted even if another qualified challenger becomes search base.

## Synthesis

Smallest shared conclusion: keep existing generated/prefilter/Top5/round-best rates, add verified `frozen_frontier_rounds` and exact-hash `guarded_navigation_rounds`, classify frozen-frontier-only sources as `productive_recovery`, and exclude them from the mature unproductive-budget list without changing training behavior.

## Implementation

- The watcher aggregates strict frozen-primary source-frontier events per source.
- It separately counts exact decision-to-search-base guarded navigation.
- Source state can now be `productive_recovery` when Top5 and round-best are zero but verified frozen-frontier evidence exists.
- `recovery_productive_sources` is exposed in JSON, operator summary, and Markdown.
- The Markdown source table exposes frozen-frontier and guarded-navigation counts.
- The two-hour self-iteration prompt and project memory require these fields before proposing a source-budget reduction.
- A source with equal/missing primary scores remains unproductive; an `active` flag alone is insufficient.

## Live verification

Modified watcher over run `20260710-205704`:

- round 8: `stagnation_restart` became `productive_recovery`, with one frozen-frontier round and one guarded-navigation round;
- round 9: Weight KDJ candidate `7cfc18fd...` reached full-eval rank 10, changed all 100 target ranks, and improved frozen-primary `[0,0,0] -> [0,0,1]`;
- after round 9, both `stagnation_restart` and `weight_kdj` are in `recovery_productive_sources` despite zero Top5;
- mature `budget_review_sources` narrowed from three sources to only `target_weight_inversion`, which still has zero Top5, zero round-best, zero frozen-frontier, and zero guarded-navigation evidence;
- watcher remained `ok/continue_current_run`; all advisors remained current at issue `2026078`;
- promotion remained evaluated and blocked by `frozen_validation_not_better` without bypass;
- static best config and metrics remained repeated for nine rounds, so no model-strength claim is made.

No supervisor restart was performed because this round changes watcher interpretation and the self-iteration prompt only; the already-running training algorithm and process were not modified. The current supervisor supplied live round-8/9 database evidence for the new watcher.

## Post-implementation continuation

At 16 completed rounds, the latest 12-round watcher window provided a broader out-of-example check:

- `recency_canary`: frozen-frontier/guarded-navigation rounds `1/1`;
- `ridge_kdj`: frozen-frontier/guarded-navigation rounds `2/0`;
- `stagnation_restart`: frozen-frontier/guarded-navigation rounds `3/3`;
- `target_weight_inversion`: frozen-frontier/guarded-navigation rounds `2/2`;
- `weight_kdj`: frozen-frontier/guarded-navigation rounds `1/0`;
- every active source had either Top5/round-best or strict recovery evidence, so mature `budget_review_sources` became empty;
- advisor freshness remained current at issue `2026078`, with no watcher database-read error;
- the latest 12 static best configs and metric signatures still repeated exactly, watcher action became `watch_stagnation_recovery`, and formal promotion remained blocked without bypass.

This continuation supports the generic source-accounting fix across multiple candidate families. It still does not show formal model improvement; recovery-frontier diversity and incumbent improvement remain separate states.

## Validation

- watcher suite: `57 passed`;
- self-iteration publishing tests: `8 passed`;
- full worker suite: `454 passed`;
- `bash -n scripts/hourly_self_iterate.sh` passed;
- `git diff --check` passed.

## Predeclared falsification

- If equal or missing primary scores create recovery value, the fix fails closed incorrectly.
- If a recovery-only source remains in `budget_review_sources`, the source-state correction fails.
- If recovery evidence changes candidate budgets, promotion, or search behavior, the scope is too broad.
- If a source is promoted or described as predictively stronger solely from recovery state, scientific acceptance fails.
- If later rounds retain the same static best and frozen promotion failure, report audit improvement only.

## Next Verification

- Continue observing whether the `bc77...` and later guarded search trajectory produces a new static rank signature or formal frozen-promotion pass.
- Treat `target_weight_inversion` as an experiment candidate only after a separate same-history, single-variable, predeclared budget hypothesis; do not change it in this watcher round.
- Revisit the round-7 `restart_not_in_full_eval` gap only if another rotated batch is skipped, so audit-slot changes are not confounded with the newly observed frontier trajectory.

## Guardrail

Legal sample space, ten-year current-regime history, ranked-uniform null context, advisor freshness, parser/sync/duplicate checks, and frozen promotion remain unchanged evidence boundaries.
