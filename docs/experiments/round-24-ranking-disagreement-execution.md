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
848 passed in 22.42s

DB_PORT=1 .venv/bin/python -m pytest -q
848 passed in 22.57s

cd apps/api
npm test
85 passed

npm run build
passed
```

## Isolated Smoke

Isolated smoke target: `dehps_round24_smoke`.

The smoke cloned the Round 23 frozen state from `dehps_round23_smoke`, inserted 145 synthetic legal historical issues with source `round24_smoke_synthetic`, completed the Engineering request, recorded Reviewer implementation acceptance in the Operator approval, approved the Operator isolated run, and executed the full legal-universe default path.

```text
implementation commit: 506e45dc3a414bd7c5f96f3158aecefe819f2e94
operator request: operator-isolated-run-ab9c47ce344691fd
operator execution: completed
elapsed: 901.582 seconds
cpu limit: 16
memory limit: 20GB
violations: []
skipped: forward_validation
```

Stage status:

```text
ranking_disagreement_feasibility_v1: completed
ranking_disagreement_historical_search_v1: completed
ranking_disagreement_frozen_validation_v1: completed
ranking_disagreement_forward_validation_v1: planned
```

Artifact validation:

```text
manifest valid: true
artifact count: 10
search issue count: 100
frozen issue count: 20
statistics comparisons: 12
validation report valid: true
```

Registry checks:

```text
hypothesis status: preregistered
evidence count: 0
engineering request: completed
operator request: completed
```

Production isolation checks against database `dehps`:

```text
round24 synthetic history records: 0
round24 smoke requests: 0
round24 hypothesis records: 0
```

Artifacts were written under:

```text
data/output/research/ranking_model_disagreement/ab9c47ce344691fd73767d903dcd181898937b9297fd2d2b9ea61c823432a356/
```

## Known Limits

- The tool is a measurement implementation, not a hypothesis decision.
- The archived results are not Evidence until a later audited Evidence submission.
- Unit tests use a small deterministic legal universe fixture; registry-backed CLI execution defaults to the full SSQ red-ball legal universe.
