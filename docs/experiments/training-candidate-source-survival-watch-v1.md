# Training Candidate Source Survival Watch V1

## Round frame

Primary goal: make candidate-source conversion auditable over the current supervisor run before changing source budgets or prefilter policy.

Non-goals:

- no source quota, reserved promotion slot, new advisor, or weight change;
- no cross-run aggregation for automated decisions;
- no restart decision from source survival alone;
- no predictive or betting claim.

Training context: SSQ red-ball legal universe 1,107,568; ranked post-filter universe 1,105,506; `current_regime_default`; expanding train window 900; eval window 100; issue `2026078`. Operational baseline remains the incumbent frozen-primary score and the ranked-uniform null diagnostic.

## Evidence before the change

Across selected recent runs, normal candidates survived prefilter at about 91%, while Weight KDJ survived at about 9%, Ridge KDJ at about 22%, and Neural KDJ at about 7%. That aggregate was confounded by stale-signal runs and could not justify a budget mutation.

In fresh run `20260710-164004`, Neural KDJ became round best in round 2 and remained round best in round 3. This falsified the simple claim that every non-normal source was being suppressed. Weight KDJ had generated 21 candidates over three completed rounds, with three reaching full evaluation and none reaching Top5; this remained too early for a policy change.

## Gauss–Riemann protocol

Historical boundary: the two names below denote historically inspired verification lenses, not literal minds or sources of authority.

### Gauss pass: verification

Strongest claim: source conversion counts are measurable from each persisted round's `source_survival` record.

Weakest assumption: low survival means prefilter bias rather than weak candidates. Stale-signal and short-window confounding prevent that inference.

Required test: aggregate only one run, expose generated, prefilter-selected, Top5, and round-best counts, and require at least four completed rounds before classification.

### Riemann pass: structure

Strongest claim: candidate sources are overlapping strata in a search space, not mutually exclusive model classes. A single latest-round snapshot loses the trajectory.

Weakest assumption: Top5 conversion is a useful structural proxy; it remains downstream of an eval-slice objective and is not forward evidence.

Required test: retain overlap explicitly, classify sources without changing promotion, and compare window status as new rounds arrive.

### Cross-review and synthesis

Gauss rejects source quotas without mature same-run counts. Riemann rejects one-round source snapshots as a basis for global search changes. The shared conclusion is an observability-only window with explicit evidence thresholds and no automatic model mutation.

## Implementation

- Aggregate current-run `generated`, `prefilter_selected`, `full_eval_top5`, and `round_best` per source.
- Record selection and Top5 conversion rates while preserving overlapping source membership.
- Require four observed rounds and eight generated candidates before starved/zero-Top5 classifications.
- Emit `insufficient_window`, `narrow`, `diverse`, or `mixed` plus a non-restart diagnostic action.
- Include the full summary in JSON, CLI/operator output, Markdown, and the two-hour self-iteration checklist.

## Validation

- Watcher tests: `51 passed`.
- Full worker suite: `438 passed`.
- Live run after three completed rounds: `insufficient_window / observe_more_rounds`, as required.
- Productive sources observed: Neural KDJ, normal, and target-weight inversion.
- Weight KDJ, Ridge KDJ, and recency canary remained `observing`; no premature starvation claim was produced.
- After round 4 was committed, the same window matured to `diverse / continue_current_run`. Productive sources were Neural KDJ, normal, Ridge KDJ, and target-weight inversion.
- Weight KDJ generated 28 candidates, five reached full evaluation, and none reached Top5; recency canary generated 16, one reached full evaluation, and none reached Top5. Both were labeled `evaluated_without_top5`, while the overall run remained diverse.
- Advisor freshness remained current through `2026078`; watcher action remained `continue_current_run`; frozen promotion remained blocked by `frozen_validation_not_better`.

## Guardrail

Source conversion is search-process evidence only. It cannot prove predictive value, replace the null baseline, bypass leakage checks, or promote a candidate without frozen/forward evidence.
