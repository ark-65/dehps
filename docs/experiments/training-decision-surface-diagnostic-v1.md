# Training Decision-Surface Diagnostic v1

## Primary Goal

Separate a stale round-best trajectory from an actually collapsed current candidate space, so self-iteration stops spending candidate budget on diversity expansion when the evaluated Top candidates already have distinct rank vectors.

## Non-Goals

- Do not change source budgets, prefilter quotas, candidate generators, score weights, sort order, promotion rules, or forward thresholds.
- Do not promote a challenger or claim predictive improvement.
- Do not treat current Top-rank-vector diversity as frozen or forward evidence.
- Do not discard the rank-homogeneity guard; preserve it as a decision-surface diagnostic.

## Task Frame

After prefilter holdout isolation was repaired, clean run `20260711-075003` reached eight durable rounds. Every round generated 28 candidates, prefiltered only 20 search-slice targets, and passed issue-level holdout isolation. Nevertheless, the watcher reported one repeated round-best config and one repeated metric signature for all eight rounds, while strategy memory continued to request candidate-space reframing.

The question is whether the current full-evaluation candidate set is actually rank-vector collapsed, or whether distinct candidates exist but the same baseline remains dominant under the decision objective. Progress requires an exact count of distinct current Top rank signatures, a corrected diagnostic that preserves both facts, and two live rounds showing the revised strategy without changing training mathematics or scientific guards.

## Historical Boundary

Gauss and Riemann below are historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`.
- Legal red-ball sample space: 1,107,568; ranked universe: 1,105,506.
- Historical mode: expanding, 900-train, 100-evaluation, current ten-year regime.
- Search/frozen split: 80/20; clean prefilter target count: 20 search issues.
- Historical frozen holdout remains quarantined; forward evidence remains `0/20`.
- Parser, sync, duplicate, universe-completeness, and recorded-conflict checks pass.

## Gauss Pass: Verification

Strongest claim: across all eight clean baseline rounds, persisted full-evaluation Top results contained five distinct nonempty rank signatures per round. The round-best signature was the same in every round, but the other Top signatures were distinct; the fifth position changed across later rounds. Therefore `rank_homogeneity.active=true` does not imply that the current candidate set is collapsed.

Weakest assumption: persisted Top5 geometry represents the full 16–21 refined candidates. The live self-diagnostic computes up to ten current signatures before persistence and supplies the stronger runtime check, but historical persistence retains only Top5 plus an optional decision candidate.

Test requested from the structural lens: distinguish geometry of the current candidate set from the time-path of the selected champion and identify which object the intervention is meant to change.

## Riemann Pass: Structure

Strongest claim: two spaces were conflated. The current candidate fiber contains multiple distinct rank functions, while the selected champion path remains on one branch. Expanding the fiber cannot by itself change the branch selected by an objective that continues to rank the incumbent first.

Weakest assumption: the objective is the only remaining obstruction. Weight trust is blocked, the historical slice remains overfit-risky, and no forward evidence exists; objective dominance is a diagnostic target, not proof that changing the objective will improve prediction.

Test requested from the verification lens: require at least five distinct current Top rank signatures while the historical round-best path remains stale, then verify that the strategy changes without changing budgets, weights, holdout use, or promotion.

## Cross-Review

- Gauss rejects the implication `stale champion => collapsed candidates` because the current Top5 has five distinct signatures in every clean round.
- Riemann rejects further diversity pressure because it operates on the wrong space: current candidate geometry is already diverse.
- Both preserve rank homogeneity as evidence that the selected decision path is stale.
- Both require any future objective experiment to remain single-variable, baseline-controlled, holdout-isolated, and non-promotional until forward evidence exists.

## Disagreement

Gauss prefers an objective-component residual audit before any scoring change. Riemann would also inspect whether the current scalar sort key hides a multi-objective frontier. The shared minimum is diagnostic only: stop labeling the candidate space collapsed, label the champion path stale, and route strategy memory to an objective-dominance audit.

## Synthesis

The smallest shared correction is:

1. Determine candidate-space status only from current refined-source survival and current Top rank-signature diversity.
2. Preserve `rank_homogeneity.active` as `round_best_path_status=stale` instead of forcing candidate-space status to `collapsed`.
3. Add `decision_surface_stale_champion` to strategy memory when current candidates are diverse but the champion path is stale.
4. Select `decision_surface_dominance_audit` before requesting more candidate-space pressure.
5. Keep promotion disabled and require frozen or forward evidence for any later model-strength claim.

## Clean Eight-Round Baseline

Run `20260711-075003` reached the predeclared eight-round maturity boundary:

- all eight rounds generated exactly 28 candidates and passed prefilter isolation;
- refined counts ranged from 16 to 21;
- each persisted Top set had five distinct nonempty rank signatures;
- round-best config and metric signatures each repeated `8/8`;
- normal source generated/prefilter/Top5/round-best rounds: `43/41/34/8`;
- Neural KDJ: `24/12/5/0`; Ridge KDJ: `24/5/3/0`; target inversion: `28/14/1/0`;
- stagnation restart generated/prefilter/Top5/search-navigation: `40/21/0/4`;
- recency canary and Weight KDJ matured to budget-review candidates, but no budget change is made in this round;
- static exact remained `[3,3,3]`, Dynamic KDJ `[2,3,3]`, near Dynamic KDJ `[0,0,0]`;
- candidate/incumbent frozen-primary remained `[0,0,0]`; promotion stayed quarantined and forward evidence remained `0/20`.

This proves a stale decision path with diverse current alternatives. It does not prove that any alternative is predictively better.

## Live Verification

Fresh run `20260711-084859`, PID `3283233`, uses unchanged operational arguments and the corrected diagnostic. Its first two durable rounds persisted:

- candidate-space status `diverse`;
- current Top rank-signature count `10`, unique count `10`;
- `round_best_path_status=stale`;
- reason `round_best_path_homogeneous_current_candidates_still_diverse`;
- failure hypothesis `decision_surface_stale_champion`;
- selected experiment `decision_surface_dominance_audit`;
- action `audit_objective_dominance_before_expanding_candidate_space`;
- promotion allowed `false`.

Both rounds kept 28 generated candidates, 20 search-only prefilter targets, 80/20 zero-overlap isolation, prefilter frozen overlap zero, advisors current, parser/sync/duplicate checks passing, promotion blocked without bypass, and forward evidence `0/20`.

## Falsification And Acceptance

Reject the correction if a current Top set with five or more distinct rank signatures is still classified as collapsed, or if an actually collapsed Top set with at most two signatures is classified as diverse. Reject it also if the change alters candidate budgets, model weights, search/frozen isolation, promotion, or forward thresholds.

Acceptance requires unit coverage for both collapsed and diverse/stale cases plus two durable live rounds that select the decision-surface audit while preserving all scientific guards.

Validation:

```text
supervisor + self-diagnostics suites: 161 passed
full worker suite: 497 passed
Python compile checks: passed
hourly self-iteration shell syntax: passed
git diff --check: passed
```

## Next Verification

The next bounded round should audit the scalar sort-key components and Pareto relationships among the stable baseline and diverse Top challengers. Predeclare the comparison before changing any sort coordinate. A future change is justified only if it exposes a distinct search-slice decision without using frozen data and is still rejected unless frozen or forward evidence improves. Do not expand candidate budgets merely because the champion path remains stale.
