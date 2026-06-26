# Self-Iteration Report: Red Number Packed Input Guard

- Date: 2026-06-26
- Primary goal: prevent packed string or byte inputs from being accepted as six separate red-ball values.
- Non-goals: no scoring, candidate ranking, strategy, advisor, training, or prediction-language changes.

## Change

`normalize_red_numbers` now rejects whole-input `str`, `bytes`, and `bytearray` values before iterating. This preserves support for per-ball string values such as `"06"`, while preventing `"123456"` or packed bytes from being silently interpreted as `(1, 2, 3, 4, 5, 6)`.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_combination.py -q
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_candidate_generation.py apps/worker-python/tests/test_next_candidates.py -q
apps/worker-python/.venv/bin/python -m pytest -q
```

All validation passed.
