# Scheduler

双色球在[中国福彩网官方开奖页](https://www.cwl.gov.cn/ygkj/wqkjgg/)标注为每周二、四、日 21:15 开奖。为了避免页面延迟，项目固定在北京时间 23:59 执行正式同步。

## Crontab

```cron
CRON_TZ=Asia/Shanghai
59 23 * * 2,4,0 cd /path/to/ark-dehps/apps/worker-python && /usr/bin/flock -n /path/to/ark-dehps/runtime/logs/ssq_draw_sync.lock /path/to/ark-dehps/apps/worker-python/.venv/bin/python -m scripts.daily_pipeline --strategy-key baseline_v1 --source zhcw --force >> /path/to/ark-dehps/runtime/logs/ssq_draw_sync.log 2>&1
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
runtime/logs/ssq_draw_sync.log
```

The training supervisor watchdog separately compares the latest history issue, canonical KDJ signal issue, and the live supervisor `--as-of-issue`. If signals lag, it stops the old supervisor, refreshes `weight-kdj-recent-1000-v1` incrementally under the heavy-job lock, verifies issue alignment, and only then starts a fresh supervisor.

Before synchronization or any heavy work, the watchdog also runs the read-only runtime storage capacity gate. It warns below `max(5%, 20 GiB)` free and fails closed below `max(1%, 5 GiB)` free (or when capacity cannot be read). The gate never authorizes automatic deletion, compression, rotation, or rewriting of evidence.

The watchdog itself still runs every ten minutes, but remote requests use a separate cadence. Draw days from 20:00–23:59 and the following recovery mornings from 00:00–01:59 poll every ten minutes. Other successful cold periods poll at most hourly; failed/error syncs retry immediately. A recent running sync gets a 30-minute competition guard, then becomes retryable if still stale. Skipping a cold remote request does not skip local capacity, forward-ledger, advisor, lifecycle, or supervisor checks.

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
