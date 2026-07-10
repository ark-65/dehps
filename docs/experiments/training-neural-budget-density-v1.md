# Training Neural Budget Density v1

## Primary Goal

Run one reversible candidate-density experiment that reduces the low-confidence Neural KDJ reservation from three to two candidates per 28-candidate round and returns exactly one slot to ordinary search.

## Non-Goals

- Do not disable Neural KDJ.
- Do not change its model, seed, hidden units, epochs, confidence threshold, or signal data.
- Do not change any other source budget, candidate generator, ranking metric, promotion rule, frozen-validation rule, or forward-evidence threshold.
- Do not claim predictive improvement from runtime or historical search diagnostics.

## Task Frame

Baseline run `20260711-041601` reached nine durable same-run rounds at Neural KDJ share `0.10`, which reserves three candidates per round. Neural KDJ generated 27 candidates, passed eight through prefilter, reached full-evaluation Top5 zero times, was round best zero times, and supplied selected search navigation zero times. Its only frozen-frontier observation is diagnostic-only under promotion-only holdout isolation.

The baseline ordinary source generated 47 candidates, passed 28 through prefilter, occupied nine Top5 positions, and was round best in all nine rounds. The supported working hypothesis is narrow: reducing Neural KDJ density from three to two preserves an advisor canary while allowing one more ordinary candidate per round. This may improve use of the fixed 28-candidate budget, but it is not yet evidence of score lift.

## Historical Boundary

