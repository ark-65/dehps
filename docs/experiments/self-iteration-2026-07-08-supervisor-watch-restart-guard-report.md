# Self-Iteration Report: Supervisor Watch Restart Guard

## Primary goal

Let the standard training-supervisor guard perform a narrow, watch-confirmed
fresh restart when rank-homogeneity monitoring has already reached the
operator-reviewed target-boundary state.

## Non-goals

- Do not change training, scoring, advisor, candidate-source, promotion, or
  search logic.
- Do not weaken frozen validation, leakage checks, or baseline/null-model
  reporting.
- Do not make any prediction, betting, or strategy-performance claim.
- Do not commit generated artifacts under `data/output` or runtime logs.

## Initial state

The required watch command completed successfully:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Observed state before the fix:

- run id: `20260707-213002`
- severity: `alert`
- action: `prepare_restart_with_more_exploration`
- failure modes: `promotion_gate:frozen_validation_not_better`,
  `eval_slice_overfit:eval_slice_overfit_no_frozen_primary_lift`, and
  `rank_homogeneity:stale_rank_signature_cycle`
- restart readiness: blocked by `active_training_supervisor_lock`
- blocker stage: `active_continuous_supervisor_target_complete`
- operator action:
  `operator_review_then_stop_continuous_training_supervisor_before_restart`
- active supervisor PID: `3016955`

The existing `scripts/ensure_training_supervisor.sh` only restarted when the
active process was stale relative to the latest known issue. It exited when the
current process was already training the latest issue, even if watch had already
recommended an operator-reviewed restart at a target boundary.

## Evidence context

- Evidence level: `operational_training_diagnostic_no_predictive_claim`.
- Legal sample space: `ssq_red_ball_combinations`.
- Legal universe: `1107568`; ranked universe: `1105506`; excluded
  combinations: `2062`.
- Historical window: `current_regime_default`, expanding train mode,
  train window `900`, eval window `100`, regime start `2016-07-07`, top-N
  `10000`.
- Operational baseline/null model: incumbent frozen-primary baseline plus
  ranked-uniform per-draw random null.
- Leakage/data checks reported by watch: frozen-primary gate active,
  eval-slice overfit guardrail active, parser/sync duplicate checks passed.
- Uncertainty: frozen validation can remain at baseline even when eval-slice
  metrics look strong.

## Diagnostic constraint

Historical Gauss/Riemann lenses were used as verification and structure
constraints, not as authority or literal reconstructions.

- Task Frame: the object is an operational restart transition under an active
  training watch alert. Progress means a safer supervisor lifecycle action, not
  a new model or strategy.
- Historical Boundary: Gauss and Riemann are historically inspired reasoning
  lenses only.
- Gauss Pass: the measurable facts are the active lock PID, watch action,
  target-boundary state, fresh supervisor progress, legal sample space,
  baseline/null model, and leakage status. The restart must not fire unless the
  lock PID and supervisor status PID refer to the same live process.
- Riemann Pass: the operational state space has a startup window where the
  heavy-job lock can point to a fresh PID before the default watch surface has
  DB rounds for that new run. That mixed state must be represented as
  not-ready, not as permission to restart again.
- Cross-Review: Gauss rejects a restart based on stale status arithmetic;
  Riemann rejects collapsing old-run status and new-lock ownership into one
  lifecycle state.
- Synthesis: automate only the existing target-boundary operator action, and
  require `lock pid == supervisor status pid == expected pid` plus matching
  watch/supervisor run id before stopping the process.
- Next Verification: targeted unit tests, shell syntax check, live guard check,
  and a fresh supervisor run with at least two persisted rounds.

## Change

- Added `training_watch_restart_guard.py`, a small testable helper that reads
  the compact watch JSON summary and returns success only when all restart
  criteria match.
- Updated `ensure_training_supervisor.sh` so a latest-issue supervisor no
  longer exits immediately. It first asks watch plus the guard whether a
  target-boundary restart is ready; otherwise it keeps the current process.
- Added `supervisor_run_id` and `supervisor_pid` to compact watch restart
  readiness so the guard can reject old-status/new-lock mixed startup windows.
- Added unit coverage for positive restart readiness, incomplete target
  boundary, mismatched lock PID, mismatched supervisor status PID, mismatched
  supervisor run id, stale progress, and missing restart candidate.

## Validation

Commands:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch_restart_guard.py apps/worker-python/tests/test_training_watch.py
bash -n scripts/ensure_training_supervisor.sh
apps/worker-python/.venv/bin/python -m py_compile apps/worker-python/scripts/training_watch_restart_guard.py apps/worker-python/scripts/watch_training_progress.py
```

Results:

- Targeted pytest: `45 passed`.
- Shell syntax check: passed.
- Python compile check: passed.
- Live guard before restart returned `watch_restart_ready_target_boundary` for
  PID `3016955`.
- `scripts/ensure_training_supervisor.sh` stopped PID `3016955` and started a
  fresh supervisor PID `3568217`, run id `20260708-080535`, as-of issue
  `2026077`.
- During fresh-start validation, the guard rejected the old-run/new-lock mixed
  window with `watch_restart_not_ready:supervisor_pid`.
- Fresh supervisor validation passed: run `20260708-080535` persisted rounds
  `1` and `2`, watch returned `severity=ok` and
  `action=continue_current_run`, and round `3` started without runtime errors.

## Guardrail

This is an operational lifecycle fix only. It does not alter model scoring,
candidate generation, advisors, dynamic weights, promotion gates, or betting
language. The observed historical response-surface behavior remains hypothesis
evidence only and does not support guaranteed hits, settled predictive
advantage, or low-risk betting advice.
