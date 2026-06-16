# Round 11 Report: Expanding Walk-Forward And Previous-Draw Micro Weights

## Summary

- Corrected the optimization protocol to support `train_mode=expanding`.
- The default minimum acceptance run is now 100 expanding regressions, matching `1-900 -> 901`, `1-901 -> 902`, through the final target.
- Added previous-draw context micro features:
  - consecutive-shape signal
  - overlap with the previous red set
  - parity-shape similarity
  - zone-shape similarity
- Ran an expanding 100-target grid search and promoted the best current config.

## Frozen Run

```text
history_scope: current_regime_default
regime_start_date: 2016-06-14
as_of_issue: 2026067
train_mode: expanding
train_window: 900
eval_window: 100
top_n: 10000
workers: 16
universe_size: 1107568
```

## Results

Previous default:

```text
structural_weight: 0.40
frequency_weight: 0.30
omission_weight: 0.30
previous_consecutive_weight: 0.00
top_100_hits: 0
top_1000_hits: 0
top_10000_hits: 1
```

Promoted config:

```text
structural_weight: 0.40
frequency_weight: 0.30
omission_weight: 0.25
previous_consecutive_weight: 0.05
previous_overlap_weight: 0.00
previous_parity_shape_weight: 0.00
previous_zone_shape_weight: 0.00
top_100_hits: 0
top_1000_hits: 0
top_10000_hits: 3
median_rank: 620321.5
best_rank: 4845
worst_rank: 1097522
```

The best micro-weight result improves top 10000 hits from 1 to 3 under the corrected expanding protocol, so the previous consecutive-shape weight is retained as the current default. This is still weak evidence and must be stress-tested on broader windows before any stronger promotion.

## Commands

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_walk_forward_optimization.py --train-mode expanding --train-window 900 --eval-window 100 --top-n 10000 --as-of-issue 2026067 --workers 16
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_weight_grid_search.py --train-mode expanding --train-window 900 --eval-window 100 --top-n 10000 --as-of-issue 2026067 --workers 16
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_walk_forward_optimization.py --train-mode expanding --train-window 900 --eval-window 100 --top-n 10000 --as-of-issue 2026067 --workers 16
```

## Next

- Add progress output to grid search so long 24-hour runs are observable.
- Cache per-candidate feature components and per-target train stats before broadening the grid.
- Add date-aware features only after history records carry draw dates through the optimization pipeline; latitude/longitude should be treated as constant unless sourced evidence shows a real draw-location change.

This remains a historical ranking experiment, not betting advice or proof of future predictive ability.
