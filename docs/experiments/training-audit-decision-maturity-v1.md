# Training Audit Decision Maturity V1

## Round frame

Primary goal: prevent long-running self-iteration from confusing an early source-conversion observation or an advisor navigation gate with evidence that is mature enough to change candidate budgets or promote a model.

Non-goals:

- no model, weight, advisor, candidate generator, prefilter, or promotion change;
- no source quota or source-based promotion reservation;
- no claim that the current model improved;
- no restart based on fewer than eight completed rounds from one supervisor run.

Training context: SSQ red-ball legal universe 1,107,568; ranked post-filter universe 1,105,506; `current_regime_default`; expanding train window 900; eval window 100; issue `2026078`. The operational baseline remains the incumbent frozen-primary score, with ranked-uniform null diagnostics and parser/sync/duplicate checks kept visible.

## Task frame

The live supervisor can compute continuously while frozen validation remains unchanged. Progress in this round means making the observation-to-decision boundary explicit: four completed same-run rounds may classify source conversion for monitoring, but a source-budget experiment may not be proposed until at least eight completed same-run rounds. The watcher must also state separately whether the promotion gate evaluated frozen validation and whether the search-navigation decision required frozen-primary lift.

## Historical boundary

The Gauss and Riemann names below denote historically inspired verification lenses, not literal minds, trained replicas, or sources of authority.

## Gauss pass: verification

Strongest claim: in live run `20260710-164004`, the frozen promotion gate is evaluated and is rejecting the current candidate because frozen validation is not better. This is distinct from the conditional frozen-primary requirement used to choose the next search base.

Weakest assumption: eight rounds are sufficient to justify a small budget experiment. Eight rounds reduce the risk of reacting to one transient prefilter outcome, but they do not prove that a source is intrinsically weak or predictively useless.

Test for the structural pass: preserve the four-round monitoring classification, add an independent eight-round same-run budget-review threshold, and surface the promotion gate as evaluated/passed/bypassed without inferring it from the navigation gate.

## Riemann pass: structure

Strongest claim: source conversion and model promotion are different layers of the training state space. Candidate sources can overlap; Top5 survival describes movement through the search pipeline, while frozen validation controls movement across the model-promotion boundary.

Weakest assumption: source labels are stable enough to support budget review. Because one configuration may belong to multiple source families, any later budget experiment must remain a reversible allocation test rather than a claim about model classes.

Test for the verification pass: the operator and Markdown views must retain source overlap warnings, expose the longer review window, and never turn a zero-Top5 source into automatic rejection or promotion of another source.

## Cross-review

Gauss rejects the old watcher label `frozen_primary_lift_required=false` as a general description of the frozen promotion gate: it reported a search-navigation condition while the actual promotion gate was actively rejecting the candidate. Riemann rejects using the four-round classification threshold as a global source-budget decision boundary because the trajectory is still short and locally conditioned on the current search base.

## Disagreement

- Evidence: eight rounds may still be too short for a budget mutation. Required evidence is persistent same-run non-conversion plus a clean baseline comparison after a single reversible allocation change.
- Scope: Weight KDJ and recency canary may be locally unproductive around the current search base without being globally unproductive. A later experiment may reduce, but must not delete, their exploration path.
- Risk: Top5 conversion is downstream of an eval-slice objective and remains vulnerable to repeated-search selection. Frozen validation, null diagnostics, and leakage checks remain mandatory.

## Synthesis

Smallest shared conclusion: keep the current supervisor running until the same-run window reaches at least eight completed rounds. Before that boundary, source survival is observation only. At and after the boundary, persistent zero-conversion sources become candidates for one conservative budget experiment, not evidence for source removal or model strength. Promotion status must be read from the frozen promotion gate, not from the navigation gate.

## Implementation

- Added a separate eight-round `budget_review_min_rounds` threshold while retaining the four-round source-observation threshold.
- Added `budget_review_ready`, `budget_review_action`, and `budget_review_sources` to JSON, CLI/operator output, and Markdown.
- Added explicit promotion fields: `promotion_frozen_validation_evaluated`, `promotion_frozen_validation_passed`, and `promotion_frozen_validation_bypassed`.
- Renamed the watcher-level navigation condition to `decision_navigation_frozen_primary_lift_required` so it cannot be mistaken for the promotion gate.
- Updated the two-hour self-iteration instructions to prohibit budget or prefilter changes before the eight-round same-run boundary.

## Live verification

At five completed rounds in run `20260710-164004`:

- supervisor PID `2277896` remained active with fresh target progress and no runtime error;
- frozen promotion was `evaluated=true`, `passed=false`, `bypassed=false`, reason `frozen_validation_not_better`;
- parser/sync/duplicate checks passed and advisor signals were current through issue `2026078`;
- source monitoring was `diverse`, while budget review was `observed=5/8`, `ready=false`, action `observe_until_budget_review_window`;
- Weight KDJ had generated 35 candidates, five reached full evaluation, and none reached Top5;
- recency canary had generated 20 candidates, three reached full evaluation, and none reached Top5;
- Neural KDJ, normal, Ridge KDJ, and target-weight inversion remained productive search sources;
- no candidate improved the incumbent frozen-primary score `[0, 0, 0]`; the model therefore cannot be described as stronger.

Validation commands:

- watcher suite: `53 passed`;
- full worker suite: `440 passed`;
- `bash -n scripts/hourly_self_iterate.sh` passed;
- `git diff --check` passed.

Mature-window update at eight completed rounds:

- `budget_review_ready=true`, action `review_persistently_unproductive_source_budgets`;
- Weight KDJ generated/selected/Top5 was `56/10/0` and recency canary was `32/4/0`;
- productive sources remained Neural KDJ, normal, Ridge KDJ, and target-weight inversion, so the search was not globally collapsed;
- four unique round-best configs were observed across eight rounds; the latest config/metric repeat streak was three and no repetition alert was active;
- all eight rounds were rejected by `frozen_validation_not_better`; promotion frozen validation remained evaluated and not bypassed;
- the smallest single-variable follow-up selected Weight KDJ only: reduce its operational share from 0.22 to 0.10 while preserving three candidates per round. Recency canary remains unchanged as a control.

## Next verification

The eight-round boundary was reached and selected the Weight KDJ-only budget experiment described above. The next audit should let fresh run `20260710-174409` reach the same eight-round maturity window, then compare source conversion, distinct configs/rank signatures, repetition, frozen promotion, null expectation, and leakage checks against the 0.22-share baseline. No further source-budget change is justified before that comparison.

## Guardrail

This round improves audit correctness, not predictive performance. Historical response-surface behavior remains hypothesis evidence only and does not support guaranteed hits, low-risk betting, or a claim of future edge.
