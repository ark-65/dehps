# Runtime Verification Session v1 acceptance report

## Round contract

- Primary goal: remove redundant payload scans inside one synchronous execution without weakening
  mutation detection.
- Engineering authorization: Agent Request `126`
  (`engineering-runtime-verification-session-9b76193`), execution `49`.
- Base commit: `9b76193`.
- Runtime operation impact: none; no database, supervisor, deployment, prediction, or research
  decision operation was performed.

## Baseline profile

The database-free baseline used all 1,107,568 canonical candidates, 100 deterministic history rows,
five Feature tiles, one configuration, NumPy reference, TopK 8,000, and eight reduction workers.

| Phase | Baseline wall | Dominant cause |
| --- | ---: | --- |
| Cold Runtime compile | 5.859 s | Feature build plus repeated artifact/ABI verification |
| Warm Runtime compile | 0.859 s | cache-entry and Runtime payload rehashing |
| One `verify_package` | 0.401 s | Feature payload digest plus Candidate digest |
| Planner prepare | 2.146 s | six nested Runtime verification paths |
| Score/rank | 1.450 s | four nested Runtime verification paths |

Within score/rank, approximately 1.385 seconds was verification rather than numeric scoring or TopK.
Baseline peak RSS was 753.1 MiB.

## Implemented boundary

- Contiguous Feature/Candidate buffers stream directly into SHA-256 without `tobytes()` copies.
- Unified Runtime verification returns the Candidate ABI receipt already produced by the joint pass.
- A real, final, package/thread-bound, single-use Verification Session performs one full entry and one
  full exit verification.
- Planner prepare, Planner score/rank, Runtime Envelope, and FullScore orchestration reuse the active
  session only inside that boundary.
- Kernel telemetry exposes verification passes and time.
- Forged, inactive, reused, mismatched-package, and cross-thread sessions fail closed.

## Full-universe result

The same full-universe profile after the change produced:

| Phase | Baseline | Session v1 | Change |
| --- | ---: | ---: | ---: |
| Cold Runtime compile | 5.859 s | 5.235 s | 1.12× |
| Warm Runtime compile | 0.859 s | 0.872 s | no demonstrated gain |
| One `verify_package` | 0.401 s | 0.255 s | 1.57× |
| Planner prepare | 2.146 s | 0.497 s | 4.32× |
| Score/rank | 1.450 s | 0.537 s | 2.70× |
| Peak RSS | 753.1 MiB | 752.8 MiB | unchanged |

Prepare and score each reported exactly two completed full verification passes. Score's numeric and
TopK body took about 0.050 seconds in the profiled run; the remaining 0.486 seconds was the explicit
pre/post integrity boundary.

Warm Runtime compilation did not improve: it still verifies individual Feature cache entries and
then verifies the assembled Runtime. That is a separately bounded cache-transaction problem and was
not hidden by the session change.

## Exactness and rejection evidence

- Existing Feature/Candidate ABI Golden fixtures remain unchanged.
- Contiguous, empty, and non-contiguous Feature arrays match the original v1 `tobytes(C)` digest
  reference exactly.
- Strict score, exact rank, TopK, Red5, Runtime Envelope, and FullScore tests remain exact.
- Mutation after prepare is rejected at score-session entry.
- Mutation injected during the first score tile is rejected at session exit.
- A forged object with `require_package`/`require_runtime` methods is rejected by concrete type check.
- Inactive, reused, other-package, and cross-thread session use is rejected.
- A malformed Runtime is rejected by stage verification before seal projection, preserving structured
  fail-closed errors.

Full legal-universe FullScore verification used two configurations and was exactly equal to the
independent reference. Peak RSS was 1,253.0 MiB. The 38.762-second Artifact call remained dominated
by cold CandidateStore/Feature preparation, so no FullScore end-to-end speedup is claimed.

## Validation

Focused Candidate/Feature/Runtime/Envelope/Kernel/shadow regression:

```text
127 passed in 16.10s
```

Complete worker regression:

```text
1219 passed, 4 warnings in 60.37s
```

The warnings are the existing Python 3.14 `multiprocessing` warning about calling `fork()` from a
multi-threaded process; this round introduced no new warning class.

## Remaining boundary

The next performance target is the warm Runtime ABI Cache transaction: perform one fail-closed
assembled-Runtime verification, invalidate/rebuild on failure, and avoid separately rehashing every
Feature entry before the same Runtime verification. This must preserve mutation detection and cache
invalidation evidence; it must not become a trust lease.
