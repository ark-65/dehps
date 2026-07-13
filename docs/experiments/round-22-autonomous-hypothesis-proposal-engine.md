# Round 22: Autonomous Hypothesis Proposal Engine

## Outcome

Round 22 establishes a deterministic, bounded engine that reads formal DEHPS research state, generates twelve preregistration-complete candidates, blocks duplicate/recycled mechanisms and leakage, ranks valid candidates, and submits at most one `research_hypothesis_proposal` Agent Request for human review.

It adds no algorithm to the production ranker, Advisor, Candidate Source, Objective, Promotion rule, training loop, or Supervisor. It creates no Hypothesis or Experiment and executes no proposal. No predictive or betting claim is made.

## Implemented surface

The Worker now includes `research_autonomy` context/evidence readers, 51-feature and ten-mechanism catalogs, a typed proposal schema, six deterministic generators, novelty detection, validation, ranking, orchestration, persistence, and the Round 21 submission adapter. The CLI supports Context build/show and Proposal generate/list/show/submit/validate; generation and validation are dry-run by default.

The API adds exactly four read-only GET endpoints for the latest context reference, proposal list, proposal detail, and inert engine status. There is no API write route.

## Einstein scientific pass

The Einstein reasoning constraint shaped the engine around the smallest falsifiable experiment rather than around a claim of improved prediction:

- Core question: which genuinely distinct, time-isolated mechanism would reduce current uncertainty most?
- Invariant: the legal universe remains exactly all 1,107,568 6-of-33 red-ball combinations, with identical history, candidate budget, compute budget, and rank cutoffs for candidate and null.
- Null: each proposal states the matched-baseline distribution expected when the mechanism contains no information.
- Measurement: exact target rank, Top 100/1,000/10,000, median/worst rank, and rank-tail behavior under expanding walk-forward evaluation.
- Failure: no rank-tail improvement, leakage, budget mismatch, frozen/search overlap, or forward-outcome selection rejects the proposal.
- Self-deception controls: seed/epoch/depth/near-weight/search-round/rename changes are not novelty; sparse hits require sequential-null discipline; frozen diagnostics are not independent forward evidence; implementation is not Evidence.

The smallest next experiment remains only a proposal. Round 22 deliberately stops before Registry creation or execution.

## Isolated smoke

Database: `dehps_round22_smoke`.

The database was initialized from the repository schema, then populated with twenty recent production training-round rows and four isolated rejected-family memory fixtures representing generic structural MLP, neural KDJ interaction, same-history KDJ parameter expansion, and random-split nonlinear separability. Production was read only.

Context construction succeeded from the current repository and formal artifacts:

```text
context fingerprint: 67bdc396e2086eaf49cd9f5591eff2fc9d6313a45b5a6e4cd4e6f9122ffcb70f
candidate proposals: 12
engine version: autonomous-hypothesis-proposal-v1
```

Repeated generation returned the same fingerprint and selected proposal. The selected candidate was the highest-ranked allowed mechanism:

```text
proposal key: auto-ranking_model_disagreement-22432c4a0ea5
mechanism: ranking_model_disagreement
score: 0.878
novel: true
rejected-family reuse: false
validation: 18/18 passed
```

Its null states that ranker-disagreement strata have the same target-rank distribution as budget-matched consensus strata. Its minimal non-null requires a fixed disagreement stratum to change the rank-tail distribution in the same direction on frozen and forward windows. It freezes 100 search issues, 20 disjoint frozen issues, at least 20 paired forward issues, no random split, no hyperparameter sweep, and no outcome-based selection.

Exactly one Request was submitted:

```text
request key: research-proposal-cd134360cc185ab8
request type: research_hypothesis_proposal
role: research
status: submitted
executed: false
```

Pre/post isolated counts prove the submission boundary:

```text
research_hypotheses: 4 -> 4 (rejected-memory fixtures only)
research_hypothesis_experiments: 0 -> 0
agent_request_executions: 0 -> 0
training_round_results: 20 -> 20
submitted proposal requests: 0 -> 1
```

The live API against the isolated database returned HTTP 200 for Context, Proposal list, Proposal detail, and Engine Status. Missing detail returned 404. Engine Status reported `executionStarted=false`, `hypothesisCreated=false`, and `writeRoutesEnabled=false`.

Production database verification returned `production_smoke_proposals=0`. No production Hypothesis, Experiment, Agent Request, execution, training row, or strategy was written. The production Supervisor was not restarted.

## Validation

Baseline from accepted Round 21:

```text
Worker: 792 passed
API: 67 passed
```

Round 22:

```text
cd apps/worker-python
.venv/bin/python -m pytest -q
813 passed in 20.69s

DB_PORT=1 .venv/bin/python -m pytest -q
813 passed in 20.57s

cd apps/api
npm test
73 passed

npm run build
passed
```

Tests cover stable context fingerprints, catalog completeness, rejected-family binding, deterministic generation, exact schema contracts, seed/epoch-only duplicates, rejected-family reuse, random-split and leakage rejection, missing nulls, compute-budget rejection, `selected=None`, submitted-only requests, no Hypothesis/Experiment/execution writes, stable CLI JSON, API pagination/404 behavior, and absence of API write methods.

## Known limitations

- Proposal scoring is a deterministic research-priority heuristic, not empirical Evidence.
- The Context API reports the formal references frozen into the latest submitted Request; it does not rebuild Context through the read-only API process.
- Rejected-family semantic aliases are explicit and auditable; newly named failure families must be added to formal Registry metadata or catalog aliases.
- Generation has six fixed templates and twelve candidates. Expanding it requires another reviewed round and equivalent novelty/leakage tests.
- The isolated Smoke database is retained for audit and can be removed manually after review.

## Next round

Do not execute the selected proposal automatically. A future round may review and preregister it through the existing Hypothesis Registry and Agent authority gates, but must preserve the exact null, same-budget baseline, failure condition, frozen/search isolation, forward minimum, no-promotion boundary, and human review.
