# Forward-Wait Strategy-Memory Decoupling

Date: 2026-07-13

## Round scope

- Primary goal: stop an active supervisor from repeatedly re-searching an unchanged historical surface when a complete, frozen future snapshot already exists.
- Non-goals: no model weights, candidate sources, budgets, ranking, forward-result interpretation, promotion gate, legal sample space, or prediction claim changes.

## Initial evidence

After issue `2026079` was synced and all three frozen line snapshots were evaluated, supervisor run `20260712-220448` continued through 137 same-history rounds. The watch showed:

- complete `2026080` snapshots for `static_100`, `dynamic_kdj`, and `dynamic_kdj_near`, with 10,000 candidates each;
- only `1/20` paired forward issues, so no promotion eligibility;
- repeated configuration and metric signatures for five consecutive observed rounds;
- 137 current-run stagnation rounds, no accepted improvement, and an active rank-homogeneity guard;
- zero frozen-primary lift, a quarantined historical holdout, and explicit uncounted adaptive/sequential search risk; and
- healthy storage, current advisors, passed draw-input boundary, and no lifecycle or parser/sync failure.

The supervisor was healthy but was spending CPU on repeated adaptive historical evaluations without an additional independent outcome.

## Historical boundary

The Gauss and Riemann passes below are historically inspired verification lenses, not literal reconstructions or authority evidence.

## Gauss pass: verification

- Object: the forward-wait predicate in `forward_evidence_wait_summary`.
- Invariant: parking is permitted only with a future complete snapshot, repeated same-history output, incomplete forward evidence, explicit adaptive/sequential risk, unchanged selection, disabled promotion, and a durable round boundary.
- Counterexample: the exact predicate was satisfied at issue `2026079 -> 2026080`, but the watcher still returned `continue_training` solely because strategy memory selected `decision_surface_dominance_audit` instead of the string `null_model_forward_audit`.
- Proof obligation: a change must keep every safety condition and only remove the diagnostic-label dependency.

## Riemann pass: structure

Strategy memory selects a local diagnostic observation; it does not add a new outcome dimension. Forward evidence is the orthogonal time direction: only the next unseen draw can change the evidence state. Treating a strategy-memory label as permission to continue turns a local diagnostic state into an unbounded same-history trajectory.

## Cross-review and synthesis

Gauss requires the future snapshot, repetition, risk ledger, selection, promotion, and durable-boundary checks to remain intact. Riemann requires the parking decision to depend on the information geometry—whether a new unseen outcome exists—not an incidental diagnostic name. Both support the same narrow change: remove the experiment-name blocker and preserve all evidence and lifecycle gates.

## Change

`forward_evidence_wait_summary` no longer blocks parking when strategy memory selects a non-null-model observation-only experiment. The selected experiment remains reported for audit context, but does not create independent evidence or override the forward-wait conditions.

## Validation

- Focused watcher, forward-wait guard, and parking tests: `129 passed`.
- Full Python worker regression: `646 passed in 22.30s`.
- Added regression: `decision_surface_dominance_audit` now parks when all independent forward-wait conditions are true.
- Live run: the updated watcher returned `watch_forward_wait_ready:2026079->2026080` while run `20260712-220448` was active.
- At the durable record for round 137, the watchdog stopped PID `563172` and atomically marked the supervisor `waiting_for_forward_issue`.
- A post-park live watch reported `parked_waiting_for_forward_issue`, `target_complete_round_recorded`, forward evidence `1/20`, and the complete `2026080` three-line snapshot.

## Boundary and next verification

This is a compute-and-overfitting containment change, not evidence of predictive ability. Historical holdout quarantine remains active and forward evaluation remains review-only. When `2026080` is synced, the watchdog must evaluate the three frozen snapshots, refresh advisors, and launch a new supervisor against the expanded history.
