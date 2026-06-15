# ark-dehps

DEHPS means Discrete Event Human Plausibility Score, or 离散事件人类合理性评分.

This project is not a lottery prediction system. It studies large discrete combination spaces with transparent feature scoring, strategy filters, and historical backtests. The first MVP uses only the red balls from 双色球 as a demo domain.

## MVP Scope

- PostgreSQL for history, features, strategies, experiments, reports, sync runs, and pipeline runs.
- Redis reserved for future queues and agent orchestration.
- Python worker for combination generation, feature calculation, scoring, crawling, syncing, backtesting, and reports.
- NestJS API and web app directories are placeholders for later stages.

## Quick Start

```bash
docker compose up -d
cd apps/worker-python
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
python scripts/generate_ssq_red_combinations.py --limit 10000
python scripts/import_history_csv.py --file ../../data/raw/ssq_history_sample.csv
python scripts/sync_latest_ssq.py --source csv --dry-run
python scripts/daily_pipeline.py --strategy-key baseline_v1 --source csv --force
```

Adminer: http://localhost:18080

- System: PostgreSQL
- Server: postgres
- Username: dehps
- Password: dehps_password
- Database: dehps

