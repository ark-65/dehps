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

Operator Request `operator-apply-forward-active-index-67eaacf` (request id 102, execution id 25) applied the partial unique index from merged commit `67eaacf`. The migration transaction compared full forward-run keys, status, candidate count, generated timestamp, and updated timestamp before and after schema assurance. All three `2026081` runs remained pending and unchanged; candidate rows stayed at 30,000; active duplicate groups stayed at zero.

The post-merge watchdog then automatically started research PID `3493934`, fingerprint `0866de81a67425cd39be4c68eef5644a70c31786197cbad0c16f92286800bef0`. Operator Request `operator-validate-idle-research-67eaacf` (request id 103, execution id 26) adopted the existing process instead of starting a duplicate. Live acceptance observed three completed tasks without runtime errors:

- `training_diagnostics`;
- `walk_forward_optimization` over 100 historical targets (about 132.5 seconds);
- `weight_grid_search` over the same 100-target boundary.

The next bounded task, `feature_family_ablation`, was running when acceptance closed. The research parent and sampled child processes both reported `VmSwap: 0 kB`. The shared heavy-job metadata identified owner `research-training`, included `production_prediction_write_allowed: false`, and reported the merged fingerprint.

Post-run database verification still showed exactly three pending `2026081` runs, 30,000 archived candidates, zero evaluation rows, zero active duplicate groups, and the original `2026-07-15 09:50:07.057287+08:00` run update marker. The ongoing bounded research is operationally accepted; its historical metrics are not a predictive-quality conclusion and cannot alter the official prediction or Promotion state.
