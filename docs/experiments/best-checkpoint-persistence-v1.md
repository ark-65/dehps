# Best Checkpoint Persistence V1

- Date: 2026-06-30
- Fresh run id: `20260630-095854`
- Primary goal: persist the current supervisor global best in Postgres so training can resume cleanly after migration without relying on `data/output`.
- Non-goals: no model, reward, search, or promotion-gate change.

## Change Summary

- Added `training_supervisor_best` as the canonical current-best checkpoint table keyed by training protocol plus history fingerprint.
- The table stores `best_config`, `best_summary`, `config_hash`, metrics, run id, round index, and history scope metadata.
- Supervisor startup now writes a round-0 checkpoint when it recovers an existing best from DB or local historical status.
- Each completed round now updates the checkpoint with the current global `best_summary`, not merely that round's `round_best`.
- Supervisor startup and carryover loading now merge this checkpoint table with legacy `training_round_results`.
- Next-candidate generation now prefers `training_supervisor_best`, with fallback to the older round-results scan for backward compatibility.

## Migration Boundary

- Required durable DB state for seamless training migration now includes:
  `training_supervisor_best`,
  `training_round_results`,
  `training_next_candidates_current`,
  `training_weight_signals`,
  and `training_target_weight_inversions` when inversion diagnostics are needed.
- Runtime files under `data/output` remain useful evidence but are no longer the only source for the current global best.

## Validation

- Targeted tests:
  `apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_postgres_store.py apps/worker-python/tests/test_next_candidates.py apps/worker-python/tests/test_training_supervisor.py -q`
  Result: `133 passed in 0.66s`.
- Full worker suite:
  `apps/worker-python/.venv/bin/python -m pytest -q`
  Result: `319 passed in 29.19s`.
- Live supervisor:
  old run `20260630-091612` was stopped; fresh run `20260630-095854` started with the same training parameters and updated code.
- Startup checkpoint:
  `training_supervisor_best` row was created with `run_id=20260630-095854`, `round_index=0`, `history_scope=current_regime_default`, `regime_years=10`, `regime_start_date=2016-06-28`.
- Round checkpoint:
  after round 1 completed, `training_supervisor_best.round_index=1` and `config_hash=0fa50505fec2eb9f8ab5859dd244c77b8178b5f63cf704332d8bfb37c345798a`.
- Next candidates:
  `training_next_candidates_current` refreshed to `run_id=20260630-095854`, `source_round_index=1`, `as_of_issue=2026073`, `next_issue=2026074`, `candidate_count=10000`, with the same checkpoint `config_hash`.

## Notes

- This is a persistence and migration-safety change only. It does not promote a predictive claim.
- The legacy round-results path remains in place so existing databases continue to work before the first checkpoint row is written.
