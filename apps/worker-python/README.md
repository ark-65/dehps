# DEHPS Python Worker

The worker generates 双色球 red-ball combinations, calculates structural features, imports/syncs history, runs baseline backtests, and writes Markdown reports.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
```

Build the constant red-ball universe:

```bash
python scripts/generate_ssq_red_combinations.py --reset
```

Generate audited next-issue red-ball candidates:

```bash
python scripts/generate_next_candidates.py --limit 5 --random-sets 200
```

Run a walk-forward ranking optimization smoke test:

```bash
python scripts/run_walk_forward_optimization.py --train-window 100 --eval-window 5 --top-n 10000 --as-of-issue 2026067 --workers 22
```

The default worker count is 16, leaving spare CPU for the system on this workstation. Pass `--workers` to override it.

For reproducibility, pass `--as-of-issue` before the next draw is known. The same complete `ssq_red_combinations` universe, history snapshot, config, train window, eval window, and `top-n` produce the same run key and ranking output. `--workers` changes runtime only, not ranking identity.

The optimization script scans the complete `C(33,6)` red-ball universe from `ssq_red_combinations` and sorts by frozen score rules. Randomness is only used as an analytical baseline in reports; it is not used to generate top candidates.
