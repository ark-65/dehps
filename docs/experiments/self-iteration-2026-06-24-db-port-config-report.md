# Self-Iteration: DB Port Config Guard

Date: 2026-06-24

## Primary Goal

Keep API startup database configuration from passing invalid `DB_PORT` values through as `NaN`.

## Non-Goals

- No training, scoring, backtest, candidate-generation, or advisor changes.
- No change to DEHPS evidence level or betting/prediction language.
- No broader environment configuration redesign.

## Change

- Added a shared decimal port parser for API config.
- Added `DEFAULT_DB_PORT=54329` and `parseDbPort`.
- Updated the PostgreSQL repository to parse `DB_PORT` with the guarded parser instead of raw `Number()`.
- Added API config tests for valid trimmed DB ports and invalid fallback values.

## Validation

```bash
cd apps/api && npm test
cd apps/api && npm run build
```

Result: 35 API tests passed; API TypeScript build passed.

## Guardrail

This is an operational startup reliability fix. It does not affect historical ranking behavior, strategy selection, candidate generation, or any claim about predictive ability.
