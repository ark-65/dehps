# Runtime Input Compiler v1

## Purpose

`runtime_input_compiler.v1` is the shared control-plane boundary between effective domain history and
kernel execution. Production prediction, walk-forward ranking, weight-grid evaluation, Red5 audit,
and simultaneous shadow now converge on:

```text
effective HistoryDraw sequence
          │
          ▼
History Snapshot Contract
          │
          ▼
effective expanding Window Artifact
          │                    Candidate ABI Package
          └─────────────┬──────────────┘
                        ▼
              Runtime ABI Cache
                        │
                        ▼
              Feature ABI packages
                        │
                        ▼
             Unified Runtime Verifier
                        │
                        ▼
              VerifiedRuntimePackage
                        │
                        ▼
                 Kernel Planner
```

The compiler is a control-plane component. It understands canonical history records and Window
semantics; kernels do not.

## Effective-history rule

Callers already select expanding or rolling training history before scoring. The compiler freezes
that exact selected sequence as a History Snapshot and materializes an expanding Window over the
whole effective snapshot. It never reconstructs unavailable earlier draws or guesses a caller's
selection policy.

When the target issue is known, it is part of `WindowSpec` and must be strictly later than every
selected issue. Production next-candidate and training target workers pass it explicitly. A missing,
noncanonical, duplicated, unsorted, or leaking issue fails closed; the compiler never pads, reorders,
casts, or repairs history.

## Shared cache identity

The process-wide compiler owns the existing bounded `RuntimeABICache`. Production scoring and its
simultaneous shadow hook therefore reuse one Feature ABI payload and one `verified_runtime_id` when
History, Window, target context, Candidate ABI, Feature Contract, compiler version, and tile ranges
are identical.

Cache reuse is not trust reuse. Feature ABI and Unified Runtime verification still execute on every
hit.

## Core caller migration

`optimization.walk_forward._kernel_score_rank` is the common scoring convergence point for:

- official next-candidate TopK generation;
- fixed and rolling walk-forward target ranks;
- Red5 nearest-combination audit;
- training prefilter and full configuration evaluation;
- weight-grid consumers built on these functions.

It no longer calls `KernelPlanner().backend().prepare(CandidateStore)`. It compiles the Runtime input,
passes only the sealed package to `prepare_feature_abi(...)`, and executes the selected Feature ABI
backend. `DEHPS_SCORING_BACKEND` still defaults to `numpy_reference`; the corresponding executed
backend is now `feature_abi_numpy_reference`. Explicit `numba_cpu` selects
`feature_abi_numba_cpu` from the same ABI contract.

## Telemetry

The ranked-universe cache record now carries:

- History Snapshot and Window Artifact identities;
- Runtime ABI Cache receipts;
- `verified_runtime_id` and verification digest;
- Feature Runtime, Candidate ABI, scoring and ranking identities;
- artifact-producing Runtime Envelope telemetry.

## Compatibility boundary

Raw `execute_shadow_pair(...)`, `run_shadow_comparison(...)`, and the low-level
`KernelPlanner.backend()` accessor have been removed. Post-draw replay, production, walk-forward,
training evaluation, simultaneous shadow, and FullScore research all enter through verified Runtime
inputs. A source-boundary test prevents application modules from importing the old raw execution
surface.

The separate full-score-grid research path is represented by `full_score_grid_artifact.v1`; it
consumes the same verified Runtime input but produces a candidate-major full-score Artifact rather
than pretending that a full matrix is a TopK `KernelResult`.

Independent raw backend classes and reference formulae remain restricted to backend implementation
tests and `scripts/benchmark_scoring_kernel.py`; they are not scheduler or application entry points.

Planner, Envelope, and FullScore nested verification now uses
[`runtime-verification-session.v1`](runtime-verification-session-v1.md): one full payload check at
entry and one at exit, with no time- or identity-based trust lease. Warm Runtime ABI Cache lookup
still performs separate entry and assembled-Runtime checks and remains the next performance boundary.

## Non-goals

- no live deployment, supervisor restart, or production write;
- no database or pending-candidate mutation;
- no scoring, feature, ranking, or evaluation formula change;
- no backend promotion;
- no GPU/SIMD implementation;
- no removal of historical compatibility APIs.
