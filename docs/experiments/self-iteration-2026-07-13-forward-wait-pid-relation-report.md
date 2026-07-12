# Forward-Wait Heavy-Job PID Relation Guard

Date: 2026-07-13

## Round scope

- Primary goal: make the forward-wait parking guard authorize the current
  training supervisor from the watcher's PID-relation evidence instead of the
  free-form heavy-job owner label.
- Non-goals: no strategy, objective, weight, advisor, candidate source, source
  budget, search base, promotion, prediction, or supervisor lifecycle changes.

## Initial evidence

Live run `20260712-220448` completed database round 24 while this round was
inspected.  The watcher reported:

- legal red-ball universe `1,107,568`, ranked universe `1,105,506`, and 2,062
  rule exclusions;
- expanding training window 900 and a non-overlapping 80-issue search / 20-issue
  frozen split ending at issue `2026079`;
- passed holdout and prefilter isolation with zero frozen issue overlap;
- passed prediction-input boundary, parser/sync checks, and zero unresolved data
  conflicts;
- `heavy_job_supervisor_relation.status=same_supervisor_pid` for PID `563172`;
- only 1 of 20 required post-protocol paired forward issues; and
- an incomplete sequential null ledger, frozen holdout quarantine, and no
  automatic promotion permission.

The current candidate Top remained diverse (10 distinct rank signatures), even
though the historical round-best signature repeated.  This is decision-surface
stagnation, not candidate-space collapse, and is not evidence of predictive
ability.

Code review found that `training_watch_forward_wait_guard.py` independently
reinterpreted `heavy_job_lock.owner == "training-supervisor"`.  It checked the
raw lock PID but did not require the watcher-owned PID-relation status and did
not require that relation to describe an active heavy job.

## Historical diagnostic boundary

The following Gauss and Riemann passes are historically inspired verification
lenses, not literal minds, complete reconstructions, or authority evidence.

## Gauss pass: verification

- Object: authorization to park one specific active supervisor at a durable
  forward-wait boundary.
- Invariant: expected PID = supervisor status PID = heavy-job relation
  supervisor PID = heavy-job PID, with `same_pid=true` and active metadata.
- Boundary cases: missing relation, a different active PID, inactive metadata,
  and a misleading owner label.
- Proof obligation: accept a valid relation even if the descriptive owner label
  changes; reject missing or inconsistent PID relations.
- Baseline: the old guard combined the expected PID with an owner-string check
  but did not consume the unified relation status.

## Riemann pass: structure

The raw supervisor status, lock metadata, and process observation form separate
local views.  The watcher already maps them onto one ownership-relation object.
The parking guard should consume that object rather than create a second,
label-based ownership interpretation.  The structural failure boundary is any
missing or non-`same_supervisor_pid` relation.

## Cross-review, disagreement, and synthesis

Gauss requires every PID equality explicitly rather than trusting the relation
status alone.  Riemann requires the status object to remain the canonical
ownership representation rather than rebuilding ownership from raw labels.
There is no unresolved disagreement for this change: require both the canonical
relation and its explicit PID/active invariants.  The owner text remains
observational only.

## Change

The forward-wait guard now requires, whenever an expected PID is supplied:

- `heavy_job_supervisor_relation.status=same_supervisor_pid`;
- `heavy_job_active=true` and `same_pid=true`; and
- both relation PIDs equal the expected supervisor PID.

Missing relation evidence and `different_active_pid` fail closed.  A changed
owner label no longer changes the decision when the PID relation is valid.

## Validation

- Focused watcher, restart-guard, and forward-wait-guard regressions passed:
  `131 passed`.
- Full Python worker regression passed: `641 passed`.
- New tests cover a non-semantic owner label, a different active PID, and a
  missing relation object.
- The current live supervisor was not stopped or restarted; round 24 became a
  durable database record and round 25 continued normally.

## Interpretation and next verification

This is an operational fail-closed ownership fix.  It does not improve model
quality, add forward evidence, alter the legal sample space, or change
selection/promotion.  When the run later reaches a valid forward-wait state, the
watchdog should be observed once to confirm the live guard reports
`watch_forward_wait_ready:<history>-><pending>` only at a durable round boundary.
