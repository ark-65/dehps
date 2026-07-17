# Unified Runtime Verifier Integration - 2026-07-17

## Goal

Replace stage-specific trust at the Kernel boundary with one sealed `VerifiedRuntimePackage` produced
by `unified_runtime_verifier.v1`.

## Non-goals

- No production or research default-path migration.
- No fused Numba Feature ABI compliance claim.
- No database migration, historical backfill, or live operation.
- No scoring, ranking, TopK, Red5, Feature formula, or weight change.

## Implemented

- `UnifiedRuntimeVerifier.verify(raw_runtime)` orchestration.
- Immutable `VerifiedRuntimePackage` and deterministic `verified_runtime_id`.
- Verification seal over all Contract, ABI, layout, runtime, and ordered tile identities.
- Revalidation immediately before Envelope compilation and Kernel scoring.
- Kernel Planner and Runtime Envelope Compiler rejection of raw runtime inputs.
- Unified telemetry fields for verifier version, verification digest, and verified runtime id.

## Rejection coverage

- raw runtime passed to Planner or Envelope Compiler;
- invalid package/verifier version;
- malformed or stale verification digest;
- Feature payload mutation after sealing;
- seal reuse with another runtime or tile plan;
- any underlying History, Window, Candidate, or Feature verifier failure.

## Validation

Unified Runtime focused result:

```text
17 passed
```

Contract/Feature/Kernel regression:

```text
98 passed
```

Full worker regression:

```text
1123 passed, 4 existing multiprocessing/fork warnings
```

## Production state

No production prediction, pending candidate, database row, backend default, watchdog state, or
historical Artifact was changed.
