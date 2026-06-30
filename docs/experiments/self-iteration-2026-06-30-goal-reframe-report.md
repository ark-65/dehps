# Self-Iteration: Goal Reframe

## Primary Goal

Reframe scheduled DEHPS self-iteration as a private prediction-training maintenance loop that checks live training progress first and uses Gauss/Riemann-style mathematical diagnostics before changing training strategy.

## Non-Goals

- Do not change training, optimization, advisor, candidate-generation, scoring, database, API, or dashboard behavior.
- Do not update `AGENTS.md`, `TASK_PLAN.md`, `PROGRESS.md`, or `docs/agents/*`.
- Do not add a model, advisor, candidate source, or strategy.
- Do not rewrite old self-iteration commits or generated runtime artifacts.

## Change

`scripts/hourly_self_iterate.sh` now instructs the scheduled Codex run to treat DEHPS as a private lottery-prediction training system while keeping all prediction-oriented work evidence-labeled and risk-bounded. The prompt requires each round to start from training progress when possible:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

The prompt also tells the run to inspect the latest `training-supervisor-*.json` and Markdown report before choosing a task. Failure to read watch/supervisor state is treated as an operational problem to fix before broader cleanup.

## Diagnostic Gate

Before changing training strategy, weight bounds, advisor selection, candidate sources, search navigation, or interpreting suspicious lift, the self-iteration prompt now requires local historical math skills:

- `$gauss`: legal sample space, historical window, null baseline, leakage, duplicates, parser/sync failures, residuals, numerical sensitivity, weight bounds, post-hoc thresholds, and proof obligations.
- `$riemann`: search-space structure, candidate diversity, co-occurrence geometry, discrete/continuous transitions, latent-state framing, and local-to-global consistency.
- `$gauss-riemann-dialogue`: task frame, Gauss pass, Riemann pass, disagreement, smallest shared conclusion, and next verification when a fix is plausible but unproven.

These skills are explicitly framed as historical reasoning lenses, not authority claims or mind reconstructions.

## Autonomy Boundary

Self-iteration may repair bugs, improve diagnostics, and adjust existing parameter boundaries or obvious safety constraints in existing strategy logic. It may not add a new model, advisor, candidate source, or large strategy unless a human explicitly requests that direction.

Any accepted change to training, optimization, dynamic weights, advisors, or supervisor code must start a fresh supervisor and monitor at least 1-2 completed rounds before reporting completion.

## Validation

```bash
bash -n scripts/hourly_self_iterate.sh
```

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

```bash
git diff --check
```

## Risk

The change affects only automation instructions and source documentation. It does not prove predictive ability, change model behavior, or alter public interfaces. The main risk is over-aggressive future automation, mitigated by the diagnostic gate, small-round rule, clean-tree guard, and explicit ban on autonomous new models or candidate sources.
