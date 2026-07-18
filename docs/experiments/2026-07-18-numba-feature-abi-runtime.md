# Numba Feature ABI Runtime Migration - 2026-07-18

## Primary goal

Close the remaining Kernel trust gap by giving `numba_cpu` an explicit execution path that accepts
only a sealed `VerifiedRuntimePackage` and consumes anonymous Feature ABI buffers without interpreting
Feature names, formulas, History, Window, or domain rules.

## Non-goals

- No production backend switch, shadow promotion, prediction generation, candidate rewrite, database
  migration, or supervisor restart.
- No Feature formula, scoring contract, ranking contract, TopK comparator, weight, model, or Candidate
  ABI change.
- No claim that the older component-producing fused `numba_cpu` path emits Feature ABI tiles.
- No GPU, CUDA, OpenCL, SIMD, or device-resident backend.

## Runtime edge

```text
FeatureABIRuntime
        -> UnifiedRuntimeVerifier
        -> VerifiedRuntimePackage
        -> KernelPlanner("numba_cpu").prepare_feature_abi
        -> FeatureABINumbaCpuBackend
        -> runtime_envelope.v1 / feature_abi_numba_cpu
        -> strict_v1 score + rank + TopK + Red5
        -> artifact_produced payload seal
```

`FeatureABINumbaCpuBackend` receives only `float64[R,32]` values, Candidate masks, weights, and the
Kernel request. Its Numba loop performs score accumulation, eight-decimal rounding, thread-local exact
rank reduction, and Red5 membership. The existing hierarchical `TopKReducer` remains the single
selection and merge implementation.

The Planner binds prepared packages to the concrete ABI backend. Raw runtimes, stale verification
seals, mutable payload drift, Runtime Envelope drift, and cross-backend prepared-package reuse fail
closed.

The older fused `NumbaCpuBackend` remains available through the legacy production/research entry and
is unchanged. This round does not label its internally generated components as Feature ABI.

## Import boundary correction

Standalone Feature Runtime test collection exposed an existing package initialization cycle:
Feature compiler -> scoring contracts -> scoring package -> shadow -> Feature ABI runtime. The shared
kernel-result digest imports are now resolved lazily. This changes no digest or execution semantics and
removes dependence on incidental module import order.

## Validation

Focused Feature ABI Runtime:

```text
24 passed
```

Feature, Candidate ABI, Kernel, TopK, and Shadow regression:

```text
122 passed
```

Complete worker regression:

```text
1168 passed, 4 existing multiprocessing/fork warnings
```

Coverage includes multiple Feature tile plans, one and multiple workers, all-score-tied ordering,
exact rank, TopK, Red5, raw-runtime rejection, verification-seal drift, backend mismatch, Runtime
Envelope reconstruction, and detached payload verification.

## Full legal-space evidence

The integration run used:

- all `C(33,6) = 1,107,568` legal candidates;
- the real History Snapshot through issue `2026081`;
- a rolling 900-draw Window targeting `2026082`;
- five Feature ABI tiles of at most 262,144 rows;
- eight weight configurations;
- exact rank, Top10000, and Red5 with two score passes.

Every backend/worker run produced the same complete result digest:

```text
8d14c40ff14164f8c62c6905da0741dd39958dad5887f26e2aefc8129d1ffd1e
```

| Backend | Workers | Wall s | Kernel s | TopK s | Strict exact |
| --- | ---: | ---: | ---: | ---: | --- |
| Feature ABI NumPy | 1 | 1.854 | 0.083 | 0.138 | yes |
| Feature ABI Numba | 1 | 3.780 | 2.172 | 0.137 | yes |
| Feature ABI Numba | 8 | 1.530 | 0.064 | 0.048 | yes |
| Feature ABI Numba | 16 | 1.611 | 0.054 | 0.049 | yes |

The first one-thread Numba measurement includes JIT compilation. Eight threads are faster than sixteen
on this host. Peak RSS was approximately 769 MiB. Candidate construction took approximately 69.5
seconds and Feature compilation approximately 4.0 seconds; these are control-plane preparation costs,
not Kernel hot-path time.

## Production state

The official backend remains `numpy_reference`. The active research runtime, forward runtime, draw
watcher, prediction runs, candidates, evaluation rows, and production schedule were not changed by
this engineering round. Promotion remains governed by future simultaneous shadow evidence and an
independent Operator approval.
