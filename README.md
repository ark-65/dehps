# ark-dehps

DEHPS means Discrete Event Human Plausibility Score, or 离散事件人类合理性评分.

DEHPS is being trained toward a prediction-oriented decision-support system. Betting-oriented recommendations are allowed as a future product direction and as clearly labeled experimental outputs, but the project has not yet reached its training target. It studies large discrete combination spaces with transparent feature scoring, strategy filters, historical backtests, training diagnostics, and operational reports. The current demo domain uses only the red balls from 双色球.

Core principle:

```text
AI proposes hypotheses. Code verifies them. Historical data judges them.
```

## MVP Scope

- PostgreSQL for history, features, strategies, experiments, reports, sync runs, pipeline runs, training rounds, and candidate snapshots.
- Redis reserved for future queues and agent orchestration.
- Python worker for combination generation, feature calculation, scoring, crawling, syncing, backtesting, training diagnostics, candidate generation, and reports.
- NestJS API for read-only research data, experiment details, training status, and dashboard-facing normalization.
- Angular dashboard for experiment review, comparison, distribution charts, report browsing, and live training/status views.

## Project Plan

Long-term work is tracked in `docs/roadmap.md`. Development should move by staged rounds, with each round ending in tests, a human-readable report, and a rollback-friendly commit.

For local setup and acceptance commands, see `docs/local-runbook.md`.

## Quick Start

```bash
docker compose up -d
cd apps/worker-python
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m pytest -q
python scripts/generate_ssq_red_combinations.py --reset
python scripts/sync_latest_ssq.py --source zhcw --history --dry-run
python scripts/daily_pipeline.py --strategy-key baseline_v1 --source zhcw --force --skip-weight-kdj-signals
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

Generated runtime state lives under `runtime/` and generated experiment outputs may appear under `data/output/`. Do not commit these directories unless a specific small evidence artifact is explicitly requested.
