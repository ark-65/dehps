# Forward Evaluation Closure And Ranking Audit — 2026-07-15

## Primary Goal

Restore the mandatory forward lifecycle after draw-sync/training-resume decoupling, and make the actual red combination's path through generation, hard filtering, scoring, rerank, and export inspectable.

## Non-Goals

- No weight, feature, advisor, objective, candidate-source, or promotion change.
- No claim that reconstructed or historical ranks prove predictive ability.
- No promotion of issue `2026080` reconstruction into official forward evidence.

## Scientific Check

- **Core question:** did issue `2026080` disappear because of generation/filtering/export, or because its model score was already weak?
- **Invariant:** one persisted `prediction_run_key + target_issue` has at most one official evaluation result; retries update the same evaluation run.
- **Hypothesis:** the evaluation gap is an orchestration regression, while the candidate miss happened before Top-N export.
- **Measurement:** durable run/result state, retry attempts, and the actual combination's structural/model/export ranks.
- **Failure mode:** evaluating a replaceable `current` snapshot after it has advanced, silently accepting partial candidates, or treating a deterministic reconstruction as official forward evidence.
- **Next experiment:** let the pending `2026081` snapshots remain frozen, sync the draw, and verify all three lines automatically transition from pending to evaluated before training resume.

## Root Cause

Commit `577b847` decoupled draw synchronization from `scripts/ensure_training_supervisor.sh`. That migration deliberately removed `evaluate_synced_predictions_if_needed`, but the new independent `DrawSyncWatch` only persisted the draw event and optionally resumed training. It did not take ownership of forward evaluation.

The old candidate storage also contained only `training_next_candidates_current`. Each new generation deleted the previous line snapshot. By the time issue `2026080` was inspected, current snapshots already targeted `2026081`, so the exact `2026080` candidate rows could no longer be evaluated as an immutable official snapshot.

## Change

- Candidate generation now writes a durable `forward_prediction_runs` record and its exact `forward_prediction_candidates` before replacing the current dashboard rows.
- Repeated snapshots for the same line/target supersede only older pending variants; pending snapshots for a different target are preserved.
- `DrawSyncWatch` runs the pending evaluator after every sync attempt, including no-change attempts, so failures retry without requiring a second history change.
- Training resume is withheld when any due evaluation fails.
- `forward_evaluation_runs` records attempt count, running/completed/failed status, and structured error details.
- `training_prediction_evaluations` remains the result table and now carries `prediction_run_key` and `evaluation_run_key`; a partial unique index enforces one official result per prediction run and target issue.
- `python -m scripts.evaluate_pending_forward_runs` provides an idempotent compensation entry point.
- Every accepted evaluation includes generated/filter/initial/model/rerank/export state plus exact-red6 and exact-red5 counts at Top100, Top1000, and Top10000.
- The current pipeline has no separate post-model reranker. Audits therefore record `rerank_applied=false` and carry the model rank through unchanged rather than inventing a stage.

## Issue 2026080 Ranking Audit

Actual reds: `[4, 5, 11, 19, 27, 32]`.

The original candidate rows had already been overwritten. Ranks were deterministically reconstructed from the timestamped pre-draw artifact `data/output/optimization/training-supervisor-20260714-160336.json`. All three reconstructions matched both the recorded config hash and history fingerprint. They are diagnostic only and explicitly carry `official_forward_evidence=false`.

| Line | Generated | Hard filter | Initial structural rank | Model/rerank rank | Final export | Red6/Red5 in Top100 / Top1000 / Top10000 |
| --- | --- | --- | ---: | ---: | --- | --- |
| `static_100` | yes | passed | 298,492 | 643,938 | absent | `0/0`, `0/0`, `0/0` |
| `dynamic_kdj` | yes | passed | 298,492 | 663,994 | absent | `0/0`, `0/0`, `0/0` |
| `dynamic_kdj_near` | yes | passed | 298,492 | 696,201 | absent | `0/0`, `0/0`, `0/0` |

The elimination stage was model scoring for every line, not generation, hard filtering, reranking, or an export bug. The model moved the actual combination down from an already weak structural rank of `298,492` to ranks between `643,938` and `696,201`. No exact-red5 combination appeared in any line's Top10,000.

Generated audit artifact: `data/output/ranking-audits/forward-ranking-audit-2026080.json` (runtime evidence, not committed).

## Database Change

- Added `forward_prediction_runs`.
- Added `forward_prediction_candidates`.
- Added `forward_evaluation_runs`.
- Added `prediction_run_key` and `evaluation_run_key` to `training_prediction_evaluations`.
- Added the unique official-result index on `(prediction_run_key, predicted_issue)`.

Runtime schema creation is idempotent and `infra/postgres/init/001_init.sql` contains the same fresh-install definition.

## Validation

- Targeted lifecycle, ranking audit, scheduler, evaluator, and storage tests: `42 passed`.
- First full worker run: `947 passed, 1 failed`; the only failure caught a missing default static line label in the new archive path.
- The default-label defect was fixed and the targeted set returned to `42 passed`.
- Live schema/upsert syntax check completed inside a rollback-only transaction.
- Compensation command currently reports three `2026081` prediction runs as `pending_missing_actual_draw`, with zero failures and no evaluation rows written.
- Final post-fix worker suite: `948 passed in 44.10s`.

## Evidence Boundary

The fix restores operational evidence capture and makes rank failure inspectable. It does not improve candidate quality. Issue `2026080` supports investigating score direction or feature drift next, but no weight or feature change is justified until a separately authorized, baseline-controlled round is defined.
