# Sequential Null Ledger Coverage Audit

Date: 2026-07-11

## Round scope

- Primary goal: make the observed-family coverage, legacy gap, arithmetic
  invariants, and strongest-band null values explicit in the training watcher.
- Non-goals: do not invent a correction for unrecorded adaptive hypotheses; do
  not change candidates, weights, source budgets, search navigation, frozen
  validation, selection, promotion, or prediction output.

## Object

The object is the persisted same-history sequential null ledger for supervisor
run `20260711-132111`, evaluated on issue `2026078`.  The legal red-ball universe
is `1,107,568`, the ranked universe is `1,105,506`, and the historical search /
frozen split remains 80 / 20 inside the 100-issue evaluation window.

## Known

- Total same-history durable rounds: `317`.
- Rounds with reconstructable self-diagnostic candidate counts: `23`.
- Legacy uncounted rounds: `294`.
- Observed candidate tests: `418`.
- Tested Top bands: `3`.
- Observed candidate-by-band family: `1,254`.
- Search/frozen overlap: zero.
- Prefilter frozen overlap: zero.
- Historical holdout remains quarantined and promotion-only.
- Forward paired evidence: `0/20`.

## Assumptions

Bonferroni remains a valid union-bound adjustment for the hypotheses that were
actually counted and does not require independence between nested Top bands.
It does not reconstruct the 294 legacy rounds, advisor/source decisions made
after seeing the same outcomes, or the outcome-dependent generation of later
hypotheses.  The observed family is therefore a lower bound, not the complete
adaptive family.

## Check

The watcher now verifies these exact invariants:

1. `observed diagnostic rounds + legacy rounds = total rounds`;
2. `observed candidate tests × tested bands = observed family`;
3. all counts remain inside their total-round bounds; and
4. full-family completeness requires zero legacy rounds plus explicit adaptive
   and sequential multiplicity registration.

Current arithmetic passed:

- round partition: `23 + 294 = 317`;
- observed family: `418 × 3 = 1,254`;
- observed diagnostic coverage: `0.072555`;
- legacy gap: `0.927445`.

The strongest observed band was Top100 with 3 hits over 80 search-slice trials:

- raw binomial tail: `0.0000000605`;
- current-round minimum-family Bonferroni: `0.0000029037`;
- observed sequential-family lower-bound Bonferroni: `0.0000758589`.

These small values do not make the result interpretable as a candidate signal,
because most of the historical adaptive path is outside the family, the
eval-slice overfit guard remains active, and no forward evaluation exists.

## Boundary

The use of exact definitions, arithmetic identities, union bounds, and refusal
to infer beyond measured error is a historically inspired Gauss-style lens, not
a literal reconstruction of Gauss or historical authority for this modern
adaptive-search protocol.

## Implementation

`watch_training_progress.py` now emits a dedicated
`dehps-sequential-null-audit-v1` object in full and operator JSON, plus a Markdown
section.  It reports:

- observed coverage and legacy-gap ratios;
- the candidate, band, and family counts;
- invariant checks and completeness flags;
- raw, current-family, and observed-sequential null values for the strongest
  band;
- forward count, overfit/multiplicity blockers, and signal interpretability;
- `selection_changed=false` and `automatic_promotion_allowed=false`.

Malformed round partitions or family products are reported as `invalid` rather
than silently interpreted.  Even a hypothetical complete registered family can
only make a historical candidate signal interpretable; it never enables
automatic promotion.

## Conclusion

The strongest defensible conclusion is `incomplete_observed_lower_bound` with
action `keep_noise_risk_and_wait_forward_evidence`.  The existing
`adaptive_hypothesis_generation_counted=false` and
`sequential_search_multiplicity_counted=false` flags are correct and must not be
changed until a genuinely registered protocol supplies the missing family.

## Next test

- Keep the supervisor parked until issue `2026079` is synced and evaluated.
- Confirm the observed ledger grows monotonically after the next fresh-history
  supervisor starts.
- Continue accumulating the predeclared 20 paired forward issues.
- Reject any future signal interpretation if the arithmetic invariants fail,
  legacy/adaptive gaps are hidden, holdout isolation changes, parser/duplicate
  checks fail, or promotion is enabled automatically.

## Live validation

The live watcher returned coverage `23/317`, legacy gap `294/317`, observed
family `1,254`, status `incomplete_observed_lower_bound`, signal status
`noise_risk`, `candidate_signal_interpretable=false`, and
`automatic_promotion_allowed=false`.  Advisor signals remained current, the
supervisor remained parked, the promotion gate remained closed, and there were
no database read errors.

The focused watcher suite passed (`85 passed`) and the full worker regression
passed (`549 passed`).
