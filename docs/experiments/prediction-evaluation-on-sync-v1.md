# Prediction Evaluation On Sync v1

Date: 2026-07-08

## Goal

Make live SSQ prediction evaluation operationally automatic: when the scheduled
sync imports or updates an actual draw, evaluate that draw against the prediction
snapshot that existed before the training supervisor refreshes for the new
latest issue.

## Non-goals

- Do not add a new scoring model, strategy, or candidate source.
- Do not change the 100-issue dynamic evaluation window already used by the
  training supervisor.
- Do not score blue-ball hits yet; the current training prediction snapshot is
  red-ball only.

## Behavior

- `scripts/ensure_training_supervisor.sh` keeps launching the supervisor with
  `--eval-window 100` and no fixed target start issue, so the 100 evaluation
  targets roll forward with the latest issue in `ssq_history`.
- Before `sync_latest_ssq.py` runs, the watchdog records the current prediction
  snapshot target issue. After sync, inserted or updated draws trigger
  `evaluate_training_prediction.py` for that pre-sync target when the actual
  draw is now present. This preserves the "prediction before draw" boundary.
- Each evaluation writes JSON and Markdown reports under
  `data/output/prediction-evaluations/`.
- The report records exact red6 rank, Top100/Top1000/Top10000 exact-hit flags,
  first exact-red5 near-miss rank, first red5-or-better rank, best red overlap,
  the prediction snapshot metadata, and guardrail warnings.
- If the current snapshot is missing, targets another issue, or was generated
  from the same or a later issue, the evaluator marks the report non-evaluable
  instead of counting it as a success.

## Validation

```bash
bash -n scripts/ensure_training_supervisor.sh
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_prediction_evaluation.py apps/worker-python/tests/test_next_candidates.py apps/worker-python/tests/test_postgres_store.py
cd apps/worker-python && .venv/bin/python scripts/evaluate_training_prediction.py --issue 2026077 --no-write-report
```

Results:

- Shell syntax check passed.
- Targeted worker tests passed: `33 passed`.
- Live no-write evaluation returned `prediction_snapshot_mismatch` for
  `2026077`, because the current snapshot already targets `2026078`. This is
  expected for retroactive validation and confirms why the scheduler must
  evaluate immediately after a new draw is synced, before the current snapshot
  is refreshed.
