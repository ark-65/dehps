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

The Runtime cache cold path now uses `DirectFeatureABIProducer`. It computes one Feature tile and
constructs the exact same Feature Artifact v1 identity and Feature ABI v1 package around that one
buffer without invoking the staged `FeatureCompiler -> FeatureABICompiler` chain. The direct result
is deliberately unverified: `RuntimeABICache` validates its source seal and bindings, marks the buffer
read-only, independently verifies the source Feature Artifact payload, and performs the formal
`FeatureABIVerifier` pass before insertion. The staged chain remains an explicit independent oracle.

Direct production means one tile payload materialization and no Artifact-to-ABI buffer copy. It does
not mean that the complete Runtime is streamed through the Kernel without retaining Feature tiles;
that requires a separately versioned streaming Runtime contract.

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

## Numba backend boundary

The explicit `feature_abi_numba_cpu` backend consumes verified `float64[R,32]` Feature ABI tiles and
does not interpret Feature names, formulas, History, or Window values. It uses Numba only for the
score/rank/Red5 compute loop and shares the Runtime Envelope and deterministic TopK reduction path
with the ABI NumPy reference.

This does not silently redefine the older fused `numba_cpu` entry as Feature ABI compliant. That
path still constructs components and scores internally. The direct producer proves exact Feature
Artifact/ABI identity but does not turn the legacy fused scoring path into an ABI implementation.
Avoiding retention of the complete set of Feature tiles still requires a verified streaming producer
and Runtime boundary. Performance is not authority to bypass the contract.

## Runtime migration

The explicit reference execution path is now:

```text
CandidateABIPackage + FeatureABIPackage tiles
        -> FeatureABIRuntimeVerifier
        -> UnifiedRuntimeVerifier -> VerifiedRuntimePackage
        -> KernelPlanner.prepare_feature_abi
        -> FeatureABINumpyReferenceBackend | FeatureABINumbaCpuBackend
        -> strict_v1 score / rank / TopK / Red5 result
        -> runtime_envelope.v1 artifact_produced evidence
```

Preflight requires ordered, contiguous, complete Feature tile coverage of the Candidate ABI rows,
one Candidate package binding, and one Window/target context. Both ABI backends require the same sealed
`VerifiedRuntimePackage`; a prepared package cannot cross backend identities. The existing legacy
non-Feature-ABI NumPy/Numba execution paths remain unchanged.

## Non-goals

- no legacy fused Numba scoring-path or production-default migration;
- no streaming Runtime or tile-at-a-time Kernel execution;
- no full candidate-space Feature materialization requirement;
- no scoring, ranking, TopK, weight, or formula change;
- no production prediction, pending candidate, database, or runtime-state mutation.
