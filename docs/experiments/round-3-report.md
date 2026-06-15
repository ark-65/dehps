# Round 3 Report

## Done

- Fixed `git_commit_and_push.py` to resolve the repository root from the script location instead of relying on the caller's current working directory.
- Added a unit test confirming the git helper runs all git commands from the repository root.
- Added failure-path coverage for `daily_pipeline.py` so failed syncs mark `pipeline_runs` as failed with an error message.
- Added failure-path coverage for `sync_ssq(...)` so failed writes mark `ssq_sync_runs` as failed with an error message.
- Confirmed crontab documentation, systemd timer files, and `runtime/logs/` behavior.
- Added scheduler failure recovery guidance.
- Ran the full daily pipeline on an isolated verification database.

## Tests

```text
20 passed in 7.10s
```

## Commands Run

```bash
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python -m pytest
docker compose exec -T postgres psql -U dehps -d postgres -c "DROP DATABASE IF EXISTS dehps_round3_verify;" -c "CREATE DATABASE dehps_round3_verify;"
docker compose exec -T postgres psql -U dehps -d dehps_round3_verify < infra/postgres/init/001_init.sql
DB_NAME=dehps_round3_verify /home/ark/workspace/dehps/apps/worker-python/.venv/bin/python scripts/daily_pipeline.py --strategy-key baseline_v1 --source zhcw --force
docker compose exec -T postgres psql -U dehps -d dehps_round3_verify -P pager=off -c "SELECT run_key,status,sync_run_key,experiment_key,error_message FROM pipeline_runs ORDER BY started_at;" -c "SELECT run_key,source,status,fetched_count,inserted_count,updated_count,skipped_count,conflict_count,error_message FROM ssq_sync_runs ORDER BY started_at;" -c "SELECT count(*) AS history_count, min(draw_date) AS min_draw_date, max(draw_date) AS max_draw_date FROM ssq_history;" -c "SELECT experiment_key,total_combinations,kept_combinations,history_draws,covered_draws,coverage_rate,lift FROM dehps_experiments ORDER BY created_at;"
```

## Pipeline Verification

Verification database: `dehps_round3_verify`

Pipeline run:

```text
run_key: daily-20260615-171818
status: success
sync_run_key: daily-20260615-171818-sync
experiment_key: baseline_v1-daily-20260615-171818
error_message: null
```

Sync run:

```text
source: zhcw
status: success
fetched_count: 1
inserted_count: 1
updated_count: 0
skipped_count: 0
conflict_count: 0
error_message: null
```

History table:

```text
history_count: 1
min_draw_date: 2026-06-14
max_draw_date: 2026-06-14
```

Latest draw:

```text
issue: 2026067
draw_date: 2026-06-14
red_numbers: [4, 19, 27, 29, 30, 32]
blue_number: 13
```

Experiment metrics:

```text
total_combinations: 1107568
kept_combinations: 1073093
history_draws: 1
covered_draws: 1
coverage_rate: 1.00000000
lift: 1.03212676
```

Generated verification outputs:

```text
data/output/daily/2026-06-15-dehps-daily-report.md
data/output/experiments/baseline_v1-daily-20260615-171818.md
```

These outputs were generated from the isolated verification database and should not be treated as promoted production artifacts unless explicitly accepted.

## Problems

- The pipeline's `zhcw` daily mode fetches only the latest draw. This is correct for scheduled daily operation, but a fresh verification database therefore contains a single history row unless history sync is run separately.
- `git_commit_and_push.py` allowed paths intentionally cover generated data and experiment reports, not arbitrary documentation. Roadmap updates should remain explicit human-reviewed commits.
- The failure recovery path is now documented, but it has not been exercised against a real external outage.

## Next Round

Round 4 should start the AI Agent experiment system:

- Review the existing Strategy, Backtest, and Critic Agent documents.
- Define a small strategy suggestion schema.
- Keep AI output advisory until a backtest report verifies or rejects it.
- Add strategy versioning before any agent-suggested strategy becomes part of a scheduled pipeline.

## Risk Note

DEHPS remains a discrete combination-space scoring and backtest platform. This report does not represent predictive ability and is not betting advice.
