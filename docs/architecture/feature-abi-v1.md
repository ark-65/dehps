# Feature ABI v1

## Purpose

`feature_abi.v1` freezes the machine representation of a compiled `feature.v1.0.0` component tile.
Feature meaning remains owned by Feature Contract and its component manifest; this ABI owns only
layout, row identity, payload framing, and runtime validation.

## Normative layout

```text
buffer: values
dtype: little-endian float64
shape: [R, 32]
order: C
strides: [256, 8] bytes when R > 0; [0, 0] for the canonical empty tile
alignment: 8 bytes
values: finite only
```

`R` is the row count of one contiguous tile. Rows identify Candidate ABI rows in the half-open range
`[start, end)`. Component column order is the order frozen by
`FEATURE_COMPONENT_MANIFEST_DIGEST`; a backend may not reorder columns or reinterpret names.

Tile size is mechanical, not semantic. The same candidate interval compiled as one tile or several
contiguous tiles must yield identical component rows after concatenation. Feature ABI v1 does not
require materializing the full candidate universe.

## Package identity

The Feature ABI header binds:

- Feature Contract and component-manifest digests;
- Feature ABI layout digest;
- source Feature Artifact version and digest;
- Window Artifact digest;
- Candidate ABI package digest;
- candidate static-input digest;
- target-context digest;
- candidate row range and component count;
- buffer metadata and payload digest.

The package digest covers the header and payload identities. Pointer addresses and allocator padding
are excluded.

## Compiler and zero-copy rule

`FeatureABICompiler` accepts only a valid `CompiledFeatureArtifact`. It describes the Artifact values
buffer directly:

```text
Feature Artifact values
        +
Feature ABI Header
        =
Feature ABI Package
```

It does not cast, transpose, reorder, repair, or copy the values buffer. A nonconforming source is
rejected by the Artifact Verifier before ABI compilation.

## Runtime verification

`FeatureABIVerifier` rejects:

- unsupported ABI, Feature Contract, Artifact, manifest, or layout identity;
- malformed dependency digests or inconsistent row ranges;
- wrong dtype, endianness, shape, stride, contiguity, alignment, or component count;
- NaN or infinite values;
- buffer metadata or payload mutation;
- mismatch with the declared source Feature Artifact.

There is no warning-only mode and no automatic conversion.

## Golden fixture

`FEATURE_ABI_GOLDEN_SUITE` freezes the layout digest and the buffer, payload, header, and package
digests for the Feature Contract Golden Row. Future NumPy, Numba, SIMD, CUDA, OpenCL, Rust, or other
implementations must reproduce these identities when emitting the same ABI package.

## Fused backend boundary

This specification does not silently redefine the current fused Numba backend as Feature ABI
compliant. A fused backend may avoid a full-universe Feature matrix only after the Runtime Migration
defines how its tile producer is verified against this ABI and proves exact component/score/rank
equivalence. Performance is not authority to bypass the contract.

## Reference runtime migration

The explicit reference execution path is now:

```text
CandidateABIPackage + FeatureABIPackage tiles
        -> FeatureABIRuntimeVerifier
        -> KernelPlanner.prepare_feature_abi
        -> FeatureABINumpyReferenceBackend
        -> strict_v1 score / rank / TopK / Red5 result
```

Preflight requires ordered, contiguous, complete Feature tile coverage of the Candidate ABI rows,
one Candidate package binding, and one Window/target context. The planner rejects `numba_cpu` for this
entry because that fused backend has not yet exposed a verified Feature ABI tile producer. Its existing
non-Feature-ABI execution path remains unchanged.

## Non-goals

- no fused Numba or production-default migration;
- no full candidate-space Feature materialization requirement;
- no scoring, ranking, TopK, weight, or formula change;
- no production prediction, pending candidate, database, or runtime-state mutation.
