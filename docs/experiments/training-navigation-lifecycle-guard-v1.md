# Training Navigation Lifecycle Guard v1

## Primary Goal

Prevent the training watcher and hourly self-iteration loop from restarting an active supervisor while a selected or preempted search-slice navigation path is still being arbitrated, and require a durable database round boundary before any restart decision.

## Non-Goals

- No new model, advisor, weight, candidate source, or search heuristic.
- No promotion based on frozen validation.
- No claim of predictive lift.
- No change to the active supervisor arguments or training data.

## Task Frame

Run `20260711-041601` had five durable rounds when the patched watcher was checked. The selected experimental navigation remained based on `search_slice_rank_geometry`, with `selection_uses_frozen_validation=false`. The supervisor had already advanced to round 6 and completed target `100/100`, but the round-6 database record was not yet durable.

The previous restart guard treated `100/100` plus an active supervisor lock as sufficient preparation for a restart. That created two lifecycle hazards:

1. It could terminate the supervisor between target completion and database flush.
2. It could interrupt a navigation candidate already selected into the current supervisor path, losing the only auditable continuation evidence for that branch.

The primary observable is therefore not a score change. It is whether a restart is rejected until both the navigation arbitration is no longer in flight and `supervisor_round_boundary.status=target_complete_round_recorded`.

## Historical Boundary

- Latest canonical issue: `2026078`.
- Legal red-ball sample space: 1,107,568 combinations.
- Search/frozen split: 80/20 with zero issue overlap.
- Frozen role: promotion only.
- `search_uses_frozen_validation=false`.
- Historical holdout remains quarantined; forward evidence remains below the 20-pair review threshold.
- This change governs process lifecycle only. Historical scores remain diagnostic and cannot establish forward predictive ability.

## Gauss Pass

The exact proof obligation is a conjunction, not an inference from log timing:

```text
restart_allowed
= requested_action
  AND continuous_run
  AND fresh_progress
  AND target_complete
  AND durable_round_recorded
  AND navigation_arbitration_inactive
  AND restart_candidate_evidence_ready
```

The old guard omitted the two middle lifecycle terms. A `100/100` progress counter proves that target computation finished; it does not prove the database transaction completed. Likewise, an eligible navigation candidate with `selected=true` or a recorded `preempted_by` is evidence that arbitration belongs to the current run, not evidence that a fresh run should replace it.

The strongest supported claim is limited: the patched guard rejects a restart at the observed non-durable boundary. The weakest assumption is that selected/preempted metadata faithfully denotes current-run arbitration; tests therefore cover both states explicitly. No score or frozen-frontier observation is used to justify the guard.

## Riemann Pass

The training loop is a discrete state machine. Candidate generation, navigation eligibility, arbitration, next-round search-base use, and durable round recording form one connected path. Treating a selected candidate as a detached restart seed breaks that path and makes later evidence ambiguous: after a restart, it is no longer clear whether a changed result came from the candidate, regenerated context, or process handoff.

The database round record is the natural boundary between states. Waiting for it preserves continuity and makes the next transition inspectable. The watcher now exposes selected/preempted state, eligibility basis, frozen-use status, navigation activity, and durable-boundary status so the operational view matches that structure.

## Cross-Review

- Gauss requires two new Boolean checks before restart: a durable round record and inactive navigation arbitration.
- Riemann requires keeping the current process alive long enough for the selected branch to reach an observable state boundary.
- Both views reject killing the process solely because the progress counter reached `100/100`.
- Both preserve the same 80/20 isolation and promotion-only frozen protocol.

## Disagreement

Gauss alone would permit restart immediately after the durable record if all exact checks pass. Riemann is more conservative when a selected or preempted branch still represents an unfinished path. The implementation resolves this by retaining the navigation-arbitration blocker while the active supervisor owns that path, even if another boundary is already durable.

## Synthesis

The smallest shared correction is an operational lifecycle guard:

- Copy navigation arbitration metadata into restart readiness.
- Mark selected or preempted eligible navigation as current-run arbitration.
- Require `target_complete_round_recorded` before the restart guard may approve termination.
- Give navigation and durable-boundary blockers explicit statuses and operator actions.
- Teach hourly self-iteration the same invariants.

This is a reversible observability and safety change. It does not alter training mathematics.

## Validation

Targeted tests:

```text
85 passed in 9.02s
```

Full worker suite:

```text
487 passed in 41.32s
```

Shell and patch checks:

```text
bash -n scripts/hourly_self_iterate.sh
git diff --check
```

Live watcher result against run `20260711-041601`:

```text
latest durable round: 5
supervisor progress round: 6
target: 100/100
boundary: target_complete_waiting_round_result
navigation eligible: true
navigation selected: true
eligibility basis: search_slice_rank_geometry
selection uses frozen validation: false
restart status: blocked_by_current_run_navigation_arbitration
operator action: continue_current_training_supervisor_through_navigation_arbitration
```

The production ensure script then reported:

```text
training watch did not request supervisor restart pid=3002210
training supervisor already running pid=3002210 as_of_issue=2026078
```

The same PID remained active after the check. This verifies the guard on the live failure boundary without replacing or mutating the supervisor.

## Next Verification

Observe the next durable round and verify that its `search_base_start.config_hash` matches the previously selected navigation hash when the branch is consumed. Continue monitoring whether navigation arbitration clears naturally; only then may the existing restart evidence be reviewed again. Accumulate genuinely forward, pre-draw paired evidence separately and do not use this lifecycle fix as predictive evidence.
