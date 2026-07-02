# Self-Iteration 2026-07-02 Supervisor Round Summary Report

## Goal

- Primary goal: expose completed-round and stagnation summary in the compact `training-supervisor-*.json` status snapshot.
- Non-goals: no model, advisor, candidate source, search navigation, weight boundary, promotion gate, betting recommendation, or predictive claim change.

## Starting State

- Initial watch command: `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`.
- Initial live run: `20260702-060504`, status `running`, watch severity `warn`, action `watch_stagnation_recovery`.
- Completed rounds at watch time: 28, stagnation rounds: 28.
- Legal sample space: SSQ red-ball combinations, `C(33, 6) = 1,107,568`; ranked universe `1,105,506`, excluded `2,062`.
- Historical window: `current_regime_default`, regime start `2016-06-30`, expanding train window `900`, eval window `100`, top-n `10000`, as-of issue `2026074`.
- Null model: ranked-uniform per draw; expected eval hits were top-100 `0.009046`, top-1000 `0.090456`, top-10000 `0.904563`.
- Leakage and data checks in watch: parser/sync duplicate checks passed, latest sync succeeded, promotion gate blocked with `frozen_validation_not_better`, eval-slice overfit guardrail was active.

## Gauss/Riemann Diagnostic

- Task Frame: the object is supervisor observability during a stalled training run. Progress means a compact status JSON can show the same completed-round/stagnation state that the Markdown report and watch already expose.
- Historical Boundary: Gauss and Riemann are used as historically inspired verification and structure lenses, not literal minds or authority.
- Gauss Pass: the measurable residual was the mismatch between a compact JSON snapshot with no completed-round summary and the Markdown/watch surfaces that already showed stagnation. The safe computation is counting completed rounds, last improved round, stagnation rounds, and latest round metrics from existing in-memory `rounds`.
- Riemann Pass: the operational state lives across status JSON, Markdown report, DB-backed watch rows, and runtime lock state. The compact JSON was missing the completed-round coordinate, making the state space harder to inspect from one artifact.
- Cross-Review: Gauss rejects any weight, gate, or source change from this evidence; Riemann rejects leaving the compact artifact structurally incomplete when operators are asked to reason about active training state.
- Synthesis: add a small `round_summary` object to compact status JSON, while keeping full `rounds` and full `best` payloads out of the compact snapshot.
- Next Verification: keep monitoring the fresh supervisor; any later strategy change still needs legal sample space, historical window, frozen validation, baseline/null model, leakage checks, uncertainty, and failure cases.

## Change

- Added `compact_round_status_summary()` to `apps/worker-python/scripts/run_training_supervisor.py`.
- Added `round_summary` to compact supervisor JSON with `round_count`, `latest_round`, `last_improved_round`, `stagnation_rounds`, and latest-round core metrics.
- Added test coverage that verifies the summary is present while full `rounds` and `best` remain omitted.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_supervisor.py -k 'compact_status_payload or training_progress_payload'
```

Result: `3 passed, 110 deselected`.

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_supervisor.py apps/worker-python/tests/test_training_watch.py
```

Result: `138 passed`.

Fresh supervisor:

- Stopped old supervisor PID `4033458`.
- Started fresh supervisor PID `4096695`, run id `20260702-080514`, as-of issue `2026074`.
- Status JSON: `data/output/optimization/training-supervisor-20260702-080514.json`.
- Log: `runtime/logs/training-supervisor-kdj-ridge-neural-target-inversion-20260702-080513.log`.
- Monitored 2 completed rounds without runtime errors.
- New JSON `round_summary` after 2 rounds: `round_count=2`, `latest_round=2`, `stagnation_rounds=2`, `top_100/1000/10000=3/3/3`.
- Watch validation: `watch_training_progress.py --run-id 20260702-080514 --limit 5` returned severity `ok`, action `continue_current_run`.

## Evidence Boundary

This round is an operational observability fix only. The fresh supervisor still showed no new improvement in the first two rounds, and the observed historical lift remains hypothesis evidence only. No output here supports guaranteed hits, settled predictive advantage, or low-risk betting.
