# Self-Iteration Report: Training Watch Supervisor Progress

- Date: 2026-07-01
- Primary goal: expose the active supervisor status-file progress in the training watcher so an alert can distinguish completed-round stagnation from current supervisor activity.
- Non-goals: no new model, advisor, candidate source, scoring rule, promotion rule, search gate, weight boundary, history-window change, or betting recommendation.
- Initial status: working tree was clean before edits.

## Training Status

- Initial watch command: `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`
- Watched run: `20260701-040511`
- Initial watch result: `severity=alert`, `action=prepare_restart_with_more_exploration`, 118 stagnation rounds.
- Latest live verification after the change: same run reached 119 rounds and still reports `severity=alert`, `action=prepare_restart_with_more_exploration`.
- Heavy-job lock: active `training-supervisor`, PID `2916275`, status `running`.
- New watcher supervisor-progress snapshot: status `running`, PID `2916275`, progress round 119, target 100/100, issue `2026071`, elapsed seconds 53.3.

Legal and evaluation context:

- Legal red-ball sample space: `C(33, 6) = 1,107,568`.
- Latest supervisor ranked universe: 1,105,506 after 2,062 exclusions.
- History scope: `current_regime_default`; regime start date `2016-06-30`.
- Train window: 900 draws; eval window: 100 draws.
- Frozen validation in the latest supervisor report covers 20 issues, `2026055` through `2026074`.
- Baseline/null context: watcher and supervisor reports retain null calibration, frozen-validation gates, baseline overlap fields, and overfit guardrails. This round makes no predictive or betting claim.

## Gauss/Riemann Diagnostic

- Task Frame: the active run is not crashed, but watch reports high stagnation, frozen-primary blocking, eval-slice overfit guardrail activation, and rank-signature homogeneity. Progress means improving observability of the running supervisor state without changing search or promotion logic.
- Historical Boundary: Gauss and Riemann are used as historically inspired verification and structure lenses, not literal minds, authorities, or complete reconstructions.
- Gauss Pass: the object is the watcher state under the legal SSQ red-ball sample space and current 900/100 train/eval windows. The measurable residual is the gap between the latest completed DB round and the supervisor status file's current target progress. No eval-slice lift, frozen-validation result, or rank-vector movement is treated as proof of predictive ability.
- Riemann Pass: the operational state has two layers: completed-round DB history and current supervisor trajectory. The old watcher compressed the state to completed rounds plus heavy-job lock, leaving the in-progress target coordinate implicit in a separate JSON file.
- Cross-Review: Gauss rejects changing gates, weights, or promotion thresholds from this evidence. Riemann rejects leaving the current trajectory hidden when the alert asks an operator to reason about whether the supervisor is alive, blocked, or ready to restart.
- Synthesis: add a machine-readable `supervisor_status` field and a Markdown `Supervisor Progress` section to surface existing status-file progress.
- Next Verification: if stagnation persists, use the watcher to distinguish active progress from a stale supervisor before stopping or replacing the live process. Any strategy change still requires the same legal sample space, frozen validation, null/baseline controls, leakage checks, and failure-case reporting.

## Change

- `apps/worker-python/scripts/watch_training_progress.py`
  - Adds safe loading of `data/output/optimization/training-supervisor-<run_id>.json`.
  - Adds a sanitized `supervisor_status` payload with run status, PID, status path, updated timestamp, and current round/target progress.
  - Adds a judgement note and Markdown `Supervisor Progress` section when status-file progress is available.
- `apps/worker-python/tests/test_training_watch.py`
  - Covers status-file progress loading.
  - Covers recommendation and Markdown rendering of supervisor progress.

This is an observability change only. It does not alter training generation, advisor budgets, ranking, promotion gates, search-base gates, or scoring.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
```

Result: `19 passed`.

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Result: wrote a live watch report for run `20260701-040511`, round count `119`, `severity=alert`, `action=prepare_restart_with_more_exploration`. The report includes `Supervisor Progress` with status `running`, PID `2916275`, progress round 119, and target 100/100.

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

Result: `344 passed`.

```bash
git diff --check
```

Result: no output.

## Result

The watcher now reports the active supervisor's current status-file progress alongside completed-round stagnation, restart readiness, heavy-job lock, and gate diagnostics. This reduces manual status-file inspection during high-stagnation alerts while preserving frozen-validation, baseline/null, leakage, uncertainty, and failure-case guardrails.
