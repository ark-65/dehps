# Runtime ABI Compiler Cache v1 acceptance report

## Round contract

- Primary goal: add the missing ABI Compiler Cache without weakening Runtime Enforcement.
- Engineering request: `engineering-runtime-abi-cache-4b599a9`.
- Execution: `44`.
- Base commit: `4b599a9`.
- Non-goals: no persistent cache, production migration, backend promotion, GPU/SIMD, Contract or ABI
  change, prediction write, database mutation, or runtime process operation.

## Root cause

Candidate ABI semantic verification already reused a safe receipt after recomputing buffer digests,
but identical Feature inputs still reran Feature construction and ABI compilation. Unified Runtime
packages were also recreated even when the complete Contract DAG and tile plan were unchanged.

A naive dictionary keyed only by package digest would be unsafe because NumPy arrays remain mutable,
and a Runtime entry could retain a large Feature buffer after the Feature LRU claimed to evict it.

## Implemented boundary

- Complete digest-bound Feature ABI cache identity.
- No-copy, read-only cached Feature values buffers.
- Mandatory Feature ABI verification on every hit.
- Mutation invalidation followed by canonical recompilation.
- Verified Runtime cache with mandatory Unified Runtime revalidation.
- Entry-count and payload-byte limits with deterministic LRU eviction.
- Dependent Runtime eviction when a Feature tile leaves the cache.
- Serialized identical concurrent compilation and structured hit/miss telemetry.

## Exactness

Cached and uncached Feature Runtime packages were executed through both
`feature_abi_numpy_reference` and `feature_abi_numba_cpu`. Target score, exact rank, TopK IDs and
scores, Red5 IDs, scores, and ranks were all array-exact.

## 100,000-candidate benchmark

One isolated in-memory benchmark used 100,000 candidates, 100 dated history rows, four 25,000-row
Feature tiles, and a 128 MiB cache limit:

| Measurement | Result |
| --- | ---: |
| setup and CandidateStore construction | 6.743 s |
| cold Runtime ABI compilation | 0.493 s |
| warm verified Runtime lookup | 0.080 s |
| cold/warm speedup | 6.175x |
| retained Feature payload | 25,600,000 bytes |
| peak process RSS | 281.9 MiB |
| warm Feature tile hits | 4/4 |
| warm Runtime hit | yes |

The warm path is not a zero-work shortcut: it still recomputes request identities and buffer digests
and re-runs Feature and Unified Runtime verifiers.

## Validation

- Runtime ABI cache focused suite: `8 passed`.
- Feature/Candidate/Runtime regression: `82 passed`.
- Full Python regression: `1203 passed, 4 existing multiprocessing fork warnings` in `48.23s`.
- GitHub Actions: pending publication.

## Production impact

None. The cache is an explicit control-plane capability and is not connected to live production or
research entry points in this round.
