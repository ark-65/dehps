# Training Objective Component Residual Audit v1

## Primary Goal

Decompose the objective-first Pareto tradeoff into exact, direction-normalized reward-component residuals without changing the production sort key, candidate path, budgets, weights, or promotion rules.

## Non-Goals

- Do not remove, rescale, or reorder an objective component.
- Do not use a counterfactual objective to select a candidate or search base.
- Do not use frozen validation to order search candidates.
- Do not interpret a locally dominant component as predictive evidence.

## Task Frame

The preceding Pareto audit showed that a diverse current Top set can coexist with a stale round-best path: the scalar objective was the first differing sort coordinate while every inspected challenger remained Pareto-incomparable. Progress in this round means reconstructing each observed objective gap from the exact reward formula, exposing the dominant local residual, and proving that the diagnostic is observation-only.

## Historical Boundary

Gauss and Riemann are used below as historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`.
- Legal red-ball sample space: `1,107,568`; ranked universe: `1,105,506`.
- Historical mode: expanding, 900-train, 100-evaluation, current ten-year regime.
- Search/frozen split: 80/20 with zero issue overlap.
- Prefilter targets: 20 search-only issues, zero frozen or outside-split issues.
- Historical frozen holdout remains quarantined; forward paired evidence remains `0/20`.

## Gauss Pass: Verification

Strongest claim: the first two durable rounds of run `20260711-103801` produced eight objective-first comparisons, and all eight objective gaps were reconstructed exactly from seven direction-normalized reward components. Missing-component count and reconstruction-mismatch count were both zero; the maximum absolute reconstruction residual was `0.0`.

Weakest assumption: the current Top5 neighborhood is representative of the local decision obstruction. The calculation is exact for the observed comparisons but does not characterize every evaluated configuration or any future issue.

Verification requested from the structural lens: determine whether the same component dominates across distinct candidate geometries, rather than treating one exact local decomposition as a global model claim.

Historical boundary note: exact arithmetic and residual checking are Gauss-inspired verification discipline; they are not authority for changing a modern training objective.

## Riemann Pass: Structure

Strongest claim: the scalar objective is a local chart whose small gaps are mostly induced by tail-risk geometry in the observed neighborhood. Seven of eight comparisons had `tail_risk_penalty` as the largest absolute component delta; the eighth was dominated by `red5_reward`.

Weakest assumption: the seven recorded components are the only useful coordinates for understanding the decision surface. They exactly reconstruct the implemented objective, but the production objective itself may omit relevant structure.

Verification requested from the arithmetic lens: require the direction-normalized component sum to equal the production objective gap before treating any structural interpretation as valid.

Historical boundary note: the chart and geometry language is a Riemann-inspired modern reconstruction, not a claim about Riemann's own formal toolkit.

## Cross-Review

- Gauss accepts the local decomposition because every production gap equals the sum of component deltas within the declared `0.00001` tolerance.
- Riemann rejects a single-component global explanation because one live branch was dominated by `red5_reward`, not tail risk.
- Both reject an immediate objective change: the evidence is historical, local, repeatedly searched, and has no paired forward validation.
- Both require the diagnostic to remain search-slice-only and excluded from candidate selection and promotion.

## Disagreement

Gauss would next predeclare a single-component counterfactual only after the dominant residual is stable across a longer fixed-budget window. Riemann would first map whether different candidate branches occupy distinct component-dominance regions. The smallest shared conclusion is to observe the residual distribution for at least eight same-run durable rounds before proposing any counterfactual sort control.

## Implementation

`run_training_supervisor.py` now:

- maps the exact objective formula into positive contributions and direction-normalized penalties;
- records per-comparison component deltas, their sum, reconstruction residual, largest absolute component, and which side each component favors;
- fails the component control closed when reward fields are missing or reconstruction exceeds tolerance;
- aggregates dominant-component and advantage counts while explicitly recording `selection_changed=false`, `selection_scope=search_slice_only`, and `selection_uses_frozen_validation=false`.

Strategy memory advances from `predeclare_objective_component_control_without_sort_change` to `observe_component_residual_stability_without_sort_change` only after the component control is measured. The hourly self-iteration checklist now requires exact reconstruction and unchanged selection/frozen-use boundaries before considering a later control.

## Live Verification

The previous supervisor `20260711-093253` was stopped only after durable round 13. Fresh supervisor `20260711-103801`, PID `3406590`, then started from the updated code and completed two durable rounds.

Across rounds 1-2:

- objective-first comparisons: `8/8`;
- Pareto tradeoffs: `8/8`;
- measured component residuals: `8/8`;
- missing reward-component comparisons: `0`;
- reconstruction mismatches: `0`;
- maximum absolute reconstruction residual: `0.0`;
- largest component: `tail_risk_penalty` in `7/8`, `red5_reward` in `1/8`;
- production selection changed by diagnostic: `false`;
- frozen validation used by diagnostic or search selection: `false`.

The production winner remained unchanged at exact Top100/1000/10000 `[3,3,3]`; Dynamic KDJ remained `[2,3,3]`, and Near Dynamic KDJ remained `[0,0,0]`. Current candidate geometry remained diverse with `10/10` distinct Top rank signatures while the round-best path stayed stale. Effective stagnation reached 169 rounds, so the audit explains a local ordering mechanism but does not establish model progress.

Advisor signals were current through `2026078`; parser, sync, duplicate, 80/20 holdout, and prefilter-isolation checks passed. Promotion remained blocked by historical holdout quarantine without bypass, and forward evidence remained `0/20`.

## Falsification

Reject this diagnostic if a reward field is absent, a penalty direction is not normalized, the component sum does not reconstruct the production objective within tolerance, or observation changes candidate order, search base, frozen use, budgets, or promotion. Reject a future tail-risk control if dominance does not remain stable over the predeclared window or if it lacks same-history, same-budget, search-only comparison and later frozen/forward review.

## Validation

- Supervisor and self-diagnostics suites: `165 passed`.
- Full worker suite: `503 passed`.
- Python compilation, `bash -n scripts/hourly_self_iterate.sh`, and `git diff --check` passed.
- Two fresh durable live rounds completed without runtime or leakage errors.

## Synthesis

The prior vague statement that the scalar objective was the tie-break is now an exact local diagnosis: tail-risk penalty generated most observed objective gaps, with one separate red5-dominated branch. This is evidence for a later bounded counterfactual audit, not permission to change the production objective and not evidence of predictive lift.

## Next Verification

Accumulate at least eight same-run durable rounds with fixed budgets and unchanged objective. If reconstruction remains exact and one component remains dominant across candidate branches, predeclare one observation-only counterfactual control for that component. Do not feed the counterfactual ranking into search, promotion, or betting output until frozen or genuinely forward evidence exists.

## Maturity Completion

Run `20260711-103801` completed the predeclared eight-round window with 32/32 measured comparisons, zero missing or reconstruction mismatches, maximum residual `0.0`, and `tail_risk_penalty` as the largest absolute component in 26/32 comparisons. The resulting observation-only control is documented in [Training Tail-Risk Counterfactual Audit v1](training-tail-risk-counterfactual-audit-v1.md).
