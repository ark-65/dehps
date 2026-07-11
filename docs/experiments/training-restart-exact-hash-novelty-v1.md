# Training Restart Exact-Hash Novelty V1

## Round frame

Primary goal: prevent same-history, exact-config restart candidates from consuming reserved full-evaluation slots after the deterministic restart catalog wraps.

Non-goals:

- no new model, advisor, weight, objective, source budget, promotion rule, or score threshold;
- no exclusion across different history fingerprints;
- no assumption that a novel hash is a better model;
- no weakening of prefilter, strict frozen-primary navigation, frozen promotion, null, or leakage controls.

## Task Frame

The object is information gain from the five reserved `stagnation_restart` slots. Under one history fingerprint and deterministic ranker, evaluating the same config hash again returns the same ranking evidence. Progress means replacing exact historical repeats with still-deterministic, previously unevaluated candidates while keeping budget and all acceptance gates unchanged.

## Historical Boundary

Gauss and Riemann below are historically inspired verification and structural lenses, not literal minds, trained replicas, or sources of authority.

## Gauss Pass: Verification

Strongest claim: with search base `6e670c97...`, run `20260710-205704` round 17 generated restart hashes `46dbe...`, `8dc255...`, `d494c...`, `60352...`, and `779e8...`. Later run `20260710-234151` rounds 1 and 2 evaluated those same five exact hashes again. Same history plus same config hash is an exact duplicate computation.

Weakest assumption: rank evaluation is deterministic for a fixed history fingerprint and config. The persisted equal hashes, fixed evaluation protocol, and deterministic candidate generator support this; the change remains restricted to same-history records.

Verification test: generate one five-config batch, pass all five hashes as exclusions, and require a deterministic replacement batch of five whose hashes are disjoint from the excluded set.

Historical boundary note: cryptographic config hashes and deterministic program replay are modern implementation tools under a Gauss-inspired verification lens.

## Riemann Pass: Structure

Strongest claim: the restart catalog contains 30 anchor/bundle configurations and the reserved budget is five, so its local catalog coordinate closes after six batches. An ever-growing batch index is not itself an invariant of new coverage.

Weakest assumption: exact-hash novelty is the relevant geometry. It proves only that the evaluated point is new under the fixed history, not that the rank vector or frozen frontier will improve.

Structural test: use historical config hashes rather than raw batch index as the exclusion boundary, retain the rotated catalog order, and fall through to later catalog entries or a deterministic bounded fallback only when required.

Historical boundary note: closed-orbit and coordinate language is a modern structural analogy under a Riemann-inspired lens.

## Cross-Review

Gauss rejects “batch 82” as proof of new work without a hash comparison. Riemann rejects treating a 30-point local catalog as an indefinitely expanding space. Both accept exact same-history hash exclusion as a verified local improvement, while refusing any predictive claim from novelty alone.

## Disagreement

- Evidence: exact hash novelty does not prove rank-signature novelty.
- Scope: the bounded 80-record history may allow a very old hash to reappear; this round only claims bounded recent same-history deduplication.
- Method: if every catalog point is excluded, deterministic fallback samples a wider bounded configuration pattern; it still receives no promotion preference.
- Risk: fewer than five candidates may remain if bounded fallback cannot fill the budget; metadata must expose generated count and reuse count.

## Synthesis

Collect recent same-history `stagnation_restart` hashes from persisted source-survival records and current committed rounds. If the next five catalog candidates contain exact repeats, filter all known hashes, continue through later catalog entries, and use deterministic fallback only to fill remaining slots. Persist the baseline repeat count, replacement count, and final reuse count for the watcher.

## Four-round baseline

Run `20260711-001405`, PID `2747049`, completed four durable rounds before deployment:

- effective stagnation advanced 83, 84, 85, 86 with restart batches 79-82;
- static config and metric signatures repeated 4/4;
- restart generated 20, prefilter-selected 17, reached Top5 twice, and produced one strict frozen-primary frontier;
- candidate-source status matured to `diverse`, but this did not change the repeated static round best;
- watcher action was `prepare_restart_with_more_exploration`, while restart readiness correctly remained blocked by insufficient restart candidate evidence;
- advisors were current at issue `2026078`; legal-universe, ranked-uniform null, parser, sync, duplicate, frozen-promotion, and leakage checks passed.

