# KDJ Intelligence Five-Agent v1

## Summary

- Added a canonical KDJ signal lane: `weight-kdj-recent-1000-v1`.
- Added full and incremental KDJ generation modes with idempotent `training_weight_signals` upsert.
- Added explicit supervisor KDJ candidate budgeting instead of post-hoc append-and-trim.
- Added a CPU-only Ridge KDJ offset advisor as an advisor-only candidate source.
- Added frozen control experiments for KDJ/neural/config candidates.
- Added a read-only service status API and dashboard tab for API, Web, DB, sync, KDJ, and training health.

## Scientific Boundary

These changes improve historical response-surface search and observability. They do not claim lottery prediction ability. KDJ, Ridge, and neural outputs are treated as candidate-generating hypotheses that must be compared against same-universe, same-window controls.

## Key Interfaces

- `generate_weight_kdj_signals.py --mode full|incremental --signal-run-id weight-kdj-recent-1000-v1 --allow-partial`
- `daily_pipeline.py --skip-weight-kdj-signals`
- `run_training_supervisor.py --enable-weight-kdj-advisor --weight-kdj-budget-share ...`
- `run_control_experiments.py --candidate-source kdj|neural|config-json`
- `GET /training-weight-signals` prefers canonical KDJ rows, falling back to latest ad hoc rows.
- `GET /service-status` returns read-only operational health and heavy-task limits.

## Verification

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests
npm test   # apps/api
npm run build   # apps/api
npm test   # apps/web
npm run build   # apps/web
git diff --check
```

Results:

- Python: 119 passed.
- API tests: 17 passed.
- API build: passed.
- Web tests: 13 passed.
- Web build: passed.
- Diff check: passed.

Smoke run:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
apps/worker-python/.venv/bin/python apps/worker-python/scripts/generate_weight_kdj_signals.py \
  --mode full \
  --signal-run-id weight-kdj-smoke-20260618-five-agent \
  --issues 1 \
  --allow-partial \
  --weights frequency_weight,omission_weight \
  --chunk-size 1 \
  --train-window 900 \
  --top-n 10000
```

Smoke result: generated 2 signal rows for issue `2026068`; no canonical prune was triggered.

Runtime check:

- `GET /health`: ok.
- `GET /service-status`: overall ok after filtering recovered Web build errors.
- `GET /training-weight-signals?limit=3`: returned the ad hoc smoke rows because canonical rows have not been fully materialized yet.
- Web frontend at `http://127.0.0.1:4200/`: HTTP 200.

## Next Acceptance Step

Run the canonical full materialization as a deliberate long job only when resources are available:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
apps/worker-python/.venv/bin/python apps/worker-python/scripts/generate_weight_kdj_signals.py \
  --mode full \
  --signal-run-id weight-kdj-recent-1000-v1 \
  --issues 1000 \
  --allow-partial \
  --chunk-size 25 \
  --train-window 900 \
  --top-n 10000
```

Do not interpret the resulting curves as prediction. Use them to compare candidate-generation hypotheses against frozen controls.
