# Round 9 Report

## Done

- Started the algorithm optimization phase.
- Defined the objective as exact historical target ranking under walk-forward evaluation.
- Added `frequency_v1`, a transparent trainable ranker using:
  - structural score
  - recent red-number frequency
  - red-number omission
- Added exact target-rank calculation across the legal red-ball universe.
- Added next-candidate preview from the trained ranker.
- Added Markdown and JSON walk-forward optimization artifacts.
- Added tests for frequency stats, configurable scoring, target rank calculation, and walk-forward summaries.
- Added an algorithm optimization plan.
- Optimized the first implementation by caching full-universe structural scores in memory.
- Added deterministic run keys based on `as_of_issue`, history fingerprint, config hash, train window, eval window, and `top_n`.
- Added multi-process full-universe ranking with `--workers`; default worker count is 16 on this workstation, and worker count is runtime metadata that does not affect deterministic run keys.

## Einstein Pass

Core question: can historical rolling-window statistics move true red-ball draws into Top 10000, then Top 1000, then Top 100 under a no-leakage walk-forward protocol?

Invariant: every legal red-ball combination has the same mathematical probability before a draw; historical ranking improvement must be treated as an empirical artifact to test, not as proof of prediction.

Hypothesis: a transparent rolling-window ranker can improve target rank distribution versus broad random ordering.

Measurement: exact target rank, Top 100/1000/10000 hit counts, hit-rate curves, rank histograms, and comparison against null/random baselines.

Failure mode: post-hoc weight tuning, using target issue data during training, or celebrating a config before it survives walk-forward and null-model checks.

Next experiment: build cached feature matrices and grid-search weights over train windows of 100, 300, and 1000 draws.

## Tests

Worker:

```text
36 passed in 7.61s
```

## Commands Run

```bash
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python -m pytest
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' /home/ark/workspace/dehps/apps/worker-python/.venv/bin/python scripts/run_walk_forward_optimization.py --train-window 100 --eval-window 5 --top-n 10000 --as-of-issue 2026067 --workers 22
```

The first uncached `eval_window=20` attempt was stopped because it repeatedly recomputed full-combination structural features and exceeded the practical interactive runtime. The cached version completed the 5-draw smoke run.

## Smoke Result

Artifact key:

```text
walk-forward-frequency_v1-asof-2026067-23560c21920b
```

Local report:

```text
data/output/optimization/walk-forward-frequency_v1-asof-2026067-23560c21920b.md
```

Local JSON:

```text
data/output/optimization/walk-forward-frequency_v1-asof-2026067-23560c21920b.json
```

Optimization output files are local training-analysis artifacts and are ignored by Git.

Runtime:

```text
elapsed: 0:09.81
maxrss: 356668KB
```

Metrics:

```text
evaluated_draws: 5
top_100_hits: 0
top_1000_hits: 0
top_10000_hits: 0
```

Target ranks:

```text
2026063: 613169
2026064: 691487
2026065: 734102
2026066: 862230
2026067: 1017135
```

## Interpretation

`frequency_v1` is not acceptable as a promoted model. The last five historical targets landed far outside Top 10000.

This is still a useful result because the evaluation protocol now exposes failure directly instead of hiding it behind candidate narratives.

## Acceptance Evidence

Model and optimization code:

```text
apps/worker-python/dehps/models/frequency_ranker.py
apps/worker-python/dehps/optimization/walk_forward.py
apps/worker-python/scripts/run_walk_forward_optimization.py
```

Tests:

```text
apps/worker-python/tests/test_frequency_ranker.py
```

Plan:

```text
docs/optimization/algorithm-plan.md
```

## Next Round

Round 10 should make the optimization loop fast enough for real sweeps:

- Cache or materialize the full feature matrix.
- Add grid-search over weights and windows.
- Compare against random same-size baselines.
- Produce rank-distribution artifacts for ECharts.

## Risk Note

This work optimizes historical ranking behavior under a frozen protocol. It does not guarantee future hits and is not betting advice.
