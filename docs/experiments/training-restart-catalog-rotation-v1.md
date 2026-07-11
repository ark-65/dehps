# Training Restart Catalog Rotation V1

## Round frame

Primary goal: prevent consecutive rank-homogeneity recovery rounds from spending the same five reserved slots on the same deterministic restart candidates while preserving the existing budget, candidate catalog, frozen promotion gate, and deterministic supervisor continuity recovery.

Non-goals:

- no new model, advisor, feature, objective, weight, candidate family, or promotion threshold;
- no increase to the five-of-28 restart budget;
- no deletion of the previously observed restart champion;
- no source quota, source-based promotion, or frozen-validation bypass;
- no predictive-strength claim from additional candidate coverage alone.

## Task frame

Run `20260710-190058` activated the early exact-repeat guard in rounds 5 and 6. Both triggered rounds generated the same five restart hashes and selected the same config `7ab17b...` as restart champion. It moved all 100 target ranks and ranked 13th then 11th, but the actual round-best config/metrics remained unchanged and frozen promotion failed in both rounds.

The two rounds began from different search bases, yet their restart hash lists were exactly equal. Code inspection identified the cause: the restart generator always returned from the beginning of its deterministic anchor/context catalog when the budget was five; `round_index` and `stagnation_rounds` affected only the random fallback after the deterministic catalog was exhausted.

Progress means all of the following:

- the first trigger retains offset 0 and reproduces the prior first batch;
- the next consecutive trigger uses offset 5 and generates a disjoint five-candidate batch;
- budget remains five and all promotion/null/leakage gates remain unchanged;
- offset metadata is persisted, visible in watcher output, and used by continuity reconstruction;
- a fresh supervisor completes the first two triggered rounds without runtime error.

## Historical boundary

The Gauss and Riemann names below denote historically inspired reasoning lenses, not literal minds, trained replicas, or sources of authority.

## Gauss pass: verification

Strongest claim: persisted rounds 5 and 6 had equal five-element restart hash lists, the same champion hash, identical round-best signature, and failed frozen promotion. The duplication is exact, not an interpretation of similar metrics.

Weakest assumption: replacing repeat evaluation with new catalog coverage has higher marginal value. The historical evaluation is deterministic on the same history, so exact re-evaluation provides little new numerical information, but a new batch still may fail to survive prefilter or improve frozen metrics.

Verification test: preserve offset-0 output, assert offset-5 output contains five unique hashes disjoint from offset 0, assert deterministic reproduction at the same offset, and reconstruct both legacy and rotated candidates from persisted metadata.

## Riemann pass: structure

Strongest claim: the recovery space already contains a nominal 30-point deterministic anchor/context catalog, but the five-slot projection repeatedly exposed only its first local chart. Rotating the projection expands observed geometry without changing the underlying space or budget.

Weakest assumption: different parameter anchors induce different target-rank geometry. Hash disjointness proves config diversity only; live `changed_target_count`, rank signature, source frontier, and frozen validation must judge structural usefulness.

Structural test: compare live batch 0 and batch 1 generation, prefilter survival, full-eval survival, champion rank movement, and frozen-primary scores. Do not treat disjoint hashes alone as model progress.

## Cross-review

Gauss rejects randomizing every trigger because it would weaken reproducibility and continuity reconstruction. Riemann rejects permanently replaying the first five anchors because a deterministic same-history evaluation has already mapped that region. Both accept deterministic, auditable batches that rotate by the existing budget and wrap only after the catalog is covered.

## Disagreement

- Evidence: greater catalog coverage is verified search diversity, not proof of a better model.
- Scope: rotation solves duplicate restart allocation only; it does not explain why the main eval objective remains at one attractor.
- Risk: a new batch can look different on the eval slice yet still overfit. Frozen validation, ranked-uniform null diagnostics, and leakage checks remain decisive.
- Method: the known `7ab17b...` candidate is not deleted; its persisted evidence and continuity path remain available, but it no longer consumes every consecutive restart batch.

## Synthesis

Smallest shared conclusion: use deterministic catalog offset `(stagnation - active trigger threshold) × restart budget`, persist the offset, retain offset 0 as the legacy default, and rotate only while the rank-homogeneity guard remains active. Keep all promotion rules unchanged.

## Implementation

- The restart generator now constructs its deterministic catalog before taking a bounded slice.
- Consecutive trigger batches use offsets `0, 5, 10, ...` for the current five-slot budget.
- The effective trigger threshold controls the batch index, so early `4/4/1` and legacy `16/12/≤4` modes each begin at offset 0.
- `restart_batch_index` and `restart_catalog_offset` are persisted in rank-homogeneity metadata and exposed by the watcher.
- Continuity reconstruction reads the persisted offset; old records without the field continue to use offset 0.

