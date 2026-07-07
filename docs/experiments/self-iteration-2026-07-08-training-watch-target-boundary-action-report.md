# Self-Iteration Report: Training Watch Target Boundary Action

## Primary goal

Make restart readiness safer during rank-homogeneity alerts by distinguishing
a continuous supervisor that is still inside its current target batch from one
that has reached a target boundary.

## Non-goals

- Do not change training, advisor, search, promotion, scoring, candidate
  generation, or restart logic.
- Do not stop, transfer, replace, or restart the live supervisor process.
- Do not promote any prediction, betting, or model-performance claim.

## Initial state

`apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`
completed successfully for run `20260707-213002` and returned:

- severity: `alert`
- action: `prepare_restart_with_more_exploration`
- failure modes: `promotion_gate:frozen_validation_not_better`,
  `eval_slice_overfit:eval_slice_overfit_no_frozen_primary_lift`,
  `rank_homogeneity:stale_rank_signature_cycle`
- restart readiness: blocked by `active_training_supervisor_lock`
- live supervisor: status `running`, run mode `continuous`, PID `3016955`
- observed target progress during diagnosis: round `98`, target progress
  `30 / 100 complete=False`

The previous restart-readiness action for any fresh continuous supervisor was
`operator_review_then_stop_continuous_training_supervisor_before_restart`.
That was too coarse for the `complete=False` state because the active
supervisor was still inside a target batch.

The evidence context remained operational-only:

- legal sample space: `ssq_red_ball_combinations`
- legal universe: `1107568`
- ranked universe: `1105506`
- excluded combinations: `2062`
- historical window: `current_regime_default`, expanding train window `900`,
  eval window `100`, top-N `10000`, regime start `2016-07-07`
- baseline/null model: incumbent frozen-primary baseline and ranked uniform
  per-draw random null
- leakage checks: frozen-primary promotion gate active, eval-slice overfit
  guardrail active, parser/sync duplicate checks reported checked

## Diagnostic constraint

Historical Gauss/Riemann lenses were used as verification and structure
constraints, not as authority or literal reconstructions.

- Task Frame: the object is an operational restart-readiness state during a
  stalled training run. Progress means clearer operator action, not a new
  strategy.
- Historical Boundary: Gauss and Riemann here are historically inspired
  reasoning lenses only.
- Gauss Pass: the measurable facts are the active lock, fresh progress,
  continuous run mode, target completion flag, frozen-validation failure,
  legal universe, baseline/null model, and leakage status. A fresh supervisor
  remains blocked while the active training-supervisor lock is held.
- Riemann Pass: the relevant state space is the lifecycle transition from
  "continuous supervisor in target batch" to "target boundary where operator
  review can stop and restart." The boundary should be represented in the
  operator action.
- Cross-Review: Gauss rejects any predictive conclusion from this change;
  Riemann rejects collapsing two lifecycle states into one stop instruction.
- Disagreement: no strategy, model, advisor, or weight claim is evaluated in
  this round.
- Synthesis: preserve the active-lock block, but return a wait-for-boundary
  action while `target_complete=False`.
- Next Verification: run the targeted watch tests and a live watch command.

## Change

- `restart_readiness_summary` now returns
  `wait_for_continuous_training_supervisor_target_boundary_before_restart`
  when restart is requested, the active lock belongs to a fresh continuous
  training supervisor, and `supervisor_target_complete` is `False`.
- Existing behavior is preserved for continuous supervisors at a target
  boundary or with missing target-boundary information: operator review can
  still stop the continuous supervisor before a fresh restart.
- `test_training_watch.py` covers the live-like `30 / 100 complete=False`
  state.

## Validation

Minimal validation passed:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
apps/worker-python/.venv/bin/python -m py_compile apps/worker-python/scripts/watch_training_progress.py
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Results:

- `test_training_watch.py`: 38 passed.
- `py_compile`: passed for `watch_training_progress.py`.
- live watch completed for run `20260707-213002` with `severity=alert`,
  `action=prepare_restart_with_more_exploration`, and active lock status.
  By that later watch, the live supervisor had reached `100 / 100
  complete=True`, so the preserved operator action was
  `operator_review_then_stop_continuous_training_supervisor_before_restart`.

## Guardrail

This is an operational watch-action fix only. It does not alter candidate
generation, scoring, training, advisors, dynamic weights, promotion gates, or
supervisor lifecycle behavior. The watch output remains diagnostic evidence
only; it does not support guaranteed hits, settled predictive edge, or
low-risk betting advice.
