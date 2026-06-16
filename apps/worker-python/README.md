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
python scripts/run_walk_forward_optimization.py --train-mode expanding --train-window 900 --eval-window 100 --top-n 10000 --as-of-issue 2026067 --workers 16
```

The default worker count is 16, leaving spare CPU for the system on this workstation. Pass `--workers` to override it.

For reproducibility, pass `--as-of-issue` before the next draw is known. The same complete `ssq_red_combinations` universe, history snapshot, config, train mode, train window, eval window, and `top-n` produce the same run key and ranking output. `--workers` changes runtime only, not ranking identity.

The default optimization protocol is expanding walk-forward: for the last 100 target issues, each target trains on every prior draw available after the minimum `--train-window` is met.

The optimization script scans the complete `C(33,6)` red-ball universe from `ssq_red_combinations` and sorts by frozen score rules. Randomness is only used as an analytical baseline in reports; it is not used to generate top candidates.

For long grid searches, progress is printed to stderr. The grid-search runner builds the static feature matrix once, then shares each target issue's dynamic feature components across all configs:

```bash
python scripts/run_weight_grid_search.py --train-mode expanding --train-window 900 --eval-window 100 --top-n 10000 --as-of-issue 2026067 --workers 16 --progress-interval 10
```

Run the adaptive training supervisor:

```bash
python scripts/run_training_supervisor.py --duration-hours 24 --train-mode expanding --train-window 900 --eval-window 100 --top-n 10000 --as-of-issue 2026067 --workers 16 --progress-interval 10 --max-configs-per-round 20 --memory-budget-gb 20
```
