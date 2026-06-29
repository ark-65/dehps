# Self-Iteration: Training Candidate Top-N Boundary

Date: 2026-06-30

## Primary Goal

Reject non-positive `top_n` values before generating walk-forward or current training next-candidate outputs.

## Non-Goals

- No scoring, strategy, advisor, or candidate-source changes.
- No change to DEHPS evidence level or prediction/betting language.
- No generated runtime artifacts under `data/output` or `runtime`.

## Change

- `run_walk_forward` now rejects `top_n < 1` before starting evaluation.
- `top_candidates_for_next` keeps the same boundary check for direct callers.
- `build_training_next_candidate_snapshot` rejects invalid `top_n` before loading training state, so a bad request cannot produce an empty candidate snapshot that looks successful.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_next_candidates.py
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_frequency_ranker.py
apps/worker-python/.venv/bin/python -m pytest -q
```

Result:

- 6 next-candidate tests passed.
- 20 frequency-ranker tests passed.
- 309 worker tests passed.

## Guardrail

This is an input-boundary hardening change. It does not improve or claim predictive ability; it only prevents invalid candidate-count requests from being reported as valid experimental output.
