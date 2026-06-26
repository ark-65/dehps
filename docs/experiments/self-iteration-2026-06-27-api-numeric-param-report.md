# Self-Iteration: API Numeric Parameter Parsing

Date: 2026-06-27

## Primary Goal

Reject non-decimal integer forms in API numeric parameters before they reach service normalization or database lookup.

## Non-Goals

- No training, scoring, candidate-generation, advisor, or strategy changes.
- No change to DEHPS evidence level or prediction/betting language.
- No broad API contract refactor.

## Change

- `ResearchController` now parses numeric query parameters and training round path indexes with a strict decimal-integer guard.
- Inputs such as `1e2`, `0x50`, and `2.5` no longer rely on JavaScript `Number()` coercion.
- Blank query parameters still defer to service defaults, and decimal integers with leading zeroes remain accepted.

## Validation

```bash
cd apps/api && npm test -- --runInBand
```

Result: 44 API tests passed.

## Guardrail

This is an API input boundary hardening change. It does not alter historical ranking behavior, strategy selection, candidate generation, or any claim about predictive ability.
