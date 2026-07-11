# Training Forward-Evidence Wait Gate v1

## Primary Goal

Turn the same-history soft stall into an evidence-aware wait state: once a complete next-issue snapshot exists and repeated rounds add adaptive tests without new observations, park the supervisor at a durable round boundary and resume automatically after that issue is synced.

## Non-Goals

- Do not change models, weights, candidate sources, budgets, objectives, ranking, frozen validation, or promotion.
- Do not treat lower CPU use as model improvement.
- Do not release the historical holdout quarantine or claim predictive evidence.
- Do not skip advisor refresh, snapshot evaluation, parser checks, or issue synchronization when new data arrive.

## Task Frame

The watcher observed more than two hundred effective same-history stagnation rounds. The current run still produced diverse current candidates, but its durable round-best configuration and metric signature repeated, strategy memory selected `null_model_forward_audit`, the forward ledger remained `0/20`, and a complete three-line snapshot already existed for issue `2026079`. Restarting with more exploration on issue `2026078` would enlarge the adaptive search family without creating the external observation required by the active experiment.

## Historical Boundary

Gauss and Riemann are used as historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical history issue: `2026078`.
- Legal red-ball universe: `1,107,568`; ranked universe: `1,105,506`.
- Search/frozen split: `80/20`, zero overlap, promotion-only frozen role.
- Forward activation: after `2026078`; pending complete snapshot: `2026079` for static, dynamic KDJ, and near-dynamic KDJ.
- The wait state is operational evidence control, not a prediction or betting signal.

## Gauss Pass: Verification

Strongest claim: after a complete prediction has already been frozen for the next unseen issue, another search round over the unchanged historical surface cannot increase the count of genuinely forward observations. It can only add another adaptively selected historical test.

Weakest assumption: four repeated durable configurations and metric signatures are enough to declare that the present run is no longer buying useful search information. The gate therefore also requires the explicit `null_model_forward_audit`, an incomplete sequential/adaptive family, a complete future snapshot, and zero selection or promotion writes.

Test requested from the structural lens: show a case where the pending issue is already synced or the future line set is incomplete; the gate must release or refuse parking respectively.

Historical boundary note: exact counters, conjunction gates, and proof obligations are Gauss-inspired verification disciplines, not historical authority for a modern supervisor.

## Riemann Pass: Structure

Strongest claim: the training state has crossed from a search-limited region into an observation-limited region. Continuing along the same historical chart changes parameters and multiplicity but not the missing forward coordinate.

Weakest assumption: process parking and later restart preserve the same experimental path. The existing continuity ledger, frozen snapshots, same-history sequential null ledger, and issue-keyed advisor refresh are therefore retained across the transition.

Test requested from the arithmetic lens: prove the resume condition is ordered by issue number and that a pending issue no longer greater than history cannot remain parked.

Historical boundary note: chart and transition language is a Riemann-inspired modern reconstruction, not a claim about Riemann's historical formalism.

## Cross-Review

- Gauss requires a complete future snapshot, exact future-issue ordering, durable database boundary, clean DB reads, and explicit false values for selection and promotion.
- Riemann requires the active strategy to be `null_model_forward_audit`, repeated same-history geometry, and a resume transition driven by new data rather than a timer reset.
- Both reject the prior `prepare_restart_with_more_exploration` recommendation for this state because restart alone produces no new forward observation.

## Implementation

- Add `dehps-forward-evidence-wait-v1` to the training watcher.
- Require at least four repeated configuration signatures, repeated metric signatures, and current-run stagnant rounds.
- Require a complete pending snapshot whose issue is strictly greater than the latest history issue.
- Require an incomplete sequential/adaptive search family and unchanged selection/promotion state.
- Replace the same-history restart recommendation with `await_new_forward_issue` when the full conjunction holds.
- Add an independent fail-closed guard that validates the watcher payload, durable round boundary, active PID/lock when present, future issue ordering, DB health, and safety state.
- Teach `ensure_training_supervisor.sh` to stop at the validated boundary and remain parked; after sync reaches the pending issue, the gate releases automatically so predictions are evaluated, advisors refresh, and a fresh supervisor can create the next snapshot.

## Falsification

Reject the change if it parks without a complete future snapshot, while DB reads fail, before a durable round record, for a mismatched PID, after the pending issue has already arrived, without repeated outputs, outside `null_model_forward_audit`, or with selection/promotion enabled. Reject it also if the new issue cannot release the gate.

## Validation

- Watcher, forward-wait guard, restart-guard, and waiting-status targeted suites: `101 passed`.
- Full worker suite: `535 passed`.
- Python compilation and shell syntax passed.

## Live Verification

On supervisor `20260711-132111`, the updated watcher changed the recommendation from `prepare_restart_with_more_exploration` to `await_new_forward_issue`. It observed effective stagnation above 200 rounds, five repeated configurations and metric signatures, strategy `null_model_forward_audit`, history issue `2026078`, complete future snapshot `2026079`, an observed sequential family above 1,100 tests, explicit uncounted adaptive search, and unchanged selection/promotion state.

The first integration attempt did not park the process. The guard failed closed because the watcher CLI's compact operator payload omitted sequential-risk and PID/lock fields, and because round 7 was not at the instantaneous durable boundary. The compact payload was extended, targeted tests were added, and the ensure path was changed to validate the wait request first and then poll for the next durable boundary rather than terminating a partial round.

The final live path synced from `2026078` with zero inserts, updates, or conflicts, confirmed the wait request, and waited while round 8 finished. At `target_complete_round_recorded`, the database and status contained eight complete current-run rounds. The sequential ledger reached 317 total same-history rounds, 23 diagnostic rounds, 418 candidate tests, an observed family of `1,254`, and 294 explicit legacy gaps. The guard then stopped PID `3579268` and did not launch a replacement process.

The status marker changed the compact supervisor state from the stale process label `running` to `waiting_for_forward_issue`, recorded history `2026078`, pending issue `2026079`, `process_active=false`, `selection_changed=false`, and `promotion_allowed=false`. A second ensure invocation re-synced the unchanged issue and returned `training supervisor remains parked`; the heavy-job lock stayed inactive. Holdout overlap remained zero, prefilter isolation passed, forward evidence remained `0/20`, and historical quarantine stayed active.

## Synthesis

The soft stall is not a request for more compute on unchanged evidence. It is an experiment waiting for an external observation. The smallest defensible recovery is to preserve the prediction snapshot and statistical path, stop adding same-history trials, and resume when the missing issue arrives.

## Next Verification

When `2026079` is synced, confirm the gate releases, all three saved snapshots are evaluated before training, advisors refresh to the new issue, and a fresh supervisor creates the next complete snapshot. After that snapshot is durable and the same-history repetition gate matures again, confirm the supervisor parks for the following issue without resetting continuity or sequential counts.
