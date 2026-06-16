# DEHPS Algorithm Optimization Plan

## Objective

Rank all legal 双色球 red-ball combinations so historical walk-forward targets land as high as possible.

Primary target:

```text
Increase actual red-ball ranks toward Top 100.
```

Intermediate targets:

```text
1. Top 10000 coverage
2. Top 1000 coverage
3. Top 100 coverage
4. Median rank and rank distribution
```

## Invariant

Every legal six-red combination has the same mathematical probability before a draw. The optimization target is historical ranking behavior under a frozen protocol, not a proof of future predictive power.

## Protocol

For every target issue:

1. Use only draws before the target issue.
2. Train on a fixed rolling window, for example 100, 300, or 1000 prior draws.
3. Rank the same complete legal red-ball universe from `ssq_red_combinations`.
4. Record the true target red set rank.
5. Count hits in Top 100, Top 1000, and Top 10000.
6. Keep the model config frozen during evaluation.

## Reproducibility Rule

Full-combination rankings must be deterministic:

- The input history must be frozen by `as_of_issue`.
- The red-ball universe must be the complete constant `C(33,6)` table with 1,107,568 rows.
- The history snapshot is identified by `history_fingerprint`.
- The model config is identified by `config_hash`.
- The run key is derived from strategy, `as_of_issue`, train window, eval window, `top_n`, `history_fingerprint`, and `config_hash`.
- No current timestamp, local timezone, random seed, machine path, or process order may affect ranking.
- Worker count may change runtime, but it must not change the run key, Top-N combinations, or ordering.
- Default optimization runs use 16 workers on this workstation, leaving spare CPU for other tasks.

If two machines have the same history snapshot and config before the next draw is published, the generated Top-N combinations and ordering must match.

## Baselines

- `baseline_v1`: structural plausibility filter.
- `frequency_v1`: structural score + recent frequency + omission score.
- Analytical random uniform expectation with the same Top-N cutoff; this baseline is not used for candidate generation.

## Feature Families

Initial transparent features:

- structural score
- anomaly penalty
- sum value
- span value
- odd/even balance
- small/big balance
- zone distribution
- consecutive pairs
- recent red-number frequency
- red-number omission

Candidate later features:

- pair frequency
- triplet frequency
- decay-weighted recency
- issue-seasonality buckets
- rank aggregation across multiple windows

## Optimization Rounds

### Round 9: Walk-Forward Skeleton

- Implement `frequency_v1`.
- Implement exact target rank calculation.
- Generate Markdown/JSON reports.
- Run a smoke evaluation.

### Round 10: Fast Matrix And Grid Search

- Maintain `ssq_red_combinations` as the full constant sample-space table.
- Cache or load the full combination feature matrix from that table.
- Use at least 16 workers for full-universe ranking and weight sweeps on this workstation, while keeping manual override available.
- Run weight grid search over rolling windows.
- Report top-performing configs without using future target labels in each fold.

### Round 11: Dashboard Visualization

- Add ECharts.
- Show rank distribution, Top-N hit-rate curves, target-rank histogram, and config comparison.

### Round 12: Candidate Promotion Rule

- Define a rule for promoting a config only if it beats random/null baselines and prior configs on frozen windows.

## Failure Conditions

- Top-N improvement disappears under walk-forward evaluation.
- Best config is selected after seeing target outcomes without nested validation.
- Results depend on one or two lucky historical issues.
- Rank distribution remains close to random despite high narrative complexity.

## Current Round 9 Result

`frequency_v1` smoke test with `as_of_issue=2026067`, `train_window=100`, `eval_window=5`, and `top_n=10000`:

```text
top_100_hits: 0
top_1000_hits: 0
top_10000_hits: 0
```

This means the first transparent statistical ranker is not good enough. The next required work is performance optimization plus grid-search evaluation, not candidate promotion.
