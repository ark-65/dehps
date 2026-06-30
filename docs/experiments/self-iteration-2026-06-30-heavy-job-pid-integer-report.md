# Self-Iteration 2026-06-30 Heavy-Job PID Integer Report

## Primary Goal

Harden heavy-job lock observability so malformed fractional PID metadata is reported as unknown instead of being truncated or probed as a different process.

## Non-Goals

- Do not change training, optimization, candidate generation, scoring, or advisor strategy logic.
- Do not alter DEHPS predictive claims or betting-oriented language.
- Do not write or commit runtime output under `data/output` or `runtime`.

## Change

- `apps/worker-python/dehps/runtime/heavy_job.py` now parses owner metadata PIDs as strict integers before process probing. Fractional values, booleans, and malformed strings return `pid_unknown`.
- `apps/api/src/research.service.ts` now applies integer-only PID parsing for `/service-status` heavy-job metadata.
- Added Python and API regression tests with fractional current-process PID values, covering the case that could previously be truncated into a live PID.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_heavy_job.py -q
# 11 passed

cd apps/api && npm test -- test/research.service.test.ts
# 51 passed

apps/worker-python/.venv/bin/python -m pytest -q
# 323 passed
```

## Scientific Boundary

This is an operational observability hardening change only. It does not alter historical backtests, legal sample-space assumptions, candidate ranking, strategy promotion, or any claim of predictive ability.
