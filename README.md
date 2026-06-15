# ark-dehps

DEHPS means Discrete Event Human Plausibility Score, or 离散事件人类合理性评分.

This project is not a lottery prediction system. It studies large discrete combination spaces with transparent feature scoring, strategy filters, and historical backtests. The first MVP uses only the red balls from 双色球 as a demo domain.

## MVP Scope

- PostgreSQL for history, features, strategies, experiments, reports, sync runs, and pipeline runs.
- Redis reserved for future queues and agent orchestration.
- Python worker for combination generation, feature calculation, scoring, crawling, syncing, backtesting, and reports.
- NestJS API and web app directories are placeholders for later stages.

## Project Plan

Long-term work is tracked in `docs/roadmap.md`. Development should move by staged rounds, with each round ending in tests, a human-readable report, and a rollback-friendly commit.

## Quick Start

```bash
docker compose up -d
cd apps/worker-python
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
python scripts/generate_ssq_red_combinations.py --limit 10000
python scripts/sync_latest_ssq.py --source zhcw --history --dry-run
python scripts/sync_latest_ssq.py --source zhcw --history
python scripts/daily_pipeline.py --strategy-key baseline_v1 --source zhcw --force
```

PostgreSQL:

- Host: localhost
- Port: 54329
- Username: dehps
- Password: dehps_password
- Database: dehps

Redis:

- Host: localhost
- Port: 63799
