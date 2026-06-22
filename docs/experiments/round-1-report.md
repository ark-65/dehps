# Round 1 Report

## Done

- Verified PostgreSQL and Redis Docker services are healthy.
- Initialized an isolated verification database: `dehps_round1_verify`.
- Verified PostgreSQL schema creation from `infra/postgres/init/001_init.sql`.
- Verified Python worker editable install with the existing `.venv`.
- Generated 10,000双色球 red-ball combinations for the minimal smoke run.
- Imported 5 temporary sample history rows during Round 1 verification. The bundled sample CSV was retired in Round 2 because the database now contains real historical data.
- Ran `baseline_v1` backtest and generated Markdown experiment reports.
- Attempted and completed full red-ball combination generation: 1,107,568 rows.

## Tests

```text
14 passed in 7.29s
```

## Commands Run

```bash
docker compose up -d
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python -m pip install -e /home/ark/workspace/dehps/apps/worker-python
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python -m pytest
DB_NAME=dehps_round1_verify python scripts/generate_ssq_red_combinations.py --limit 10000
DB_NAME=dehps_round1_verify python scripts/import_history_csv.py --file <temporary-history-fixture.csv>
DB_NAME=dehps_round1_verify python scripts/run_backtest.py --strategy-key baseline_v1
DB_NAME=dehps_round1_verify python scripts/generate_ssq_red_combinations.py
DB_NAME=dehps_round1_verify python scripts/run_backtest.py --strategy-key baseline_v1
```

## Database

Verification database table counts after the full run:

```text
ssq_red_combinations: 1107568
ssq_history: 5
dehps_experiments: 2
dehps_experiment_reports: 2
```

The main `dehps` database was not reset or polluted by the sample CSV import.

## Baseline Result

Final experiment: `baseline_v1-20260615-161817`

```text
total_combinations: 1107568
kept_combinations: 1073093
keep_rate: 0.96887324
history_draws: 5
covered_draws: 5
coverage_rate: 1.0
lift: 1.03212676
```

Markdown report:

```text
retired local artifact: data/output/experiments/baseline_v1-20260615-161817.md
```

## Problems

- The project had already advanced beyond pure Round 1 before this formal acceptance pass, including real historical sync support. Round 1 was therefore closed as an acceptance/verification round rather than a fresh implementation round.
- The temporary sample issue IDs overlap real 2026 issue IDs in the main database. To avoid conflicts and preserve the checked main database, Round 1 sample import was run against `dehps_round1_verify`.
- Full combination generation completed successfully but took 38.4 seconds, which is acceptable for a bootstrap job and worth tracking if it grows more complex.

## Next Round

Round 2 should formalize daily data synchronization as a separate acceptance pass:

- Validate `sync_latest_ssq.py` against the current-date 10-year history behavior.
- Confirm `--dry-run`, source abstraction, conflict recording, and CSV fallback.
- Run `daily_pipeline.py` on a verification database.
- Produce a Round 2 report and merge via PR with squash.

## Risk Note

DEHPS is a discrete combination-space scoring and backtest platform. This report does not represent predictive ability and is not betting advice.
