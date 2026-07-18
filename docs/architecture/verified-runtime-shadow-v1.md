# Verified Runtime Shadow v1

## Purpose

Forward simultaneous shadow evidence must prove more than equivalent outputs. Both backends must
consume one already verified input identity. The shadow control path is therefore:

```text
effective forward history
          │
          ▼
History Snapshot + expanding Window Artifact
          │
          ├──────── Candidate ABI Package
          │
          ▼
 Runtime ABI Cache / Feature Compiler
          │
          ▼
   VerifiedRuntimePackage
          │ verified_runtime_id
          ├──────────────────────┐
          ▼                      ▼
Feature ABI NumPy       Feature ABI Numba CPU
          │                      │
          └──────────┬───────────┘
                     ▼
          strict shadow comparison
                     │
                     ▼
      official candidate artifact binding
```

The effective history passed to the existing forward scorer is treated as an immutable History
Snapshot and materialized as an expanding Window Artifact. This preserves the exact selected input
boundary without reconstructing a broader history that is not present at the shadow hook.

## Shared-runtime invariant

`execute_feature_abi_shadow_pair(...)` accepts one `VerifiedRuntimePackage`. It prepares and executes
both Feature ABI backends from that object and rejects a result whose telemetry does not carry the
supplied `verified_runtime_id`.

Shadow evidence records:

- `verified_runtime_id`;
- Runtime verification and Feature Runtime digests;
- `runtime_identity_mismatch_count`;
- Runtime ABI Cache key, package and hit/miss receipts;
- both artifact-producing Runtime Envelopes.

The exact comparison includes Runtime identity. A backend can no longer pass solely because it
recomputed equal numeric values from independently interpreted inputs.

## Production boundary

Official forward candidates are generated through the core verified Runtime path with the default
`numpy_reference` selection, which executes `feature_abi_numpy_reference`. The simultaneous shadow
hook reuses the same Runtime compiler/cache identity, executes NumPy reference and Numba CPU from
that sealed package, and binds the reference result back to the already generated rows by strict
candidate id and score comparison.

A shadow compilation, verification, backend, or comparison failure remains a structured warning in
prediction metadata. It cannot replace candidates, block official persistence, enable promotion, or
change the production backend default.

## Cache behavior

The process-local forward shadow cache may reuse Feature tiles and the sealed Runtime identity across
lines only when the complete History/Window/Candidate/Feature key is identical. Every hit still
re-runs Feature ABI and Unified Runtime verification. Different effective histories, target date
contexts, candidate packages, layouts, or feature inputs cannot collide.

## Post-draw replay

Post-draw and post-hoc reconstruction now compile the sealed effective history and canonical
CandidateStore through `RuntimeInputCompiler`, then execute both Feature ABI backends from one
`VerifiedRuntimePackage`. Runtime ABI Cache identity is part of the comparison evidence.

The raw `execute_shadow_pair(...)`, `run_shadow_comparison(...)`, and `KernelPlanner.backend()`
entry points have been removed. Independent backend classes remain available only inside backend
implementation tests and the explicit benchmark oracle. Existing shadow artifacts and pending
predictions are not rewritten.

## Non-goals

- no production backend switch;
- no prediction or candidate regeneration;
- no database schema or runtime-state mutation;
- no scoring, feature, ranking, or evaluation contract change;
- no automatic promotion;
- no GPU/SIMD backend.
