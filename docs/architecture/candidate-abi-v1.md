# Candidate ABI v1 Specification

## Status and scope

This document is the normative implementation specification for `candidate.v1.0.0` and the machine layout `candidate_abi.v1`.

Primary goal:

> Freeze one unique, stable, verifiable, and reproducible candidate identity and ABI before any production integration.

This round provides a control-plane reference compiler, fail-closed verifier, language-neutral golden fixtures, and conformance tests. It does not connect the ABI to the current `CandidateStore` or scoring kernel.

Non-goals:

- no production prediction or pending-run mutation;
- no `CandidateStore`, Kernel, Numba, TopK, Feature, GPU, cache, database, or evaluation behavior change;
- no historical fingerprint rewrite;
- no backend-default or runtime-state change.

## Architectural rule

The legal boundary is:

```text
Candidate Contract + Universe Manifest + Candidate Manifest
                              |
                              v
                     Candidate Compiler
                              |
                              v
                    Candidate ABI Package
                              |
                              v
                    Candidate ABI Verifier
                              |
                              v
                            Kernel
```

The Kernel may consume only a verified ABI package. It does not parse manifests, repair candidates, infer domain rules, rank combinations, or decide what a number means.

The system-wide rule is:

> Every runtime-visible object must have an explicit Contract, a compiled ABI, a verifier, and a stable identity.

## Contract, manifest, ABI, and artifact boundaries

| Object | Responsibility | Must not contain |
| --- | --- | --- |
| Candidate Contract | legality, canonical number order, lexicographic enumeration, rank/unrank, mask semantics, canonical record serialization, failure policy | filters, strategy names, backend layouts |
| Universe Manifest | concrete `domain_size`, `pick_count`, universe cardinality under the Contract | selected candidate rows, score or filter policy |
| Candidate Manifest | one concrete, canonically ordered candidate subset | dtype, pointers, alignment, scores, features |
| Candidate ABI | dtype, shape, layout, byte order, alignment, strides, buffer framing and digests | domain interpretation, filtering, feature meaning |
| Candidate Set Artifact | durable identity and provenance of one compiled candidate payload | mutable process addresses |

Changing a filter changes the Candidate Manifest or Candidate Set Artifact. It does not change `candidate_abi.v1`. Changing the row representation, `lex_id` width, endianness, or mask layout requires a new ABI version. Changing rank semantics or legal candidate meaning requires a new Candidate Contract identity.

## Candidate Contract `candidate.v1.0.0`

### Universe

Candidate Contract v1 describes a finite fixed-cardinality combination universe:

```text
domain = {1, 2, ..., domain_size}
candidate = choose pick_count unique members
```

The v1 limits are:

- `domain_size` is a Python/JSON integer in `[1,64]`;
- `pick_count` is an integer in `[1,domain_size]`;
- universe cardinality is `C(domain_size,pick_count)`;
- cardinality must be at most `2^32`, so every zero-based `lex_id` fits `uint32`;
- these limits belong to v1 because its mask is 64-bit and its `lex_id` is 32-bit.

The SSQ red-ball universe is one manifest under this generic Contract:

```text
domain_size = 33
pick_count = 6
cardinality = C(33,6) = 1,107,568
```

The Contract contains no `SSQ`, issue, draw, filter, or score branch.

### Candidate legality and canonical form

A legal candidate is exactly `pick_count` integer values. Values must be unique, strictly increasing, and within `[1,domain_size]`.

The compiler and verifier reject these inputs rather than sorting or coercing them:

- descending or partially sorted rows;
- duplicate numbers;
- strings, booleans, floats, or implicit numeric conversions;
- values outside the universe;
- the wrong row width.

A Candidate Manifest is an ordered subset of the full universe. Its rows must have strictly increasing `lex_id`; duplicate or reordered rows are invalid. An empty candidate set is valid and has its own stable identity.

### Canonical enumeration and `lex_id`

The full universe is enumerated by ordinary tuple lexicographic order. `lex_id` is zero-based and always refers to the unfiltered full universe, never to the row position in a filtered candidate set.

