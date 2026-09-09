# AGENTS.md - DEHPS Agent Rules

## Project Positioning

DEHPS means Discrete Event Human Plausibility Score, or 离散事件人类合理性评分.

DEHPS is being trained toward a prediction-oriented decision-support system. Betting-oriented recommendations are allowed as a future product direction and as clearly labeled experimental outputs. The current 双色球 red-ball domain is a demo and training space for transparent structural scoring, strategy filters, historical backtests, training diagnostics, and operational reporting.

Core principle:

```text
AI proposes hypotheses. Code verifies them. Historical data judges them.
```

## Permanent Training Mainline Integration Rule

For every training, research, feature, model, evaluation, statistical, synthetic,
walk-forward, resampling, forward-evidence, gate, or automatic-decision change:

```text
Capability complete != code complete.
```

The capability is complete only after the current canonical Goal, Task DAG,
dependency resolver, Ready Queue, unified Research Evidence Supervisor,
immutable execution/artifact records, status projection, downstream consumer,
and deterministic replay have all used it successfully. A Python module, CLI,
test, config, report, manual run, or merged PR alone is not completion.

- Every task must declare its Goal, Ready condition, runner, upstream artifacts,
  downstream artifacts, status projection, Evidence rule, decision consumer,
  and next consumer before implementation.
- Executable training tasks move through `CODE_COMPLETE`,
  `INTEGRATION_PENDING`, `INTEGRATED`, `VALIDATED_IN_MAINLINE`, and `COMPLETE`.
- A task with no downstream consumer, no successful mainline execution fact, or
  no replay proof is `INTEGRATION_PENDING`, never `COMPLETE`.
- The minimum proof is:
  `Goal -> Resolver -> Ready Queue -> Supervisor -> Capability -> Artifacts ->
  Status -> Next Task`.
- The canonical implementation must be singular. Manual CLI and legacy runners
  may inspect or replay, but may not be a competing completion path.
- When an `INTEGRATION_PENDING` mainline capability exists, integrate it before
  adding another same-level capability.
- Every final training report must include the integration matrix and answer:
  `YES — validated by unified mainline execution and replay`, or
  `NO — INTEGRATION_PENDING`.

The complete binding contract and acceptance matrix are in
`docs/architecture/training-mainline-integration-governance.md`.

### Control-layer refactor scope (owner-authorized 2026-09-09)

For the bounded R0–R5 roadmap in
`docs/architecture/control-layer-refactor-roadmap-20260909.md`, apply the
control-domain acceptance clarification in the governance contract. Keep the
Goal -> Resolver -> Ready Queue -> Supervisor -> Artifacts -> Status -> Next Task
proof, but validate independent experiment/observation capabilities in their own
authorized control domain. Record offline integration, release readiness,
deployment, business-cycle acceptance, and scientific conclusions separately.
Unrelated historical mail failures do not block an isolated engineering result.

The owner's direct continuing authorization is recorded in
`docs/experiments/2026-09-09-control-layer-refactor-checkpoint.md`. It authorizes
this bounded development, its necessary isolated engineering tests, ordinary
fixes, documentation, and reviewable PRs, including these rule clarifications.
For this scope, do not require the owner to repeat that authorization or fabricate
an approved lifecycle Request to represent it. Record it as owner consent, never
as independent Reviewer approval. This is a task-specific authorization, not a
general bypass in the runtime authorization policy. Check scope and revocation
before continuing; preserve platform protections and independent review.

Refresh only the changed control domain's execution process. An independent
experiment must not restart Formal P3. Formal P3 may remain on a fixed legacy
release during its frozen contract; report this explicitly as retained legacy
execution. V11 remains archived and unschedulable. Production changes require
a concrete reviewed release/rollback package and authorized Operator execution;
engineering PR acceptance alone is not deployment approval or evidence.

## Mandatory Report Integrity And Continuity Gate

Every development task must preserve the completeness and continuity of
prediction and post-draw reports. This applies even when no report file is
changed: database/schema locks, shared worker code, frozen source bindings,
dependency dispatch, status projection, consumers, timers, and delivery can
affect reports indirectly.

