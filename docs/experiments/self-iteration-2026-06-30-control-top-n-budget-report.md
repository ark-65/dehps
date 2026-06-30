# Self-Iteration: Control Experiment Top-N Budget Boundary

Date: 2026-06-30

## Primary Goal

Reject non-positive `top_n` control experiment budgets before producing candidate or null-baseline summaries.

## Non-Goals

- No scoring, strategy, advisor, candidate-source, or promotion-gate changes.
- No change to DEHPS evidence level or prediction/betting language.
- No generated runtime artifacts under `data/output` or `runtime`.

## Change

- `run_control_experiments` now rejects `top_n < 1` before building evaluation summaries.
- `random_same_budget_summary` now rejects invalid budgets instead of producing negative analytical cutoff and expected-hit values.
- Fixed neural candidate loading and fixed candidate-set evaluation now share the same positive `top_n` guard for direct callers.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_control_experiments.py -q
apps/worker-python/.venv/bin/python -m pytest -q
```

Result:

- 9 control-experiment tests passed.
- 330 worker tests passed.

## Guardrail

This is an input-boundary hardening change for frozen control experiments. It does not improve or claim predictive ability; it prevents invalid candidate-budget requests from contaminating baseline/null-model evidence.
