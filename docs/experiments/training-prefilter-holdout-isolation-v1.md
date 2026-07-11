# Training Prefilter Holdout Isolation v1

## Primary Goal

Make the light candidate prefilter obey the same 80-search / 20-frozen boundary as full evaluation, fail closed on any issue overlap, and prevent unverified historical prefilter rounds from influencing source-survival, navigation-credit, or budget evidence.

## Non-Goals

- Do not change model weights, source shares, candidate generators, ranking metrics, promotion thresholds, or forward-evidence thresholds.
- Do not use this correction as evidence of predictive lift.
- Do not resume the candidate-space distinguishability experiment until the corrected run establishes a clean baseline.
- Do not reinterpret historical frozen observations as forward-unseen evidence.

## Task Frame

Control run `20260711-063645` completed nine durable rounds with a formal 80/20 evaluation split and reported `search_uses_frozen_validation=false`. Code inspection showed that `prefilter_configs` independently sampled every fourth target from the complete 100-period evaluation window before full evaluation partitioned its results. The question was whether the prefilter target set intersected the frozen 20-period suffix and, if so, how to repair and audit the entire candidate funnel.

Progress requires exact issue-level proof that the old path intersects the frozen suffix, a new path whose prefilter targets are a subset of the search issues, a fail-closed runtime check, watcher invalidation of unverified historical source evidence, and at least two durable live rounds without runtime or scientific-guard errors.

## Historical Boundary

Gauss and Riemann below are historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`.
- Legal red-ball sample space: 1,107,568; ranked universe: 1,105,506.
- Historical mode: expanding, 900-train, 100-evaluation, current ten-year regime.
- Intended split: 80 search issues and 20 promotion-only frozen issues.
- Historical frozen data remain quarantined; forward evidence remains `0/20`.
- Parser, sync, duplicate, universe-completeness, and recorded-conflict checks pass.

## Gauss Pass: Verification

Strongest claim: the old prefilter selected 25 targets from the full 100-period window. Five were exactly inside the frozen suffix: `2026059`, `2026063`, `2026067`, `2026071`, and `2026075`. The formal search/frozen sets themselves had zero overlap, but the upstream selection function had already used frozen outcomes to decide which configurations reached full evaluation.

Weakest assumption: every historical result is equally affected. The overlap proves a breached selection boundary, not that each selected candidate changed because of the five observations. Runtime completion, fixed candidate counts, process-group shutdown, parser/sync checks, and promotion quarantine remain independently verifiable; source conversion, navigation, budget efficacy, and model-strength comparisons do not.

Test requested from the structural lens: identify every adaptive stage before promotion and verify that the boundary is applied before, not after, candidate selection.

## Riemann Pass: Structure

Strongest claim: holdout isolation is a property of the complete adaptive map, not only the final metric object. The old pipeline had the geometry `100-period prefilter -> candidate selection -> 80/20 full-evaluation split`; therefore the boundary surface was introduced too late. The repaired geometry is `80-period prefilter -> candidate selection -> 80-search/20-frozen evaluation`, with an issue-level consistency audit joining the two stages.

Weakest assumption: correcting the boundary will improve search quality. It may reduce apparent prefilter performance or change selected candidates, but that is removal of information leakage rather than model improvement.

Test requested from the verification lens: prove that every prefilter issue belongs to the full-evaluation search set, no prefilter issue belongs to the frozen set, and no issue falls outside the declared split.

## Cross-Review

- Gauss rejects the old `search_uses_frozen_validation=false` field because it described only the formal split and did not measure the prefilter.
- Riemann rejects treating the prefilter as a harmless speed optimization because it changes the candidate set and therefore the downstream search path.
- Both preserve the 80/20 split, historical quarantine, null model, promotion gate, and forward ledger.
- Both require historical isolated-protocol rows without explicit prefilter proof to be excluded from source-survival and budget evidence.

## Disagreement

Gauss would preserve unaffected operational claims on a per-claim basis. Riemann treats all downstream adaptive path comparisons from the old prefilter as structurally contaminated. The shared minimum is:

- retain only independently verified runtime/allocation/lifecycle conclusions;
- invalidate old source-survival, navigation-credit, budget-efficacy, candidate-diversity, and model-strength conclusions;
- make no retroactive claim about which candidate would have won under a clean prefilter;
- restart from the same canonical history with explicit issue-level isolation metadata.

## Synthesis

The smallest shared correction is:

1. Compute the frozen count before prefiltering and restrict prefilter target indices to the search prefix.
2. After full evaluation, compare prefilter issue IDs against the declared search and frozen issue sets.
3. Raise a runtime error before round persistence or search-base continuation if a frozen or outside-split issue is present.
4. Persist prefilter target count, search overlap, frozen overlap, outside-split count, status, and frozen-use flag.
5. Make the watcher exclude isolated-protocol rows whose prefilter proof is missing or failed.
6. Require the same fields in the long-term self-iteration checklist.

## Falsification And Acceptance

The repair is rejected if any fresh round has one of these properties:

- prefilter target count is still 25 at an 80/20 split;
- `prefilter_isolation_status` is not `passed`;
- `prefilter_frozen_issue_overlap_count` or `prefilter_outside_split_issue_count` is nonzero;
- `prefilter_uses_frozen_validation` is not false;
- old unverified rounds continue to count toward source maturity or budget review;
- promotion, frozen quarantine, null context, advisor freshness, or parser/sync/duplicate guards regress.

Acceptance requires two durable rounds, each with 20 prefilter targets entirely inside the 80-issue search set, fixed total candidate budget 28, no runtime error, and unchanged promotion/forward safeguards.

## Live Verification

The contaminated supervisor process group for run `20260711-063645` was stopped before modification. Its exact issue audit was:

```text
prefilter target count: 25
frozen overlap count: 5
frozen overlap issues: 2026059, 2026063, 2026067, 2026071, 2026075
```

Fresh supervisor run `20260711-075003`, PID `3225667`, started after the code update. Its first three durable rounds all generated exactly 28 candidates and persisted:

```text
search/frozen: 80/20
prefilter target count: 20
prefilter search overlap count: 20
prefilter frozen overlap count: 0
prefilter outside-split count: 0
prefilter uses frozen validation: false
prefilter isolation status: passed
```

All three rounds kept formal issue overlap at zero, historical quarantine active, promotion blocked without bypass, advisor signals current for their declared scopes, parser/sync/duplicate checks passing, and forward evidence at `0/20`. Static exact metrics remained `[3,3,3]`; Dynamic KDJ remained `[2,3,3]`; no predictive-strength claim is made.

Replaying the watcher on old run `20260711-063645` now reports `leakage_boundary:prefilter_isolation_unverified`, source status `invalidated`, `candidate_source_survival.observed_round_count=0`, and `evidence_ready=false`. The fresh run reports three eligible observed rounds and zero excluded rounds.

Validation:

```text
focused prefilter isolation tests: 5 passed
focused holdout/source watcher tests: 12 passed
supervisor + watcher suites: 228 passed
full worker suite: 495 passed
Python compile checks: passed
hourly self-iteration shell syntax: passed
git diff --check: passed
```

## Next Verification

Run `20260711-075003` reached eight same-run clean rounds with every prefilter audit passed. Its source and repetition baseline is therefore mature. A follow-up rank-signature audit showed five distinct persisted Top signatures per round despite one repeated champion, so the next correction separates candidate-space diversity from decision-surface stagnation; see `docs/experiments/training-decision-surface-diagnostic-v1.md`. Do not compare causal efficacy against contaminated historical source statistics.
