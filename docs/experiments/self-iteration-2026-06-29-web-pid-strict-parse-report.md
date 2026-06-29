# Self-Iteration 2026-06-29 - Web PID Strict Parse

## Primary Goal

Prevent malformed `runtime/logs/web-dashboard.pid` content from being partially parsed as a stale process id in the API service-status view.

## Non-Goals

- Do not change training, optimization, candidate generation, or scoring logic.
- Do not change service-status severity rules beyond the malformed PID boundary.
- Do not add generated runtime artifacts.

## Change

`ResearchService.readPidFile` now accepts only a complete positive decimal PID string. Inputs such as `999999999abc` are treated as unknown PID evidence instead of being truncated to `999999999`.

## Validation

- `cd apps/api && npm test` -> 49 passed
- `cd apps/api && npm run build` -> passed

## Evidence Boundary

This is an operational observability fix. It does not alter DEHPS prediction hypotheses, historical backtests, or betting-oriented outputs.
