# Candidate-Source Budget Evidence Geometry

Date: 2026-07-11

## Round scope

- Primary goal: distinguish operational candidate-source conversion evidence
  from repeated same-history performance evidence before any source-budget
  experiment is proposed.
- Non-goals: no advisor budget, candidate-source allocation, strategy weight,
  search threshold, promotion rule, or prediction output changes.

## Task Frame

Run `20260711-132111` completed eight holdout-isolated rounds on issue `2026078`.
The candidate-source survival window reached its predeclared eight-round budget
review boundary and identified `recency_canary`, `target_weight_inversion`, and
`weight_kdj` as sources with no full-evaluation Top5 conversions.  At the same
time, the run had eight identical winning configuration and metric signatures.

Progress means deciding whether those eight rounds are evidence for an automatic
budget change, only enough to name a controlled experiment candidate, or not
useful at all.

## Historical Boundary

The Gauss and Riemann passes below are historically inspired verification and
structural lenses.  They are not literal reconstructions of either
mathematician's mind, and historical authority is not evidence for the result.

## Gauss Pass: Verification

- Strongest claim: eight identical final configuration/metric signatures on one
  history surface are not eight independent performance observations.
- Weakest assumption: distinct candidate-generation rounds may still be
  correlated even when their aggregate conversion counts differ.
- Check requested from the structural pass: determine whether the actual
  source-conversion vectors vary, instead of treating the final champion as the
  entire state.
- Exact observations: legal universe `1,107,568`; ranked universe `1,105,506`;
  eight observed rounds; one history surface; one final-performance signature;
  frozen overlap zero; prefilter frozen overlap zero; parser/sync/duplicate
  checks passed.

## Riemann Pass: Structure

- Strongest claim: source-budget evidence lives on the path from generation to
  prefilter to full-evaluation Top5, not only at the final champion.  Distinct
  conversion vectors can therefore contain operational information even when
  the final performance point is unchanged.
- Weakest assumption: a different aggregate conversion vector represents
  meaningful candidate-space exploration rather than superficial count noise.
- Check requested from the verification pass: canonicalize every round's source
  conversion vector and count distinct signatures.
- Exact observation: all eight source-conversion vectors were distinct, while
  the history and final-performance signature counts were both one.

## Cross-Review

Gauss accepts that the source pipeline varied, but rejects interpreting that
variation as predictive strength or independent future evidence.  Riemann
accepts the repeated historical surface limitation, but rejects collapsing the
operational evidence count to one because the candidate-source paths were not
identical.

## Disagreement

- `scope`: operational compute allocation versus predictive utility.
- `evidence`: whether eight different conversion vectors on one historical
  surface generalize to the next issue.
- Required evidence: a predeclared, single-variable budget experiment evaluated
  against the same baseline after fresh history becomes available; forward
  evidence remains quarantined and review-only.

## Synthesis

The smallest shared conclusion is:

1. The three zero-Top5 sources may be named as candidates for a future
   single-variable budget experiment.
2. The eight rounds do not prove those sources are predictively useless.
3. No automatic budget change is allowed.
4. The watcher must expose both source-conversion and final-performance evidence
   geometry so an operator cannot confuse raw round count with independent
   performance evidence.

## Implementation

The candidate-source survival diagnostic now reports:

- distinct history-surface, source-conversion, and final-performance signature
  counts;
- an evidence geometry classification;
- whether a predeclared budget experiment candidate is available;
- explicit same-history repetition and evidence limitations; and
- `automatic_budget_change_allowed=false`.

These fields are preserved in the operator JSON and Markdown report.  Existing
budget review thresholds and source states are unchanged.

## Next Verification

- Keep run `20260711-132111` parked until issue `2026079` is synced.
- Do not change all three source budgets together.
- After fresh history arrives, select at most one source-budget variable, record
  the baseline, challenger, historical window, null/baseline discipline, and
  falsification threshold before starting a new supervisor.
- Reject or roll back the challenger if it does not improve source conversion or
  candidate diversity against the same baseline, or if any holdout, leakage,
  parser, duplicate, or forward-quarantine guard fails.

## Live evidence

The updated watcher reported eight source-conversion signatures, one history
signature, one final-performance signature, evidence geometry
`distinct_source_conversion_same_performance`, a budget experiment candidate,
and `automatic_budget_change_allowed=false`.  It continued to return
`await_new_forward_issue` with selection and promotion disabled.

The focused watcher suite passed (`82 passed`) and the full worker regression
passed (`546 passed`).
