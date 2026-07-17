# Candidate ABI Verified Identity Cache

## Round boundary

Primary goal: remove repeated full-space Candidate ABI semantic verification from
Kernel `prepare()` while preserving fail-closed payload drift detection.

Non-goals:

- no Candidate ABI, scoring, ranking, or feature contract change;
- no candidate generation, prediction, evaluation, promotion, or database write;
- no persistent cross-process trust cache;
- no production backend switch or live-process restart.

## Root cause

`CandidateArrayCompiler.compile()`, `CandidateStore.validate()`, every backend
`prepare()`, and higher runtime verifiers all called `CandidateABIVerifier.verify()`.
The verifier correctly recomputed buffer digests, but also repeated the Python
row-by-row rank, unrank, mask, and canonical-number proof across more than 1.1
million rows. The scoring kernel itself completed in fractions of a second while
this repeated proof consumed tens of seconds.

## Change

The verifier now mints a `CandidateABIVerification` receipt after the complete
semantic proof. The bounded process-local LRU is keyed by the verified package
digest and additionally binds:

- verifier version;
- header digest;
- all three complete buffer metadata records and cryptographic buffer digests;
- row count and payload byte count.

Every verification call still recomputes metadata and cryptographic digests over
the complete `numbers`, `mask`, and `lex_id` payload. Only after those bytes match
the sealed header and cached receipt may it skip the row-wise semantic proof.
Payload mutation therefore rejects structurally before cache lookup succeeds.
Equivalent packages with identical frozen bytes can share the proof; object
identity alone is never sufficient. The cache is bounded to 64 identities.

`PreparedCandidateStore` carries the receipt, and kernel telemetry now records
the verified candidate ID and cache-hit state. NumPy and Numba therefore expose
the same Candidate ABI verification evidence.

## Full-space measurement

Read-only local measurements used the existing ranked-universe cache. No database
or production runtime was touched.

| Candidate set | Rows | First compile + full semantic proof | Cached NumPy prepare | Cached Numba prepare | Payload |
| --- | ---: | ---: | ---: | ---: | ---: |
| current production-filtered universe | 1,105,506 | 33.883 s | 0.0237 s | 0.0246 s | 19,899,108 bytes |
| full `C(33,6)` universe | 1,107,568 | 30.692 s | 0.0157 s | 0.0154 s | 19,936,224 bytes |

Both full-space backends used verification ID
`verified_candidate.v1-f8d3c9529726127e`. The initial proof remains mandatory;
the improvement applies only to redundant verification of the same sealed
Candidate ABI identity.

## Validation

Focused contract, scoring-kernel, and Feature ABI runtime tests:

```text
67 passed in 7.98s
```

Coverage includes distinct package objects sharing one digest-bound receipt and
mutation of a previously verified payload being rejected as
`candidate_buffer_metadata_mismatch`.

## Operational state

This round did not alter existing prediction runs, pending candidates, draw
history, evaluation rows, production defaults, watchdog state, or the live
research lane. The separate production deployment and pending-forward evaluation
operation still requires explicit Operator approval.
