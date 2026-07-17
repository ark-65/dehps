# Candidate ABI v1 Specification Round

Date: 2026-07-17

## Primary goal

Freeze Candidate Contract `candidate.v1.0.0` and Candidate ABI `candidate_abi.v1` before production integration, with a language-neutral specification, reference Compiler, independent Verifier, Golden Fixtures, and executable proof obligations.

## Non-goals

- no production prediction or pending-run mutation;
- no CandidateStore, Kernel, Numba, TopK, Feature, GPU, cache, database, evaluation, or backend-default change;
- no historical fingerprint or artifact rewrite;
- no runtime deployment or supervisor restart.

## Frozen decisions

| Area | Candidate v1 decision |
| --- | --- |
| Universe | Generic fixed-cardinality combinations with `domain_size <= 64` |
| Canonical candidate | `pick_count` unique integers, strictly increasing, in `[1,domain_size]` |
| Enumeration | Full-universe tuple lexicographic order |
| `lex_id` | Zero-based `uint32`; never filtered-set row position |
| Rank identity | `rank(unrank(i)) == i` and `unrank(rank(candidate)) == candidate` |
| Mask | `uint64`, number `n` maps to bit `n-1` |
| ABI layout | Little-endian struct-of-arrays: `uint8[N,K]`, `<u8[N]`, `<u4[N]` |
| Failure policy | Reject; never sort, coerce, repair, or warn-and-continue |
| Runtime boundary | Kernel may receive only a verified ABI package |

Candidate filters remain Manifest/Artifact semantics. They do not enter Candidate Contract or ABI identity.

## Artifacts

- normative specification: `docs/architecture/candidate-abi-v1.md`;
- executable Contract, rank/unrank/mask rules, Compiler, Verifier, and Runtime Envelope fragment: `apps/worker-python/dehps/input_contracts/candidate_abi.py`;
- language-neutral conformance fixture: `apps/worker-python/dehps/input_contracts/fixtures/candidate_abi_v1_golden.json`;
- property and tamper tests: `apps/worker-python/tests/test_candidate_abi_contract.py`;
- Contract Runtime status and compatibility matrix update: `docs/architecture/contract-runtime-architecture.md`.

## Verification

### Focused contract suite

```text
40 passed in 0.22s
```

This covered Candidate ABI, shared Contract primitives, and History/Window Contract compatibility before the final boundary additions.

### Candidate ABI suite

```text
28 passed
```

The final Candidate suite covers:

- complete lexicographic rank/unrank enumeration for every combination universe with `domain_size <= 10`;
- SSQ boundary and interior Golden Fixtures;
- number/mask/number round trips;
- stable canonical record and ABI package digests;
- byte-for-byte recompilation reproducibility;
- generic non-SSQ compilation with `domain_size=10`, `pick_count=3`;
- empty candidate-set identity;
- rejection of invalid numbers, order, duplicates, ABI version, Contract digest, layout digest, dtype, byte order, shape, alignment, metadata, and payload tampering;
- Runtime Envelope candidate identity fields.

### Full SSQ bijection audit

The read-only audit iterated every zero-based id in the legal SSQ red-ball universe:

```text
candidate_abi_ssq_bijection_ok
cardinality=1107568
first=(1, 2, 3, 4, 5, 6)
last=(28, 29, 30, 31, 32, 33)
```

For all 1,107,568 ids, `candidate_rank(candidate_unrank(i)) == i`.

### Full worker regression

```text
1079 passed, 4 warnings in 46.42s
```

The four warnings are the existing Python 3.14 `multiprocessing` fork deprecation warnings in training-supervisor parallel tests. There were no test failures.

## Gauss-style proof pass

- Object: finite lexicographically ordered fixed-cardinality combination universe.
- Invariant: the rank and unrank functions partition the universe into identical binomial block sizes at every position.
- Boundary checks: first and last SSQ rows, empty candidate set, number 64 at mask bit 63, negative/out-of-range ids, accepted and rejected `uint32` cardinalities.
- Exact check: every SSQ `lex_id` passed the round trip; all small universes through size 10 were exhaustively compared with `itertools.combinations`.
- Smallest justified conclusion: the reference implementation establishes a unique Candidate v1 identity for the specified finite domain. It does not yet prove production CandidateStore integration or Kernel compatibility.

## Runtime Envelope and propagation boundary

The specified candidate fragment now carries:

```text
candidate_contract
candidate_abi
candidate_digest
layout_digest
package_digest
```

The reference ABI package exposes the fragment. Propagation to newly created artifacts, cache records, evaluation, shadow reports, and telemetry is intentionally deferred to a separate integration round. Existing evidence and pending predictions remain untouched.

## Migration result

Candidate ABI v1 is now a specification and conformance oracle, not a production input. The production Kernel compatibility matrix explicitly rejects Candidate ABI v1 until a later round proves exact equality with the characterized CandidateStore and adds an approved compatibility edge.

This preserves the required development order:

```text
Specification -> Compiler -> Verification -> Integration -> Shadow -> Promotion
```
