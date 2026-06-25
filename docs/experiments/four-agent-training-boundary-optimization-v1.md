# Four Agent Training Boundary Optimization V1

## Summary

This round applied a four-agent review pattern to the stalled training supervisor:

- Gauss verification agent: primary frozen hits must be separated from secondary shape improvements.
- Riemann structure agent: rank-signature collapse should constrain search-base selection.
- Probability-focus control agent: the same focus candidate must not refresh its TTL forever.
- Source-survival agent: candidate sources already enter the search, so report/acceptance boundaries should be fixed before budget changes.

The main agent integrated the shared conclusion into a conservative supervisor change. No new scoring algorithm, candidate family, or lottery signal was added.

## Changes

- Split source-frontier evidence into primary hit score and secondary shape score.
- `select_source_frontier_champion` now activates only on primary frozen hit lift.
- `source_frontier_diagnostics` records `best_non_normal_primary` and `best_non_normal_secondary`.
- `frozen_validation_promotion_gate` now reports and requires `primary_hit_passed`.
- `probability_focus` no longer refreshes TTL for the same hash with the same score.
- Search-base selection can skip rank signatures flagged by the rank-homogeneity guardrail.
- Status/report output now separates legal universe size, ranked universe size, and excluded universe count.

## Validation

Unit test:

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_supervisor.py -q
```

Result:

```text
88 passed in 0.53s
```

Live supervisor validation:

```text
run_id=20260625-174916
pid=1706400
log=runtime/logs/training-supervisor-four-agent-20260625-174916.log
status=data/output/optimization/training-supervisor-20260625-174916.json
report=data/output/optimization/training-supervisor-20260625-174916.md
```

Observed live checks:

- Round 1 and round 2 completed and were persisted.
- Both rounds remained `Top100=2`, `Top1000=3`, `Top10000=3`, `improved=false`.
- `promotion_gate.primary_hit_passed=false` when frozen primary hits did not improve.
- `source_frontier_champion.reason=below_threshold` during the first two rounds.
- `search_base` metadata now includes rank-signature fields and cooldown fields.
- Report shows `Legal universe size=1107568`, `Ranked universe size=1105506`, `Excluded universe count=2062`.

## Acceptance

- Primary and secondary frontier evidence are no longer conflated.
- Secondary-only rank shape or Red5 lift cannot activate source-frontier champion.
- Secondary-only objective lift cannot promote retained best.
- Probability-focus same-hash same-score refresh is blocked by helper tests.
- Rank-signature cooldown is available to both probability-focus and normal search-base fallback paths.
- Fresh supervisor with the updated code completed two persisted rounds without runtime errors.
