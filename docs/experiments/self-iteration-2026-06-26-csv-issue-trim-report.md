# Self-Iteration: CSV Issue Boundary Normalization

Date: 2026-06-26

## Primary Goal

Prevent CSV history rows with padded issue cells from being dropped by `start_issue` / `end_issue` filtering before draw validation runs.

## Non-Goals

- No scoring, training, advisor, or candidate-generation logic changes.
- No new prediction or betting claims.
- No generated `data/output` or `runtime` artifacts are promoted.

## Change

`CsvSsqDataSource.fetch_history()` now trims `start_issue`, `end_issue`, and each row's `issue` before applying range filters. The returned row keeps the canonical trimmed issue string so downstream validation and sync status use the same value.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_ssq_client.py
apps/worker-python/.venv/bin/python -m pytest -q
cd apps/api && npm test -- --runInBand
cd apps/web && npm test -- --watch=false
```
