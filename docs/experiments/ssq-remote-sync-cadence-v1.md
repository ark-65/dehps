# SSQ remote sync cadence v1

Date: 2026-07-11

## Primary goal

Keep local training health checks at ten-minute cadence while reducing remote SSQ requests that cannot produce a new forward observation outside plausible publication windows.

## Evidence

- The watchdog log contained 1,442 historical `syncing ssq history` attempts.
- On 2026-07-11 it requested unchanged issue `2026078` every ten minutes throughout the afternoon.
- The [official China Welfare Lottery draw page](https://www.cwl.gov.cn/ygkj/wqkjgg/) states that SSQ draws occur Tuesday, Thursday, and Sunday at 21:15.
- The existing daily pipeline remains scheduled at 23:59 on draw days.

## Protocol

- The watchdog cron still runs every ten minutes.
- Local capacity, frozen-forward ledger, advisor freshness, lifecycle, and supervisor checks still run on every invocation.
- Remote sync remains due on draw days from 20:00 through 23:59 and on the following Monday/Wednesday/Friday from 00:00 through 01:59.
- Outside those windows, successful remote attempts are limited to once per 60 minutes.
- A missing prior attempt, failed/error latest status, stale running status beyond 30 minutes, or clock invariant failure makes remote sync immediately due. A recent running attempt is allowed a 30-minute competition guard.
- An hourly cold fallback protects against schedule changes and special draw arrangements.

The expected upper bound falls from 1,008 watchdog remote requests per week to approximately 258 while retaining ten-minute polling around official draws.

## Safety boundaries

- A skipped remote request writes an explicit zero-change synthetic sync record only for the current watchdog process; it does not insert a database sync run.
- Conflict storage is still checked from the database every invocation.
- Forward evaluation retry planning still runs even when remote sync is skipped.
- Advisor freshness and supervisor parking/restart logic still run every ten minutes.
- `selection_changed=false` and `promotion_allowed=false`.

## Validation

- Pure cadence and watchdog contract tests: 12 passed.
- Cold live plan at Saturday 18:22: `due=false`, reason `cold_poll_interval_not_elapsed`, next remote retry in about 58 minutes.
- Cold live watchdog: remote request skipped; forward evaluation batch accepted 0 due rows; supervisor remained parked for `2026079`.
- Full worker suite: 630 passed.
- Post-merge `main` commit `991d5c2` at Saturday 18:31: capacity healthy; cadence `due=false`, reason `cold_poll_interval_not_elapsed`; remote sync skipped, forward retry planner accepted 0 due rows, and the supervisor remained parked for `2026079`.

## Failure modes

- Official schedules can change; the cold hourly fallback bounds detection delay without relying solely on weekday rules.
- If the sync runner records failed/error, or remains running beyond 30 minutes, backoff is bypassed.
- If cadence planning cannot read its database state, the watchdog fails closed rather than silently skipping remote sync.