- Before implementation, record the expected issues and deadlines, the current
  report-chain state, and the direct and indirect impact of the proposed change.
- Before release, validate the affected canonical report path and its failure
  handling in isolation. Check frozen source compatibility; do not rewrite
  historical source contracts merely to make validation pass.
- Before declaring completion, record before/after evidence for the exact issue:
  prediction sealed before the draw, complete registered report and input
  provenance, deterministic replay, readable downstream output, delivery ledger,
  and enabled timers with the next expected trigger. Updated runtime paths need
  a fresh canonical execution under the accepted commit.
- Tests passing, a merged PR, a zero service exit code, or `ALREADY_SENT` for an
  older issue never proves the current issue's report is complete or delivered.
  Unresolved report regressions or missing acceptance evidence block completion.
- A future scheduled delivery is `PENDING_DELIVERY`, never delivery acceptance.
  A missed pre-draw deadline remains an explicit gap; never manufacture a past
  prediction, report success, or hypothetical realized return to close it.
- Preserve original artifacts, failed events, and delivery records. Production
  recovery and resends still require their existing authorization; validation
  does not authorize test mail or duplicate delivery.
- Every final development report must include a report-impact verdict and the
  evidence required by the [report integrity acceptance contract](docs/architecture/training-mainline-integration-governance.md#report-integrity-and-continuity-acceptance).
  `NO_RUNTIME_IMPACT` is allowed only with a concrete dependency and diff audit,
  not merely because the change is described as documentation or research.

## Development Rules

- Work in staged, reviewable rounds.
- Each round must have one primary goal, explicit non-goals, relevant validation, and a human-readable report when the change affects project behavior or operations.
- Do not add new algorithms, models, or strategies during consolidation or acceptance rounds.
- Prefer small reversible changes over broad refactors.
- Start by checking `git status --short`. If the tree is dirty, stop and report the blocker unless the user explicitly asks to work with those changes.
- Never overwrite user changes, generated evidence, or runtime state without explicit instruction.
- If a task cannot be completed, report the blocker, command output, and next step. Do not pretend completion.

## Validation Commands

Use the smallest sufficient validation for the touched surface:

```bash
apps/worker-python/.venv/bin/python -m pytest -q
cd apps/api && npm test
cd apps/web && npm test
cd apps/web && npm run build
```

If dependencies are missing, install them using the project-local instructions first. If validation still fails because of environment limits, record the exact failure and the next recovery step.

During rapid DEHPS training exploration, favor live program validation over broad unit-test churn:

- After code changes to training, optimization, dynamic weights, or advisors, start the updated supervisor promptly and monitor at least 1-2 completed training rounds.
- Treat the round as incomplete until the new run has produced round output without runtime errors.
- Defer broad unit-test rewrites during fast iteration. Add or update tests only for critical leakage boundaries, crash reproducers, or when stabilizing a feature for acceptance.
- If the live run errors, fix the runtime failure first, then restart a fresh supervisor and monitor again.

When model training or optimization appears to diverge, stall, collapse into one candidate family, or produce suspicious jumps, bring in the local historical math skills as a diagnostic constraint before changing strategy logic:

- Use `$gauss` for exact checks: legal sample space, null baseline, leakage, duplicate combinations, residuals, numerical sensitivity, weight bounds, and proof obligations.
- Use `$riemann` for structural checks: whether the search space, candidate diversity, co-occurrence geometry, continuity/discrete transitions, or latent state representation is being framed incorrectly.
- Use `$gauss-riemann-dialogue` for cross-review when a fix looks plausible but unproven; record the Gauss pass, Riemann pass, disagreement, smallest shared conclusion, and next verification in the round report or supervisor notes.
- Do not promote a new weight, advisor, candidate source, or training heuristic from these skills until code and live historical rounds verify it against the same baseline/null-model discipline.

## Data, Runtime, And Git Rules

- Do not commit `data/output`, `runtime`, `node_modules`, `.venv`, `dist`, `build`, caches, logs, or other generated runtime artifacts unless the user explicitly asks for a specific small evidence artifact.
- Commit only files that belong to the current round.
- Every accepted code change should be committed and pushed unless the user explicitly says not to.
- Publish accepted changes through a ready-for-review PR, never a draft PR, unless the user explicitly requests a draft.
- After opening a ready PR, enable GitHub auto-merge with the repository's normal merge method. If checks, branch policy, or GitHub configuration prevent auto-merge, report the exact blocker instead of merging manually, except for the exhausted-CI-quota case below.
- GitHub CI free quota is currently exhausted. When GitHub explicitly reports that a job was not started because Actions quota, spending limit, or account billing prevented runner allocation, treat that as infrastructure unavailability rather than a test failure. Run the smallest sufficient local unit-test and validation commands for the changed surface; if they pass, immediately merge the ready PR with the repository's normal merge method without waiting for GitHub CI or asking for renewed permission. Record the GitHub annotation, local commands, and results. This exception never applies when a runner started and reported a code, test, lint, build, policy, or review failure.
- After a training, optimization, worker-runtime, or supervisor change is accepted, do not continue relying on an older live training process. Start a fresh training supervisor with the updated code and arguments, then record the new run id before reporting completion.
- Reports under `docs/experiments/` are source evidence and may be committed when they are the intended round artifact.

## Component Responsibilities

- Python worker (`apps/worker-python`): combination generation, structural feature calculation, crawling/syncing, storage integration, backtesting, training diagnostics, candidate artifacts, and experiment reports.
- NestJS API (`apps/api`): read-only research and training-status APIs, database normalization, websocket status delivery, and service-level API contracts for the dashboard.
- Angular Web (`apps/web`): operational dashboard, experiment review, comparison views, distribution charts, training status, report browsing, and evidence-labeled prediction or betting-oriented language when the feature requires it.
- PostgreSQL (`infra/postgres`): durable history, strategy, experiment, sync, pipeline, training, and candidate tables.
- Redis (`docker-compose.yaml`): reserved infrastructure for future queue or orchestration work.

## Codex Self-Iteration Rules

- Self-iteration must be conservative and auditable.
- Every self-iteration must declare exactly one current role. The default is Engineering Agent.
- A single self-iteration may not combine Research, Engineering, Reviewer, or Operator authority. A role change ends the current execution and requires a new typed Agent Request.
- Non-read Engineering work requires an approved `engineering_*` request and execution-time reauthorization. An unapproved request is not permission to act.
- Research Agent may define research contracts and submit research requests, but may not modify files, run Shell, create commits or PRs, operate infrastructure, or directly change Hypothesis status.
- Engineering Agent may implement an approved contract, but may not create hypotheses, change null/failure conditions, add Evidence, or decide research outcomes.
- Reviewer may approve or reject requests and append audit Decisions, but may not execute or modify the reviewed work.
- Operator may execute an approved isolated or production operation, but may not change its research definition, algorithm, or conclusion.
- Any production operation requires an approved Operator Request. No Agent receives production strategy promotion authority; the existing Promotion Gate remains authoritative.
- When no legal approved request exists, stop and record `no_authorized_agent_request` rather than broadening the task or role.
- Automated runs must check for a clean working tree before changing files.
- Prefer fixing test failures, obvious bugs, broken docs, startup errors, and observability gaps before broader cleanup.
- Do not create speculative algorithms or promote experimental outputs during self-iteration.
- If no safe improvement exists, stop and record why.

## DEHPS Prediction And Betting Guardrails

- Keep the legal sample space and historical window explicit.
- Compare filters against a baseline or null model when making performance claims.
- Experimental results may be presented as predictive signals or candidate predictive ability, but they must include training status, evidence level, failure cases, and uncertainty.
- Treat historical lift as evidence for a prediction hypothesis, not by itself as proof that the training target has been reached.
- Betting advice is allowed only when it is clearly tied to the current evidence level and risk language; do not present immature training output as guaranteed or settled.
- Check leakage, duplicate combinations, parser errors, sync errors, and post-hoc threshold selection before trusting surprising results.
- Report missed issues and failure modes alongside successful metrics.
