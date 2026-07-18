# Runtime Verification Session v1

## Purpose

A `VerifiedRuntimePackage` is a seal, not an immutable-memory guarantee. NumPy read-only flags can be
reopened by a retained owner or alias, so a time-based or object-identity cache cannot safely replace
payload verification.

Before this round, each Planner phase repeatedly verified the same payload inside one synchronous
call:

```text
prepare
  Unified Runtime verify
  Candidate verify
  Envelope compile
    Unified Runtime verify
    Runtime verify
    Envelope state verify × 3

score
  Unified Runtime verify
  Runtime verify
  ready Envelope verify
  produced Artifact verify
```

The full legal-universe profile showed that these nested scans consumed about 1.385 seconds of a
1.450-second NumPy score/rank call.

## Session contract

`RuntimeVerificationSession` defines one synchronous boundary:

```text
full payload verification at entry
                 │
                 ▼
 package/thread-bound active session
                 │
       Planner + Envelope + Compute
                 │
                 ▼
full payload verification at exit
```

The session:

- is created only by `UnifiedRuntimeVerifier`;
- is final and cannot be subclassed;
- is bound to the exact `VerifiedRuntimePackage` object and its Runtime object;
- is bound to the thread that entered it;
- is single-use and inactive outside `with` scope;
- has no TTL, weak-reference shortcut, object-id cache, or implicit renewal;
- records entry/exit verification time and completed full-pass count.

Envelope and Artifact APIs validate the concrete session type before reusing it. An object that only
implements similarly named methods cannot bypass Runtime verification.

## Mutation boundary

Entry verification detects mutation after prepare and before execution. Exit verification detects a
payload mutation that happens while scoring is running. Nested Envelope state and binding checks
continue to run, but they reuse the active session rather than rescanning Feature and Candidate
buffers.

Normal completion therefore requires exactly two full payload passes for prepare and two for score.
If exit verification fails, no `KernelResult` is returned and telemetry is not recorded as a
successful execution.

## Zero-copy digest streaming

Feature and Candidate SHA-256 framing is unchanged. For a nonempty C-contiguous NumPy buffer,
hashing now consumes `memoryview(array).cast("B")` instead of `array.tobytes(order="C")`. Empty
buffers append zero bytes, and non-contiguous reference inputs retain the old C-order fallback.

The digest bytes and all Golden fixtures remain unchanged. This removes a payload-sized temporary
copy; it does not cache or omit hashing.

## Telemetry

Kernel telemetry now records:

- `prepare_runtime_verification_passes`;
- `prepare_runtime_verification_seconds`;
- `runtime_verification_passes`;
- `runtime_verification_seconds`.

These fields distinguish compute throughput from integrity overhead and make any future attempt to
reduce the required pre/post pass count visible.

## Non-goals

- no time-based verification lease;
- no Runtime ABI Cache invalidation change;
- no immutable-memory or `mprotect` claim;
- no scoring, ranking, Feature, Candidate, or Artifact identity change;
- no backend promotion, GPU/SIMD, supervisor, database, or production operation.
