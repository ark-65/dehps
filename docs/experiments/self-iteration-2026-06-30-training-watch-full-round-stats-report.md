# Self-Iteration Report: Training Watch Full Round Stats

- Date: 2026-06-30
- Primary goal: prevent `watch_training_progress.py --limit 5` from reporting recent-window counts as full training-run counts.
- Non-goals: no model, advisor, candidate source, strategy, weight boundary, or supervisor restart change.
- Initial status: working tree was clean before edits.

## Training Status

- Latest watched run: `20260630-181946`
- Initial watch result: `severity=warn`, `action=watch_stagnation_recovery`
- Heavy-job lock: active training supervisor process
- Legal red-ball sample space: 1,107,568 combinations
- Latest supervisor ranked universe: 1,105,506, with 2,062 excluded combinations
- Historical windows in latest supervisor report: train window 900, eval window 100, frozen validation window 20 issues (`2026054` through `2026073`)
- Baseline/null context: latest supervisor report compares candidate hits with `null_baseline` and `default_baseline`; this round made no performance or betting claim.
- Leakage posture: monitor-only change; no parser, sync, candidate scoring, history window, threshold, or model training logic was changed.

## Gauss/Riemann Diagnostic

- Task Frame: the watch script returned `round_count=5` when called with `--limit 5`, while the live run had more completed rounds. Progress is a monitoring correctness issue, not evidence of predictive ability.
- Historical Boundary: Gauss and Riemann are used here as historically inspired verification and structure lenses, not literal minds or authority.
- Gauss Pass: the measurable residual was `round_count=5` versus the full run count. The proof obligation was to keep total rounds, last improved round, stagnation rounds, improvement count, and best objective independent of recent-window display limits.
- Riemann Pass: the state space had two mixed coordinates: full-run state and recent-window state. The repair separates them as `round_count` and `round_window_count`.
- Cross-Review: Gauss rejects any stagnation conclusion computed from a truncated sample; Riemann rejects a single `limit` coordinate representing both historical state and display window.
- Synthesis: the smallest safe fix is full-run statistics for operational judgment, plus explicit recent-window metadata for the limited query.
- Next Verification: continue watching `warn/watch_stagnation_recovery`; do not promote any signal without the existing null/baseline, leakage, uncertainty, and failure-mode controls.

## Change

`scripts/watch_training_progress.py` now loads a lightweight full-run stats view using only `round_index`, `improved`, and `objective_score`. The `--limit` argument still controls the recent rows used for latest metrics and advisor snapshot, but total rounds and stagnation fields come from the full run.

The watch payload and CLI print now include:

- `round_count`: full completed rounds for the run
- `round_window_count`: rows loaded by the recent-window limit

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
apps/worker-python/.venv/bin/python -m py_compile apps/worker-python/scripts/watch_training_progress.py
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
git diff --check
```

Observed watch validation after the change:

```json
{"run_id":"20260630-181946","round_count":26,"round_window_count":5,"severity":"warn","action":"watch_stagnation_recovery"}
```

## Result

The live warning remains a real training-watch warning, but the monitor no longer confuses the `--limit 5` recent window with total completed training rounds.
