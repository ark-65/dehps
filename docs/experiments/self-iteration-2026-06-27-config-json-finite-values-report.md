# Self-Iteration: Config JSON Finite Values

Date: 2026-06-27

## Primary Goal

Reject non-finite numeric values in manually supplied `FrequencyRankerConfig` JSON before they can be clamped into training or experiment inputs.

## Non-Goals

- No training, scoring, candidate-generation, advisor, or strategy changes.
- No change to DEHPS evidence level or prediction/betting language.
- No broad config schema refactor.

## Change

- Added a shared finite-number parser for `FrequencyRankerConfig` JSON overrides.
- Applied it to frozen control experiment config JSON, dynamic KDJ base config JSON, neural KDJ advisor base config JSON, and weight KDJ signal base config JSON.
- Values such as `NaN`, `Infinity`, `-Infinity`, and booleans are rejected instead of being silently coerced or clamped.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_control_experiments.py apps/worker-python/tests/test_dynamic_kdj_backtest.py apps/worker-python/tests/test_neural_kdj_advisor.py apps/worker-python/tests/test_generate_weight_kdj_signals.py -q
apps/worker-python/.venv/bin/python -m pytest -q
```

Result:

- 29 focused tests passed.
- 289 worker tests passed.

## Guardrail

This is an experiment input-boundary hardening change. It does not alter historical ranking behavior, strategy selection, candidate generation, or any claim about predictive ability.
