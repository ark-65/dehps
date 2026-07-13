# Round 23: Autonomous Experiment Planning And Preregistration

## Outcome

Round 23 establishes a deterministic planning layer that converts an approved autonomous research proposal into a frozen experiment contract. It supports the first selected Round 22 mechanism, `ranking_model_disagreement`, and stops before implementation, execution, Evidence, production training, Objective, Promotion, Supervisor, or betting-advice changes.

The implemented flow is:

```text
approved research_hypothesis_proposal
-> ExperimentPlan build and validation
-> preregistered Hypothesis
-> four planned Experiments
-> submitted Engineering request
-> draft Operator request
```

No experiment is run by this round.

## Implemented Surface

The Worker adds `dehps.research_planning` with typed plan models, deterministic fingerprinting, approved proposal reading, a ranking-disagreement protocol builder, resource and artifact contracts, implementation and execution request contracts, validation, Registry materialization, and a high-level service.

The CLI adds:

```text
dehps experiment-plan build
dehps experiment-plan validate
dehps experiment-plan show
dehps experiment-plan list
dehps experiment-plan materialize
dehps experiment-plan engineering-request
dehps experiment-plan operator-request
```

`build` and `validate` are dry-run. `materialize` creates a Hypothesis and planned Experiments only. `engineering-request` submits a Research-to-Engineering request. `operator-request` creates a draft isolated-run request and does not submit or execute it.

The API adds five read-only endpoints under `/research-planning`. It reads materialized plan records from Hypothesis metadata, planned Experiment records, and plan-linked Agent Requests. There is no API write route.

## Einstein Scientific Pass

- Core question: do fixed ranker disagreements identify target-rank regions a single ranker fails to cover?
- Invariant: the legal universe is the same 1,107,568 red-ball combinations for candidate and baseline arms.
- Null: under identical candidate budget and rank distribution, disagreement strata and matched baselines have no systematic target-rank distribution difference.
- Measurement: exact target rank, Top bands, rank-tail metrics, baseline lift, stability, direction consistency, paired differences, confidence intervals, permutation nulls, effect sizes, and adjusted p-values.
- Failure mode: leakage, dynamic ranker selection, frozen/forward threshold edits, best-stratum-only reporting, single-issue dependence, budget mismatch, weakened baseline, or forward sample below 20 issues.
- Next experiment: Engineering must implement only the isolated measurement tool, then Operator may run it only after Engineering completion and review.

## Protocol Freeze

The `ranking_model_disagreement` protocol freezes:

- rankers: frequency-based, structural, and omission-based rankers;
- features: rank mean/median/min/max/std/range, pairwise gaps, ranker-order entropy, consensus band, and disagreement band;
- strata: low, medium, high, and extreme disagreement;
- baselines: budget-matched random, rank-matched consensus, and current production ranker;
- windows: 100 search issues, 20 disjoint frozen issues, at least 20 future forward issues, expanding mode, and no random split;
- stage order: feasibility, historical search, frozen validation, forward validation, and decision review.

The plan requires frozen validation before forward validation and complete reporting for all strata and baselines.

## Validation

Automated validation:

```text
cd apps/worker-python
.venv/bin/python -m pytest -q
835 passed in 20.65s

DB_PORT=1 .venv/bin/python -m pytest -q
835 passed in 21.75s

cd apps/api
npm test
79 passed

npm run build
passed
```

Isolated smoke database: `dehps_round23_smoke`.

The smoke initialized schema, submitted and Reviewer-approved a Round 22 `ranking_model_disagreement` proposal, built the Round 23 plan, validated it, materialized it, submitted Engineering, and created the Operator draft:

```text
proposal request: research-proposal-65887d9b99bfbba0
proposal status: approved
proposal key: auto-ranking_model_disagreement-1bf87b0c0493
plan key: plan-auto-ranking_model_disagreement-1bf87b0c0493-v1
plan fingerprint: ab9c47ce344691fd73767d903dcd181898937b9297fd2d2b9ea61c823432a356
plan validation: 20/20 passed
hypothesis status: preregistered
planned experiments: 4
engineering request: engineering-experiment-tool-ab9c47ce344691fd, submitted
operator request: operator-isolated-run-ab9c47ce344691fd, draft
executions: 0
evidence: 0
```

Live API smoke against `dehps_round23_smoke` returned HTTP 200 for all five `/research-planning` GET routes and HTTP 404 for a missing plan. The temporary API process used `API_PORT=3023` and was stopped after verification.

## Known Limits

- The plan records symbolic issue-range boundaries from the approved proposal context; concrete issue lists are an Engineering implementation responsibility and must be emitted as artifacts before execution.
- The Operator request is intentionally draft-only until Engineering produces a completed tool request.
- The plan is a preregistration contract, not Evidence that `ranking_model_disagreement` works.