## Static validation

- focused rank-homogeneity/restart/continuity tests: `13 passed`;
- watcher suite: `53 passed`;
- full worker suite: `446 passed`;
- `git diff --check` passed.

## Fresh supervisor

- run id: `20260710-195125`;
- PID: `2483978`;
- issue: `2026078`;
- Weight KDJ share: baseline `0.22`;
- historical sync before launch: zero inserts, zero updates, zero conflicts;
- live result: two consecutive trigger batches completed and persisted.

## Live verification

Rounds 1–4 completed with `improved=false`, the same rank signature `d43d9d633505f974...`, and no restart budget. This preserved the early-trigger boundary rather than activating rotation prematurely.

Round 5 verified the compatibility batch:

- trigger mode `exact_repeat`, batch/offset `0/0`, budget 5;
- generated five and prefilter-selected two restart candidates;
- the five hashes exactly matched the pre-change first batch;
- champion `7ab17b...` was full-eval rank 13, changed all 100 target ranks, and had frozen-primary `[0,0,1]`;
- because that config had already been used as the startup continuity base, search navigation selected a different challenger;
- promotion remained blocked by `frozen_validation_not_better`.

Round 6 verified rotation:

- batch/offset `1/5`, budget 5;
- generated five and prefilter-selected two restart candidates;
- its five hashes were disjoint from round 5;
- champion `106e8166...` was different from the first-batch champion, full-eval rank 12, changed all 100 target ranks, and had maximum absolute rank delta 937,143;
- it became the next search base through the standard `round_best` navigation path;
- the round completed Static, Dynamic KDJ, near-term Dynamic KDJ, strategy-memory, database, and status writes without runtime error.

The allocation and rank-geometry tests passed, but the rotated champion did not improve quality evidence:

- frozen-primary remained `[0,0,0]` against `[0,0,0]`;
- source-frontier improvement basis was `none` and tail-over-1,000,000 worsened by two targets;
- the watcher correctly marked the experimental navigation quality as `zero_frozen_primary_without_tail_or_frontier_lift`;
- formal promotion was evaluated, failed with `frozen_validation_not_better`, and was not bypassed;
- static metrics remained `[3,3,3]`, Dynamic KDJ was `[0,0,1]`, and near-term Dynamic KDJ was `[0,0,0]` in round 6;
- round-best config/metric repetition remained active at six of six rounds.

Watcher severity remained `ok` with action `continue_current_run`. All advisor families were current through `2026078`. Parser/sync/duplicate checks passed for 3,475 historical rows and the complete 1,107,568-combination legal red-ball universe.

## Outcome and next verification

Rotation passes its stated acceptance boundary: consecutive recovery rounds no longer spend the same five slots on the same hashes, deterministic recovery remains intact, and the second batch produced a different rank geometry and search base. It does not prove predictive or frozen-validation improvement.

The live run also exposes the next separate hypothesis: a restart candidate can fail the experimental-navigation quality diagnostic yet still become `decision_round_best` and then the standard search base while the stricter primary-navigation gate is inactive. That behavior predates rotation but becomes more visible as new catalog batches are explored. It should be audited as its own single-variable navigation-quality round; do not change it inside this catalog-allocation acceptance round.

Keep supervisor `20260710-195125` running. The next audit should inspect whether round 7 breaks the repeated round-best signature and whether the low-quality rotated search base improves, degrades, or leaves frozen/null diagnostics unchanged. If navigation quality is gated later, preserve restart evaluation evidence while preventing a candidate with no frozen-primary, tail, or source-frontier lift from becoming the search base solely because it changed ranks.

## Predeclared falsification

- If the first triggered round does not persist batch/offset `0/0`, the trigger-position calculation fails.
- If the next consecutive triggered round does not persist `1/5`, or its restart hashes overlap batch 0, rotation fails.
- If either triggered round errors, fails to persist, or bypasses frozen validation, runtime acceptance fails.
- If the rotated batch generates distinct hashes but changes no target rank or produces no useful full-eval evidence, structural benefit remains unproven even though allocation correctness passes.
- If frozen validation does not pass, do not describe the model as stronger.

## Guardrail

Catalog rotation is a search-coverage change only. Legal sample space, history window, ranked-uniform null context, advisor freshness, parser/sync/duplicate checks, and frozen promotion remain mandatory evidence boundaries.
