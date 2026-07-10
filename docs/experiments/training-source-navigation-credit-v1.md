# Training Source Navigation Credit v1

## Primary Goal

Make candidate-source survival diagnostics distinguish a source that fails to reach full-evaluation Top5 from a source that is nevertheless selected, without frozen-validation input, as the next search base and actually advances the search path.

## Non-Goals

- No model, advisor, candidate generator, budget, threshold, weight, or ranking change.
- No automatic source-budget adjustment.
- No promotion or quarantine release.
- No predictive-lift claim.

## Task Frame

The active run `20260711-041601` reached eight durable rounds, the predeclared minimum for source-budget review. Its `stagnation_restart` source generated 40 candidates and placed none in full-evaluation Top5, so the old survival summary classified it as `evaluated_without_top5` and would have included it in `budget_review_sources`.

That label omitted a separate observed role. The source supplied the selected experimental navigation in five of eight rounds. For each selected round with a following durable round, the following `search_base_start.config_hash` matched the selected navigation hash. Selection used `search_slice_rank_geometry`, while `selection_uses_frozen_validation=false` and the frozen window remained promotion-only.

Progress for this round means correcting the source diagnostic so that exact, selected, holdout-isolated search transitions are visible and cannot be mistaken for persistent source inactivity.

## Historical Boundary

Gauss and Riemann below are historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`.
- Legal red-ball sample space: 1,107,568.
- Ranked universe: 1,105,506; excluded: 2,062.
- Historical scope: expanding, 900-train, 100-evaluation, current ten-year regime.
- Search/frozen split: 80/20 with zero issue overlap.
- Frozen role: promotion only; `search_uses_frozen_validation=false`.
- Forward paired evidence: `0/20`; quarantine remains active.
- Ranked-uniform search-slice null expectation over 80 draws: 0.007237 / 0.072365 / 0.723651 hits at Top100 / Top1000 / Top10000.
- Parser, sync, duplicate, universe-completeness, and data-conflict checks passed.

## Gauss Pass: Verification

Strongest claim: the old classification was arithmetically incomplete. It counted generated, prefilter-selected, Top5, round-best, and frozen-frontier events, but assigned zero credit to five exact selected search-base transitions. Therefore `evaluated_without_top5` did not mean “without operational use.”

Weakest assumption: a selected search transition is useful enough to protect a source from the label “persistently unproductive.” This does not assert score improvement. It asserts only that the source performed an intended exploration function and should not be budget-reviewed as unused under a Top5-only definition.

Required countercheck from the structural lens: verify that the source is identified through the exact selected hash and diagnostic source, rather than inferred from a nearby candidate or a preempted counterfactual.

The implementation awards one `search_navigation_round` only when all conditions hold:

1. Frozen validation is promotion-only and search use is explicitly false.
2. The selected search-base source is `experimental_navigation`.
3. Navigation is explicitly marked selected.
4. Selection explicitly did not use frozen validation.
5. Selected, navigation, and diagnostic candidate hashes agree.
6. The diagnostic source is active and names the originating candidate source.

## Riemann Pass: Structure

Strongest claim: candidate sources have at least two distinct roles in the search-state graph. One role is local ranking quality inside a round; another is generating an edge to the next search state. A Top5-only coordinate observes the first role but collapses the second.

Weakest assumption: following a new edge is structurally valuable even when the global best and metric vector do not change. Here that value is limited to search coverage and auditability, not model quality.

Required countercheck from the verification lens: reject preempted candidates, mismatched hashes, frozen-influenced selection, and diagnostic records whose source cannot be resolved exactly.

## Cross-Review

- Gauss rejects counting mere eligibility, because it is a counterfactual rather than an executed transition.
- Riemann rejects treating Top5 absence as proof that a source did nothing, because the source may have changed the next state.
- Both require an exact selected-hash chain and explicit holdout isolation.
- Both keep the evidence label operational and forbid promotion or predictive claims from it.

## Disagreement

Gauss would prefer a future rate threshold before calling a navigation source broadly productive. Riemann accepts a single executed edge as evidence that the source has a distinct operational role. The implementation uses the narrower state name `productive_search_navigation` and exposes the exact count, while the eight-round maturity gate remains required before budget review. Whether the source budget is optimal remains unresolved and requires a separate single-variable experiment.

## Synthesis

The smallest shared conclusion is a verified local correction: selected, holdout-isolated navigation is operational source output and must be reported separately from Top5 performance. It protects such a source from the specific claim “persistently unproductive” without treating navigation as score lift.

The watcher now records:

- `search_navigation_rounds` per source;
- `search_navigation_sources` in JSON, operator, and Markdown output;
- state `productive_search_navigation` when the source has executed such a transition;
- explicit interpretation that this is search-path evidence, not predictive lift.

## Validation

Focused watcher suite:

```text
74 passed in 4.52s
```

Full worker suite:

```text
490 passed in 39.06s
```

Live watcher against eight durable rounds:

```text
run: 20260711-041601
rounds: 8
durable boundary: target_complete_round_recorded
stagnation_restart generated: 40
stagnation_restart prefilter selected: 21
stagnation_restart full-eval Top5: 0
stagnation_restart selected search navigation: 5
stagnation_restart state: productive_search_navigation
budget review ready: true
budget review sources: neural_kdj, recency_canary, ridge_kdj
```

The previous false-positive source, `stagnation_restart`, is absent from budget review. The active supervisor continued into round 9 under the same PID `3002210`; no restart was required because this change affects watcher diagnostics only.

## Next Verification

Treat `neural_kdj`, `recency_canary`, and `ridge_kdj` only as candidates for a later budget experiment. Before changing one source, predeclare one baseline share, one alternative share, the same-history comparison window, and falsification conditions for candidate diversity, Top5 conversion, search-navigation coverage, and runtime stability. Change only one source per round, preserve the 80/20 isolation and null/leakage checks, and verify at least two fresh supervisor rounds before acceptance.