## Implementation

- `historical_candidate_source_hashes` recovers bounded, deduplicated hashes from persisted source-survival records.
- `stagnation_restart_candidate_configs` accepts exact hash exclusions, preserves catalog order, skips known hashes, and uses a bounded deterministic fallback if needed.
- The supervisor compares the unfiltered five-candidate batch with history before applying exclusions.
- `restart_candidate_novelty` records history size, baseline repeat hashes/count, generated count, replacement count, final reuse count, and whether enforcement occurred.
- The watcher surfaces the diagnostic in JSON, Markdown, recommendation notes, and operator summary.
- The two-hour self-iteration prompt and project memory state that batch/offset growth is not coverage evidence and require `generated_reused_count=0` when filtering is active.

## Live verification

Patched-code replay against the real pre-deployment boundary (`20260710-234151` round 1) loaded 70 earlier same-history restart hashes:

- the unfiltered batch contained five candidates;
- three were exact historical repeats: `46dbe...`, `8dc255...`, and `d494c...`;
- filtering still returned five deterministic candidates;
- the filtered batch intersected historical hashes at zero.

Fresh run `20260711-004820`, PID `2785108`:

- recovered monotonic effective stagnation 87 and revalidated search base `2296dbb...` at frozen primary `[0,0,1]` versus `[0,0,0]`;
- round 1 generated five restart candidates with a 100-hash recent same-history set;
- its unfiltered batch had no natural exact repeat, so metadata correctly reported `baseline_reused_count=0`, `replacement_count=0`, `generated_reused_count=0`, and `novelty_enforced=false`;
- round 1 reached restart batch 83/offset 415 without a runtime error and was durably recorded with watcher `round_lag=0`;
- its restart champion reached full-eval rank 5, changed all 100 target ranks, and had strict frozen primary `[0,0,1]`, making navigation eligible without granting formal promotion;
- static remained `[3,3,3]`, dynamic was `[0,1,2]`, and near-dynamic was `[0,0,1]`;
- round 2 started at effective stagnation 88 with five generated restart candidates and `generated_reused_count=0`.

Round 2 completed and was durably recorded:

- restart batch 84/offset 420 used a 105-hash recent history, generated all five slots, and reported `baseline_reused_count=0`, `replacement_count=0`, and `generated_reused_count=0`;
- its restart champion changed all 100 target ranks but remained frozen-primary `[0,0,0]`, so strict-primary navigation blocked it;
- Ridge KDJ independently supplied a strict frozen-primary `[0,0,1]` frontier without bypassing formal promotion;
- static remained `[3,3,3]`, dynamic was `[0,1,1]`, and near-dynamic was `[0,0,1]`;
- watcher reported `target_complete_round_recorded`, `round_lag=0`, current advisors at issue `2026078`, and passing legal-universe, ranked-uniform null, parser, sync, duplicate, and leakage checks.

Neither fresh live round naturally hit an exact repeat, so live acceptance proves the no-regression path and complete novelty metadata. The activated filtering path is proved by the real-database replay and deterministic focused test; later catalog cycles remain the next natural live activation opportunity.

## Validation

- focused supervisor restart/history tests: `7 passed`;
- focused watcher gate test: `1 passed`;
- full worker suite: `468 passed`;
- shell syntax and `git diff --check`: passed.

## Predeclared falsification

- If an excluded same-history exact hash appears in the generated restart batch, deduplication fails.
- If filtering reduces a fillable five-slot batch below five candidates, deterministic replacement fails.
- If replacement output changes across identical replays, determinism fails.
- If different history fingerprints are excluded together, the scope boundary fails.
- If watcher metadata reports generated reuse above zero after enforcement, operational acceptance fails.
- If a novel candidate bypasses strict frozen-primary navigation or frozen promotion, scientific acceptance fails.
- If static/frozen metrics remain unchanged, do not claim model-strength improvement.

## Next Verification

- Continue watching later catalog cycles for a natural live `novelty_enforced=true` event.
- Require every enforced event to keep five candidates and `generated_reused_count=0`.
- Continue treating novel hash coverage as operational evidence only until rank-signature or frozen metrics improve.

## Guardrail

Legal sample space, ten-year current-regime history, ranked-uniform null context, advisor freshness, strict-primary navigation, frozen promotion, and leakage boundaries remain unchanged.
