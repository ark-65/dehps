# Production/research watchdog split — 2026-07-16

## Round contract

- Primary goal: keep forward-wait as a production prediction lock while allowing fingerprinted, read-only historical research on unchanged history.
- Non-goals: no score, feature formula, weight, model-selection, train/eval-window default, TopN, draw, current `2026081` prediction, evaluation result, or promotion change; no predictive-lift claim.
- Authorization: Agent Request `engineering-split-production-research-6ed4eca` (request id 101, execution id 24).
- Starting commit: `6ed4eca797ba92a6d5c01fad7cb959146c481e27`.

## Root cause

The production watchdog correctly recognized that history `2026080` already had a complete three-line prediction for target `2026081`. The defect was that its isolated research completion check used only `as_of_issue + history_fingerprint`. Consequently, unchanged draw history was treated as proof that all research was duplicate, even when the code, feature/model version, parameters, windows, candidate algorithm, task suite, or random seeds had changed.

The official snapshot writer also automatically marked a different active run for the same line and target as `superseded` and deleted its archived candidates. That behavior made accidental repeated production generation destructive and contradicted the explicit-operator replacement boundary.

## Execution split

| Production state | Formal prediction | Evaluation | Historical research |
| --- | --- | --- | --- |
| `READY_FOR_PRODUCTION` | allowed | no | allowed |
| `WAITING_FOR_DRAW` | blocked | no | `RESEARCH_ONLY` |
| `READY_FOR_EVALUATION` | blocked | allowed | allowed |
| `EVALUATING` | blocked | in progress | allowed, subject to the heavy-job lock |
| `READY_FOR_PROMOTION` | blocked until the normal gate resolves | complete | allowed |

The launcher now logs the explicit `WAITING_FOR_DRAW` capability decision, parks only the production supervisor, and schedules `scripts/run_isolated_research_lane.py --mode research`. The research process holds the shared `research-training` heavy-job lock, so a newly ready production job cannot overlap its CPU/memory workload.

## Training fingerprint

The canonical SHA-256 fingerprint contains:

- history maximum issue and history-content fingerprint;
- execution mode and research suite version;
- model, feature, and candidate-algorithm versions;
- a config hash covering profile, task list, train/eval windows, TopN, history scope, regime window, train mode, and random seeds;
- Git commit;
- primary random seed.

Each completed fingerprint has its own immutable-named local manifest in addition to the latest pointer. Therefore `A -> B -> A` remains idempotent: the second `A` is recognized even though `B` is the latest run. Failed fingerprints remain retryable.

The default idle suite composes existing research tools only:

1. read-only training diagnostics;
2. walk-forward optimization;
3. weight-grid search;
4. feature-family ablation;
5. dynamic-KDJ frozen backtest;
6. frozen random-seed controls.

All child processes inherit PostgreSQL `default_transaction_read_only=on`. Research may write local reports and manifests, but cannot write training, prediction, evaluation, event, or promotion tables. It never calls the production training supervisor or official candidate generator.

## Official prediction protection

Ordinary snapshot persistence now checks for an existing run key or an active `(line_key, target_issue)` run and raises `active_forward_prediction_exists:...:explicit_supersede_required`. It no longer silently changes status or deletes archived candidates.

The schema adds the partial unique index:

```sql
CREATE UNIQUE INDEX idx_forward_prediction_one_active_line_target
ON forward_prediction_runs (line_key, target_issue)
WHERE status IN ('pending', 'evaluating', 'evaluation_failed');
```

The manual compensation script `scripts/supersede_forward_prediction_run.py` requires the run key twice plus actor and reason. It only permits `pending` or `evaluation_failed` transitions, records the audit metadata, and preserves the candidate evidence. Applying the index to production and running this script are Operator actions; neither occurs in the Engineering execution.

## Validation

Pre-change production audit:

- active official runs for `2026081`: exactly one per `static_100`, `dynamic_kdj`, and `dynamic_kdj_near`;
- active duplicate `(line_key, target_issue)` groups: zero;
- forward runs: 3 pending;
- archived candidates: 30,000.

Engineering validation:

```text
bash -n scripts/ensure_training_supervisor.sh
89 focused research/forward/storage tests passed
992 full worker tests passed in 44.62s
```

The tests cover fingerprint changes from parameters, code and seeds; stable per-fingerprint manifests; production/research state capabilities; read-only database enforcement; the full idle task command boundary; active official-run conflict rejection; evidence-preserving explicit supersede; and the launcher contract.

## Evidence boundary

This round repairs orchestration, idempotence, and provenance. It does not show that any research task improves future ranking performance. Any candidate produced by historical work remains outside the official `2026081` prediction and must pass the existing frozen, forward-evidence, leakage, null-model, and Promotion gates.

## Operational acceptance

Production index application and a fresh bounded research run from the merged commit are pending separately authorized Operator executions. Acceptance requires the research fingerprint to complete without runtime errors and the three `2026081` runs, their statuses, and all 30,000 candidate rows to remain unchanged.