Gauss and Riemann below are historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`; advisor families are current for their declared scopes.
- Legal red-ball sample space: 1,107,568; ranked universe: 1,105,506.
- Historical mode: expanding, 900-train, 100-evaluation, current ten-year regime.
- Search/frozen split: 80/20 with zero issue overlap.
- Search never reads frozen validation; frozen validation is promotion-only.
- Historical frozen holdout remains quarantined.
- Forward paired evidence remains `0/20`; no automatic quarantine release is allowed.
- Ranked-uniform search-slice null expectations remain 0.007237 / 0.072365 / 0.723651 at Top100 / Top1000 / Top10000 over 80 draws.
- Parser, sync, duplicate, universe-completeness, and recorded-conflict checks pass.

## Gauss Pass: Verification

Strongest claim: at 28 candidates, share `0.10` maps by the existing ceiling rule to three Neural KDJ slots, while share `0.07` maps to two. With all other configured shares fixed, the ordinary allocation increases by exactly one and total configured allocation remains 28.

Weakest assumption: nine zero-Top5 rounds imply that the marginal third Neural KDJ proposal is less useful than one additional ordinary proposal. Source membership can overlap, and the new run begins after additional search history, so a cross-run score difference cannot by itself establish causality.

Test requested from the structural lens: preserve a nonzero Neural KDJ path and verify that the changed density does not collapse candidate diversity or silently alter another source.

## Riemann Pass: Structure

Strongest claim: this changes sampling density inside the same candidate space, not the model family or decision boundary. Two Neural KDJ proposals retain a nonlinear-advisor path, while the returned slot increases coverage of ordinary exploitation/exploration/replay geometry.

Weakest assumption: the first two Neural KDJ proposals retain the most useful part of the advisor ordering. The experiment does not prove that the third proposal is globally redundant.

Test requested from the verification lens: confirm persisted per-round budgets, generated counts, source survival, rank signatures, round repetition, runtime stability, and exact holdout isolation rather than relying on command-line intent.

## Cross-Review

- Gauss rejects disabling Neural KDJ or changing more than one share because attribution would be lost.
- Riemann rejects reducing `recency_canary` from four to three because that would break the current two-field positive/negative symmetry.
- Both preserve Ridge KDJ as the transparent lightweight nonlinear control and preserve Neural KDJ as a two-candidate canary.
- Both require the new run to retain the same legal sample space, history issue, null context, and leakage boundaries.

## Disagreement

Gauss treats two completed rounds as sufficient only for allocation and runtime acceptance. Riemann requires a longer trajectory before judging whether search geometry improved. The shared decision is to accept implementation correctness after two durable rounds but defer budget efficacy until at least eight same-run rounds or a matched rollback control.

## Synthesis

The smallest shared experiment is one reversible operational change:

```text
Neural KDJ budget share: 0.10 -> 0.07
Neural KDJ candidates:   3 -> 2
ordinary budget slots:   +1
total configured budget: 28 unchanged
```

`scripts/ensure_training_supervisor.sh` exposes the value through `DEHPS_NEURAL_KDJ_BUDGET_SHARE` and uses `0.07` as the experimental operational default. The supervisor already records both configured share and persisted candidate budgets. No model weights or ranking rules change; the candidate merge pipeline additionally enforces the predeclared fixed-budget invariant after deduplication.

## Predeclared Verification And Falsification

Runtime/allocation acceptance after two durable rounds requires:

1. A fresh run and PID using `--neural-kdj-budget-share 0.07`.
2. Persisted `neural_kdj_advisor.budget_share=0.07` and per-round Neural KDJ budget/generated count of two.
3. Total generated candidates remain 28, with other configured advisor budgets unchanged.
4. Ordinary generated count increases by one in comparable rank-homogeneity rounds when probability-focus, restart, and inversion availability match.
5. No runtime error, parser/sync/duplicate failure, issue overlap, frozen search use, promotion bypass, or forward-ledger invalidation.

Immediate rollback conditions:

- Neural KDJ disappears rather than retaining two proposals.
- Total budget changes or another configured source budget changes.
- Holdout isolation, advisor freshness, null context, or leakage checks regress.
- The supervisor fails to persist a complete round.

Budget efficacy remains unproven after two rounds. At eight same-run rounds, compare source survival, ordinary Top5 conversion, selected search navigation, rank-signature diversity, repetition, and frozen-primary diagnostics against the registered baseline. If no distinct search benefit survives a same-incumbent or matched rollback check, restore `0.10` rather than trying an unregistered midpoint.

## Live Verification

The first attempted run, `20260711-052816` (PID `3081601`), correctly launched with share `0.07` but failed the predeclared allocation check before completing a durable round: the first round generated only 27 candidates. Hash deduplication removed one reserved/ordinary overlap and the candidate pipeline had no ordinary overflow pool to refill the released slot. The run was stopped and excluded from experimental evidence.

The repair keeps reserved-source ordering unchanged, generates a deterministic ordinary fallback pool, and fills only deduplication gaps after all reserved sources merge. A baseline replay showed that deduplication had also reduced the old run's first round to 26 candidates, so budget underfill was a pre-existing allocation bug rather than evidence for either Neural share. Any later efficacy comparison must use the repaired allocator on both sides.

Stopping the failed run also exposed that signaling only the supervisor parent could leave target-worker children alive. Shutdown now resolves the process group, signals the full group, and waits until both parent and group members exit. A process-group smoke test started a leader plus child (`3105226,3105228`) and verified that no members remained after group termination.

The repaired fresh run is `20260711-053216`, PID `3086812`. Its command line and status record both confirm `--neural-kdj-budget-share 0.07`.

Round 1 persisted:

- total generated/refined: `28/17`;
- configured ordinary buckets: 12 versus the registered share-0.10 baseline of 11;
- Neural KDJ budget/generated/prefilter/Top5: `2/2/0/0`;
- normal-source generated/prefilter/Top5/round-best attribution: `8/7/5/true`, with overlapping source membership explicitly retained;
- Weight/Ridge/recency budgets remained `7/3/4`;
- static metrics remained `[3,3,3]`, and promotion remained blocked with candidate/incumbent frozen-primary `[0,0,0]`.

Round 2 persisted:

- total generated/refined: `28/16`;
- configured ordinary buckets again remained 12;
- Neural KDJ budget/generated/prefilter/Top5: `2/2/0/0`;
- normal-source generated/prefilter/Top5/round-best attribution: `6/6/5/true`;
- Weight/Ridge/recency budgets remained `7/3/4`; probability focus used its existing one-candidate runtime slot;
- static metrics remained `[3,3,3]`, Dynamic KDJ `[2,3,3]`, and near Dynamic KDJ `[0,0,0]`.

Across both rounds, the selected next search base came from holdout-isolated experimental navigation with `selection_uses_frozen_validation=false`. Search/frozen remained 80/20 with zero overlap, promotion was evaluated and not bypassed, historical quarantine stayed active, advisors were current, parser/sync/duplicate checks passed, and forward evidence remained `0/20`.

This verifies runtime, allocation, fixed-budget refill, and safety correctness only. Two rounds do not establish Neural-density efficacy or predictive lift. The run remains active to reach the eight-round maturity boundary.

Validation:

```text
candidate-budget/refill focused tests: 10 passed
full worker suite: 492 passed
bash -n scripts/ensure_training_supervisor.sh: passed
git diff --check: passed
```

## Next Verification

Continue run `20260711-053216` to at least eight durable rounds. Then compare source survival, ordinary conversion, selected navigation, signature diversity, repetition, and frozen diagnostics. Because the allocator repair affects both shares and the new run began from a revalidated continuity seed rather than an identical start, any efficacy claim still requires a repaired share-`0.10` rollback/control; otherwise restore `0.10` and retain only the fixed-budget and process-group fixes.
