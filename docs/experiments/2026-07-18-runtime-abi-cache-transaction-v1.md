# Runtime ABI Cache Transaction v1 acceptance report

## Round contract

- Primary goal: replace redundant per-Feature warm-cache payload scans plus the assembled Runtime
  scan with one fail-closed assembled Runtime verification.
- Engineering authorization: Agent Request `127`
  (`engineering-runtime-cache-transaction-bc1e4c7`), execution `50`.
- Base commit: `bc1e4c7`.
- Runtime operation impact: none. No database, supervisor, prediction, pending-candidate, backend
  default, or production-state operation was performed.

## Implemented transaction

The warm path is now:

```text
recompute every Feature Contract DAG key
                    │
                    ▼
require exact cached entry/package bindings
                    │
                    ▼
require exact cached Runtime identity
                    │
                    ▼
one Unified Runtime full verification
                    │
                    ▼
return the warm Runtime package
```

The transaction still recomputes Candidate static digests. It checks Feature headers, package
identities, row ranges, read-only flags, Window/Candidate/target bindings, ordered Runtime membership,
and the cached Runtime seal before return. The single Unified Runtime pass recomputes the actual
Candidate and Feature payload digests.

If the transaction cannot prove that complete identity, the existing path remains authoritative:
each Feature entry is fully verified, corrupt entries are invalidated and deterministically
recompiled, dependent Runtime entries are removed, and an invalid Runtime seal is reminted. No cache
entry is silently repaired.

## Receipt contract

`RuntimeABICacheCompilation` now records:

- `verification_strategy`: `assembled_runtime_transaction`, `per_feature_verification`, or
  `transaction_fallback_recovery`;
- `feature_payload_verification_passes`: separate cache-layer Feature verifier passes;
- `runtime_payload_verification_passes`: complete Unified Runtime verifier calls;
- `transaction_recovered`: whether a matched warm transaction failed and the compatibility path
  produced a valid result.

A normal warm hit reports zero separate Feature passes and one Runtime pass. These counters describe
cache orchestration passes; they do not claim that compiler-internal validation is absent on a cold
miss.

## Failure and concurrency evidence

- A read-only Feature payload mutated after insertion fails the assembled verification, invalidates
  that Feature entry, evicts its dependent Runtime, recompiles exact values, and returns a fresh seal.
- A mutated `VerifiedRuntimePackage.verification_digest` is invalidated and reminted.
- A changed Candidate static scoring input changes the affected Feature DAG key; it is not accepted as
  the old experiment identity.
- Four concurrent identical Runtime compilations create each of the three test Feature tiles once,
  produce one Runtime miss and three hits, and return one canonical verified package object.
- Existing LRU entry/byte bounds and read-only buffer rules are unchanged.

## Full legal-universe benchmark

The database-free benchmark used all 1,107,568 canonical candidates, 100 deterministic History rows,
five Feature tiles of at most 262,144 rows, and a 512 MiB cache budget.

| Metric | Session v1 baseline | Transaction v1 | Change |
| --- | ---: | ---: | ---: |
| Warm Runtime compile | 0.872 s | 0.339 s mean | 2.57× faster |
| Best warm Runtime compile | — | 0.312 s | — |
| Profiled warm Runtime compile | — | 0.374 s | — |
| Separate Feature payload passes | 5 | 0 | removed |
| Assembled Runtime payload passes | 1 | 1 | preserved |
| Peak RSS | 752.8 MiB | 753.25 MiB | unchanged |
| Swap | 0 | 0 | unchanged |

The three unprofiled warm samples were `0.312s`, `0.347s`, and `0.359s`. All warm results retained the
same Verified Runtime ID and all five Feature package digests as the cold result. The cache held five
Feature entries, one Runtime entry, and 283,537,408 Feature payload bytes without eviction.

The profiled warm call spent about `0.225s` in the one `verify_package` call and `0.132s` recomputing
the five Feature DAG keys. Candidate validation and Candidate static hashing remain visible by design;
Candidate static-key caching was an explicit non-goal of this round.

## Validation

Focused Candidate/Feature/Runtime/Kernel/Shadow regression:

```text
125 passed in 15.08s
```

Runtime ABI Cache unit and recovery regression:

```text
12 passed in 4.22s
```

Complete worker regression:

```text
1223 passed, 4 warnings in 48.61s
```

The warnings are the existing Python 3.14 `multiprocessing` warning about `fork()` from a
multi-threaded process. This round introduced no new warning class.

## Remaining boundary

The next approved performance boundary remains a fused/zero-materialization Feature producer. This
round did not change Feature formulas, Scoring or Ranking contracts, Kernel backends, production
defaults, or any live prediction artifact.
