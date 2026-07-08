# Dual-Line Regression Comparison V1

## Goal

Make `dynamic_kdj` comparable with `static_100` before forward promotion:

- Both lines still generate next-issue Top10000 candidates.
- Both lines expose a compact `regression_100` summary in prediction metadata.
- Each current snapshot with regression metadata is persisted to `training_prediction_line_regressions`.
- Dashboard next-candidate view shows a side-by-side 100-issue exact/red5 comparison.

## Non-Goals

- No new betting recommendation.
- No claim that KDJ dynamics imply future mean reversion.
- No replacement of the main supervisor objective during the one-week forward validation period.

## Behavior

- `static_100` uses the supervisor best summary as its 100-issue regression baseline.
- `dynamic_kdj` reruns the latest 100 target issues with per-target KDJ adjustment:
  - each target uses history before that target;
  - each target uses only KDJ signals with `issue < target_issue`;
  - fallback targets are counted when no KDJ offset is applied.
- The persisted comparison fields include exact Top100/1000/10000, red5 Top100/1000/10000, rank range, fallback target count, changed target count, and leakage status.

## Gauss-Riemann Review

Historical boundary: Gauss and Riemann are used as verification lenses, not literal minds or authority.

Gauss pass:

- Legal red-ball sample space remains `1,107,568`.
- The dynamic 100-issue pass has an explicit no-leakage boundary: KDJ signals must satisfy `issue < target_issue`.
- The stored summary records misses through hit counts and rank ranges, not only successful bands.

Riemann pass:

- Both lines use the same historical window and ranked candidate universe.
- The only structural difference is static best weights versus per-target KDJ response offsets.
- Forward sync evaluations remain the deciding evidence, because historical regression can still be post-hoc or unstable.

Smallest shared conclusion:

`dynamic_kdj` is now a legitimate second line for comparison, but it is still an experimental response layer until sync-generated prediction reports show durable advantage over `static_100`.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_next_candidates.py apps/worker-python/tests/test_postgres_store.py apps/worker-python/tests/test_prediction_evaluation.py`
- `cd apps/web && npm test`
- `cd apps/web && npm run build`
