# Self-Iteration: Red Number Integer Boundary

## Goal

Tighten the shared SSQ red-ball normalization boundary so non-integer values cannot be silently truncated into legal red-ball numbers.

## Non-Goals

- No scoring, optimization, training, strategy, or prediction behavior was changed.
- No generated runtime or data artifacts were added.
- No lottery-prediction claim was introduced.

## Change

- `normalize_red_numbers()` now rejects booleans, floats, and non-integer strings instead of applying broad `int()` coercion.
- Integer strings such as `"06"` remain accepted for compatibility with existing parser and CSV ingestion paths.
- Added focused domain tests for accepted integer strings and rejected non-integer values.

## Validation

Focused boundary and parser validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_combination.py apps/worker-python/tests/test_ssq_parser.py apps/worker-python/tests/test_red_ball_features.py apps/worker-python/tests/test_ssq_client.py
```

Result:

```text
24 passed in 1.36s
```

Full worker regression:

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

Result:

```text
230 passed in 67.19s (0:01:07)
```

## Evidence Level

Operational data-quality guardrail. This preserves the explicit legal sample space for SSQ red balls and does not alter DEHPS model hypotheses or training claims.
