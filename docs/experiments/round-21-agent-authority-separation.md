# Round 21: Research and Engineering Agent Authority Separation

## Outcome

Round 21 establishes a default-deny authority model for Research, Engineering, Reviewer, and Operator Agents. It adds typed request approval, immutable audit Decisions, frozen approved payloads, execution-time reauthorization, structured handoffs, a human-operated audit CLI, and a read-only API.

It adds no model, algorithm, feature, Advisor, Candidate Source, Objective, Promotion rule, Angular page, LLM provider, multi-Agent dialogue framework, automated research loop, or automatic PR/merge behavior. It did not modify frozen strategy or restart the production Supervisor.

## Authority and lifecycle

Four roles and nineteen actions are centrally defined. Every Role × Action combination is explicit; omitted combinations are denied. No Agent has production strategy promotion authority.

Fourteen request types define initiator, reviewer, executor, minimum risk, required registry links and payload fields, production permission, code-modification permission, and Hypothesis-status permission.

Three additive PostgreSQL tables store requests, append-only Decisions, and executions. Direct status updates require a Repository transaction guard. Each transition and Decision is atomic. Submitted requests cannot be deleted, and any request that has reached approval has a permanently frozen payload.

Execution always re-runs policy authorization against the persisted type, status, risk, environment, and executor role. An Engineering completion does not create Evidence; a failed execution does not change Hypothesis status; and an Operator execution records its environment and run ID.

## Handoff contracts

Research→Engineering `engineering_experiment_tool` requests require the frozen scientific question, input/tool boundaries, baseline, metric, failure condition, non-goals, registry keys, and no production impact.

Engineering may return only implementation/test/interface/artifact/limitation fields. The validator rejects extra conclusion fields and recursively rejects research claims such as accepted/rejected, signal existence, or proven lift.

Engineering→Research remains a new research step. A `research_evidence_submission` must cite a completed `operator_isolated_run` with an audited execution row. A completed engineering implementation cannot be cited directly as Evidence.

## Self-iteration and interfaces

`scripts/hourly_self_iterate.sh` now declares Engineering Agent as its single default role. It requires an approved typed request before non-read work, ends the execution on role change, forbids Research file/Shell/Git work, requires Operator Requests for production operations, and records `no_authorized_agent_request` when no legal task exists.

`AGENTS.md` carries the same durable role rules.

The `dehps agent` CLI supports request create/list/show/submit/review/approve/reject/cancel, execution start/complete/fail, Decision reads, and database-free authorization dry-runs. It emits stable sorted JSON and returns exit code 2 for denied/invalid operations. It performs no Shell, Git, Supervisor, or production action.

The NestJS module exposes five GET-only Agent endpoints with type/status/role/risk/time filters and pagination. Missing records return 404. The public authority endpoint exposes the default-deny matrix and Promotion reservation without credentials.

A live API process against `dehps_round21_smoke` returned HTTP 200 for request list/detail, Decision list, execution list, and authority. The missing request route returned HTTP 404. Parsed JSON preserved payloads, environments, run/execution audit fields, and the `existing_promotion_gate` reservation.

## Isolated smoke

Database: `dehps_round21_smoke`.

The validation completed this role-correct chain:

1. Research created, submitted, and—after Reviewer approval—completed a hypothesis proposal request.
2. A separate human-operated isolated fixture created one Hypothesis and planned Experiment; proposal completion itself created neither.
3. Research submitted a structured experiment-tool handoff; Reviewer approved it; Engineering executed and returned the restricted result contract.
4. Research submitted an Experiment plan; Reviewer approved it.
5. Research submitted an Operator isolated-run request referencing the completed tool; Reviewer approved it; Operator completed it with run ID `r21-smoke-run`.
6. Research submitted an Evidence Proposal referencing that isolated execution; Reviewer moved it to `under_review`.

Final Agent records:

```text
requests: 5
decisions: 20
executions: 3
r21-proposal: completed
r21-tool: completed
r21-plan: approved
r21-run: completed
r21-evidence: under_review
research_hypothesis_evidence: 0
```

Four application-level escalation attempts were rejected: Research executing Engineering work, editing an approved payload, Reviewer executing an Operator run, and Engineering submitting a research decision.

Database negative checks also failed as required:

- direct approved-payload update: `approved agent request payload is frozen`;
- Decision update: `agent request decisions are immutable`;
- submitted Request delete: `submitted agent requests cannot be deleted`.

## Production isolation

Production database `dehps` was read only. `to_regclass('public.agent_requests')` remained `NULL`, and its pre/post `dehps_strategies` count remained 1. Therefore no Round 21 DDL, request, execution, Smoke key, Evidence, or strategy mutation entered production.

This round touched neither training nor supervisor code. In accordance with the explicit non-goal, no production Supervisor was restarted and no live training rounds were required.

## Validation

Baseline from accepted Round 20:

```text
Worker: 756 passed
API: 58 passed
```

Round 21:

```text
cd apps/worker-python
.venv/bin/python -m pytest -q
792 passed in 24.12s

DB_PORT=1 .venv/bin/python -m pytest -q
792 passed in 21.47s

cd apps/api
npm test
67 passed

npm run build
passed
```

The tests cover every Role/Action pair, default denial, isolated/production differences, critical review, request schema, transitions, transaction rollback, Decision append-only behavior, payload freeze, role mismatch, execution reauthorization, handoff contracts, Promotion denial, CLI exit/JSON behavior, single-role self-iteration, API filtering/404s, and absence of API write methods.

## Known limitations

- Roles are asserted domain identities; signed workload authentication is a future integration concern.
- Agent Requests authorize and audit work but do not themselves execute Shell, Git, Supervisor, migration, release, or research-registry mutations.
- The TypeScript public authority matrix mirrors the Python policy for read-only presentation; future action additions must update both and their contract tests.
- Production Agent tables remain intentionally uninitialized pending an explicit reviewed Operator migration request.
- The isolated Smoke database is retained for audit and can be removed manually after review.

## Next round

Do not add autonomous multi-Agent execution by default. A future round may bind authenticated workload identities to these roles or add a reviewed Operator adapter, but it must preserve execution-time authorization, immutable decisions, Hypothesis Registry boundaries, and the existing Promotion Gate.
