# Near Dynamic KDJ Line V1

Date: 2026-07-09

## Goal

Add `dynamic_kdj_near` as a rolling near-term prediction line:

- Regress only the latest 9 known target issues.
- Predict the next unknown issue.
- Keep retraining the current as-of window continuously; do not seal a stagnant near-window policy.

When a new draw is synced, the window moves right by one issue and the line retrains.

## Behavior

- The line reuses the existing KDJ dynamic weight adjustment and KDJ-state strength band.
- The near regression window is fixed at 9 targets.
- Stagnation is recorded as a diagnostic only; it does not stop near-line retraining or freeze the candidate snapshot.
- Scheduled sync captures and evaluates `static_100`, `dynamic_kdj`, and `dynamic_kdj_near`.
- Rolling near-line reports are written under `data/output/near-dynamic-line-reports/`.
- The success target is 3 exact red6 Top100 hits in a 10-issue rolling window; red5 is only auxiliary.

## Gauss-Riemann Review

Historical boundary: Gauss and Riemann are used as verification lenses, not literal minds or evidence.

Gauss pass:

- Legal red-ball sample space remains `1,107,568`.
- Each target must use only history and KDJ signals before that target issue.
- The 3/10 goal is much stronger than a random Top100 baseline and must be treated as an experimental gate.
- Forward evaluation remains line-keyed by snapshot so post-draw rewrites are rejected without freezing the training loop.

Riemann pass:

- The near line is a local rolling state model, not a global replacement for the main line.
- The meaningful object is the moving window `101-109 -> 110`, then `102-110 -> 111`.
- A weight that works in one local window is not assumed to continue into the next window.

Smallest shared conclusion:

`dynamic_kdj_near` is acceptable as a monitored short-horizon experimental line. It may reveal local structure, but promotion requires forward reports, leakage checks, and comparison against the existing lines.

## Validation

```bash
bash -n scripts/ensure_training_supervisor.sh
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_next_candidates.py apps/worker-python/tests/test_prediction_evaluation.py apps/worker-python/tests/test_training_supervisor.py apps/worker-python/tests/test_training_watch.py
cd apps/api && npm test
cd apps/web && npm test
cd apps/web && npm run build
```
