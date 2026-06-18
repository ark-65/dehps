# Weight KDJ + Neural Weight Advisor v0

## Summary

- Added a durable `training_weight_signals` table for one row per target issue and weight field.
- Added an offline generator for per-weight response probes and stock-style K/D/J signal calculation.
- Added a read-only API and dashboard charts for recent weight KDJ signals.
- Added supervisor advisor-only integration behind `--enable-weight-kdj-advisor`.

## Scientific Boundary

This is a historical response-surface experiment. It checks whether weight perturbations have stable, inspectable patterns over historical target issues. It does not claim that KDJ curves or neural advisors predict future lottery draws.

## Data Flow

1. `generate_weight_kdj_signals.py` selects recent target issues, defaulting to 1000.
2. For each issue and each `FrequencyRankerConfig` weight, it evaluates clamped perturbations around the base config.
3. The best objective response becomes `close_value`; issue and rolling bounds define RSV.
4. K/D/J and `recommended_offset` are written to `training_weight_signals` with idempotent upsert.
5. `/training-weight-signals?limit=1000` returns grouped series for the dashboard.
6. Supervisor can optionally consume these offsets as candidate proposals, still passing them through prefilter and frozen validation.

## Commands

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/generate_weight_kdj_signals.py \
  --issues 1000 \
  --train-window 900 \
  --top-n 10000 \
  --chunk-size 25
```

Small smoke run:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/generate_weight_kdj_signals.py \
  --issues 3 \
  --weights frequency_weight,omission_weight \
  --chunk-size 1 \
  --dry-run
```

Advisor-only supervisor mode:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_training_supervisor.py \
  --duration-hours 1 \
  --train-window 900 \
  --eval-window 100 \
  --top-n 10000 \
  --enable-weight-kdj-advisor
```

## Acceptance

- KDJ formula handles flat intervals with RSV 50.
- `training_weight_signals` uses `(signal_run_id, issue, weight_name)` for idempotent writes.
- API returns an empty list when the KDJ table does not exist yet.
- Dashboard shows KDJ charts only when signal rows exist.
- Supervisor default behavior is unchanged unless advisor mode is enabled.
