# Core scoring Runtime migration v1 acceptance report

## Round contract

- Primary goal: migrate the shared production/research scoring convergence point to verifier-gated
  Feature ABI execution.
- Engineering authorization: Agent Request `123`
  (`engineering-core-scoring-runtime-migration-60660e8`), execution `46`.
- Base commit: `60660e8`.
- Runtime operation impact: none; no process was started, restarted, deployed, or pointed at a live
  database.

## Root cause

After simultaneous shadow migrated, `_kernel_score_rank` still selected a legacy backend, prepared a
CandidateStore directly, packed Window statistics independently, and executed without a History,
Window, Feature ABI, or Unified Runtime seal. Because production prediction and core research both
converged there, the Runtime enforcement boundary was not yet authoritative for normal scoring.

## Implemented boundary

- Added the shared `RuntimeInputCompiler` and process-wide verifier-gated ABI cache.
- Canonical effective history becomes a History Snapshot plus Window Artifact.
- Known production/training target issues enter Window identity and leakage checks.
- `_kernel_score_rank` accepts effective history rather than a preinterpreted PackedWindowState.
- Default and explicit backend selection now route through Feature ABI Planner entries.
- Official forward generation and simultaneous shadow reuse the same Runtime compiler, cache, and
  `verified_runtime_id`.
- Runtime input identity and cache receipts propagate through ranked-universe telemetry.
- Noncanonical three-digit test issues were replaced only in legal-input fixtures; an explicit test
  proves that such input is rejected rather than repaired.

## Exactness contract

A fixed 3,000-candidate fixture compares the migrated core entry against the legacy NumPy reference
for two configurations. The following arrays are required to be bit-exact:

- target scores;
- exact ranks;
- TopK candidate row IDs and scores;
- Red5 candidate row IDs, scores, and ranks.

The same fixture executes explicit Numba selection through `feature_abi_numba_cpu` and requires the
same arrays. Repeated execution with a different worker count must retain the Runtime identity and
return Feature and Runtime cache hits.

## Validation

- Affected scoring/training/runtime regression: `280 passed, 4 existing multiprocessing fork
  warnings` in `17.96s`.
- Full Python regression: `1207 passed, 4 existing multiprocessing fork warnings` in `61.42s`.
- API and Web code were not changed, so their suites were not required.

## Full legal-universe execution

One database-free synthetic run used all `1,107,568` legal candidates, 100 canonical history rows,
one production-shaped configuration, Top10K, four Feature tiles, and eight reduction workers.

| Stage | Wall time |
| --- | ---: |
| Ranked-universe construction without mmap cache | 40.046 s |
| CandidateStore / Candidate ABI cold construction | 36.009 s |
| Runtime Input / Feature ABI cold compilation | 6.515 s |
| Feature ABI prepare and verification | 2.466 s |
| Feature ABI score/rank/TopK call | 1.737 s |
| Legacy NumPy prepare | 0.025 s |
| Legacy NumPy score/rank/TopK call | 1.493 s |

The Feature ABI and legacy Top10K IDs/scores were exact. Peak RSS was `752.7 MiB`; swap was not
used. Candidate construction is common cold setup rather than new Runtime overhead.

A second identical Runtime execution in the same process reported:

| Stage | Cold | Warm |
| --- | ---: | ---: |
| Runtime compilation/lookup | 6.677 s | 0.940 s |
| prepare and verification | 2.287 s | 2.610 s |
| score/rank/TopK | 1.797 s | 1.797 s |

The cold and warm executions had the same `verified_runtime_id` and artifact payload digest. The
warm path hit every Feature tile and the Runtime cache.

This benchmark also exposes the next performance obligation: repeated fail-closed prepare/execution
verification currently costs materially more than the numerical kernel itself. Runtime enforcement
is accepted here, but no production operation or backend promotion should claim throughput parity
until a separately reviewed verification-lease or zero-materialization fused-producer design reduces
that overhead without weakening mutation detection.

## Remaining migration boundary

- one offline residual-analysis script still uses the full-score-grid helper outside KernelResult;
- historical/post-hoc legacy shadow helpers remain intentionally isolated;
- three real future issues still require complete pre-draw and post-draw shadow attestations;
- no backend-default promotion is authorized by this implementation round.