For candidate `a=(a0,...,a{k-1})`, rank counts the lexicographic blocks skipped before each position:

```text
rank(a) = sum over positions i
          sum over x in [a{i-1}+1, ai)
          C(domain_size-x, pick_count-i-1)
```

where `a{-1}=0`. `unrank` subtracts the same block sizes until the unique tuple is selected.

Every conforming implementation must satisfy:

```text
rank(unrank(i)) == i
unrank(rank(candidate)) == candidate
```

for every `i` in `[0, cardinality)` and every legal candidate.

### Mask

The mask is an unsigned 64-bit value. Candidate number `n` maps to bit `n-1`:

```text
mask = OR(1 << (n - 1) for n in candidate)
```

All bits at or above `domain_size` must be zero, and the mask population count must equal `pick_count`. `numbers -> mask -> numbers` must reproduce the canonical tuple exactly.

### Canonical record serialization and digest

One canonical candidate record serializes as:

| Field | Encoding |
| --- | --- |
| `domain_size` | one unsigned byte |
| `pick_count` | one unsigned byte |
| `numbers` | `pick_count` unsigned bytes in canonical order |
| `mask` | little-endian `uint64` |
| `lex_id` | little-endian `uint32` |

The record digest is:

```text
SHA-256("dehps.candidate-record.v1" + NUL + canonical_record_bytes)
```

No JSON whitespace, object address, native byte order, pointer, padding, process time, source-row id, or backend name enters this identity.

## Candidate ABI `candidate_abi.v1`

### Layout

Candidate ABI v1 is a struct-of-arrays package with three independent C-contiguous buffers:

| Buffer | dtype | Shape | Strides | Byte order | Minimum alignment |
| --- | --- | --- | --- | --- | --- |
| `numbers` | `uint8` | `[N,pick_count]` | `[pick_count,1]` bytes | not applicable | 1 byte |
| `mask` | `uint64` | `[N]` | `[8]` bytes | little-endian | 8 bytes |
| `lex_id` | `uint32` | `[N]` | `[4]` bytes | little-endian | 4 bytes |

The immutable layout digest is calculated from the symbolic layout definition, not from `N`, pointers, buffer padding, or allocation addresses. Concrete shapes, strides, byte lengths, alignments, and per-buffer digests are recorded in the package header.

There is no array-of-objects form, Python tuple buffer, nullable row, native-endian ambiguity, or hidden stride.

### Binary payload identity

Each buffer is hashed independently in C order with a named domain:

```text
dehps.candidate-abi.buffer.numbers.v1
dehps.candidate-abi.buffer.mask.v1
dehps.candidate-abi.buffer.lex_id.v1
```

The payload digest hashes the ordered buffer metadata and buffer digests. The header digest hashes contract identity, manifests, layout, payload identity, dimensions, cardinality, and buffer metadata. The package digest hashes the header digest and payload digest.

This framing lets another language reproduce the identity without reproducing NumPy allocation details.

## Candidate Compiler

The reference `CandidateCompiler` is a control-plane oracle. Its input is:

```text
Candidate Contract
Universe Manifest(domain_size,pick_count)
Candidate Manifest(canonical candidate rows)
```

Its output is:

```yaml
candidate_abi_package:
  header:
    abi_version: candidate_abi.v1
    candidate_contract: candidate.v1.0.0
    universe_manifest_digest: sha256
    candidate_digest: sha256
    layout_digest: sha256
    payload_digest: sha256
    row_count: N
    domain_size: integer
    pick_count: integer
    universe_cardinality: integer
    buffers:
      - name: numbers
        dtype: uint8
        endianness: not_applicable
        shape: [N, pick_count]
        strides: [pick_count, 1]
        alignment: 1
        byte_length: integer
        buffer_digest: sha256
      - name: mask
        dtype: uint64
        endianness: little
        shape: [N]
        strides: [8]
        alignment: 8
        byte_length: integer
        buffer_digest: sha256
      - name: lex_id
        dtype: uint32
        endianness: little
        shape: [N]
        strides: [4]
        alignment: 4
        byte_length: integer
        buffer_digest: sha256
  payload:
    numbers: buffer
    mask: buffer
    lex_id: buffer
```

