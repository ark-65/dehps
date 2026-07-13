# Navigation Search-Base Consumption Audit

## Primary Goal

Make the training watcher verify that a selected search-slice navigation hash is actually consumed by the following durable database round's `search_base_start.config_hash`.

## Non-Goals

- No training, candidate generation, ranking, objective, advisor, source-budget, search-base selection, promotion, or supervisor-lifecycle change.
- No use of frozen validation for navigation.
- No predictive or betting claim.

## Task Frame and Historical Boundary

The watcher already exposed whether experimental navigation was selected, but it did not verify the next database round's starting base. This left a gap between a selection log and durable evidence that the branch was actually consumed. Gauss- and Riemann-style checks here are historically inspired diagnostic lenses, not literal reconstructions or authority.

## Gauss Pass: Verification

- Object: consecutive durable `training_round_results` rows in one supervisor run.
- Invariant: when round `r` records a selected navigation hash under `eligibility_basis=search_slice_rank_geometry` and `selection_uses_frozen_validation=false`, round `r+1` must record the identical `search_base_start.config_hash`.
- Boundary cases: no selection is `not_available`; a final selected round without its next database row is `pending_next_durable_round`; a missing or unequal next-round hash is `invalid`.
- Proof obligation: exact hash equality in persisted rows, not supervisor progress or strategy-memory logs.

## Riemann Pass: Structure

The relevant state transition has two distinct surfaces: selection at the end of one durable round and consumption at the start of the next. The audit keeps that edge explicit instead of treating an in-memory navigation choice as completed coverage.

## Cross-Review, Disagreement, and Synthesis

- Gauss challenge: a selection count alone does not prove consumption.
- Riemann challenge: a local selection event must be connected to the next durable state transition.
- Disagreement: none on the minimum read-only audit. Neither lens supports changing strategy or claiming predictive improvement.
- Smallest shared conclusion: credit navigation consumption only after exact next-round database equality; otherwise remain pending or invalid.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py apps/worker-python/tests/test_training_watch_restart_guard.py` — 126 passed.
- Live `watch_training_progress.py --limit 12` on run `20260712-220448`:
  - selected/verified/pending/violations: `8/7/1/0`;
  - round 123 selected `ae712a63556557a9a74f7b81044233769badc23622b883d4e42ae4c311291702`;
  - round 124 persisted the same `search_base_start.config_hash`;
  - round 124 selected `81d470cfb3d7c36ae21a00476f482dc613dfe72bc876b4cf14f0bb6fac6d822d`, while round 125 was not yet database-recorded, so the audit correctly remained pending.

## Evidence and Risk

The legal red-ball universe remains 1,107,568 combinations; the current ranked universe is 1,105,506. Historical evaluation remains an 80-issue search slice plus a disjoint 20-issue promotion-only frozen slice. Historical holdout quarantine remains active. Forward evidence remains 1/20 paired issues, and the sequential null audit remains an incomplete observed lower bound with uncounted adaptive generation and sequential reuse. Automatic promotion and automatic budget changes remain disabled. This round improves operational auditability only.

