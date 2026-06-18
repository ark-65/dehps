# KDJ/Ridge/Neural Advisor Delivery v1

Date: 2026-06-18

## Summary

This delivery moves weight KDJ from smoke/demo data into the canonical training data rail and wires KDJ, Ridge, and a small NumPy MLP as advisor-only candidate sources. None of these advisors promote a config directly; promotion still requires the normal supervisor evaluation and control experiments.

## Canonical KDJ Materialization

- Run id: `weight-kdj-recent-1000-v1`
- Mode: full
- Issues: 1000
- Signals: 30000
- Distinct weights: 30
- Issue range: `2019107` to `2026068`
- Weight coverage: every configured weight has 1000 rows
- Latest draw date: `2026-06-16`

Command used:

```bash
env PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  apps/worker-python/.venv/bin/python apps/worker-python/scripts/generate_weight_kdj_signals.py \
  --mode full \
  --signal-run-id weight-kdj-recent-1000-v1 \
  --issues 1000 \
  --allow-partial \
  --chunk-size 5 \
  --train-window 900 \
  --top-n 10000 \
  --heavy-job-lock-timeout-seconds 0 \
  --cpu-threads 1
```

The API default `/training-weight-signals?limit=3` now resolves to the canonical run and returns the latest points ending at `2026068`.

## Advisor Integration

Supervisor smoke run:

- Run id: `20260618-162859`
- Status: completed
- Rounds: 1
- Candidate budget: exploitation 3, exploration 2, replay 2, baseline 1, weight KDJ 2, Ridge KDJ 1, Neural KDJ 1
- Weight KDJ candidates: 2
- Ridge KDJ candidates: 1
- Neural KDJ candidates: 1
- Latest signal issue for all advisors: `2026068`

The supervisor now supports:

- `--enable-weight-kdj-advisor`
- `--enable-ridge-kdj-advisor`
- `--enable-neural-kdj-advisor`
- `--weight-kdj-budget-share`
- `--ridge-kdj-budget-share`
- `--neural-kdj-budget-share`

All advisor output is recorded under `prefilter.*_kdj_advisor` with signal counts, fields, selected/rejected counts, validation metrics where applicable, and candidate config hashes.

## Neural Control Gate

Generated candidate:

- JSON: `data/output/optimization/neural-kdj-advisor-20260618-082929.json`
- Advisor source: `neural_kdj_advisor_v0`
- Advice count: 9
- Candidate count: 1

Control experiment:

- JSON: `data/output/optimization/control-experiments-20260618-162957.json`
- Report: `data/output/optimization/control-experiments-20260618-162957.md`
- Verdict: failed promotion gate
- Candidate objective: `-16.872638`
- Candidate tail risk penalty: `16.568616`
- Objective failures: `omission_baseline`, `null_baseline`
- Tail risk: passed versus current best frozen baseline

Interpretation: the MLP produced a loadable advisor candidate, but controls rejected promotion. This is expected behavior for v0: neural suggestions are hypotheses, not a decision rule.

## Resource Guard

Heavy jobs now share `runtime/logs/dehps-heavy-job.lock` and default CPU thread limits for BLAS/OMP/MKL/NumExpr. The lock writes owner metadata and auto-refreshes heartbeat while held. `/service-status` exposes `heavyTaskLimits.heavyJobLock`.

Runtime check after delivery:

- API: ok, PID `3529949`
- Web: ok, port `4200`
- DB latest issue: `2026068`
- KDJ service: ok, canonical latest signal run `weight-kdj-recent-1000-v1`
- Heavy-job lock: inactive, `metadata_missing`

## Verification

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests
npm test && npm run build  # apps/api
npm test && npm run build  # apps/web
git diff --check
curl -fsS http://127.0.0.1:3000/health
curl -fsS 'http://127.0.0.1:3000/training-weight-signals?limit=3'
curl -fsS http://127.0.0.1:3000/service-status
```

Results:

- Python: 135 passed
- API: 17 passed, build passed
- Web: 14 passed, build passed
- Runtime health: ok
- Service status: ok

## Scientific Boundary

KDJ, Ridge, and Neural outputs are historical response-surface hypotheses. They do not establish predictive ability and do not bypass same-window, same-universe, same-`top_n` controls.
