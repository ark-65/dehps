# Self-Iteration Report: Training Watch Restart Readiness

- Date: 2026-07-01
- Primary goal: make the training-watch restart alert machine-readable about whether a fresh supervisor can be started safely.
- Non-goals: no new model, advisor, candidate source, scoring rule, promotion gate, search-base gate, history-window change, weight-bound change, or betting recommendation.
- Initial status: working tree was clean before edits.

## Training Status

- Initial watch command: `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`
- Watched run: `20260701-040511`
- Initial watch result: `severity=alert`, `action=prepare_restart_with_more_exploration`, 59 stagnation rounds.
- Latest live verification after the change: same run reached 60 rounds and still reports `severity=alert`, `action=prepare_restart_with_more_exploration`.
- Heavy-job lock: active `training-supervisor`, PID `2916275`, status `running`.

Legal and evaluation context:

- Legal red-ball sample space: `C(33, 6) = 1,107,568`.
- Latest supervisor ranked universe: 1,105,506 after 2,062 exclusions.
- History scope: `current_regime_default`; regime start date `2016-06-30`.
- Train window: 900 draws; eval window: 100 draws.
- Frozen validation in the latest supervisor report covers 20 issues, `2026055` through `2026074`.
- Baseline/null context: watch and supervisor reports retain null calibration, frozen-validation gates, baseline overlap fields, and overfit guardrails. This round makes no predictive or betting claim.

## Gauss/Riemann Diagnostic

- Task Frame: the active run is not crashed, but shows high stagnation, frozen-primary blocking, eval-slice overfit guardrail activation, and rank-signature homogeneity. Progress means preventing the operational alert from being read as permission to start a second supervisor while the current heavy-job lock is active.
- Historical Boundary: Gauss and Riemann are used as historically inspired verification and structure lenses, not literal minds, authorities, or complete reconstructions.
- Gauss Pass: the object is the restart decision state, not a prediction signal. The invariant is that one heavy-job lock may own the supervisor at a time. A restart recommendation is only operationally launch-ready if no active heavy-job lock blocks a fresh run. No lift or future-hit claim is inferred from the 3/3/3 eval-slice score.
- Riemann Pass: the failure mode is a state-space transition ambiguity: `prepare_restart_with_more_exploration` describes a desired transition from current run to fresh run, but the old payload did not expose whether that transition edge was currently blocked by the runtime lock.
- Cross-Review: Gauss rejects weakening frozen-validation or search-base gates from this evidence. Riemann rejects leaving an implicit transition state in prose-only judgement when automation may consume the JSON payload.
- Synthesis: add a `restart_readiness` field and matching Markdown section so restart alerts distinguish requested preparation from safe launch readiness.
- Next Verification: if stagnation persists, use the readiness status before stopping or replacing the live supervisor; any strategy or gate change still requires the same legal sample space, frozen validation, null/baseline controls, leakage checks, and failure-case reporting.

## Change

- `apps/worker-python/scripts/watch_training_progress.py`
  - Adds `restart_readiness_summary()` with `requested`, `ready`, `status`, `blockers`, and current lock metadata.
  - Adds a judgement note when restart preparation is requested but a heavy-job lock is still active.
  - Renders a `Restart Readiness` section in Markdown reports when restart preparation is requested.
- `apps/worker-python/tests/test_training_watch.py`
  - Covers active-lock restart blocking and Markdown readiness rendering.

This is an observability and operational-safety change. It does not modify training generation, advisor budgets, ranking, promotion, frozen-validation, or search navigation.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
```

Result: `16 passed`.

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Result: wrote a live watch report for run `20260701-040511`, round count `60`, `severity=alert`, `action=prepare_restart_with_more_exploration`. The Markdown report includes `Restart Readiness` with `Ready for fresh supervisor: False`, blocker `active_training_supervisor_lock`, and lock PID `2916275`.

```bash
git diff --check
```

Result: no output.

## Result

The watch alert is now explicit that the current high-stagnation run should be prepared for restart but is not launch-ready while the active training supervisor lock is still held. This reduces accidental concurrent-supervisor risk without making any prediction or performance claim.
