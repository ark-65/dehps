# Scoring Kernel `strict_v1` migration report

## Round contract

- Primary goal: land a deterministic, chunked, replaceable scoring kernel shared by production and research.
- Source baseline: `2111a70`.
- Accepted backends: `numpy_reference` and opt-in `numba_cpu` only.
- Non-goals: CUDA, OpenCL, GPU selection, C++/Rust SIMD, fixed point, Arrow/Parquet migration, model/feature/weight changes, and a production-default backend change.
- Production safety: no write was issued to history, prediction, candidate, evaluation, promotion, or training runtime tables.

## What changed

The 32-component dynamic scorer now has a stable ABI built from `CandidateStore`, `PackedWindowState`, `WeightMatrix`, `KernelRequest`, `KernelWorkspace`, `KernelResult`, and `ScoringKernelBackend`. Window dictionaries and tuple-keyed profiles are packed into dense arrays before execution. Candidate numbers use `uint8[N,6]`; candidate membership and stable lexicographic identity use `uint64[N]`.

`numpy_reference` is the streaming oracle. `numba_cpu` fuses component construction, eight-configuration score accumulation, eight-decimal rounding, exact-rank thread-local reduction, and Red5 popcount inside one `njit(parallel=True, fastmath=False)` candidate loop. Both reuse bounded tile workspaces and avoid a full candidate-by-config score matrix.

Production candidate generation and research walk-forward/weight-grid ranking now enter through the same `KernelPlanner`. The default is still `numpy_reference`; `DEHPS_SCORING_BACKEND=numpy_reference` is the explicit rollback.

## Correctness evidence

The strict contract is documented in `docs/architecture/scoring-kernel-strict-v1.md` and tested with exact array equality. The focused suite covers component cells, rounded scores, equal-score boundaries, TopK, Red5, chunk invariance, thread-count invariance, fixed-seed weight matrices, dense dtypes, non-finite rejection, planner fallback, and Numba compile flags.

Real database history was checked at issues `2026078`, `2026079`, and `2026080` using the current production hard-filter universe of 1,105,506 rows and all eight default grid configurations. For every window:

- packed component cells equaled the compatibility implementation exactly;
- target scores and exact ranks matched exactly;
- strict TopK candidate ids and scores matched exactly;
- Red5 candidate ids, scores, and global ranks matched exactly;
- NumPy and hot Numba result digests matched.

The pre-migration TopK helper exposed one defect: it used score-only `argpartition` before applying the lexicographic sort. On issue `2026080`, Top1000 across eight configs had 146/8000 candidate-id differences at tied boundary scores, while every selected score was identical. This behavior contradicted the declared `score desc, lex id asc` rule and was not chunk-invariant. `strict_v1` makes boundary selection obey the same lex rule as ordering. Persisted prediction runs and candidates were not rewritten.

Validation after implementation:

```text
1025 passed, 4 warnings in 53.06s
```

The four warnings are the existing Python 3.14 `fork()`-from-a-multithreaded-process deprecation warnings in training-supervisor multiprocessing tests; there were no test failures.

The first GitHub Actions run exposed a capacity-only portability edge: its Numba runtime allowed two threads while two strict tests requested four. The backend now caps the request to `NUMBA_NUM_THREADS`, reports the actual count, and retains exact output. The complete suite above was rerun with `NUMBA_NUM_THREADS=2` to reproduce the constrained runner.

## Full-space benchmark

Host:

```text
Linux 7.0.0-27-generic x86_64
Python 3.14.4
NumPy 2.4.6
22 logical CPUs
31,788,532 KiB RAM
```

Protocol:

- candidates: full `C(33,6) = 1,107,568` legal space;
- real windows: three (`2026078`–`2026080`);
- configurations: eight;
- Red5 enabled, so each measurement performs two bounded score passes;
- score cells per measurement: 17,721,088;
- TopK: 1000;
- chunks: 65,536 / 131,072 / 262,144 / 524,288;
- Numba threads: 1 / 2 / 4 / 8 / 16;
- measurements: 72, all exact against the NumPy oracle;
- peak process RSS: approximately 1,270.5 MiB, dominated by building the uncached full benchmark store;
- swap: 0 KiB in every measurement.

Across all four required chunk sizes and three windows, median wall time was:

| Backend | Threads | Wall s | Cells/s | Scaling vs Numba-1 | Speed vs NumPy reference |
| --- | ---: | ---: | ---: | ---: | ---: |
| NumPy reference | 1 request worker | 2.860 | 6.20M | — | 1.00x |
| Numba CPU | 1 | 0.587 | 30.21M | 1.00x | 4.87x |
| Numba CPU | 2 | 0.367 | 48.32M | 1.60x | 7.80x |
| Numba CPU | 4 | 0.249 | 71.03M | 2.35x | 11.46x |
| Numba CPU | 8 | 0.233 | 76.20M | 2.52x | 12.29x |
| Numba CPU | 16 | 0.188 | 94.22M | 3.12x | 15.20x |

The NumPy row's worker count is an API value, not a BLAS thread limit; its matrix multiplication used several BLAS threads. Numba-1 still ran about 4.9x faster because it avoids materializing the 32-column component tile and fuses score/rank work.

For Numba, chunk sensitivity was small after 131,072; 262,144 remained a sound default. The final run's workspace estimate scales linearly from 4.1 to 32.5 MiB for Numba and 20.1 to 160.5 MiB for NumPy over the four chunks. Scaling flattens after four threads because exact TopK/Red5 merging remains serial and the fused loop approaches memory bandwidth limits. The eight-thread cProfile run spent 0.149 seconds of 0.236 seconds in ten compiled tile calls and about 0.085 seconds in deterministic TopK merging. That serial third of the run explains the 8/16-thread plateau and identifies the next optimization boundary without changing the numerical contract.

The evidence files are runtime artifacts and are intentionally not committed:

```text
runtime/benchmarks/scoring-kernel-strict-v1.json
runtime/benchmarks/scoring-kernel-strict-v1.md
runtime/logs/scoring-kernel.jsonl
```

## Is this true fusion?

Yes. The acceleration is not an old Python candidate loop wrapped by JIT. cProfile shows ten calls to the Numba backend tile for the two passes over five chunks; it does not show 1,107,568 Python candidate callbacks or 32 Python feature functions per row. Inside each compiled `prange` iteration, the kernel computes all 32 components, accumulates all configuration scores, rounds, updates a thread-local exact-rank reduction, and calculates Red5 membership. The 4.00x single-thread improvement over an already vectorized/multithreaded NumPy reference, followed by real 1→2→4 scaling, is consistent with fused memory traffic and compiled parallel work. The remaining Python/Numpy activity is bounded tile-level TopK reduction, visible directly in the profile.

## Operational state check

Before the round:

```text
history rows: 3477, latest issue: 2026080
forward prediction runs: 3 pending
forward candidates: 30000
forward evaluation runs: 0
prediction-run digest: 1c2a9b4545ea4286c8a7d9095178dff8
candidate digest: 9e55ad55d8dd7d3fd12a0385125d4985
```

The same query is rerun at acceptance. Digests must remain identical before the change can be published.

## Next boundary

The next performance round should optimize deterministic tile-local/global TopK merging and persist a reusable full-legal benchmark store. GPU/OpenCL remains premature until that serial ranking boundary and backend equivalence gate are stable. Production may opt into `numba_cpu` only through a separate acceptance/promotion decision; this round intentionally leaves it on `numpy_reference`.
