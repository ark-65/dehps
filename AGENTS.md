# AGENTS.md - DEHPS Agent Rules

## Project Positioning

DEHPS means Discrete Event Human Plausibility Score, or 离散事件人类合理性评分.

DEHPS is being trained toward a prediction-oriented decision-support system. Betting-oriented recommendations are allowed as a future product direction and as clearly labeled experimental outputs. The current 双色球 red-ball domain is a demo and training space for transparent structural scoring, strategy filters, historical backtests, training diagnostics, and operational reporting.

Core principle:

```text
AI proposes hypotheses. Code verifies them. Historical data judges them.
```

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

## Data, Runtime, And Git Rules

- Do not commit `data/output`, `runtime`, `node_modules`, `.venv`, `dist`, `build`, caches, logs, or other generated runtime artifacts unless the user explicitly asks for a specific small evidence artifact.
- Commit only files that belong to the current round.
- Every accepted code change should be committed and pushed unless the user explicitly says not to.
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
