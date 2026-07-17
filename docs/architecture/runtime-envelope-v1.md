# Runtime Envelope v1

## Purpose

`runtime_envelope.v1` is the standalone provenance record for a DEHPS runtime artifact. A detached
JSON result must still answer which History Snapshot, Window, Candidate ABI, Feature ABI, scoring,
ranking, backend, and code revision produced it.

The Envelope is evidence, not a bag of optional metadata. Missing identities, malformed state,
digest drift, backend drift, and detached payload mutation are fail-closed errors.

## Bound identity

Runtime Envelope v1 records:

- History Contract, snapshot id, digest, latest issue, and draw count;
- Window Contract, spec digest, and Window Artifact digest;
- Candidate Contract, ABI, candidate/layout/package digests;
- Feature Contract, ABI, component-manifest/layout/runtime digests, and tile count;
- Scoring Contract and actual backend;
- Ranking Contract;
- optional Evaluation Contract, currently null before Evaluation Contract v1;
- full 40- or 64-character code commit;
- ABI/runtime package digest;
- final artifact payload digest;
- canonical runtime state and state path.

Contract records include normative and Golden Suite identities. Serialized Envelopes include their own
canonical digest and cannot be loaded without it.

## Runtime state machine

The only legal path is:

```text
compiled_abi
    -> verified_runtime
    -> kernel_ready
    -> kernel_executing
    -> artifact_produced
```

States cannot be skipped, repeated, reversed, or entered directly. `artifact_produced` additionally
requires a payload digest. The full path is stored in every final Envelope so a detached artifact does
not depend on transient in-process state.

## Compiler

`RuntimeEnvelopeCompiler.compile_kernel_ready()` accepts a verified `FeatureABIRuntime`, explicit
backend, and full code commit. It:

1. re-verifies History Snapshot, Window Artifact, Candidate ABI, Feature ABI, tile coverage, and all
   cross-stage bindings;
2. emits `compiled_abi` identity;
3. advances sequentially through `verified_runtime` to `kernel_ready`;
4. verifies the Envelope against the source runtime after every stage.

The explicit Feature ABI backend transitions to `kernel_executing`, computes a canonical digest over
all KernelResult arrays, then enters `artifact_produced`.

## Detached verification

`RuntimeEnvelopeV1.from_dict()` reconstructs ContractRefs, verifies every field, requires and checks
the serialized Envelope digest, and rejects malformed payloads without repair.

`RuntimeEnvelopeVerifier.verify_artifact_payload()` compares the final Envelope with a separately
computed artifact payload digest. This detects result changes even when the artifact has left the
database or worker process.

## History and Window boundary

Feature ABI Runtime now carries both `HistorySnapshotArtifact` and `WindowArtifact`. Preflight verifies:

- the History Snapshot payload and canonical id;
- Window payload and spec identity;
- Window snapshot id equals History snapshot id;
- Window history digest equals History digest;
- Window input draw count equals History draw count.

This prevents a valid Window digest from being attached to a different History value object.

## Compatibility and migration

New explicit Feature ABI KernelResults carry Runtime Envelope v1. Existing production predictions and
historical artifacts remain under their original evidence contract and are not backfilled or rewritten.

The next step is a Unified Runtime Verifier that returns one verified package to Kernel Planner,
followed by Envelope propagation to exports, APIs, shadow reports, and evaluation artifacts.

## Non-goals

- no historical Artifact or prediction rewrite;
- no production backend switch;
- no fused Numba Feature ABI compliance claim;
- no Evaluation Contract definition;
- no database migration or live operation.
