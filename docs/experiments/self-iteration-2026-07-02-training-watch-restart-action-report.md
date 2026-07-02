# Self-Iteration Report: Training Watch Restart Action

## Primary goal

Make restart readiness more precise when a restart is recommended but the active
training supervisor is still reporting fresh progress.

## Non-goals

- Do not change training, advisor, search, promotion, or candidate-source logic.
- Do not promote any prediction or betting claim.
- Do not stop, transfer, or replace the existing live supervisor process.

## Initial state

`apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`
completed successfully for run `20260702-091522` and returned:

- severity: `alert`
- action: `prepare_restart_with_more_exploration`
- failure modes: `promotion_gate:frozen_validation_not_better`,
  `eval_slice_overfit:eval_slice_overfit_no_frozen_primary_lift`,
  `rank_homogeneity:stale_rank_signature_cycle`
- restart readiness: blocked by `active_training_supervisor_lock`
- supervisor progress: fresh, running, round 41, target progress 100 / 100

Evidence context remained operational-only: legal sample space
`ssq_red_ball_combinations`, legal universe `1107568`, ranked universe
`1105506`, excluded `2062`, historical window `current_regime_default`
with expanding train window `900`, eval window `100`, top-N `10000`,
baseline/null model present, and leakage checks reporting parser/sync duplicate
status checked.

## Diagnostic constraint

Historical Gauss/Riemann lenses were used only as review constraints, not as
authority. Gauss-style verification rejects any strategy change from this
alert alone because frozen validation remains at baseline and the watch is an
operational diagnostic, not predictive proof. Riemann-style structure treats
the rank-homogeneity cycle as a search-space navigation symptom, but it does
not justify a new advisor, source, or heuristic without fresh validation.

Smallest shared conclusion: improve the operational action label for the
already-detected lock/progress state. The supervisor should not be replaced in
parallel while its progress is fresh; the watch should say to wait for the
active supervisor to finish or stop it deliberately before starting a fresh run.

## Change

- `restart_readiness_summary()` now chooses
  `wait_for_active_training_supervisor_to_finish_or_stop_before_restart` when
  the restart recommendation is blocked by an active training-supervisor lock
  and supervisor progress is fresh.
- The existing no-progress active-lock case still reports
  `stop_or_transfer_active_training_supervisor_before_restart`.
- The Judgement note now says to wait for active work to finish or
  stop/transfer the lock owner before starting a fresh run.

## Validation

Minimal validation passed:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
apps/worker-python/.venv/bin/python -m py_compile apps/worker-python/scripts/watch_training_progress.py
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
git diff --check
```

Results:

- `test_training_watch.py`: 28 passed.
- `py_compile`: passed for `watch_training_progress.py`.
- `watch_training_progress.py --limit 5`: completed for run `20260702-091522`
  with `severity=alert`, `action=prepare_restart_with_more_exploration`, and
  `operator_action=wait_for_active_training_supervisor_to_finish_or_stop_before_restart`.
- `git diff --check`: passed.

## Guardrail

This is an operational observability fix only. It makes no predictive claim,
does not change any training objective, and does not lower the frozen-validation,
baseline/null-model, leakage, uncertainty, or failure-case requirements.
