# Training observability-only supervisor mode — 2026-07-15

## Round contract

- Primary goal: permit a bounded, full-computation supervisor run that measures real stage timing without modifying durable training, promotion, prediction, or forward-evaluation state.
- Non-goals: no scoring, feature, advisor, budget, neural-capacity, promotion-gate, candidate-filter, or production-data change.
- Execution boundary: `--observability-only` requires `--max-rounds >= 1`; normal supervisor behavior remains the default.

## Safety contract

Observability-only mode disables every known external write surface:

- no training round, line result, best checkpoint, target inversion, or promotion-state database writes;
- no current-candidate or forward-prediction refresh;
- no training-event HTTP posts;
- no schema creation during database seed loading;
- local compact status JSON, Markdown report, and logs remain enabled.

The mode also sets libpq `PGOPTIONS=-c default_transaction_read_only=on` before the first database connection. This is a fail-closed backstop: an overlooked or future PostgreSQL write raises `ReadOnlySqlTransaction` instead of modifying durable state.

Completed stage telemetry is retained in `round_execution_history` for the latest eight rounds, so a two-round run preserves both sets of stage durations in its final status artifact.

## Validation

- Focused supervisor, CLI, telemetry, and persistence-policy tests: 174 passed.
- Python compile checks: passed.
- PostgreSQL guard probe: `transaction_read_only=on`; a dedicated `CREATE TABLE` probe was rejected with `ReadOnlySqlTransaction`; the probe relation was confirmed absent.
- Full Python worker suite: 957 passed.
- Live two-round operator run: pending merge and separate approved Operator execution.

## Acceptance gates for the live run

The isolated run must use the existing 28-configuration baseline and complete exactly two rounds. Acceptance requires:

1. both rounds complete without runtime errors;
2. final status identifies `execution_mode=observability_only` and records every skipped persistence round;
3. stage history reports worker/config/target geometry and elapsed time for both rounds;
4. the existing issue `2026081` forward prediction rows and candidates have the same content fingerprint before and after the run;
5. durable training/promotion/prediction table counts and latest update markers are unchanged, excluding Agent Request audit rows created to authorize the operation.

Only after those checks should a separate research contract choose among a targeted serial-stage repair or controlled 28/48/96, neural-capacity, or inversion-budget experiments.
