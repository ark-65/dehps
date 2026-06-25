# Self-Iteration Report: Unhandled Rejection Service Status

Date: 2026-06-25

## Primary Goal

Make the API service-status view flag Node `UnhandledPromiseRejectionWarning` log lines as operational failures.

## Non-Goals

- No training, scoring, backtest, candidate-generation, or advisor logic changes.
- No generated `data/output` or `runtime` artifacts are promoted.
- No change to DEHPS evidence level, prediction claims, or betting language.

## Change

`apps/api/src/research.service.ts` now treats unhandled Promise rejection log lines as recent errors when deriving service health. The existing zero-error summary filter and recovery-line handling remain unchanged.

`apps/api/test/research.service.test.ts` adds a service-status regression case for a web dashboard log containing `UnhandledPromiseRejectionWarning`.

## Validation

Focused validation:

```bash
cd apps/api && npm test
cd apps/api && npm run build
```

Result: API tests passed (`40` tests), and TypeScript build passed.

## Guardrail

This is an operational observability fix only. It does not alter historical ranking behavior, structural scoring, candidate generation, strategy selection, or any claim about predictive ability.
