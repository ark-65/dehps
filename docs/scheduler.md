# Scheduler

双色球通常每周二、四、日开奖。为了避免页面延迟，建议晚上 22:30 或更晚执行。

## Crontab

```cron
30 22 * * 2,4,0 cd /path/to/ark-dehps/apps/worker-python && /path/to/ark-dehps/apps/worker-python/.venv/bin/python scripts/daily_pipeline.py --strategy-key baseline_v1 --auto-git >> /path/to/ark-dehps/runtime/logs/daily_pipeline.log 2>&1
```

## systemd

Copy files from `infra/systemd/` to `/etc/systemd/system/`, update paths in the service, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dehps-daily-pipeline.timer
systemctl list-timers dehps-daily-pipeline.timer
```

## Logs

Crontab should append stdout and stderr to:

```text
runtime/logs/daily_pipeline.log
```

For systemd installs, inspect the timer and service with:

```bash
systemctl status dehps-daily-pipeline.timer
systemctl status dehps-daily-pipeline.service
journalctl -u dehps-daily-pipeline.service --since today
```

## Failure Recovery

If a scheduled run fails:

1. Inspect `pipeline_runs.error_message` and `pipeline_runs.summary`.
2. Inspect the linked `ssq_sync_runs` row when `sync_run_key` is present.
3. Check `runtime/logs/daily_pipeline.log` or the systemd journal.
4. Re-run with `--source zhcw --force` only after confirming the previous failure did not leave partial output that should be removed.
5. Keep verification reruns on a separate database until the recovery path is understood.
