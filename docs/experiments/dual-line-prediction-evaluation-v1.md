# Dual-Line Prediction Evaluation V1

## Goal

Run two forward prediction lines for the next SSQ issue and evaluate both after sync:

- `static_100`: current dynamic 100-issue training line.
- `dynamic_kdj`: same training base config plus next-issue KDJ weight offsets.

## Non-Goals

- No betting recommendation or probability claim.
- No promotion of `dynamic_kdj` into the main training objective.
- No blue-ball scoring; blue is recorded only.

## Behavior

- `training_next_candidates_current` now stores current snapshots by `line_key`, so A/B lines do not overwrite each other.
- Supervisor and manual generation refresh both lines.
- Sync automation captures pre-sync snapshots and evaluates any predicted issue that becomes available after sync.
- Evaluation writes JSON/Markdown runtime artifacts under `data/output/prediction-evaluations/` and persists a DB row in `training_prediction_evaluations`.
- API supports `GET /training-next-candidates?lineKey=static_100|dynamic_kdj`.
- Dashboard can switch between the two next-candidate lines and shows dynamic fallback/offset state.

## Gauss-Riemann Review

Historical boundary: Gauss and Riemann are used here as verification lenses, not literal minds or authority.

Gauss pass:

- Legal red-ball sample space is fixed at `1,107,568`.
- Evaluation records `as_of_issue`, `predicted_issue`, `snapshot_key`, candidate count, exact rank, Top100/1000/10000, and red5 best rank.
- Leakage guard requires `as_of_issue < predicted_issue`; failure is stored as `leakage_guard_failed`.
- Reports include misses and missing-snapshot states, not only hits.

Riemann pass:

- Both lines share the same history scope and ranked red-ball universe.
- The structural difference is isolated to static best config versus KDJ-adjusted weight vector.
- A one-week forward run should be read as evidence about response geometry, not proof of lottery mean reversion.

Smallest shared conclusion:

`dynamic_kdj` is acceptable as a parallel forward-validation line. Main-plan promotion requires later sync-created evaluation reports to beat the static line under the same issue sequence.

## Validation

- `bash -n scripts/ensure_training_supervisor.sh`
- `apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_prediction_evaluation.py apps/worker-python/tests/test_next_candidates.py apps/worker-python/tests/test_dynamic_kdj_backtest.py apps/worker-python/tests/test_postgres_store.py apps/worker-python/tests/test_training_watch.py`
- `cd apps/api && npm test`
- `cd apps/web && npm test`
- `cd apps/web && npm run build`
