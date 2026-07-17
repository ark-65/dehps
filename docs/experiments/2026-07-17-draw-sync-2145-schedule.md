# SSQ Draw Sync 21:45 Schedule

Date: 2026-07-17

## Primary goal

Move the formal SSQ post-draw update task to 21:45 Asia/Shanghai on Tuesday, Thursday, and Sunday: 30 minutes after the published 21:15 draw time.

## Operational rule

```text
official draw: Tue/Thu/Sun 21:15 Asia/Shanghai
formal update: Tue/Thu/Sun 21:45 Asia/Shanghai
source not updated: keep polling and recover when the result becomes available
```

The source result remains authoritative. The 21:45 task is the first formal post-draw update attempt, not an assertion that every source must already be current.

## Changed surfaces

- checked-in systemd timer: `Tue,Thu,Sun *-*-* 21:45:00 Asia/Shanghai`;
- documented crontab: `45 21 * * 2,4,0` with `CRON_TZ=Asia/Shanghai`;
- dashboard/API schedule metadata;
- current scheduler and dashboard documentation.

Historical experiment reports describing the earlier 23:59 schedule remain unchanged as historical evidence.

## Non-goals

- no change to the official 21:15 draw-time statement;
- no change to candidate generation, scoring, ranking, evaluation, or training;
- no change to the draw-sync watcher's hot-window or recovery behavior;
- no forced data synchronization during this configuration round.

## Validation

```text
systemd-analyze calendar 'Tue,Thu,Sun *-*-* 21:45:00 Asia/Shanghai'
Next elapse: Sun 2026-07-19 21:45:00 CST

API tests: 111 passed
```

The live user crontab is updated only after the repository change is merged, then read back to verify the installed schedule.
