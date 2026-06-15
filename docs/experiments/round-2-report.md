# Round 2 Report

## Done

- Retired the bundled sample history CSV now that the database contains real双色球 history.
- Removed stale sample-derived daily and experiment output files.
- Made CSV history input explicit via `--csv-file` or `SSQ_CSV_PATH`.
- Updated README quick start to use `zhcw --history`.
- Updated data-source documentation to describe real historical sync and explicit CSV import.
- Fixed `sync_ssq(..., history=True)` summary so `latest_draw` reports the max issue instead of the oldest paged row.
- Added tests for explicit CSV source behavior and latest issue reporting.

## Tests

```text
17 passed in 7.41s
```

## Commands Run

```bash
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python -m pytest
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python scripts/sync_latest_ssq.py --source zhcw --history --dry-run
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python scripts/sync_latest_ssq.py --source csv --history --dry-run
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python scripts/sync_latest_ssq.py --source zhcw --history
```

## Sync Verification

Real history dry-run:

```text
fetched_count: 1497
latest_issue: 2026067
latest_draw_date: 2026-06-14
status: dry_run
```

Real history idempotent sync against the main `dehps` database:

```text
fetched_count: 1497
inserted_count: 0
updated_count: 0
skipped_count: 1497
conflict_count: 0
status: success
```

Database check after sync:

```text
history_count: 1497
min_draw_date: 2016-06-16
max_draw_date: 2026-06-14
zhcw_count: 1497
```

CSV without an explicit file now fails intentionally:

```text
error: --source csv requires --csv-file or SSQ_CSV_PATH
```

## Problems

- `zhcw --history` returns pages in newest-to-oldest order. The sync summary previously used the last validated draw and therefore reported the oldest issue as `latest_draw`; this round fixed it by selecting the max issue.
- Empty directories such as `data/raw/` are not tracked by Git after removing the bundled sample CSV.

## Next Round

Round 2 can continue with the full daily pipeline acceptance:

- Run `daily_pipeline.py --source zhcw --force` on a verification database.
- Confirm `pipeline_runs`, `ssq_sync_runs`, generated daily report, and experiment report are coherent.
- Add failure-path tests for sync and pipeline status recording.
- Keep outputs separated from production data unless explicitly promoting a report.

## Risk Note

DEHPS remains a discrete combination-space scoring and backtest platform. This report does not represent predictive ability and is not betting advice.
