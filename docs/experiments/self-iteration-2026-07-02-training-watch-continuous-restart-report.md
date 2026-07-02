# Self-Iteration Report: Training Watch Continuous Restart Readiness

## Primary goal

Make restart readiness explicit when a restart is recommended, the active
training supervisor still reports fresh progress, and the supervisor status is
continuous rather than timed.

## Non-goals

- Do not change training, advisor, search, promotion, scoring, or candidate
  generation logic.
- Do not promote any prediction or betting claim.
- Do not stop, transfer, replace, or restart the live supervisor process.

## Initial state

`apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`
completed successfully for run `20260702-160908` and returned:

- severity: `alert`
- action: `prepare_restart_with_more_exploration`
- failure modes: `promotion_gate:frozen_validation_not_better`,
  `eval_slice_overfit:eval_slice_overfit_no_frozen_primary_lift`,
  `rank_homogeneity:stale_rank_signature_cycle`
- restart readiness: blocked by `active_training_supervisor_lock`
- live supervisor: progress fresh, PID `164181`, round `60+`

The evidence context remained operational-only: legal sample space
`ssq_red_ball_combinations`, legal universe `1107568`, ranked universe
`1105506`, excluded `2062`, historical window `current_regime_default` with
expanding train window `900`, eval window `100`, top-N `10000`, baseline/null
model present, and parser/sync duplicate status checked.

## Diagnostic constraint

Historical Gauss/Riemann lenses were used as verification and structure
constraints, not as authority or literal reconstructions.

- Task Frame: the object is a watch/restart operational decision during a
  high-stagnation training run. Progress means clearer operator action, not a
  new predictive signal.
- Gauss Pass: the measurable residual remains eval-slice strength versus
  frozen-validation failure. A restart recommendation is not launch-ready while
  the active heavy-job lock is owned by the training supervisor.
- Riemann Pass: the structural issue is the run-state space. A fresh-progress
  timed supervisor can plausibly be waited out, while a fresh-progress
  continuous supervisor has no natural deadline and needs explicit operator
  review before stopping and restarting.
- Synthesis: surface `run_mode` and distinguish continuous active supervisors
  from timed active supervisors. Keep all null-model, leakage, uncertainty, and
  failure-case labels intact.

## Change

- `watch_training_progress.py` now carries `deadline` and `run_mode` from the
  supervisor status into watch summaries and Markdown.
- For backward compatibility with already-running supervisors, a status file
  with explicit `deadline: null` and missing `run_mode` is treated as
  `continuous`.
- Restart readiness now reports
  `operator_review_then_stop_continuous_training_supervisor_before_restart`
  when restart is requested, the active lock is held by a training supervisor,
  progress is fresh, and the supervisor run mode is continuous.

## Validation

Minimal validation passed:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
apps/worker-python/.venv/bin/python -m py_compile apps/worker-python/scripts/watch_training_progress.py
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Results:

- `test_training_watch.py`: 31 passed.
- `py_compile`: passed for `watch_training_progress.py`.
- live watch completed for run `20260702-160908` with `severity=alert`,
  `action=prepare_restart_with_more_exploration`, and
  `operator_action=operator_review_then_stop_continuous_training_supervisor_before_restart`.

## Guardrail

This is an operational observability fix only. It does not change training
behavior or make any claim of predictive edge. Historical lift remains
hypothesis evidence only and still requires legal sample space, historical
window, baseline/null model, leakage checks, uncertainty, and failure modes.
