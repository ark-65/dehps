# Feature ABI Direct Producer v1

## Purpose

`dehps.feature-abi-direct-producer.numpy-reference.v1` removes the redundant staged construction path
from Runtime ABI Cache misses while preserving every existing Feature Artifact v1 and Feature ABI v1
identity.

```text
Window Artifact + Candidate ABI + Candidate static inputs
                         │
                         ▼
              Direct Feature ABI Producer
                         │
              one values tile buffer
                         │
              Artifact v1 identity + ABI v1 header
                         │
                         ▼
               unverified producer result
                         │
                         ▼
        Runtime ABI Cache source/binding checks
                         │
                         ▼
          Feature Artifact Verifier (full pass)
                         │
                         ▼
             Feature ABI Verifier (full pass)
                         │
                         ▼
              read-only cached ABI package
                         │
                         ▼
              Unified Runtime Verifier
```

The producer is not a verifier and cannot mint a `VerifiedRuntimePackage`.

## Identity preservation

For the same `FeatureCompileRequest`, the direct producer must reproduce the staged reference exactly:

- component values and the one underlying values object;
- Feature Artifact header and Artifact digest;
- Feature ABI buffer metadata and payload digest;
- Feature ABI header and package digest;
- resulting Runtime digest and Verified Runtime seal.

The shared `feature_artifact_digest(...)` and internal ABI package constructor prevent the direct and
staged paths from implementing those canonical projections independently. Golden and multi-context
tests remain the authority for byte-level equality.

## Ownership and validation

The component producer allocates one `float64[R,32]` C-contiguous tile. Direct production rejects a
wrong dtype, shape, stride, alignment, non-contiguous layout, or non-finite value; it does not cast,
copy, transpose, reorder, or repair the output. Artifact and ABI headers describe that same object.

`FeatureABIProducerResult` records producer version, source Artifact identity, one payload
materialization, and whether an ABI buffer copy occurred. Cache receipts separately expose source
Artifact payload verification passes so cold construction and warm transactions cannot be confused.
Runtime ABI Cache rejects:

- producer-version mismatch;
- more or fewer than one payload materialization or any claimed ABI copy;
- malformed Artifact contract identity;
- source Artifact seal mismatch;
- source Window/Candidate/static/target/range binding mismatch;
- source Artifact values-digest mismatch;
- any Feature ABI verifier failure.

Only after those checks does the cache retain the read-only package. Runtime verification and
pre/post execution Verification Sessions remain unchanged.

## Reference oracle

`StagedFeatureABIProducer` explicitly preserves the original:

```text
FeatureCompiler -> CompiledFeatureArtifact -> FeatureABICompiler
```

It is an oracle and benchmark baseline, not the default Runtime cache producer. Producer version is
part of the process-local Feature cache key, while exact Artifact/ABI output identity remains the
same across the two implementations. Existing explicit `feature_compiler` / `abi_compiler`
constructor injection is preserved through this staged adapter; it cannot be combined with a direct
producer in one cache instance.

## Boundary

This producer fuses control-plane Feature Artifact and ABI construction. It does not fuse scoring,
does not make the legacy `numba_cpu` path Feature ABI compliant, and does not eliminate retention of
all Feature tiles in a complete `VerifiedRuntimePackage`. A future streaming Runtime would need its
own verifier, ordered coverage state machine, second-pass/Red5 strategy, final seal, and artifact
contract before tile-at-a-time execution could replace the current complete Runtime package.

## Non-goals

- no Feature formula or numerical-contract change;
- no Feature ABI, Scoring, Ranking, Evaluation, or fingerprint change;
- no streaming Runtime, trust lease, Candidate static-key cache, GPU, or SIMD;
- no backend-default, prediction, database, pending-candidate, supervisor, or production operation.
