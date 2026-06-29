# Self-Iteration: Training Watch Filename Length Boundary

Date: 2026-06-30

## Primary Goal

Keep training-watch report output reliable when a run id is unexpectedly long.

## Non-Goals

- No training, scoring, candidate-generation, advisor, or strategy changes.
- No change to DEHPS evidence level or prediction/betting language.
- No generated runtime artifacts under `data/output` or `runtime`.

## Change

- `safe_filename_component` now bounds sanitized filename components to 96 characters by default.
- Long filename components retain a readable prefix and append a short SHA-256 suffix so distinct long run ids remain distinguishable.
- Existing path separator and punctuation sanitization behavior is unchanged.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_watch.py -q
apps/worker-python/.venv/bin/python -m pytest -q
```

Result:

- 9 training-watch tests passed.
- 310 worker tests passed.

## Guardrail

This is an operational robustness change for report writing. It does not alter historical ranking behavior, candidate generation, strategy selection, or any claim about predictive ability.
