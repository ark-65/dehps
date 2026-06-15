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

