# Feature ABI Direct Producer v1 acceptance report

## Round contract

- Primary goal: replace staged Feature Artifact-to-ABI construction on Runtime cache misses with a
  direct one-buffer producer without changing any Artifact, ABI, Runtime, score, or rank identity.
- Engineering authorization: Agent Request `128`
  (`engineering-feature-abi-direct-producer-13f1dfd`), execution `51`.
- Base commit: `13f1dfd`.
- Einstein failure condition: reject the change if any identity differs, verifier authority weakens,
  a second Feature matrix appears, or paired full-universe cold performance does not improve.
- Runtime operation impact: none. No database, prediction, pending-candidate, supervisor, backend
  default, promotion, or production operation was performed.

## Implemented boundary

- `DirectFeatureABIProducer` computes one reference component tile and directly constructs the exact
  Feature Artifact v1 source identity and Feature ABI v1 package around that buffer.
- No cast, repair, transpose, reorder, or Artifact-to-ABI buffer copy is allowed.
- The producer result is unverified. Runtime ABI Cache validates producer/source identity, makes the
  buffer read-only, independently verifies the source Artifact payload, and performs one formal
  Feature ABI payload verification per cold tile.
- Complete Unified Runtime verification is unchanged.
- `StagedFeatureABIProducer` retains the original two-compiler path as a separate oracle.
- Existing explicit compiler injection remains compatible through that staged adapter and is rejected
  if mixed with a direct producer.
- Producer implementation version is present in Feature cache identity and receipts; it does not
  alter Artifact, ABI, or Runtime identity.

## Exactness evidence

Sixteen combinations of expanding/rolling Window, null/dated target context, and empty/small/partial
candidate ranges produced exact equality for:

- values arrays and component output object identity;
- Feature Artifact headers and source Artifact digests;
- Feature ABI headers, payload metadata, and package digests.

Default direct Runtime cache output is also compared against independently staged Feature packages
through both Feature ABI NumPy and Numba Kernel backends. Target score, exact rank, TopK IDs/scores,
Red5 IDs/scores/ranks, Runtime seal, and every package digest remain strictly identical.

Malformed float32, non-contiguous, and non-finite component outputs are rejected rather than repaired.
Forged producer source seals and forged, internally consistent source headers with false Artifact
values digests are rejected by Runtime ABI Cache. Existing cached-payload mutation,
Runtime-seal recovery, Candidate re-key, LRU, and concurrent compilation tests remain green.

## Digest-work evidence

For one 600-row tile, instrumentation of every Feature Artifact/ABI and Candidate-static
`feature_array_digest` call measured:

| Producer | Digest calls | Bytes presented to digest functions |
| --- | ---: | ---: |
| Direct | 65 | 832,800 |
| Staged | 90 | 1,622,400 |

The direct path reduces measured digest bytes by 48.7% while retaining one cache-layer source
Artifact verification, one Feature ABI verification, and one complete Runtime verification. This
counter covers the Feature compiler/ABI digest function; Candidate ABI verifier internals remain
unchanged.

## Full legal-universe benchmark

The database-free paired benchmark used 1,107,568 candidates, 100 deterministic History rows, five
Feature tiles of at most 262,144 rows, a 512 MiB cache budget, and the cross-order
`staged -> direct -> direct -> staged`.

| Producer | Samples | Mean cold Runtime compile |
| --- | --- | ---: |
| Staged reference | 4.441s, 4.519s | 4.480s |
| Direct | 2.933s, 3.008s | 2.971s |

Direct production is `1.51x` faster. Both implementations retained exactly 283,537,408 Feature
payload bytes, reported five formal Feature payload verification passes and one complete Runtime
verification pass, and produced the same five package/source digests and
`verified_runtime.v1-89f276156d69da51`.

The paired process peak was 752.82 MiB with zero swap, compared with 753.25 MiB for the preceding
Runtime Cache transaction baseline. No additional Feature matrix was observed: every direct package
retained the exact captured component output object and one payload materialization.

## Validation

Producer, Feature ABI, compiler, and Runtime cache regression:

```text
56 passed in 6.83s
```

Candidate/Feature/Runtime/Kernel/forward-shadow regression:

```text
156 passed in 20.96s
```

Complete worker regression:

```text
1247 passed, 4 warnings in 60.27s
```

The warnings are the existing Python 3.14 `multiprocessing` warning about `fork()` from a
multi-threaded process. This round introduced no new warning class.

## Remaining boundary

This is a direct one-buffer tile producer, not yet a streaming Runtime. Eliminating retention of all
five Feature tiles requires a separately reviewed Runtime state machine that verifies ordered tiles,
supports strict TopK/exact-rank/Red5 reduction, seals the final Artifact, and remains deterministic
across tile sizes and retry boundaries. No such claim or production switch is made here.
