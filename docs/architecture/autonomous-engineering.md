# Autonomous Engineering Implementation Contracts

Round 27 adds the engineering bridge between an approved Experiment Plan and future Engineering Agent execution.

The component is deliberately non-mutating:

```text
Experiment Plan
-> EngineeringContext
-> Repository Locator
-> Change Plan
-> Test Plan
-> ImplementationContract
-> Validator
```

It does not modify code, run experiments, write Evidence, update the Registry, restart services, commit, merge, or touch production training.

## EngineeringContext

The context is built from formal sources:

- materialized Experiment Plan from the Hypothesis Registry metadata;
- repository code graph;
- feature catalog;
- mechanism catalog;
- current public Python interfaces;
- existing test files.

It does not read prompts, Markdown conclusions, or chat instructions as engineering evidence.

## Repository Locator

The locator identifies existing implementation surfaces before any new file is proposed:

- Rankers
- Features
- Baselines
- Experiments
- Metrics
- Statistics
- Existing tests

For the current ranking-disagreement mechanism, the locator reuses:

```text
apps/worker-python/dehps/experiments/ranking_disagreement/
apps/worker-python/dehps/models/frequency_ranker.py
apps/worker-python/dehps/features/red_ball_features.py
apps/worker-python/dehps/candidates/null_model.py
apps/worker-python/tests/test_ranking_disagreement_*.py
```

The invariant is simple: do not duplicate a mechanism implementation when an existing package already owns it.

## ImplementationContract

The contract records:

- modules to modify;
- files to add;
- interfaces to add;
- tests to add;
- located existing components;
- forbidden paths;
- compatibility requirements;
- non-goals;
- production impact;
- objective/promotion/registry/evidence/execution permissions.

All runtime authority flags default to false:

```text
objective_policy_change_allowed = false
promotion_change_allowed = false
registry_update_allowed = false
experiment_execution_allowed = false
evidence_write_allowed = false
production_impact = none
```

## Validation

The validator fails the contract if:

- plan identity is missing;
- existing repository components are not located;
- change plan is empty;
- unit/integration/regression/smoke tests are missing;
- forbidden paths are planned for modification;
- production impact is not `none`;
- Objective, Promotion, Registry, Experiment execution, or Evidence writes are allowed.

## CLI

```text
dehps engineering graph
dehps engineering locate
dehps engineering contract
dehps engineering plan
dehps engineering validate
```

Every command is a dry run and emits `writes: []`.

## API

The API is read-only:

```text
GET /engineering/contracts
GET /engineering/plan
GET /engineering/status
```

These endpoints expose existing engineering request and plan state. They do not generate new contracts.
