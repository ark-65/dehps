# Isolated Research Execution

Round 24 adds the first execution lane for a preregistered autonomous experiment. The lane is intentionally narrow: it can run the frozen `ranking_model_disagreement` measurement tool in an isolated database, archive artifacts, and expose read-only execution status. It cannot create Evidence, change Hypothesis status, update production training, change Objective Policy, promote strategies, restart a Supervisor, or run forward validation.

## Control Flow

```text
approved Engineering request
-> Engineering execution completed with implementation artifact contract
-> Reviewer acceptance
-> approved Operator isolated-run request
-> feasibility
-> historical_search
-> frozen_validation
-> artifact validation
-> Operator execution completed
```

The tool verifies the approved Operator request before `run-isolated`. It refuses the default `dehps` database and requires `production_access: false`.

## Worker Surface

The package `dehps.experiments.ranking_disagreement` contains:

- fixed ranker adapters: `frequency_based`, `structural`, `omission_based`;
- `RankMatrix` validation for stable combination order, no missing ranks, and no duplicates;
- frozen disagreement features and search-only strata thresholds;
- budget-matched baselines with exact candidate-count checks;
- deterministic metrics, bootstrap/permutation statistics, and adjusted p-values;
- immutable artifact writing and manifest hash validation;
- CLI commands under `dehps ranking-disagreement`.

Every issue is evaluated using only draws before the target issue. Search thresholds are fit only on the historical search window and then reused unchanged in frozen validation.

## API Surface

The API exposes read-only execution endpoints:

```text
GET /research-execution/runs
GET /research-execution/runs/:id
GET /research-execution/runs/:id/artifacts
GET /research-execution/runs/:id/results
GET /research-execution/status
```

There are no write routes. The API reads Operator Agent Requests and their execution records.

## Artifact Contract

Artifacts are written under:

```text
data/output/research/ranking_model_disagreement/<plan_fingerprint>/
```

Required files:

- `manifest.json`
- `issue_windows.json`
- `ranker_versions.json`
- `strata_thresholds.json`
- `feasibility.json`
- `search_results.json`
- `frozen_results.json`
- `per_issue_results.jsonl`
- `statistics.json`
- `validation_report.json`
- `execution_summary.md`

Each artifact records the plan key, plan fingerprint, hypothesis key, proposal fingerprint, history fingerprint, legal-universe fingerprint, code commit, generation time, and content hash. The manifest records artifact file hashes.

## Safety Boundary

The execution lane is measurement-only. It archives outputs for review but does not interpret the hypothesis outcome. A later Reviewer/Evidence round must decide whether the archived execution is mature enough to become Evidence.
