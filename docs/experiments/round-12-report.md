# Round 12 Report: Progress Output And Feature-Matrix Cache

## Summary

- Added progress output to `run_walk_forward_optimization.py` and `run_weight_grid_search.py`.
- Reworked grid search so all configs share one static full-universe feature matrix.
- Added per-target dynamic component caching: frequency, omission, previous consecutive shape, overlap, parity shape, and zone shape are computed once per target issue and reused across configs.
- Preserved deterministic ranking: cached grid ranks are tested against individual per-config ranking.

## Cache Strategy

```text
static_rows: 1107568
config_count: 8
dynamic_components: computed once per target and shared across all configs
sample_space: ssq_red_combinations complete C(33,6)
```

The cache does not change scoring rules. It only avoids recalculating the same candidate feature components for each weight config.

## Verification

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests
```

Result:

```text
42 passed
```

Short grid smoke:

```bash
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_weight_grid_search.py --train-mode expanding --train-window 900 --eval-window 2 --top-n 10000 --as-of-issue 2026067 --workers 16 --progress-interval 1
```

Result:

```text
elapsed=0:16.56
maxrss=459412KB
progress lines: static feature matrix + 2/2 targets
```

Full 100-target cached grid:

```bash
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_weight_grid_search.py --train-mode expanding --train-window 900 --eval-window 100 --top-n 10000 --as-of-issue 2026067 --workers 16 --progress-interval 10
```

Result:

```text
elapsed=2:24.26
maxrss=459316KB
top config: structural=0.40, frequency=0.30, omission=0.25, previous_consecutive=0.05
top_100_hits: 0
top_1000_hits: 0
top_10000_hits: 3
```

Single-config walk-forward progress smoke:

```bash
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_walk_forward_optimization.py --train-mode expanding --train-window 900 --eval-window 2 --top-n 10000 --as-of-issue 2026067 --workers 16 --progress-interval 1
```

Result:

```text
elapsed=0:17.47
maxrss=495440KB
progress lines: 2/2 targets
```

## Notes

- The cached 100-target, 8-config expanding grid now completes in about 2 minutes 24 seconds on this machine.
- The previous uncached 8-config expanding grid took about 12 minutes 5 seconds, so this round gives roughly a 5x improvement for the current grid size.
- The next scaling step is a persistent matrix artifact or vectorized backend so 24-hour searches can sweep much larger config spaces.

This remains a historical ranking experiment, not proof of future predictive ability or betting advice.
