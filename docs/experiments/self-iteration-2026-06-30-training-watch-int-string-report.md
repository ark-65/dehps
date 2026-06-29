# Self-Iteration: Training Watch Integer String Boundary

- Date: 2026-06-30
- Primary goal: tighten training watch integer parsing so malformed string forms cannot be reported as valid metrics.
- Non-goals: no strategy, advisor, scoring, candidate generation, or prediction behavior changes.

## Change

`scripts/watch_training_progress.py` now accepts integer strings only when they are ASCII decimal digits after trimming whitespace. Ambiguous forms such as `+3`, `-1`, `1_000`, `0x10`, `1e3`, `3.0`, non-ASCII digits, and blank strings are rejected as `None`.

## Rationale

Training watch output is operational evidence. A malformed count or rank string should remain visibly absent instead of being normalized by Python's permissive integer parser. This preserves the project stance that historical training diagnostics are evidence to inspect, not predictive claims to polish.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_watch.py -q` passed, 10 tests.
- `apps/worker-python/.venv/bin/python -m pytest -q` passed, 311 tests.
