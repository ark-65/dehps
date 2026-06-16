# Round 10-14 Report: Sorted Re-Ingest, Constant Universe, Regime Window, First Weight Search

## Summary

- Rebuilt `ssq_red_combinations` as the complete constant red-ball universe: 1,107,568 rows.
- Re-ingested SSQ history from issue `2003001` through `2026067` after sorting validated draws by `issue ASC`.
- Added database audit tooling for history monotonicity, duplicate issues, latest issues, and complete universe checks.
- Added `current_regime_default` training scope: most recent 10 years ending at `as_of_issue` when no authoritative issue-level equipment-change schedule is available.
- Changed `frequency_v1` default weights to the best small-grid result: structural `0.40`, frequency `0.30`, omission `0.30`.

## Data Audit

```text
ssq_history total_draws: 3464
issue range: 2003001 to 2026067
draw date range: 2003-02-23 to 2026-06-14
duplicate issues: 0
id_issue_monotonic: true
ssq_red_combinations total_rows: 1107568
complete_universe: true
```

The first rows by `id ASC` and `issue ASC` both start at `2003001`, and the latest issue query returns `2026067` first. This confirms insert order is aligned with draw order while latest reads use `issue DESC`.

## Physical Regime Policy

Current public material supports the active SSQ equipment facts: Ryo-Catteau Myosotis draw machine and solid draw balls made from natural rubber and closed-cell foam, about 25g and 50mm. No authoritative issue-level material-change schedule is frozen in this repo, so model training defaults to the most recent 10 years. Full history remains available for audit only.

See `docs/sources/ssq-physical-regime.md`.

## Walk-Forward Results

Protocol:

```text
history_scope: current_regime_default
regime_start_date: 2016-06-14
as_of_issue: 2026067
train_window: 1000
eval_window: 100
top_n: 10000
workers: 16
universe_size: 1107568
```

First `frequency_v1` baseline:

```text
weights: structural=0.55, frequency=0.30, omission=0.15
top_100_hits: 0
top_1000_hits: 0
top_10000_hits: 0
```

Small grid best:

```text
weights: structural=0.40, frequency=0.30, omission=0.30
top_100_hits: 0
top_1000_hits: 0
top_10000_hits: 1
median_rank: 642637
best_rank: 6804
```

Random uniform analytical expectation for 100 evaluated draws at top 10000 is about `0.9029` hits. The tuned result is only a small first improvement and is not enough for promotion beyond the current default.

## Commands

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/generate_ssq_red_combinations.py --reset --batch-size 10000
apps/worker-python/.venv/bin/python apps/worker-python/scripts/sync_latest_ssq.py --source zhcw --history --from-issue 2003001 --to-issue 2026067 --dry-run
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/sync_latest_ssq.py --source zhcw --history --from-issue 2003001 --to-issue 2026067
apps/worker-python/.venv/bin/python apps/worker-python/scripts/audit_ssq_database.py
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_weight_grid_search.py --train-window 1000 --eval-window 100 --top-n 10000 --as-of-issue 2026067 --workers 16
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_walk_forward_optimization.py --train-window 1000 --eval-window 100 --top-n 10000 --as-of-issue 2026067 --workers 16
```

## Next Optimization

- Cache per-target structural/frequency/omission score components so wider grid search does not rescan the full universe for every weight set.
- Add pair/triplet frequency and decay-weighted recency features, then compare against the current default under the same frozen 100-draw protocol.
- Do not promote a configuration unless it beats random expectation, structural zero model, and the prior default on a larger frozen window.

DEHPS measures historical ranking behavior under frozen protocols. This report does not prove future predictive ability and is not betting advice.
