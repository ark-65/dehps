# Training Search-Slice Navigation V1

## Primary Goal

Restore the intended rank-geometry escape path under promotion-only holdout isolation, without allowing frozen validation to influence search or promotion.

## Non-Goals

- Do not add a model, advisor, candidate source, objective term, or weight.
- Do not increase candidate, CPU, or restart budgets.
- Do not weaken the 80/20 isolation, null baseline, leakage checks, or historical holdout quarantine.
- Do not claim predictive lift from historical navigation behavior.

## Task Frame

Run `20260711-020627` completed 14 durable rounds before the controlled handoff. Its latest 11-round audit window contained seven productive ordinary/advisor sources and new restart hashes every round, yet one repeated best config and one repeated metric signature. Restart champions changed all 80 search targets and were fully evaluated around rank 11–12, but never became the next search base.

Progress for this round means one post-isolation restart champion can become search base using only search-slice rank geometry, and the following round actually starts from that config. Failure means the candidate remains unreachable, uses frozen evidence, violates distance/cooldown/rank-change constraints, breaks isolation, or causes a runtime error.

## Historical Boundary

Gauss and Riemann are used here only as historically inspired verification and structural-reframing lenses, not as literal minds, trained replicas, or authorities. The code, persisted database rows, legal sample space, null model, and live rounds remain the evidence.

## Gauss Pass: Verification

- Legal red-ball sample space remains `C(33,6) = 1,107,568`; the ranked universe in the live run is `1,105,506` after existing exclusions.
- History is fixed at issue `2026078` with a 100-issue evaluation split: 80 search issues and 20 frozen promotion-only issues.
- Persisted overlap is `0`; `search_uses_frozen_validation=false`.
- Advisor signals are current at `2026078`; target inversion correctly ends at the search cutoff `2026058`.
- Before the fix, `exploration_navigation_eligible` began with `require_frozen_primary_lift`. Under promotion-only isolation this flag is deliberately false, making eligibility identically false regardless of rank movement, distance, or novelty.
- The fix separates two proof obligations:
  - promotion-only search navigation: search-slice rank change, config distance, recent-hash cooldown, and rank-signature cooldown;
  - legacy frozen-gated navigation: strict frozen-primary lift plus existing quality checks.
- Metadata explicitly records the eligibility basis and whether frozen validation was used.

Strongest claim: the old Boolean condition made the post-isolation experimental-navigation path unreachable.

Weakest assumption: a changed search-slice rank vector is useful exploration geometry; it is not evidence of predictive improvement.

Test requested from the structural lens: verify that the selected config becomes the next round's actual coordinate, rather than only changing metadata.

## Riemann Pass: Structure

- The candidate parameter space was not collapsed: search bases and restart hashes changed. The map from those coordinates to the winning 80-target rank signature was locally degenerate.
- The restart champion supplies a different point in rank-vector space, while generic challengers remained closer to the repeated objective plateau.
- Prioritizing an eligible experimental-navigation point before a generic challenger changes the next local neighborhood without changing the incumbent or promotion boundary.
- The appropriate invariant is not parameter distance alone but a changed target-rank vector subject to distance and cooldown constraints.

Strongest claim: the defect confused “a candidate exists in a different rank geometry” with “the candidate has frozen-primary evidence,” even though those coordinates belong to separate search and promotion spaces.

Weakest assumption: one or two navigated rounds may still return to the same global plateau; local escape does not guarantee global improvement.

Test requested from the verification lens: persist the selected source, basis, frozen-use flag, next-round starting hash, isolation fields, and promotion result.

## Cross-Review

Gauss rejects any claim that rank movement is model lift and requires frozen quarantine to remain closed. Riemann rejects another budget-only mutation because the existing candidates already span new parameter points but the intended rank-space transition was unreachable. Both accept a control-flow repair whose observable effect is limited to search-base navigation.

## Disagreement

- `scope`: It is unresolved whether repeated global round bests are caused mainly by objective discretization or by insufficient local neighborhoods around the new rank geometry.
- `evidence`: Two live rounds can prove the branch and state transition work, but cannot prove future prediction strength.
- Required evidence: subsequent same-history rounds must show whether rank-signature diversity increases, while genuinely forward paired issues remain the only path toward a prediction claim.

## Synthesis

The smallest shared conclusion is a verified local control-flow defect: promotion-only isolation unintentionally disabled the experimental rank-geometry transition. The repair may improve search coverage, but promotion, model strength, and betting value remain unproven.

## Implementation

- Promotion-only mode can mark an experimental navigation candidate eligible from search-slice rank geometry without consulting frozen-primary or frozen-quality outcomes.
- Strict legacy mode still requires frozen-primary lift and existing quality checks.
- An eligible experimental navigation candidate is selected before a generic search challenger, but never before a formally improved model.
- The watcher exposes `eligibility_basis` and `selection_uses_frozen_validation` in gate, Markdown, CLI, and operator summaries.
- Hourly self-iteration must verify that a selected navigation hash becomes the next durable round's `search_base_start`, preventing log-only coverage claims.

## Live Validation

Controlled handoff:

- old run/PID: `20260711-020627` / `2868765`;
- fresh run/PID: `20260711-033806` / `2960838`;
- same as-of issue and training arguments;
- continuity mode: `holdout_isolated_search_replay`;
- continuity frozen use: `false`.

Round 1 durable evidence:

- effective stagnation started at `109`, preserving same-history continuity;
- restart baseline hashes `5/5` were historical repeats, replaced `5/5`, generated reuse `0`;
- restart champion `cb5de2ba398f...` was full-eval rank `12` and changed `80/80` target ranks;
- next search base source: `experimental_navigation`;
- eligibility basis: `search_slice_rank_geometry`;
- selection uses frozen validation: `false`;
- config distance: `2.8124445` versus minimum `0.08`;
- holdout overlap: `0`;
- search uses frozen validation: `false`;
- promotion remained blocked by `historical_frozen_holdout_quarantined`;
- static result remained `[3,3,3]`; no predictive-lift claim is made.

Round 2 durable evidence:

- `search_base_start.config_hash=cb5de2ba398f...`, exactly matching round 1's selected navigation hash;
- the starting primary coordinates were `structural/frequency/omission = 0.20/0.20/0.05`;
- restart champion improved its full-eval position from rank `12` to rank `9` and again changed `80/80` targets;
- target-weight inversion produced an exploration champion at full-eval rank `5`;
- the next base moved to the already active probability-focus candidate, so experimental navigation did not reserve the search path indefinitely;
- holdout overlap remained `0`, search frozen use remained `false`, and promotion remained quarantined;
- the global historical round best still did not improve. The rank-9/rank-5 observations are path evidence only and are not assigned causal or predictive significance from two rounds.

## Validation

```text
apps/worker-python/.venv/bin/python -m pytest -q \
  apps/worker-python/tests/test_training_supervisor.py \
  apps/worker-python/tests/test_training_watch.py
216 passed

cd apps/worker-python && .venv/bin/python -m pytest -q
481 passed

bash -n scripts/hourly_self_iterate.sh
passed
```

## Next Verification

Continue observing whether the new path increases durable rank-signature diversity rather than merely cycling among alternative bases. Keep the forward-evidence ledger unchanged at `0/20` until issue `2026079` is actually drawn and synced; only paired forward evidence can support a prediction claim.
