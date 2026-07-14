# Round 25: Autonomous Evidence Evaluation And Hypothesis Decision

## Goal

Round 25 establishes the post-experiment research loop:

```text
completed Experiment
-> formal artifact validation
-> Evidence generation
-> statistical review
-> Decision Draft
-> Reviewer approval
-> Hypothesis Registry update
```

This round does not add models, features, candidate sources, training changes, Objective changes, Promotion changes, production training, new experiments, or PR automation.

## Implemented Surface

Worker package:

```text
apps/worker-python/dehps/research_evidence/
```

CLI:

```text
dehps evidence build
dehps evidence show
dehps evidence aggregate
dehps decision draft
dehps decision review
dehps decision approve
dehps decision reject
```

API:

```text
GET /research-evidence
GET /research-evidence/:key
GET /research-decisions
GET /research-decisions/:key
GET /research-review/status
```

## Scientific Guardrail

Einstein pass:

- Core question: can completed experiment artifacts be converted into formal evidence without hidden post-hoc interpretation?
- Invariant: Evidence must cite immutable artifact hashes, plan fingerprints, hypothesis identity, metric values, and Registry Evidence IDs.
- Null: without forward/future coverage or adjusted statistical support, the correct autonomous decision is not acceptance.
- Measurement: baseline lift, effect size, bootstrap confidence interval, permutation p-value, adjusted p-value, Top-K hits, rank/tail metrics, direction consistency, heterogeneity, and forward coverage.
- Failure mode: reading Markdown, prompt reasoning, stale artifacts, mismatched hashes, missing Evidence IDs, or changing Registry state without Reviewer approval.
- Next experiment: future rounds may use approved decisions to plan the next research question, but Round 25 stops after Registry update.

## Validation

```text
cd apps/worker-python
.venv/bin/python -m pytest -q
857 passed in 20.32s

DB_PORT=1 .venv/bin/python -m pytest -q
857 passed in 20.78s

cd apps/api
npm test
91 passed

npm run build
passed
```

## Isolated Smoke

Target database:

```text
dehps_round25_smoke
```

Required smoke flow:

```text
read Round 24 artifact directory
build Evidence
aggregate Evidence
draft Decision
Reviewer approve
Registry transition
verify Evidence append
verify Decision append
verify Hypothesis status update
verify Family status
verify production database has no Round 25 writes
```

Smoke result:

```text
artifact validation: valid
metric observations: 12
Evidence appended: 12
aggregation direction: neutral
aggregation strength: insufficient
forward coverage: 0
family rejection suggested: false
Decision Draft: inconclusive
Decision request: decision-draft-auto-ranking_model_disagreement-1bf87b0c0493-27f2b5c5ae6885df
Decision request status after approval: completed
Hypothesis status: inconclusive
Family status: active
Evidence rows: 12
Agent decision execution: completed
```

Production isolation checks against database `dehps`:

```text
prod_round25_evidence: 0
prod_round25_decision_requests: 0
prod_round25_hypothesis: 0
```

## Expected Round 24 Decision Shape

Round 24 completed feasibility, historical search, and frozen validation, but forward validation remained planned. Round 25 therefore should treat the Round 24 result as formal Evidence and should draft an `inconclusive` decision unless later forward/future Evidence is appended.

The isolated smoke followed this expected shape: the completed Round 24 frozen artifacts became formal Evidence, but the absence of forward coverage prevented acceptance or family rejection.
