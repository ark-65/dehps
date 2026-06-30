# Self-Iteration: Neural KDJ Signal Query Bounds

Date: 2026-06-30

## Primary Goal

Reject non-positive Neural KDJ advisor signal query bounds before loading database rows.

## Non-Goals

- No scoring, strategy, advisor model, or candidate promotion changes.
- No change to DEHPS evidence level or prediction/betting language.
- No generated runtime artifacts under `data/output` or `runtime`.

## Change

- `load_signal_rows` now rejects `limit < 1`.
- Optional `train_window` and `top_n` filters now reject values below 1 before issuing a database query.
- The failure is explicit, so invalid operator input cannot silently produce an empty advisor payload that looks successful.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_neural_kdj_advisor.py
apps/worker-python/.venv/bin/python -m pytest -q
```

Result:

- 8 Neural KDJ advisor tests passed.
- 322 worker tests passed.

## Guardrail

This is an operational input-boundary hardening change. It does not alter historical ranking behavior, candidate scoring, strategy selection, or any claim about predictive ability.
