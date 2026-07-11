# Training Holdout Isolation V1

## Round scope

- Primary goal: stop the long-running search loop from using the same historical
  rows both to choose its next search coordinate and to claim frozen-validation
  evidence.
- Non-goals: no new model, advisor, candidate source, weight, source budget, null
  model, or promotion threshold.
- Evidence level: training-loop and leakage-boundary correction only. This report
  makes no predictive-lift or betting-performance claim.
- Legal red-ball universe: `C(33, 6) = 1,107,568`; the ranked universe in the live
  run remained `1,105,506` after the existing fixed filter excluded `2,062`
  combinations.
- Historical scope: `current_regime_default`, expanding train window `900`, total
  evaluation lookback `100`, `as_of_issue=2026078`.

## Baseline defect

The old supervisor evaluated every candidate on the same 100 historical targets,
sorted candidates with metrics from all 100 targets, then called the trailing 20
targets `frozen_validation`. The same trailing 20 targets also drove:

- strict frozen-primary search navigation;
- source-frontier and decision-candidate selection;
- supervisor continuity recovery;
- recovery-productivity diagnostics later considered by self-iteration.

The database audit for the current history fingerprint and issue found:

- `203` durable round rows across `17` run ids;
- `202` rows used the exact same trailing issue set `2026059..2026078` (one early
  row used only `2026078`);
- `41` distinct decision-candidate hashes;
- `31` decision rows reported a frozen-primary lift;
- `89` distinct search-base hashes;
- `19` search-base rows reported a frozen-primary lift.

This proves that the trailing 20 targets were repeatedly observed and sometimes
used to choose future candidates. They were a reusable navigation validation set,
not an unseen promotion holdout.

## Gauss–Riemann cross-review

### Task Frame

The object is the separation between search evidence and promotion evidence in a
deterministic same-history training loop. Progress requires a disjoint issue split,
machine-readable proof that frozen results do not select candidates or search
bases, a fail-closed response to the already contaminated historical holdout, and
live durable rounds without runtime or existing-guard regressions.

### Historical Boundary

The following Gauss and Riemann passes are historically inspired verification and
structural lenses. They are not literal reconstructions of either mathematician's
mind, and their names are not evidence.

### Gauss Pass: Verification

- Strongest claim: a holdout that has been read in 202 same-history rounds and has
  influenced at least 19 search-base choices cannot support an unqualified unseen
  validation claim.
- Weakest assumption: persisted decision/search metadata undercounts exposure,
  because every full-eval candidate also received trailing-20 metrics even when it
  was not selected. The measured exposure is therefore a lower bound.
- Exact obligations: search/frozen issue intersection must be zero; persisted
  search target count must be 80; frozen issue count must be 20; selection metadata
  must say `selection_uses_frozen_validation=false`; promotion must remain blocked
  even if the pre-quarantine frozen comparison passes.
- Test requested from the structural pass: explain whether a fixed coordinate can
  retain the meaning of “future” after the search trajectory repeatedly conditions
  on it.

### Riemann Pass: Structure

- Strongest claim: the old loop used one coordinate space for two incompatible
  roles. Search continuity moved through a geometry already shaped by the supposed
  validation coordinate, so a local frozen lift could not be interpreted as a
  global generalization event.
- Weakest assumption: an `80/20` split is sufficient for operational search. It is
  a clean boundary, not proof that 80 search observations provide low-variance
  optimization.
- Reformulation: treat each summary as a product of a search slice and a promotion
  slice. Search ranking, advisor anchors, target inversion, probability focus, and
  continuity live only on the search coordinate. The promotion coordinate is not a
  continuation direction.
- Test requested from the verification pass: persist both issue sets and prove
  disjointness rather than relying on window-size arithmetic.

### Cross-Review

- Gauss rejects “promotion-only” as a label unless every selection path carries an
  explicit non-use flag and the database target arrays prove the split.
- Riemann rejects merely disabling one frozen-primary branch: full-window sort
  metrics would still leak the final 20 targets into every downstream choice.
- Both reject increasing candidate count or relaxing the promotion gate as a
  remedy.

### Disagreement

- `scope`: this patch establishes a local historical boundary, but it does not
  create genuinely future observations.
- `evidence`: a future promotion policy still needs enough post-activation draws
  and a predeclared acceptance rule; the required sample size is unresolved.
- `risk`: canonical advisor models are trained from the available historical data.
  Their candidates may be explored on the search slice, but no advisor result can
  become promotion evidence while the historical holdout is quarantined.

### Synthesis

The smallest shared conclusion is a verified leakage-boundary correction:
separate the existing 100-target lookback into 80 search targets and 20 trailing
promotion diagnostics, prohibit frozen results from all search/navigation choices,
and quarantine the historically reused 20-target result until genuinely forward
unseen evidence exists. This makes the training evidence more honest; it does not
make the model predictively stronger by itself.

### Next Verification

1. Verify every durable round stores 80 search rows, 20 frozen issues, and zero
   overlap.
2. Verify decision and search-base metadata both use `search_slice_only` and set
   frozen use to false.
3. Verify `pre_quarantine_passed=true` still yields formal
   `passed=false/reason=historical_frozen_holdout_quarantined`.
