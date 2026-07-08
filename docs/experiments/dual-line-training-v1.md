# Dual-Line Training V1

## Goal

Train two comparable prediction lines in the same supervisor run:

- `static_100`: existing main static-weight training line.
- `dynamic_kdj`: independent KDJ policy line that trains offset strength against the same 100-issue window.

## Behavior

- The supervisor still has one process and one shared ranked universe.
- Every round writes the existing main `training_round_results` row.
- Every round also writes `training_line_round_results` rows for both lines.
- `dynamic_kdj` trains a policy by sweeping KDJ offset strength over the same target issues.
- The dynamic line keeps its own best policy and uses that policy for next-issue Top10000 prediction.
- Candidate snapshots and sync-after-draw prediction evaluation remain line-keyed.
- `watch_training_progress.py` reports both lines side by side with latest and recent-window Top100/1000/10000 metrics.

## Non-Goals

- No second OS-level supervisor process.
- No betting recommendation or probability claim.
- No promotion of dynamic KDJ into the main static training objective until forward reports support it.

## Gauss-Riemann Review

Historical boundary: Gauss and Riemann are used as verification lenses, not literal minds or authority.

Gauss pass:

- Legal red-ball sample space remains `1,107,568`.
- Both lines share the same history window, target issues, top-N, and ranked candidate universe.
- Dynamic KDJ only uses signals with `issue < target_issue` inside per-target training.
- Each line stores Top100/1000/10000 and red5 Top100/1000/10000 for round comparison.

Riemann pass:

- The structural difference is isolated to static weights versus a dynamic KDJ response policy.
- KDJ offset strength is now a trainable coordinate rather than a fixed post-processing layer.
- Forward sync reports remain the deciding evidence because same-window regression can still overfit.

Smallest shared conclusion:

`dynamic_kdj` is now a real second training line inside the supervisor. It is still experimental; one-week forward validation should decide whether it becomes the primary plan.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_next_candidates.py apps/worker-python/tests/test_postgres_store.py apps/worker-python/tests/test_prediction_evaluation.py apps/worker-python/tests/test_training_supervisor.py`
- `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --run-id 20260708-180612 --limit 5`
- `apps/worker-python/.venv/bin/python -m pytest -q`
- `cd apps/api && npm test`
- `cd apps/web && npm test`
- `cd apps/web && npm run build`
