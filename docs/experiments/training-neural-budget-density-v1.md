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

`scripts/ensure_training_supervisor.sh` exposes the value through `DEHPS_NEURAL_KDJ_BUDGET_SHARE`; `0.07` was used only for the registered experimental run. The supervisor already records both configured share and persisted candidate budgets. No model weights or ranking rules change; the candidate merge pipeline additionally enforces the predeclared fixed-budget invariant after deduplication.

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

This verified runtime, allocation, fixed-budget refill, and safety correctness only. Two rounds did not establish Neural-density efficacy or predictive lift, so the run continued to the registered eight-round maturity boundary.

## Eight-Round Result

Run `20260711-053216` completed the predeclared eight-round window with all rounds generating exactly 28 candidates:

- Neural KDJ generated/prefilter/Top5/round-best/navigation: `16/2/0/0/0`;
- normal-source generated/prefilter/Top5/round-best rounds: `52/50/39/8`;
- stagnation restart generated/prefilter/search-navigation: `40/21/6`;
- candidate-source status remained diverse, but Neural KDJ, recency, Ridge KDJ, target inversion, and Weight KDJ all remained zero-Top5 in this path;
- round-best configs and full metric signatures each had two unique values; the dominant value occurred five times and the latest repeat streak was three;
- the old unrepaired `0.10` run had only one repeated config/signature, but it used an underfilling allocator and a different continuity path, so that contrast is not causal evidence for `0.07`.

At round 8, static exact metrics were `[3,3,3]`, Dynamic KDJ `[2,3,3]`, and near Dynamic KDJ `[0,0,0]`. The candidate and incumbent frozen-primary scores remained `[0,0,0]`; promotion remained blocked by historical quarantine and was not bypassed. Search/frozen remained 80/20 with zero overlap, all advisor signals were current for their declared scopes, parser/sync/duplicate checks passed, and forward evidence remained `0/20`.

### Maturity Cross-Review

Gauss pass: allocation correctness and increased normal-source throughput are verified, but there is zero frozen-primary residual and no promotion outcome difference. The repaired allocator and continuity start changed simultaneously with the share, so the old baseline fails the same-code proof obligation.

Riemann pass: the path visited two round-best/signature states instead of one, but this may be the geometry of full-budget refill or the revalidated continuity seed rather than Neural density. The local trajectory does not identify the responsible coordinate.

Shared conclusion: `0.07` is operationally safe but not proven superior. Restore the conservative registered `0.10` default, retain the allocator/process-group fixes, and run a repaired-allocator control before any density claim.

The `0.07` process completed round 9 before the handoff and was then stopped as a full process group; the already-started partial round 10 was not persisted. No worker processes remained.

## Repaired 0.10 Control

The operational default was restored to `0.10`. Control run `20260711-063645`, PID `3153509`, uses the same repaired allocator and explicitly records `--neural-kdj-budget-share 0.10`.

Its first two durable rounds both generated 28 candidates:

- Neural KDJ generated/prefilter/Top5: `6/1/0`;
- normal-source generated/prefilter/Top5/round-best rounds: `13/11/9/2`;
- configured ordinary buckets remained 11, Neural budget remained three, and Weight/Ridge/recency budgets remained `7/3/4`;
- one selected navigation round and one probability-focus round were both search-slice-only;
- static exact metrics remained `[3,3,3]`, frozen-primary remained `[0,0,0]`, and promotion remained blocked without bypass;
- 80/20 isolation, advisor freshness, parser/sync/duplicate checks, and forward `0/20` status remained intact.

For reference, the first two `0.07` rounds were Neural `4/0/0` and normal `14/13/10`. The one-candidate/one-Top5 difference is path-dependent, source memberships overlap, and neither side changed the static or frozen boundary. It is not evidence that either share is better.

The control then completed the same eight-round maturity window. Every round generated exactly 28 candidates:

