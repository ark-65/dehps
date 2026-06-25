# Source Frontier Training Optimization V1

## Summary

This round implements the shared Gauss/Riemann conclusion for the stalled supervisor:

- Gauss side: do not trust a candidate source unless it survives explicit frozen validation, baseline comparison, and logged failure boundaries.
- Riemann side: treat advisor sources as different regions of the search space, and record whether any non-normal source forms a real frontier instead of letting the normal source dominate silently.

The change adds source-frontier diagnostics and a conservative source-frontier champion. It does not add a new scoring algorithm, model, lottery signal, or best-promotion shortcut.

## Behavior

Each evaluated round now records, per candidate source:

- generated configs;
- configs that reached full evaluation;
- configs that reached the full-eval top 5;
- whether the source supplied the round best;
- the best full-eval rank for that source;
- the source best's normal Top10000 and frozen Top10000 evidence.

When the supervisor has stalled for at least `SOURCE_FRONTIER_STAGNATION_THRESHOLD` rounds, a non-normal source may guide the next search base only if its frozen-validation frontier score is better than the current baseline. The retained best still must pass the existing promotion gate.

## Scientific Boundary

This is search-space steering and observability, not a prediction claim. A non-normal source can become a temporary search base only after frozen-validation lift. It cannot become the retained best unless the normal best-promotion path accepts it.

Historical lift remains evidence for a training hypothesis, not proof of future prediction ability.

## Validation

Unit test:

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_supervisor.py -q
```

Result:

```text
83 passed in 0.59s
```

Live supervisor validation:

```text
run_id=20260625-143815
pid=1618510
log=runtime/logs/training-supervisor-source-frontier-20260625-143815.log
status=data/output/optimization/training-supervisor-20260625-143815.json
report=data/output/optimization/training-supervisor-20260625-143815.md
```

Observed rounds:

| Round | Improved | Top100 | Top1000 | Top10000 | Source-frontier champion | Best non-normal |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | false | 2 | 3 | 3 | inactive, below_threshold | neural_kdj, frozen Top10000 0 |
| 2 | false | 2 | 3 | 3 | inactive, below_threshold | recency_canary, frozen Top10000 0 |

The fresh supervisor completed two full rounds and started round 3 without runtime errors. The new diagnostics appeared in the report under `Source Frontier`.

## Acceptance

- Source-frontier metadata is persisted in `prefilter`.
- The markdown report shows a compact source-frontier table.
- Non-normal candidates are visible when they reach full evaluation.
- The champion remains inactive before the stagnation threshold.
- The champion remains inactive when frozen Top10000 does not improve.
- Existing retained-best promotion still uses the frozen validation promotion gate.
