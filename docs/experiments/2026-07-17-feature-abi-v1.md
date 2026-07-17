# Feature ABI v1 Specification - 2026-07-17

## Goal

Freeze the first machine layout for compiled Feature tiles and provide a zero-copy reference compiler
and fail-closed verifier before touching Kernel Planner.

## Non-goals

- No Feature ABI Runtime Migration.
- No NumPy, Numba, scoring, ranking, TopK, or backend-default change.
- No full-universe Feature matrix requirement.
- No production prediction, pending candidate, database, fingerprint, or live operation.

## Implemented

- `feature_abi.v1` layout definition and layout digest.
- Dense little-endian `float64[R,32]`, C-order, canonical nonempty/empty strides, 8-byte alignment.
- Candidate ABI row-range identity with tile size explicitly non-semantic.
- Header, buffer metadata, package digest, and Feature Runtime Envelope projection.
- Zero-copy `FeatureABICompiler` from `CompiledFeatureArtifact`.
- Fail-closed `FeatureABIVerifier` with source Artifact binding.
- Golden buffer, payload, header, and package digests.

## Important boundary

This ABI describes compiled Feature values. It does not move Feature Manifest interpretation into the
Kernel and it does not label the current fused Numba path compliant by convention. Runtime Migration
must establish the verified producer/preflight edge explicitly.

## Validation

Focused tests cover:

- frozen layout and manifest binding;
- zero-copy buffer reuse;
- Golden digest stability;
- deterministic package identity;
- payload, layout, contiguity, and source-binding rejection;
- tile-boundary independence.

Feature-focused result:

```text
24 passed
```

Contract/kernel regression:

```text
81 passed
```

Full worker regression:

```text
1106 passed, 4 existing multiprocessing/fork warnings
```

## Production state

No live operation or database migration is part of this round. Existing production predictions,
2026081 pending runs/candidates, backend defaults, watchdog state, and historical artifacts remain
unchanged.
