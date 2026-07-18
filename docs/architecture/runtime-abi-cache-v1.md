# Runtime ABI Compiler Cache v1

## Purpose

`runtime_abi_cache.v1` inserts a bounded, verifier-gated cache between Contract compilation and the
Kernel Planner:

```text
History / Window / Candidate / Feature Contracts
                       │
                       ▼
              Feature Compiler
                       │
                       ▼
                 Feature ABI
                       │
              miss ┌───┴───┐ warm transaction
                   │ Cache │
                   └───┬───┘
                       │ verify the assembled Runtime once
                       ▼
             Unified Runtime Verifier
                       │
                       ▼
              VerifiedRuntimePackage
```

The cache saves deterministic Feature numerical recomputation. It is not an authority and never
replaces Candidate, Feature, or Unified Runtime verification.

## Feature cache identity

Every Feature tile key binds the complete effective input identity:

- History Contract and History Snapshot digest;
- Window Contract, Window Artifact, and WindowSpec digests;
- Candidate Contract, ABI version, layout, package, and candidate-static-input digests;
- Feature Contract, ABI version, layout, component manifest, and compiler version;
- target context digest;
- half-open candidate row range.

The key is canonical JSON under a domain-separated SHA-256 digest. Tile size is not a Feature
semantic, but its resulting row ranges are part of each cache identity. A different tile plan may
reuse only tiles whose exact ranges and parent identities already exist.

## Runtime cache identity

A verified runtime key binds the Unified Runtime Verifier version, combined Feature Runtime digest,
History Snapshot, Window Artifact, Candidate ABI package, and ordered Feature ABI package digests.
The cache may return the same `VerifiedRuntimePackage` object for an identical Runtime DAG, but calls
`UnifiedRuntimeVerifier.verify_package()` before every return. A normal fully warm lookup first
recomputes every Feature Contract DAG key, requires exact cached entry/package bindings, assembles the
Runtime identity, and then performs one full Runtime verification. It does not separately hash every
Feature tile before the same verifier hashes those tiles again.

## Mutation and trust boundary

Feature ABI compilation continues to describe the Feature Artifact values buffer without copying it.
Before insertion, the cache marks that buffer read-only. A fully warm Runtime transaction is accepted
only after:

1. every current request is revalidated and every cache key, including Candidate static input, is
   recomputed;
2. every key resolves to the exact cached Feature entry, whose identity, read-only flag, and bindings
   still match;
3. the resulting ordered Feature packages resolve to the exact cached Runtime identity;
4. `UnifiedRuntimeVerifier` performs one complete Candidate/Feature payload scan and verifies the
   Runtime seal.

If any transaction check fails, the cache executes the original per-Feature verification path. That
path invalidates and recompiles a corrupt Feature entry or invalidates and remints a corrupt Runtime
seal. The transaction is therefore a scan coalescing boundary, not a lease or verifier bypass. Direct
`compile_feature(...)` hits also retain their full `FeatureABIVerifier` pass.

A writable, mutated, stale, or misbound package is evicted and recompiled. The cache never resets a
writeable flag, patches metadata, casts buffers, copies payloads, or treats a stored digest as a
permanent trust receipt.

## Concurrency and memory

The process-local cache uses one reentrant lock. Identical concurrent misses are serialized and
produce one canonical cached package; no partially compiled entry is visible. This first version
prioritizes deterministic control-plane behavior over parallel compilation of unrelated keys.

Feature entries are bounded by both entry count and retained payload bytes using deterministic LRU
eviction. Verified Runtime entries retain only packages that still exist in the Feature cache. When a
Feature tile is evicted or invalidated, every dependent Runtime entry is removed, so runtime references
cannot silently defeat the byte limit. An individual package larger than the limit is verified and
returned but not cached.

## Integration boundary

The public control-plane entry is `RuntimeABICache.compile_runtime(...)`. It returns a
`VerifiedRuntimePackage`, per-tile key/digest/hit/storage/byte telemetry, and the runtime-cache result.
Its receipt also records producer identity/materialization evidence, source Artifact payload pass
count, verification strategy, separate Feature payload pass count, Runtime payload pass count, and
whether a failed warm transaction recovered through the compatibility path.
The package is accepted by the existing NumPy and Numba Feature ABI Planner entries.

This round does not switch production or research callers to the cache. Migration remains explicit so
existing prediction identity, backend defaults, and live process state do not change accidentally.

## Non-goals

- no persistent or distributed cache;
- no cross-process mmap serialization;
- no GPU/SIMD backend;
- no Contract, ABI, Feature formula, scoring, or ranking change;
- no cache-based verifier bypass, TTL, object-identity lease, or Candidate static-key memoization.