The compiler does not sort malformed input or repair its values. Compilation concludes by running the independent verifier over the emitted package.

## Candidate ABI Verifier

The verifier is a mandatory fail-closed gate before future Kernel execution. It validates:

1. exact ABI version and Candidate Contract normative identity;
2. exact v1 layout digest;
3. universe bounds, cardinality, and Universe Manifest digest;
4. row count and all concrete shapes;
5. exact dtype and little-endian requirements;
6. C contiguity, strides, byte lengths, and minimum alignment;
7. every buffer digest and the aggregate payload digest;
8. candidate legality and canonical row order;
9. `rank`, `unrank`, and mask round trips for each row;
10. Candidate Manifest digest reconstructed from the ABI payload.

The verifier returns no corrected package. Any mismatch raises a structured `CandidateContractViolation` and the package is rejected.

Representative failure codes include:

- `unsupported_candidate_abi_version`
- `candidate_contract_mismatch`
- `candidate_layout_digest_mismatch`
- `candidate_buffer_dtype_mismatch`
- `candidate_buffer_shape_mismatch`
- `candidate_buffer_not_contiguous`
- `candidate_buffer_alignment_mismatch`
- `candidate_buffer_metadata_mismatch`
- `candidate_payload_digest_mismatch`
- `candidate_lex_id_mismatch`
- `candidate_mask_mismatch`
- `candidate_abi_order_violation`
- `candidate_digest_mismatch`

There is no warning mode or automatic conversion path.

## Golden fixtures

The language-neutral fixture is stored at:

```text
apps/worker-python/dehps/input_contracts/fixtures/candidate_abi_v1_golden.json
```

It freezes SSQ-universe boundary rows, an interior row, `lex_id`, mask, record digest, and a three-row ABI package identity. NumPy, Numba, SIMD, CUDA, OpenCL, Rust, or any future implementation must reproduce every value exactly before promotion.

The executable test suite additionally exhausts every candidate of all combination universes with `domain_size <= 10`. This proves the reference `rank` and `unrank` are inverse functions over those complete spaces rather than over a few examples.

## Runtime Envelope v1 projection

Candidate ABI v1 reserves this runtime-envelope fragment:

```yaml
runtime:
  candidate:
    candidate_contract: candidate.v1.0.0
    candidate_abi: candidate_abi.v1
    candidate_digest: sha256:...
    layout_digest: sha256:...
    package_digest: sha256:...
```

The reference package exposes this fragment now. Propagation into new candidate artifacts, cache records, evaluations, shadow reports, and telemetry is a later integration migration. Existing artifacts and pending predictions are not rewritten. Missing historical fields must remain interpretable by their historical evidence contracts rather than being silently backfilled.

## Compatibility and migration

Candidate ABI v1 is not yet an accepted input to the production scoring Kernel. The current `CandidateStore` remains the active production representation. This round adds a conformance oracle alongside it.

The future migration gate is:

1. compile the existing full candidate universe into Candidate ABI v1;
2. prove exact `numbers`, mask, ordering, and candidate identity against the characterized current store;
3. add an explicit Kernel compatibility edge for `candidate_abi.v1`;
4. run shadow scoring and ranking without changing production output;
5. propagate Runtime Envelope fields only to newly created artifacts;
6. promote through a separate approval.

Until that gate is complete, no Kernel may claim Candidate ABI v1 conformance merely because its arrays look similar.

## Acceptance criteria

Candidate ABI v1 is specified when the repository proves:

- uniqueness: each legal combination has one canonical tuple, `lex_id`, mask, record serialization, and digest;
- stability: language-neutral golden values and package digests are frozen;
- verifiability: independent validation rejects version, contract, dtype, shape, alignment, layout, digest, and payload tampering;
- reproducibility: recompiling the same manifests yields byte-identical buffers and identities;
- domain isolation: the same compiler and verifier work for a non-SSQ universe without importing domain code;
- migration safety: current CandidateStore, Kernel, production predictions, pending runs, and persistence state remain unchanged.
