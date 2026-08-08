# Prediction v2 structural baseline-comparison preregistration — Round 75

## Round contract

- Primary goal: freeze and mainline-integrate a result-blind comparison against stronger, transparent, label-symmetric structural baselines.
- Task: `prediction-v2-structural-baseline-comparison-preregistration`.
- Ready condition: the structural route decision is `VALIDATED_IN_MAINLINE`, replay verified, and all three route children are registered.
- Runner: unified Research Evidence Supervisor.
- Downstream consumer: `prediction-v2-structural-baseline-comparison-execution`.
- Non-goals: execute the baselines, read portfolio results or history, query the database, create prediction Evidence, train a model, activate a portfolio, or open a promotion gate.

## Frozen result-blind program

The Research request froze three simple comparator classes before reading any portfolio result:

1. `SINGLETON_FIRST_GREEDY_V1`
2. `PAIR_FIRST_GREEDY_V1`
3. `DISTANCE_FIRST_GREEDY_V1`

Each class receives 128 replicates, 176 construction steps per replicate, and 256 candidate considerations per step. This is 45,056 candidate considerations per replicate, 5,767,168 per class, and 17,301,504 across all three classes. Proposal considerations are the frozen complexity-accounting unit and exactly match the original optimizer's 5,767,168-proposal class budget.

Candidate construction uses one deterministic SHA-256-derived without-replacement stream per replicate and consumes disjoint chunks. There is no duplicate, repeat, deduplication, or uniqueness-validation pass. Non-repetition follows from construction; no extra scan is scheduled or represented in the artifacts.

The four frozen metrics are singleton square sum, pair square sum, minimum replacement distance, and total pairwise replacement distance. The candidate must strictly dominate at least 122 of 128 replicates in every comparator class, while no comparator replicate may strictly dominate the candidate. Passing supports only `SUPPORTED_BEYOND_FROZEN_TRANSPARENT_BASELINES`; it does not establish usefulness, predictive probability, statistical significance, or global optimality. Failure archives the portfolio as engineering evidence only. Invalid execution produces no decision.

## Governance and implementation

- Research Request 402 / execution 323 froze the result-blind scientific contract.
- Engineering Request 403 / execution 324 authorized only implementation of that contract.
- The source contract binds the single preregistration module and the four immutable route artifacts.
- The capability registers exactly three deterministic children plus the mainline execution artifact.
- Workload counters are all zero in this round: database queries, historical rows, folds, bootstrap children, and baseline proposals.
- The additive manifest migration revises only the existing preregistration placeholder, adds only the separate execution placeholder, and preserves prior durable state and facts.

## Validation before publication

- Ruff formatting and linting: pass.
- Targeted preregistration, route-decision, source-partition, Supervisor execution/replay, status, artifact-index, and additive-migration tests: 81 passed.
- Full worker suite: 2,255 passed, 4 skipped, and the same 42 known failures from deliberately retired legacy training, legacy three-line prediction, legacy mail, and legacy forward-evaluation paths; no new failure appeared in the touched mainline surface.
- Result-blind boundary: pass; portfolio results read = 0.
- Repeated-validation boundary: pass; no repeated-validation fields or workload are present.

## Integration matrix

| Link | Before merged-main execution | Acceptance requirement |
|---|---|---|
| Goal | active M4 information-theory evidence goal | preserved by additive migration |
| Resolver | preregistration Ready | execution becomes Ready only after preregistration completion |
| Ready Queue | preregistration selected | separate execution is the sole new downstream task |
| Supervisor | capability implemented | fresh merged-main Supervisor execution succeeds |
| Capability | deterministic zero-work preregistration | exact source and four route identities consumed |
| Artifacts | three children plus execution | all four registered immutably |
| Status | projection implemented | reports preregistration validated and next execution Ready |
| Next Task | execution placeholder | resolver reports Ready after completion fact |
| Replay | deterministic replay implemented | same registered content, zero workload rerun |

Final integration answer before publication and live merged-main execution:

`NO — INTEGRATION_PENDING`

This becomes `YES — validated by unified mainline execution and replay` only after the ready PR merges, the exact 67→68 additive migration is imported into the durable control plane, a fresh Supervisor completes the preregistration, and replay verifies the same registered content.
