# Round 13 Report: 24h Adaptive Training Supervisor And Draw Sync Schedule

## Summary

- Added `run_training_supervisor.py` for long-running adaptive training.
- The supervisor cycles through micro, small, medium, and large weight perturbation phases.
- Each round keeps the best config by Top 100, Top 1000, Top 10000, then median-rank priority.
- Status is written to ignored local files under `data/output/optimization`.
- Added Beijing-time draw sync schedule documentation for Tuesday, Thursday, and Sunday at 23:59.

## Supervisor Defaults

```text
duration_hours: 24
train_mode: expanding
train_window: 900
eval_window: 100
top_n: 10000
workers: 16
max_configs_per_round: 20
memory_budget_gb: 20
```

## Search Phases

```text
micro:  +/- 0.01
small:  +/- 0.03
medium: +/- 0.07
large:  +/- 0.15 plus broad historical baselines
```

The current best config becomes the center for the next round when it improves the frozen ranking objective.

## Verification

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests
```

Result:

```text
44 passed
```

Supervisor smoke:

```bash
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_training_supervisor.py --duration-hours 0.001 --train-window 900 --eval-window 1 --top-n 10000 --as-of-issue 2026067 --workers 16 --progress-interval 1 --max-configs-per-round 2 --memory-budget-gb 20
```

Result:

```text
elapsed=0:16.15
maxrss=460216KB
status_path: data/output/optimization/training-supervisor-*.json
report_path: data/output/optimization/training-supervisor-*.md
```

## Scheduled Draw Sync

The local crontab should contain:

```cron
CRON_TZ=Asia/Shanghai
59 23 * * 2,4,0 cd /home/ark/workspace/dehps/apps/worker-python && /usr/bin/flock -n /home/ark/workspace/dehps/runtime/logs/ssq_draw_sync.lock /home/ark/workspace/dehps/apps/worker-python/.venv/bin/python scripts/daily_pipeline.py --strategy-key baseline_v1 --source zhcw --force >> /home/ark/workspace/dehps/runtime/logs/ssq_draw_sync.log 2>&1
```

## Guardrail

The supervisor optimizes historical walk-forward ranking behavior. Any large jump toward 100/100 Top 10000 coverage must be treated first as a leakage/overfit signal until it survives a frozen future validation window.
