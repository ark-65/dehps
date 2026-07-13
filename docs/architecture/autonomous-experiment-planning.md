# Autonomous Experiment Planning And Preregistration

## Purpose

Round 23 turns an approved `research_hypothesis_proposal` Agent Request into a frozen experiment contract. It creates a formal Hypothesis, preregisters it, creates planned Experiments, and prepares Engineering and Operator requests without implementing experiment code, running an experiment, writing Evidence, changing production training, changing the Objective, changing Promotion gates, or restarting the Supervisor.

The boundary is:

```text
approved proposal -> deterministic ExperimentPlan -> plan validation
                                                |
                                                v
                         preregistered Hypothesis + planned Experiments
                                                |
                                                v
                       submitted Engineering request + draft Operator request
```

## Planning Model

`dehps.research_planning` defines a serializable `ExperimentPlan` with stable fingerprints. The same approved proposal payload, ResearchContext, and planner version produce the same plan key, protocol, stage list, resource budget, and plan fingerprint.

The planner does not use any runtime result value. It records planned inputs, formulas, contracts, windows, budgets, artifacts, stop conditions, and request payloads. Result artifacts and Evidence remain future outputs of reviewed isolated execution.

## Ranking Disagreement Protocol

The first registered protocol supports `ranking_model_disagreement`. Its core question is whether disagreements between fixed legal rankers over the same combination identify target-rank regions not covered by a single-ranker view.

The plan freezes three rankers before validation:

- `frequency_based_ranker`
- `structural_ranker`
- `omission_based_ranker`

Each ranker records a version, implementation path, fixed config, and config hash. The ranker list is not selected from observed results.

The feature contract preregisters:

- `rank_mean`
- `rank_median`
- `rank_min`
- `rank_max`
- `rank_std`
- `rank_range`
- `pairwise_rank_gap`
- `ranker_order_entropy`
- `consensus_band`
- `disagreement_band`

Each feature records its formula, pre-target ranker-output inputs, dtype, shape, sort direction, missing-value rule, and implementation path. Target issue results and post-draw updates are explicitly forbidden.

The strata are fixed:

- `low_disagreement`
- `medium_disagreement`
- `high_disagreement`
- `extreme_disagreement`

Thresholds may only come from the search window and must freeze before frozen validation. All strata must report complete results.

## Baselines And Metrics

The plan preserves the approved proposal baseline and adds three matched baseline arms:

- `budget_matched_random`
- `rank_matched_consensus`
- `current_production_ranker`

Every baseline must match candidate count, time window, legal universe, Top-K budget, and fixed seed. Rank distribution matching is preregistered for consensus and best-effort for random controls.

Required metrics include exact target rank, Top 100/1,000/10,000 hits, mean/median/p95/worst rank, reciprocal rank, tail counts, baseline lift, stratum stability, and direction consistency. Additional statistics include paired rank difference, bootstrap confidence interval, permutation null, effect size, and multiple-comparison adjusted p-value.

## Validation And Materialization

`ExperimentPlanValidator` rejects a plan when the proposal is not approved, the proposal fingerprint changes, null or failure condition are rewritten, the baseline is weakened, validation windows shrink, search/frozen/forward windows overlap, candidate and baseline budgets differ, features use future information, rankers or strata become mutable, production writes are allowed, promotion is authorized, resources are not executable, or artifact contracts are incomplete.

`materialize` creates or reuses the Hypothesis family, creates the Hypothesis from the frozen plan, transitions it to `preregistered`, and creates four planned Experiments:

- `ranking_disagreement_feasibility_v1`
- `ranking_disagreement_historical_search_v1`
- `ranking_disagreement_frozen_validation_v1`
- `ranking_disagreement_forward_validation_v1`

No execution or Evidence record is created.

## Interfaces

Worker CLI:

```text
dehps experiment-plan build
dehps experiment-plan validate
dehps experiment-plan show
dehps experiment-plan list
dehps experiment-plan materialize
dehps experiment-plan engineering-request
dehps experiment-plan operator-request
```

`build` and `validate` write nothing. `materialize` creates only the Hypothesis and planned Experiments. `engineering-request` submits an `engineering_experiment_tool` request. `operator-request` creates an `operator_isolated_run` draft only; it cannot be submitted until a completed Engineering tool request exists.

Read-only API:

```text
GET /research-planning/plans
GET /research-planning/plans/:key
GET /research-planning/plans/:key/stages
GET /research-planning/plans/:key/requests
GET /research-planning/status
```

The API exposes no write route.
