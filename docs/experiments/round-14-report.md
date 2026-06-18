# Round 14 Report: DB-First Training Intelligence

## Summary

- Training rounds now use `training_round_results` as the durable per-round record.
- The supervisor writes compact live status by default and keeps full round payloads in Postgres via idempotent upsert.
- Candidate generation now splits each round budget across exploitation, exploration, historical replay/blend, and baseline/null configs.
- Stagnation automatically widens exploration and injects low-coverage weight fields.
- Prefiltering keeps a diversity quota so short-window prefilter misses do not fully starve unusual configs.
- Each full-refine round now keeps structural, frequency, omission, null, and current-best frozen baselines for control comparison.
- Best/top/control summaries carry a trailing frozen-validation window that is recorded but not used to change the scoring formula.
- A diagnostics script summarizes stagnation, best-config churn, phase improvement rate, weight coverage, tail target issues, and latest hit counts.

## Search Control

Default candidate budget shares:

```text
exploitation: 40%
exploration: 30%
replay:       20%
baseline:     10%
```

Historical DB rows seed replay and a deterministic lightweight surrogate once enough prior rounds exist. This is still a transparent optimizer, not a large-model training loop.

## Validation And Controls

- Frozen validation window: `max(1, min(20, eval_window // 5))` for multi-draw windows, trailing within the evaluated round payload and not part of the objective formula change.
- Control baselines: pure structural, pure frequency, pure omission, null, and current best frozen at round start.
- The controls are stored under `prefilter.control_experiments` and included in diagnostics.

## DB-First Behavior

- `training_round_results` is the source of truth for round list/detail APIs.
- `trainingStatus()` prefers DB rounds and uses logs only for live progress.
- Large JSON status files are no longer required for supervisor recovery/status; `--write-status-json` remains available for explicit compatibility snapshots.

## Diagnostics

Run:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/generate_training_diagnostics.py --run-id <run_id>
```

The report is written to `data/output/optimization/training-diagnostics-<run_id>.md`.

## Verification

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests
(cd apps/api && npm test)
(cd apps/web && npm test)
```

Results:

```text
apps/worker-python: 81 passed
apps/api: 10 passed
apps/web: 10 passed
```

Smoke run:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_training_supervisor.py --duration-hours 0.001 --train-window 900 --eval-window 2 --top-n 10000 --as-of-issue 2026067 --workers 2 --progress-interval 1 --max-configs-per-round 6 --memory-budget-gb 20 --event-url ''
apps/worker-python/.venv/bin/python apps/worker-python/scripts/generate_training_diagnostics.py --run-id 20260618-100334
```

Result:

```text
run_id: 20260618-100334
rounds: 1
db controls: 5
frozen_validation_window: 1
best_summary_has_frozen_validation: true
diagnostics: data/output/optimization/training-diagnostics-20260618-100334.md
```

## Guardrail

This round improves search memory, diagnostics, and experiment control. It does not convert historical backtests into prediction ability; any apparent lift must still survive frozen validation windows and baseline comparisons.
