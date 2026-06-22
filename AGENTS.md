# AGENTS.md - DEHPS Agent Rules

## Project Positioning

DEHPS means Discrete Event Human Plausibility Score, or 离散事件人类合理性评分.

This project is not a lottery prediction system, does not provide betting advice, and must not package experimental results as predictive ability. The current 双色球 red-ball domain is a demo space for studying transparent structural scoring, strategy filters, historical backtests, training diagnostics, and operational reporting.

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

## Data, Runtime, And Git Rules

- Do not commit `data/output`, `runtime`, `node_modules`, `.venv`, `dist`, `build`, caches, logs, or other generated runtime artifacts unless the user explicitly asks for a specific small evidence artifact.
- Commit only files that belong to the current round.
- Every accepted code change should be committed and pushed unless the user explicitly says not to.
- Reports under `docs/experiments/` are source evidence and may be committed when they are the intended round artifact.

## Component Responsibilities

- Python worker (`apps/worker-python`): combination generation, structural feature calculation, crawling/syncing, storage integration, backtesting, training diagnostics, candidate artifacts, and experiment reports.
- NestJS API (`apps/api`): read-only research and training-status APIs, database normalization, websocket status delivery, and service-level API contracts for the dashboard.
- Angular Web (`apps/web`): operational dashboard, experiment review, comparison views, distribution charts, training status, and report browsing without predictive or betting language.
- PostgreSQL (`infra/postgres`): durable history, strategy, experiment, sync, pipeline, training, and candidate tables.
- Redis (`docker-compose.yaml`): reserved infrastructure for future queue or orchestration work.

## Codex Self-Iteration Rules

- Self-iteration must be conservative and auditable.
- Automated runs must check for a clean working tree before changing files.
- Prefer fixing test failures, obvious bugs, broken docs, startup errors, and observability gaps before broader cleanup.
- Do not create speculative algorithms or promote experimental outputs during self-iteration.
- If no safe improvement exists, stop and record why.

## DEHPS Scientific Guardrails

- Keep the legal sample space and historical window explicit.
- Compare filters against a baseline or null model when making performance claims.
- Treat historical lift as a diagnostic result, not proof of future predictive power.
- Check leakage, duplicate combinations, parser errors, sync errors, and post-hoc threshold selection before trusting surprising results.
- Report missed issues and failure modes alongside successful metrics.
