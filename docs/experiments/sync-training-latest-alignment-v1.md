# Sync And Training Latest Alignment V1

## Primary Goal

Keep scheduled SSQ data sync and the long-running training supervisor aligned to the latest known issue before training continues.

## Non-Goals

- Do not change ranking, scoring, candidate generation, advisors, or prediction logic.
- Do not promote a new strategy or claim predictive improvement.
- Do not commit generated runtime output from `data/output` or `runtime`.

## Problem

The local database had stopped at issue `2026070` while the remote ZHCW source had issue `2026073`.

Two operational gaps caused the stale training window:

- The scheduled daily pipeline used `fetch_latest()` for ZHCW. If multiple draws were missed, it could insert only the latest draw and skip intermediate issues.
- `scripts/ensure_training_supervisor.sh` only checked whether a supervisor process existed. A live process pinned to an old `--as-of-issue` was treated as healthy and was not restarted.

There was also an API-shape issue in open-ended history sync: `--history --from-issue 2026070` without `--to-issue` returned zero rows from the ZHCW endpoint. The sync layer now resolves the remote latest issue first and uses it as the end issue.

## Change

- `sync_ssq(..., history=True, from_issue=..., to_issue=None)` now fetches the remote latest issue and uses it as the effective end issue.
- `daily_pipeline.py` now syncs ZHCW through history mode starting from the local max issue instead of only fetching the latest draw.
- `ensure_training_supervisor.sh` now:
  - runs an incremental ZHCW history sync first,
  - reads the latest local DB issue after sync,
  - extracts the live supervisor `--as-of-issue`,
  - stops and restarts the supervisor when the live issue is stale,
  - leaves an already-aligned supervisor running.

## Operational Recovery

Manual sync filled the missing issues:

```bash
cd /home/ark/workspace/dehps/apps/worker-python
.venv/bin/python scripts/sync_latest_ssq.py --source zhcw --history --from-issue 2026071 --to-issue 2026073
```

Result: `inserted_count=3`, latest issue `2026073`.

The updated watchdog then stopped stale supervisor pid `1334480` running `--as-of-issue 2026070` and started pid `1388459` with `--as-of-issue 2026073`.

Fresh supervisor run:

- Run id: `20260629-110939`
- Log: `runtime/logs/training-supervisor-kdj-ridge-neural-target-inversion-20260629-110939.log`
- Status: `data/output/optimization/training-supervisor-20260629-110939.json`

Round 1 reached `target=100/100 issue=2026073` and completed its decision loop with `no_improvement best_top10000=3`. Round 2 also reached `target=100/100 issue=2026073`, completed with `no_improvement best_top10000=3`, and round 3 started, confirming the new run continued after two latest-aligned decision loops.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_ssq_sync.py apps/worker-python/tests/test_daily_pipeline.py -q
```

Result: `12 passed`.

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

Result: `295 passed`.

```bash
cd apps/worker-python
.venv/bin/python scripts/sync_latest_ssq.py --source zhcw --history --from-issue 2026070 --dry-run
```

Result: `fetched_count=4`, latest issue `2026073`.

Updated watchdog no-new-data check:

- Synced from local issue `2026073`.
- Result: `fetched_count=1`, `skipped_count=1`, latest issue `2026073`.
- Existing supervisor pid `1388459` was kept because it already ran `--as-of-issue 2026073`.

## Positioning

This is an operational freshness fix. It makes scheduled sync and training supervision respect the current historical data boundary, but it does not change the DEHPS scoring hypothesis or establish a new performance claim.
