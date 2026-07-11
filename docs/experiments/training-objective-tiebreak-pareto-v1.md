# Training Objective Tiebreak Pareto Audit v1

## Primary Goal

Make the stale decision surface measurable by identifying the first differing sort coordinate and the Pareto relation between the stable baseline and diverse Top challengers, without changing training selection.

## Non-Goals

- Do not change the sort key, objective formula, weights, candidate sources, budgets, prefilter, or promotion rules.
- Do not select a Pareto challenger or claim predictive improvement.
- Do not use frozen validation to order candidates.
- Do not treat a small objective gap as evidence that the objective should be removed.

## Task Frame

The preceding decision-surface round established that current Top candidates have distinct rank signatures even though the round-best path remains stale. This round asks which sort coordinate selects the repeated baseline and whether that baseline Pareto-dominates the challengers on directly interpretable rank-quality fields. Acceptance requires a deterministic search-slice-only diagnostic, a strategy-memory route that forbids an ad hoc sort change, and a fresh durable supervisor round with all scientific guards intact.

## Historical Boundary

Gauss and Riemann below are historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`.
- Legal red-ball sample space: 1,107,568; ranked universe: 1,105,506.
- Historical mode: expanding, 900-train, 100-evaluation, current ten-year regime.
- Search/frozen split: 80/20; ordering diagnostic scope: search slice only.
- Historical frozen holdout remains quarantined; forward evidence remains `0/20`.
- Parser, sync, duplicate, universe-completeness, and recorded-conflict checks remain required.

## Gauss Pass

Strongest claim: across three durable rounds from run `20260711-084859`, all 12 baseline/challenger comparisons first differed at `objective_score`. The absolute objective gap ranged from `0.0010830000001078588` to `3.396342000000004`, while all 12 comparisons were Pareto tradeoffs rather than baseline or challenger dominance.

Weakest assumption: the persisted Top5 captures the relevant local decision surface. It is sufficient to falsify baseline Pareto dominance in the observed neighborhood, but not to characterize every refined candidate or justify changing the objective.

Proof obligation: reconstruct the sort coordinates exactly, compare only same-round search-slice summaries, preserve directionality for lower-is-better rank/tail fields, and expose the diagnostic without feeding it back into selection.

## Riemann Pass

Strongest claim: the scalar objective is acting as a local chart that orders points which are incomparable in the broader rank-quality geometry. A stable scalar winner can therefore coexist with multiple structurally distinct alternatives.

Weakest assumption: the chosen Pareto coordinates are the complete geometry. They intentionally exclude the scalar objective and include interpretable hit, tail, and rank fields, but other legitimate coordinates may exist.

Structural test: route the next experiment toward component residuals while leaving the chart and candidate path unchanged. If the live surface is not objective-first or not tradeoff-shaped, the route must fall back to a mixed or dominance diagnosis.

## Cross-Review

- Gauss verifies 12/12 first differences at objective score and 12/12 Pareto tradeoffs.
- Riemann interprets this as scalar ordering of non-dominated alternatives, not candidate collapse.
- Both reject an immediate sort change because the observed slice is historical and the frozen holdout is quarantined.
- Both require the next control to be predeclared, single-variable, same-budget, and rejected absent frozen or forward improvement.

## Disagreement

Gauss prefers decomposing the objective into exact residual contributions before proposing any alternate coordinate. Riemann would additionally map a broader Pareto frontier. The shared minimum is the implemented diagnostic: record first differences, objective-gap scale, dominance counts, and field-level tradeoffs, then stop before selection changes.

## Synthesis

The diagnostic compares the current sorted Top5. For each challenger it records the first differing sort field, objective gap when relevant, Pareto relation, and fields where either side is better. Strategy memory selects `objective_tiebreak_pareto_audit` only when every inspected challenger is objective-first and every relation is a tradeoff. Its action is `predeclare_objective_component_control_without_sort_change`; promotion remains disallowed.

## Baseline Audit

Across three durable rounds of `20260711-084859`:

- comparisons: `12`;
- first sort-key difference at objective score: `12/12`;
- Pareto tradeoffs: `12/12`;
- baseline dominance: `0`; challenger dominance: `0`;
- challengers had better median rank in `12/12` and better best rank in `11/12`;
- baseline had better objective in `12/12`, better worst rank in `11/12`, and better Top-500k coverage in `9/12`;
- objective-gap range: `0.0010830000001078588` to `3.396342000000004`.

This falsifies the hypothesis that the repeated baseline simply dominates the local alternatives. It does not establish that any challenger predicts better.

## Implementation

`run_training_supervisor.py` now exposes the ordered sort-field names, a direction-normalized Pareto vector, and `decision_surface_dominance_diagnostic`. Round self-diagnostics include its search-slice-only output. Strategy memory counts decision-surface statuses independently from the stale champion path and routes an objective-first tradeoff surface to the predeclared component-control action. Hourly self-iteration now forbids ad hoc sort, weight, budget, or promotion changes under this status.

## Live Verification

Fresh run `20260711-091651`, PID `3311752`, completed durable round 1 with unchanged training arguments:

- candidate space `diverse`, current Top rank signatures `10/10`, round-best path `stale`;
- decision-surface status `objective_tiebreak_tradeoff`;
- first differences at objective score `4/4`;
- Pareto tradeoffs `4/4`; baseline and challenger dominance both `0`;
- objective gap `0.001083` to `0.606811`, maximum relative gap `0.0001193171`;
- challengers improved median rank `4/4`; baseline improved worst rank `4/4`;
- selected experiment `objective_tiebreak_pareto_audit` with promotion disabled;
- prefilter isolation passed with 20 search issues and zero frozen/outside overlap;
- advisors current, parser/sync/duplicate checks passed, historical holdout quarantined, forward evidence `0/20`;
- round boundary `target_complete_round_recorded` with zero DB lag.

## Falsification

Reject the diagnostic if sort-field names do not match the tuple order, lower-is-better fields are not direction-normalized, equal keys are mislabeled, or a dominant candidate is reported as a tradeoff. Reject the operational change if it affects candidate order, frozen use, promotion, budgets, or model weights. A future objective-component control must be rejected if it lacks a same-budget baseline, changes more than one component, reads frozen results for selection, or fails to improve later frozen/forward evidence.

## Validation

Targeted supervisor and self-diagnostics tests cover objective-first tradeoffs and strategy routing. The full worker suite, compile checks, shell syntax, and diff checks are required before publication.

## Next Verification

Predeclare one objective-component residual control without changing the production sort key. Separately, profile and parallelize independent Dynamic KDJ target evaluations with result-equivalence tests; compute acceleration must not be counted as model progress. Intel Arc is visible to the host, but the current Python environment has no GPU compute backend, so GPU enablement requires a separate measured feasibility round rather than an unverified dependency change.
