# Runtime Envelope v1 Core Integration - 2026-07-17

## Goal

Create a standalone, fail-closed Runtime Envelope for the explicit Feature ABI KernelResult path and
bind the complete History→Window→Candidate→Feature→Scoring→Ranking execution identity.

## Non-goals

- No historical or 2026081 prediction backfill.
- No production/research default backend change.
- No database migration or live operation.
- No fused Numba compliance claim and no Evaluation Contract definition.

## Implemented

- `runtime_envelope.v1` immutable value object and canonical digest.
- Sequential runtime state machine from `compiled_abi` through `artifact_produced`.
- Runtime Envelope Compiler and fail-closed Verifier.
- Full ContractRef serialization and fail-closed `from_dict()` reconstruction.
- Required full code commit and explicit backend binding.
- Detached KernelResult payload digest and verification.
- Runtime Envelope fields and digest in Feature ABI telemetry and KernelResult.
- Explicit History Snapshot value in Feature ABI Runtime, with History/Window cross-verification.
- Optional Evaluation Contract slot reserved as null until Evaluation Contract v1.

## Rejection coverage

- invalid or skipped state transitions;
- final state without payload digest;
- invalid code commit;
- missing or stale serialized Envelope digest;
- History/Window snapshot mismatch;
- Candidate, Feature, runtime, or backend binding drift;
- detached TopK/result payload mutation.

## Validation

Runtime Envelope/Feature Runtime focused result:

```text
13 passed
```

Contract/Feature/Kernel regression:

```text
94 passed
```

Full worker regression:

```text
1119 passed, 4 existing multiprocessing/fork warnings
```

## Production state

No live state was changed. Existing production predictions, 2026081 pending runs/candidates, backend
defaults, watchdog state, database rows, and historical artifacts remain unchanged.
