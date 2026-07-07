# Self-Iteration Report: Training Watch Target Progress Summary

## Primary goal

Expose supervisor target progress in the compact operator/CLI restart
readiness summary when training watch recommends preparing a fresh supervisor
but an active training-supervisor lock blocks restart.

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
- live supervisor: status `running`, run mode `continuous`, PID `3016955`,
  progress round `38`, target progress `100 / 100 complete=True`

The compact JSON summary emitted by the CLI included restart readiness status,
operator action, fresh progress, progress round, and run mode, but omitted the
target progress fields that were already present in the full watch artifact and
Markdown report.

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

- Task Frame: the object is an operational watch summary during a stalled
  training run. Progress means clearer operator state, not a new strategy.
- Historical Boundary: Gauss and Riemann here are historically inspired
  reasoning lenses only.
- Gauss Pass: the measurable facts are the active lock, fresh progress, target
  completion, frozen-validation failure, legal universe, baseline/null model,
  and leakage status. A restart recommendation remains blocked while the
  active training-supervisor lock is held.
- Riemann Pass: the relevant state space is the operator transition from
  "active continuous supervisor" to "fresh supervisor after review." Target
  completion is part of that state and should not disappear in the compact
  surface used by operators.
- Cross-Review: Gauss rejects any predictive conclusion from this change;
  Riemann rejects hiding lifecycle state in only the full artifact while the
  compact CLI surface drives triage.
- Disagreement: no strategy or model claim is evaluated in this round.
- Synthesis: copy existing target progress fields into the compact summary
  without changing training behavior.
- Next Verification: run the targeted watch tests and a live watch command.

## Change

- `watch_training_progress.py` now includes
  `supervisor_target_index`, `supervisor_target_total`, and
  `supervisor_target_complete` in the operator summary when restart readiness
  is requested.
- `test_training_watch.py` covers those fields in fresh-progress and
  continuous-supervisor restart-readiness scenarios.

## Validation

Minimal validation passed:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
apps/worker-python/.venv/bin/python -m py_compile apps/worker-python/scripts/watch_training_progress.py
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Results:

- `test_training_watch.py`: 35 passed.
- `py_compile`: passed for `watch_training_progress.py`.
- live watch completed for run `20260707-213002` with `severity=alert`,
  `action=prepare_restart_with_more_exploration`, and compact restart
  readiness fields `supervisor_target_index=100`,
  `supervisor_target_total=100`, `supervisor_target_complete=True`.

## Guardrail

This is an operational observability fix only. It does not alter candidate
generation, scoring, training, advisors, dynamic weights, promotion gates, or
supervisor lifecycle behavior. The watch output remains diagnostic evidence
only; it does not support guaranteed hits, settled predictive edge, or
low-risk betting advice.
