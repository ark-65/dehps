# Self-Iteration: Heavy Job Interrupted Status

## Goal

Treat `interrupted` heavy-job metadata as a terminal, inactive state across both the Python runtime helper and the API `/service-status` view.

## Non-Goals

- No training, scoring, candidate-generation, advisor, or betting recommendation logic changed.
- No generated runtime output under `data/output` or `runtime` was committed.

## Change

- Added `interrupted` to the heavy-job inactive status set in `apps/worker-python/dehps/runtime/heavy_job.py`.
- Added the same inactive status to the API service-status heavy-job parser in `apps/api/src/research.service.ts`.
- Added regression coverage for live-PID metadata with `status: interrupted` so dashboards do not report a terminal lock as actively occupying heavy-job capacity.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q
cd apps/api && npm test
cd apps/api && npm run build
```

Results:

- Python tests: `269 passed`
- API tests: `43 passed`
- API build: passed

## Guardrail

This is an operational observability fix only. It does not alter historical backtests, sample-space assumptions, candidate ranking, strategy promotion, or any claim about predictive ability.
