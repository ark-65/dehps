# DEHPS Python Worker

The worker generates 双色球 red-ball combinations, calculates structural features, imports/syncs history, runs baseline backtests, and writes Markdown reports.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
```

Generate audited next-issue red-ball candidates:

```bash
python scripts/generate_next_candidates.py --limit 5 --random-sets 200
```
