# Ranking Contract Provenance Acceptance

## Goal

Make the ranking contract part of the prediction/evaluation evidence chain without modifying the three pending 2026081 prediction runs, their 30,000 candidates, or any historical fingerprint.

## Non-goals

- no Kernel P2 or TopK performance work;
- no prediction rerun;
- no candidate, model, weight, feature, or filter change;
- no production backend switch;
- no historical backfill.

## Root cause

The strict TopK fix changed the formal total-order contract, but the durable prediction schema had no field that distinguished old score-only boundary selection from `strict_v1`. Evaluation, status, API, and exports therefore could not prove which ranking semantics produced a candidate set. The previous `config_hash` also represented model configuration, not the full production prediction identity.

## Baseline before migration

- latest history: 3477 rows, issue `2026080`;
- forward prediction runs: 3, all pending for `2026081`;
- durable candidates: 30,000;
- forward evaluation runs: 0;
- run digest: `43a46ddbf69f9fc571794b8a6dec1770`;
- candidate digest: `ff08616a719209319920a39578379a20`.

The digests cover the original run identity/status/config/timestamp fields and every prediction-run/rank/red-number/score candidate tuple respectively.

## Implementation

- centralized `legacy_score_partition` and `strict_v1` definitions and normalization;
- nullable provenance columns on current candidates, forward predictions, forward evaluation runs, and persisted prediction evaluations;
- explicit `strict_v1` enforcement for every new formal prediction;
- additive production `prediction_fingerprint` with a partial unique index;
- per-run evaluation inheritance and persistence;
- normalized propagation through audit, exports, CLI, watchdog, research, API, telemetry, and promotion;
- mixed-contract promotion rejection;
- a future shadow-report schema with zero-difference fields and a dedicated contract-difference classification;
- an idempotent, no-backfill migration entry point.

## Validation

- Python full suite: `1035 passed`, 4 existing multiprocessing fork deprecation warnings;
- API suite: `111 passed`;
- API TypeScript build: passed;
- Web suite: `18 passed`;
- Angular production build: passed;
- focused provenance/watch/kernel suite: `208 passed`.

## Production acceptance

The schema migration and post-migration state digest check are performed as a separate approved Operator execution. The required invariant is:

- the three 2026081 rows remain stored with null `ranking_contract` and read as `legacy_score_partition`;
- no `prediction_fingerprint` is backfilled;
- all 30,000 candidate rows and scores remain unchanged;
- no evaluation is created;
- statuses and timestamps remain unchanged.