4. Verify continuity accepts only the new isolation protocol and re-evaluates the
   recovered config on the current 80/20 split.
5. Accumulate genuinely future prediction evaluations before defining a new
   promotion acceptance test; do not silently recycle the current trailing 20.

## Implementation

- `evaluate_configs` now builds summaries with
  `search_slice_frozen_promotion_v1`: the first 80 targets populate top-level
  search metrics and `target_results`, while the last 20 populate only
  `frozen_validation`.
- Search and frozen issue lists, window sizes, overlap count, roles, and non-use
  flag are persisted in `evaluation_split`.
- Same-history historical summaries keep their configs but are re-evaluated under
  the new split before they can seed an incumbent or leaderboard.
- Search-base recovery accepts only records with the isolation protocol and
  `search_uses_frozen_validation=false`; legacy frozen-selected continuity records
  are rejected.
- Probability focus, decision candidates, target-inversion anchors, dynamic KDJ
  comparison, and moving search bases use the search slice. Source-frontier frozen
  results remain diagnostic and are not fed to navigation.
- Formal promotion fails closed with
  `historical_frozen_holdout_quarantined`, while preserving the raw comparison as
  `pre_quarantine_*` diagnostics.
- The watcher exposes the split, overlap, role, quarantine, forward-evidence
  requirement, and search-selection basis in JSON, Markdown, evidence context, and
  operator summaries.
- Frozen source-frontier rows remain visible as diagnostics but are excluded from
  source productivity, guarded navigation, and budget-review protection under the
  promotion-only protocol.
- Target inversion declares its expected search-slice cutoff, so freshness checks
  distinguish an intentional `2026058` search cutoff from a stale canonical
  advisor signal.
- The two-hour self-iteration prompt and project memory now forbid frozen-guided
  search, continuity, source budgets, and lift claims.

## Activated database replay

Run `20260711-014006` round 2 persisted:

- `jsonb_array_length(target_results)=80`;
- `jsonb_array_length(best_summary.frozen_validation.issues)=20`;
- search issues `2025130..2026058`;
- frozen issues `2026059..2026078`;
- `issue_overlap_count=0`;
- decision and search-base basis `search_slice_only`;
- decision and search-base frozen-use flags `false`;
- promotion reason `historical_frozen_holdout_quarantined`.

This run completed two durable rounds and proved the main isolation path. It was
then replaced because the final patch also taught advisor freshness to recognize
the intentional search-slice cutoff.

## Final live verification

Final run: `20260711-020627`, PID `2868765`.

Durable round 1 proved:

- persisted search/frozen counts `80/20` with zero issue overlap;
- decision `probability_focus` and next search base `search_challenger` both used
  `selection_basis=search_slice_only` and
  `selection_uses_frozen_validation=false`;
- the raw eval-slice overfit diagnostic remained active, while its navigation form
  was explicitly inactive; raw frozen primary and overfit results therefore did
  not alter search control flow;
- promotion remained blocked by `historical_frozen_holdout_quarantined`;
- static and Dynamic KDJ line evaluation windows were both `80`; dynamic changed
  80 targets and scored exact `[2,3,3]` against static `[3,3,3]`;
- target inversion declared `signal_scope=search_slice`, expected cutoff
  `2026058`, and watcher freshness reported `current_search_slice` while canonical
  Weight/Ridge/Neural advisors remained current at `2026078`;
- watcher legal universe, search-slice ranked-uniform null, parser, sync,
  duplicate, and leakage checks passed.

Durable round 2 independently persisted the same `80/20/0-overlap` boundary.
Decision and next search base both used search-slice probability focus with frozen
use false. Raw frozen-primary and eval-overfit navigation flags again remained
false, and promotion again remained quarantined. Static stayed `[3,3,3]`; Dynamic
KDJ stayed `[2,3,3]`, both on 80 targets. The watcher reported:

- `target_complete_round_recorded`, `round_lag=0`;
- all canonical advisors current at `2026078` and target inversion
  `current_search_slice` at the declared `2026058` cutoff;
- ranked-uniform null scoped to the 80-target search slice;
- parser/sync/duplicate and leakage checks passing;
- source evidence `2/4` rounds and budget evidence `2/8`, so no source-budget
  change is justified;
- no frozen frontier affected source productivity or budget protection.

The final process remained active and continued into round 3 after verification.

## Validation

- Focused supervisor/watcher suites: `210 passed`.
- Full worker suite: `475 passed`.
- `bash -n scripts/hourly_self_iterate.sh` and `git diff --check` are required before
  publication.

## Falsification and remaining limits

- Any non-zero search/frozen issue overlap falsifies the isolation claim.
- Any selected decision, continuity seed, advisor anchor, or search base with
  `selection_uses_frozen_validation=true` falsifies the navigation claim.
- Any formal promotion while `historical_holdout_quarantined=true` is a guard
  failure.
- Passing historical frozen metrics cannot establish future predictive lift.
- The current static search score may remain `[3,3,3]`; unchanged score is not a
  failure of isolation and must not be advertised as model improvement.
- A future promotion protocol still needs predeclared forward sample size, null
  comparison, uncertainty, failure cases, and leakage review.
