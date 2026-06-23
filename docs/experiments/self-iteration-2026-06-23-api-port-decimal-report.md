# Self-Iteration: API Port Decimal Parsing

Date: 2026-06-23

## Primary Goal

Tighten API startup port parsing so `API_PORT` accepts only plain decimal digit strings after trimming whitespace.

## Non-Goals

- No training, scoring, backtest, candidate-generation, or advisor changes.
- No change to DEHPS evidence level or betting/prediction language.
- No broad API configuration refactor.

## Change

- `parseApiPort` now rejects non-decimal numeric forms such as `0x10` and `1e3` instead of accepting JavaScript `Number()` coercions.
- API config tests now cover trimmed valid values and rejected non-decimal values.

## Validation

```bash
cd apps/api && npm test
```

Result: 30 tests passed.

## Guardrail

This is an operational startup reliability fix. It does not affect historical ranking behavior, strategy selection, or any claim about predictive ability.
