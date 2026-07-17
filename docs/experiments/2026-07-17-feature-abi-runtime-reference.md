# Feature ABI Runtime Reference Migration - 2026-07-17

## Goal

Establish the first explicit Kernel Planner execution path that verifies Candidate ABI and Feature ABI
before score/rank execution, with strict equality against the existing NumPy reference path.

## Non-goals

- No claim that the fused Numba backend is Feature ABI compliant.
- No replacement or slowdown of the existing NumPy/Numba production and research entry.
- No production backend switch, prediction regeneration, pending-candidate rewrite, or database change.
- No Feature formula, score, rank, TopK, Red5, or weight change.

## Runtime edge

```text
Candidate ABI Package
        +
Feature ABI tiles
        |
        v
FeatureABIRuntimeVerifier
        |
        v
KernelPlanner.prepare_feature_abi
        |
        v
FeatureABINumpyReferenceBackend
        |
        v
strict_v1 KernelResult
```

The joint verifier requires:

- a valid Candidate ABI package;
- at least one valid Feature ABI tile;
- every tile bound to the same Candidate package;
- ordered, contiguous, non-overlapping coverage of every Candidate row exactly once;
- one Window Artifact and target context across all tiles;
- one canonical empty tile for an empty Candidate runtime.

The runtime digest covers the Candidate package and ordered Feature tile package identities.

## Execution behavior

The reference backend consumes Feature ABI values directly, applies the existing strict score rounding,
and preserves:

- exact rank counting;
- `score DESC, candidate row id ASC` TopK ordering;
- Red5 selection and exact rank;
- target-excluded behavior;
- chunk/tile-boundary independence.

Telemetry now carries Candidate ABI, Feature Contract/ABI/layout, Window Artifact, target context, and
Feature runtime digests for this explicit execution path.

## Fused backend gate

`KernelPlanner("numba_cpu").prepare_feature_abi(...)` fails with
`feature_abi_backend_not_migrated`. This is intentional: the current fused backend computes components
internally but does not yet expose a verifiable Feature ABI producer. Existing Numba execution remains
available through its prior entry and is not mislabeled as migrated.

## Validation

Focused tests cover:

- exact score/rank/TopK/Red5 equality for multiple Feature tile sizes;
- deterministic runtime identity;
- incomplete coverage, Candidate binding, and context-drift rejection;
- explicit fused-backend rejection;
- prepared-backend mismatch rejection;
- all-score-tied strict row-id ordering.

Feature ABI Runtime focused result:

```text
8 passed
```

Contract/Feature/Kernel regression:

```text
89 passed
```

Full worker regression:

```text
1114 passed, 4 existing multiprocessing/fork warnings
```

## Production state

No live operation was performed. Existing production predictions, 2026081 pending runs/candidates,
backend defaults, watchdog state, and historical artifacts remain unchanged.