- Neural KDJ generated/prefilter/Top5/round-best/navigation: `24/6/2/0/0`;
- normal-source generated/prefilter/Top5/round-best rounds: `47/44/35/8`;
- stagnation restart generated/prefilter/Top5/search-navigation: `40/19/0/3`;
- the eight round-best configs and full metric signatures each collapsed to one value, repeated for all eight rounds;
- rank homogeneity remained active with one recent rank signature and `stagnation_rounds=140`;
- Neural KDJ and Ridge KDJ reached Top5, but neither supplied round best, selected navigation, or an eligible frozen frontier;
- recency canary remained prefilter-starved, while Weight KDJ and target inversion were evaluated without Top5 survival.

At round 8, static exact metrics were `[3,3,3]`, Dynamic KDJ `[2,3,3]`, and near Dynamic KDJ `[0,0,0]`, exactly matching the `0.07` maturity boundary. Candidate and incumbent frozen-primary scores remained `[0,0,0]`; promotion remained blocked and was not bypassed. Search/frozen remained 80/20 with zero overlap, frozen validation was not used by search, advisors were current, parser/sync/duplicate checks passed, and forward evidence remained `0/20`.

## Final Density Cross-Review

### Gauss Pass

The repaired-allocator comparison satisfies the fixed-budget proof obligation: both runs completed eight rounds at 28 generated candidates per round with the same legal universe, canonical issue, history window, isolation protocol, and registered source budgets except for the one Neural/ordinary slot under test. The observed differences are real diagnostics: `0.07` produced two round-best configs and two metric signatures versus one and one at `0.10`; `0.10` produced two Neural Top5 survivals versus zero at `0.07`. Neither difference changed any line-level exact score, frozen-primary residual, promotion result, or forward evidence.

The remaining proof failure is causal pairing. The runs were sequential and inherited different search-continuity states. Source memberships also overlap. A difference in source attribution, repetition, or navigation therefore cannot identify the Neural budget share as its cause.

### Riemann Pass

The `0.07` path covered more local search states, while the `0.10` path retained denser nonlinear-advisor coverage. Neither path crossed into a new outcome geometry: both ended on the same static, dynamic, near-term, frozen, and forward boundaries. The search is moving among candidate coordinates without producing a distinct validated function value.

The structural bottleneck is therefore not established as Neural sampling density. It is the mapping from candidate diversity to distinguishable ranked outputs: normal search remains round best in every observed round, restart proposals navigate without Top5 survival, and the final score surface remains homogeneous.

### Disagreement

Gauss would require a paired or reset-state A/B run before attributing the diversity difference to `0.07`. Riemann considers that additional density testing low-value because both mature paths already collapse at the same validation boundary. The shared minimum is to stop tuning this coordinate and preserve the reversible registered default.

### Synthesis

The Neural-density hypothesis is closed as inconclusive, not promoted:

- keep the operational default at `0.10`;
- retain the fixed-budget deduplication refill and process-group shutdown fixes;
- do not claim predictive lift from either run;
- move the next bounded experiment to candidate-space reframing and output distinguishability, with the same null, leakage, frozen-holdout, and forward-evidence gates;
- treat Neural/Ridge Top5 survival only as source-health evidence until it produces round-best, navigation, frozen, or forward value.

Validation:

```text
candidate-budget/refill focused tests: 9 passed
full worker suite: 492 passed
bash -n scripts/ensure_training_supervisor.sh: passed
git diff --check: passed
```

## Next Verification

The next optimization round should predeclare one small candidate-space-reframing change and leave source shares unchanged. Its falsification target is output distinguishability, not compute activity: require more than one recent rank/metric signature without losing fixed-budget completion, and require any claimed benefit to survive the static/null comparison and frozen/forward gates. If the change only increases proposal novelty while line, frozen, and forward outcomes remain unchanged, reject it as another form of soft stagnation.

## Post-Audit Boundary Correction

A later issue-level audit found that the light prefilter sampled every fourth target from the complete 100-period evaluation window before the formal 80/20 split. Five of its 25 targets belonged to the frozen suffix. The density runs therefore remain valid evidence for fixed-budget allocation, runtime completion, and process-group shutdown, but their source conversion, navigation, repetition, diversity, and budget-efficacy comparisons are contaminated and must not support model-strength or source-budget decisions. The `0.10` default remains the conservative registered value, not a demonstrated winner. Corrected evidence begins with run `20260711-075003`; see `docs/experiments/training-prefilter-holdout-isolation-v1.md`.
