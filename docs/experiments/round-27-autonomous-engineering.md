# Round 27: Autonomous Experiment Implementation

## Goal

Round 27 converts an approved Experiment Plan into a formal Engineering Implementation Contract.

The new system reads an Experiment Plan, locates existing code, builds a code graph, produces a change plan, produces a test plan, validates the result, and exposes the output through CLI and read-only API surfaces.

It does not modify repository files at runtime, execute experiments, write Evidence, update the Registry, restart services, merge, or touch production training.

## Implemented Surface

Worker package:

```text
apps/worker-python/dehps/engineering/
```

CLI:

```text
dehps engineering plan
dehps engineering locate
dehps engineering validate
dehps engineering contract
dehps engineering graph
```

API:

```text
GET /engineering/contracts
GET /engineering/plan
GET /engineering/status
```

## Scientific Guardrail

Einstein pass:

- Core question: can an approved experiment plan become an auditable engineering contract without the Research Agent deciding implementation details by prompt?
- Invariant: contract generation is read-only and may not modify code, training, Objective, Promotion, Registry, Evidence, or production.
- Null: if existing modules cannot be located or forbidden paths are touched, the contract is invalid.
- Measurement: located component count, code graph coverage, change plan completeness, unit/integration/regression/smoke test coverage, validator pass/fail, and unchanged git status after CLI smoke.
- Failure mode: duplicated experiment implementation, missing tests, production training edits, Objective/Promotion drift, Registry writes, or hidden experiment execution.
- Next experiment: future rounds may let Engineering Agent execute an approved contract; Round 27 stops at contract generation.

## Validation

```text
cd apps/worker-python
.venv/bin/python -m pytest -q
879 passed in 23.12s

DB_PORT=1 .venv/bin/python -m pytest -q
879 passed in 23.53s

cd apps/api
npm test
97 passed

npm run build
passed
```

## Isolated Smoke Plan

Target database:

```text
dehps_round27_smoke
```

Required smoke flow:

```text
clone existing Round 25/26 smoke state with a materialized Round 23 plan
run dehps engineering locate
run dehps engineering contract
run dehps engineering validate
run dehps engineering plan
verify existing code and tests are located
verify contract validation passes
verify writes is []
verify git status is unchanged by CLI execution
verify no commit is created
verify production database is not modified
```

Smoke result:

```text
database: dehps_round27_smoke
base state: cloned from dehps_round25_smoke
plan_key: plan-auto-ranking_model_disagreement-1bf87b0c0493-v1

commands:
  dehps engineering locate
  dehps engineering contract
  dehps engineering validate
  dehps engineering plan
  dehps engineering graph

located_components: 25
existing_components: 25
test_components: 13
graph_source_files: 155
graph_test_files: 136
modules_to_modify: 6
files_to_add: 1
tests_to_add: 4
contract_valid: true
validate_valid: true
contract_writes: []
plan_writes: []
head_unchanged: true
git_status_unchanged: true

production isolation:
  prod_engineering_requests: 0
  prod_round27_scheduler: 0
```

The smoke confirms that Round 27 can read a materialized Round 23/24 plan, locate existing implementation and test surfaces, generate a complete Implementation Contract and Engineering Plan, validate them, and leave the repository and production database unchanged.

## Non-goals Confirmed

Round 27 does not:

- modify production training
- modify Objective
- modify Promotion
- auto-merge
- restart services
- execute Experiment
- write Evidence
- update Registry
