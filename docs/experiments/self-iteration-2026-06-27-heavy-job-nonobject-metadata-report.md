# Self-Iteration: Heavy-Job Non-Object Metadata Guard

## Primary Goal

Make heavy-job lock status readers treat syntactically valid but non-object JSON metadata as unreadable metadata instead of crashing or surfacing an ambiguous runtime error.

## Non-Goals

- Do not change training, optimization, candidate generation, ranking, or betting-oriented language.
- Do not add or promote any algorithm, model, advisor, or strategy.
- Do not write generated runtime artifacts under `data/output` or `runtime`.

## Change

- `apps/worker-python/dehps/runtime/heavy_job.py` now rejects heavy-job metadata JSON whose root is not an object.
- `apps/api/src/research.service.ts` applies the same guard for `/service-status` heavy-job metadata.
- Added regression tests for Python owner-status inspection and API service-status reporting.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_heavy_job.py -q
```

Result: `10 passed`.

```bash
cd apps/api && npm test -- test/research.service.test.ts
```

Result: `47 passed`.

## Positioning

This is an operational observability hardening change only. It does not alter DEHPS historical scoring, sample-space assumptions, candidate ranking, strategy promotion, or any claim of predictive ability.
