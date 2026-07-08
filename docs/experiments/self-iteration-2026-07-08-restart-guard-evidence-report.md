# Self-Iteration Report: Restart Guard Evidence Gate

## Primary goal

Harden the training-watch restart guard so it only permits an operator-reviewed
continuous-supervisor restart when the watch summary includes concrete restart
candidate and experimental-navigation evidence.

## Non-goals

- Do not change scoring, advisor, candidate-source, promotion, dynamic-weight,
  or search strategy logic.
- Do not weaken frozen validation, leakage checks, baseline/null reporting, or
  evidence-level language.
- Do not make prediction, betting, or model-performance claims.
- Do not commit generated `data/output` or `runtime` artifacts.

## Initial state

The required watch command completed successfully:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Observed state before the fix:

- run id: `20260708-103002`
- severity: `alert`
- action: `prepare_restart_with_more_exploration`
- failure modes: `promotion_gate:frozen_validation_not_better`,
  `eval_slice_overfit:eval_slice_overfit_no_frozen_primary_lift`, and
  `rank_homogeneity:stale_rank_signature_cycle`
- restart readiness: blocked by `active_training_supervisor_lock`
- blocker stage: `active_continuous_supervisor_target_complete`
- active supervisor PID: `3694584`
- restart candidate: rank vector changed, `100` changed targets, full eval rank
  `14`, frozen primary `[0, 0, 0]`, frontier improvement basis `secondary`
- experimental navigation: eligible, quality `passed`, config distance
  `2.0982626296634663`, minimum distance `0.08`

## Evidence context

- Evidence level: `operational_training_diagnostic_no_predictive_claim`.
- Legal sample space: `ssq_red_ball_combinations`.
- Legal universe: `1107568`; ranked universe: `1105506`; excluded
  combinations: `2062`.
- Historical window: `current_regime_default`, expanding train mode,
  train window `900`, eval window `100`, regime start `2016-07-07`, top-N
  `10000`.
- Baseline/null model: incumbent frozen-primary baseline plus ranked-uniform
  per-draw random null.
- Leakage/data checks reported by watch: frozen-primary gate active,
  eval-slice overfit guardrail active before restart, parser/sync duplicate
  checks passed.
- Uncertainty: frozen validation can remain at baseline even when eval-slice
  metrics look strong.

## Diagnostic constraint

Historical Gauss/Riemann lenses were used as verification and structure
constraints, not as authority or literal reconstructions.

- Task Frame: the object is the restart decision for an active continuous
  training supervisor under rank-homogeneity stagnation. Progress means safer
  lifecycle control, not a new strategy.
- Historical Boundary: Gauss and Riemann are historically inspired reasoning
  lenses only.
- Gauss Pass: the measurable facts are lock PID, supervisor status PID, watch
  action, target-boundary freshness, restart-candidate rank-vector change,
  changed target count, frontier-improvement basis, navigation eligibility,
  legal sample space, historical window, baseline/null model, and leakage
  checks. A restart guard must reject missing or contradictory evidence.
- Riemann Pass: the lifecycle state has a mixed startup window where the
  heavy-job lock can point to a new PID while watch still reports the old run
  until DB rounds are persisted. That state must remain not-ready.
- Cross-Review: Gauss rejects restart permission from a single boolean
  `restart_candidate_active`; Riemann rejects collapsing candidate evidence and
  navigation eligibility into one undifferentiated state.
- Synthesis: keep the existing operator-reviewed target-boundary restart, but
  require explicit candidate and navigation evidence before the guard returns
  success.
- Next Verification: targeted unit tests, live guard checks, fresh supervisor
  restart, and at least two persisted rounds from the new run.

## Change

- Added parsing for positive integer and float evidence fields in
  `training_watch_restart_guard.py`.
- Required restart guard success to include:
  - restart candidate rank vector changed
  - changed target count greater than zero
  - full eval rank greater than zero
  - primary or secondary frontier improvement
  - improvement basis of `primary` or `secondary`
  - experimental navigation eligible
  - navigation quality `passed`
  - navigation rank vector changed
  - navigation config distance at least the minimum distance
- Added unit tests for unchanged rank vectors, missing frontier improvement,
  and navigation quality/distance failures.

## Validation

Commands:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch_restart_guard.py apps/worker-python/tests/test_training_watch.py
apps/worker-python/.venv/bin/python -m py_compile apps/worker-python/scripts/training_watch_restart_guard.py
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5 | apps/worker-python/.venv/bin/python apps/worker-python/scripts/training_watch_restart_guard.py --expected-pid 3694584
scripts/ensure_training_supervisor.sh
```

Results:

- Targeted pytest: `50 passed`.
- Python compile check: passed.
- Live guard before restart returned `watch_restart_ready_target_boundary` for
  PID `3694584`.
- `scripts/ensure_training_supervisor.sh` synced issue `2026077`, stopped PID
  `3694584`, and started fresh supervisor PID `3881115`.
- Fresh supervisor run id: `20260708-140600`.
- During the old-status/new-lock startup window, the updated guard rejected the
  mixed state for PID `3881115` with `watch_restart_not_ready:supervisor_pid`.
- Fresh supervisor validation: run `20260708-140600` persisted rounds `1` and
  `2`; watch returned severity `ok`, action `continue_current_run`, and round
  boundary `target_complete_round_recorded`.

## Guardrail

This is an operational lifecycle guard hardening only. It does not alter model
scoring, candidate generation, advisor behavior, promotion gates, dynamic
weights, or betting language. The observed historical response-surface behavior
remains hypothesis evidence only and does not support guaranteed hits, settled
predictive advantage, or low-risk betting advice.
