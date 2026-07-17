# Unified Runtime Verifier

## Purpose

`unified_runtime_verifier.v1` is the sole control-plane authority that turns raw runtime inputs into a
`verified_runtime_package.v1`. Kernel Planner and Runtime Envelope Compiler no longer accept raw
`FeatureABIRuntime` values.

The boundary is:

```text
HistorySnapshotArtifact
WindowArtifact
CandidateABIPackage
FeatureABIPackage tiles
        |
        v
UnifiedRuntimeVerifier
   reject / accept
        |
        v
VerifiedRuntimePackage + verification seal
        |
        +-> RuntimeEnvelopeCompiler
        +-> KernelPlanner
```

## Verification scope

The Unified Verifier delegates normative checks to the stage verifiers, then verifies the cross-stage
DAG as one unit:

- History Snapshot payload, canonical id, latest issue, and draw count;
- Window contract, payload, spec, indices, and History Snapshot binding;
- Candidate Contract, ABI layout, buffers, rank/unrank/mask identity, ordering, and package digest;
- Feature Contract/ABI, buffer layout, finite values, source identity, and package digest;
- complete, ordered, non-overlapping Feature tile coverage of Candidate rows;
- one Window Artifact, target context, and Candidate package across all Feature tiles.

Any stage error is surfaced as `runtime_stage_verification_failed` with the originating cause code.

## Verification seal

The sealed digest covers:

- verifier and package versions;
- combined runtime digest;
- History and Window contract/artifact identities;
- Candidate contract, ABI, layout, and package identity;
- Feature contract, ABI, layout, manifest, and every ordered tile package digest.

`VerifiedRuntimePackage` exposes a deterministic `verified_runtime_id`. Revalidation recomputes all
stage digests and the seal. A changed buffer, substituted runtime, different tile plan, stale seal, or
unsupported verifier version is rejected.

The seal is not a security signature. It is a deterministic integrity and provenance identity under a
specific verifier implementation, which is additionally bound by the Runtime Envelope code commit.

## Kernel boundary

The explicit Feature ABI Planner path requires:

```python
verified = UnifiedRuntimeVerifier().verify(raw_runtime)
prepared = KernelPlanner("numpy_reference").prepare_feature_abi(
    verified,
    code_commit=full_git_sha,
)
```

Passing `raw_runtime` directly produces `runtime_package_not_verified`. Prepared packages are
revalidated immediately before scoring, so mutable NumPy payload drift after sealing is detected.

## Non-goals

- no cryptographic signing or remote attestation;
- no legacy production-path migration;
- no fused Numba compliance claim;
- no historical Artifact backfill;
- no database or live runtime operation.
