# Self-Iteration Report: Training Watch Restart Diagnostics

- Date: 2026-07-01
- Primary goal: expose existing rank-homogeneity restart diagnostics in the training watcher so stagnation recovery can be audited without manually querying the DB.
- Non-goals: no new model, advisor, candidate source, scoring rule, promotion rule, search gate, weight boundary, history-window change, or betting recommendation.
- Initial status: working tree was clean before edits.

## Training Status

- Initial watch command: `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`
- Watched run: `20260701-040511`
- Initial watch result: `severity=warn`, `action=watch_stagnation_recovery`, 29 stagnation rounds.
- Supervisor process status: active under the heavy-job lock with PID `2916275`.
- Latest completed round inspected from DB: round 29.
- Current supervisor progress file showed round 30 in progress, so the process was not stuck.

Legal and evaluation context:

- Legal red-ball sample space: `C(33, 6) = 1,107,568`.
- Latest supervisor ranked universe: 1,105,506 after 2,062 exclusions.
- History scope: `current_regime_default`.
- Train window: 900 draws; eval window: 100 draws.
- Frozen validation window in the active report: 20 issues, `2026055` through `2026074`.
- Baseline/null context: watcher and supervisor reports retain frozen-validation gates, null calibration, and baseline overlap context; this round makes no predictive or betting claim.

## Gauss/Riemann Diagnostic

- Task Frame: the active run showed stagnation recovery, frozen-primary blocking, and rank-homogeneity pressure. Progress means improving auditability of an existing guardrail signal without changing candidate generation or promotion logic.
- Historical Boundary: Gauss and Riemann are used as historically inspired verification and structure lenses, not literal minds, authorities, or complete reconstructions.
- Gauss Pass: the object is the watcher summary of already-recorded DB diagnostics under the legal SSQ red-ball sample space and current 900/100 train/eval windows. The measurable residual is whether a restart candidate changes historical target rank vectors while still failing frozen-primary promotion. DB round 29 recorded `rank_vector_changed=True`, `changed_target_count=99`, and `max_abs_delta=904798`; the watcher did not surface these fields.
- Riemann Pass: the search-space obstruction is structural visibility. The supervisor already represents a restart point that moves away from the incumbent rank vector, but the watcher compressed the space to gate pass/fail labels. That made the local geometry of stagnation recovery harder to inspect.
- Cross-Review: Gauss rejects changing gates or claiming lift from this evidence. Riemann rejects treating a pass/fail gate summary as enough to understand whether the search is escaping a stale rank-signature region.
- Synthesis: the smallest safe fix is to expose existing restart champion and experimental navigation metadata in watch JSON/Markdown, preserving all frozen-validation and null/baseline controls.
- Next Verification: if stagnation persists, inspect whether future restart champions keep changing rank vectors and whether any candidate achieves frozen-primary lift before promotion.

## Change

- `apps/worker-python/scripts/watch_training_progress.py`
  - Added safe summary fields for `rank_homogeneity_restart_champion`.
  - Added safe summary fields for `experimental_navigation_candidate`.
  - Added Markdown gate lines and a judgement note showing restart rank-vector movement.
- `apps/worker-python/tests/test_training_watch.py`
  - Extended the gate snapshot test to cover restart champion and experimental navigation output.

This is an observability change only. It does not alter training behavior, candidate budgets, promotion gates, search-base gates, or scoring.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
```

Result: `14 passed`.

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Result: `severity=warn`, `action=watch_stagnation_recovery`; generated report included restart champion and experimental navigation lines.

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

Result: `339 passed`.

## Result

The watcher now reports whether the rank-homogeneity restart champion changed target rank vectors and how large the observed movement was. This makes the current stagnation recovery state auditable without weakening frozen-validation, leakage, baseline/null, or failure-case guardrails.
