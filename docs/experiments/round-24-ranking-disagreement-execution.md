# Round 24: Ranking Disagreement Isolated Execution Tool

## Outcome

Round 24 implements the isolated execution tool for the Round 23 frozen `ranking_model_disagreement` plan:

```text
plan-auto-ranking_model_disagreement-1bf87b0c0493-v1
ab9c47ce344691fd73767d903dcd181898937b9297fd2d2b9ea61c823432a356
```

The implementation can run feasibility, historical search, and frozen validation in order, archive immutable artifacts, and complete an audited Operator isolated-run execution. Forward validation remains planned and is not executed.

## Implemented Surface

Worker package:

```text
apps/worker-python/dehps/experiments/ranking_disagreement/
```

CLI:

```text
dehps ranking-disagreement feasibility
dehps ranking-disagreement search
dehps ranking-disagreement frozen
dehps ranking-disagreement run-isolated
dehps ranking-disagreement validate-artifacts
dehps ranking-disagreement show-results
```

API:

```text
GET /research-execution/runs
GET /research-execution/runs/:id
GET /research-execution/runs/:id/artifacts
GET /research-execution/runs/:id/results
GET /research-execution/status
```

## Guardrails

- Plan fingerprint is validated before registry-backed execution.
- Ranker list is fixed and alias-normalized to `frequency_based`, `structural`, `omission_based`.
- Rankers use only pre-target history.
- Search thresholds are fit only in `historical_search`.
- Frozen validation reuses frozen thresholds.
- All four strata and all three baselines are reported.
- Baseline candidate budgets must exactly match the stratum budget.
- `run-isolated` refuses the default production database.
- No Evidence is written.
- Hypothesis status remains `preregistered`.
- No production training, Objective, Promotion, Supervisor, betting, or candidate output is modified.

## Validation

Implementation validation completed:

```text
cd apps/worker-python
.venv/bin/python -m pytest -q
848 passed in 20.84s

DB_PORT=1 .venv/bin/python -m pytest -q
848 passed in 20.47s

cd apps/api
npm test
85 passed

npm run build
passed
```

## Isolated Smoke

The isolated smoke target is `dehps_round24_smoke`. It must approve the Engineering request, complete Engineering execution, accept the implementation, approve the Operator request, run the three non-forward stages, validate artifacts, and complete Operator execution.

Smoke result will be recorded in this report after the isolated execution command completes.

## Known Limits

- The tool is a measurement implementation, not a hypothesis decision.
- The archived results are not Evidence until a later audited Evidence submission.
- Unit tests use a small deterministic legal universe fixture; registry-backed CLI execution defaults to the full SSQ red-ball legal universe.
