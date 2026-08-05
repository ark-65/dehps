# M4 P2.6.1 Round 16 exact settled-fold resume

Date: 2026-08-05

Role: Engineering Agent

Agent Request:
`engineering-m4-p2-6-1-exact-settlement-resume-round-16-20260805`
(#274)

Execution: #195

## Primary goal

Make an interrupted exact P2.6.1 replicate restore its already-settled fold
prefix without refitting the four frozen probes, while preserving the existing
strict-prior checkpoint journal bytes and final replicate result exactly.

## Non-goals

- No model, feature, target, fold, hyperparameter, seed, metric, solver,
  tolerance, refit cadence, or statistical contract change.
- No rewrite or deletion of a legacy strict-prior checkpoint journal.
- No production restart, database migration, statistical result inspection,
  Evidence Progress, Gate, or Promotion under Engineering authority.
- No claim that legacy checkpoint-only prefixes can be inverted into missing
  probabilities or settlement state.

## Incident and exact boundary

The 2026-08-05 14:59 Asia/Shanghai restart preserved every strict-prior
checkpoint journal, but each worker restarted its fold loop at zero. After
about 54 minutes, the service consumed the equivalent of 20.3 out of 22
logical CPUs while useful checkpoint append throughput measured only 0.79
folds/s. The existing journal records prediction checkpoint digests before
target access, but not the probability vectors, probe-state digests, target
vectors, or fold settlements required to reconstruct the final replicate.

A SHA-256 digest is not invertible. Therefore a legacy checkpoint-only prefix
must replay exactly once. The accepted implementation is additive and starts
building resumable state while that replay or new work proceeds.

## Implementation

Each newly settled fold appends one post-target sidecar entry under
`artifacts/settled-fold-resume/`. The entry contains:

- the digest of the corresponding unchanged strict-prior checkpoint entry;
- all four exact probe-state digests;
- all four 33-value probability vectors as big-endian float64 bytes, combined,
  zlib-compressed, and base64 encoded;
- the legal 6-of-33 target vector;
- a previous-entry digest and canonical entry digest.

On restart, a contiguous sidecar prefix is accepted only after the evaluator:

1. validates the entry chain, schema, fold order, probability framing, state
   digests, and legal target encoding;
2. binds the sidecar entry to the persisted strict-prior checkpoint entry;
3. recomputes all four formal prediction checkpoint digests from the restored
   float64 bits and state digests;
4. allows target access only after all four checkpoint digests match;
5. compares the restored target with the deterministic dataset target;
6. recomputes all issue metrics and settlement digests;
7. hydrates the final aggregation arrays and executes only the missing suffix.

Trace-capture and runtime-audit executions deliberately retain full fitting so
their frozen fit-count contracts remain unchanged. Completed replicate
artifacts do not include the optional sidecar path, so result identity is
unchanged.

## Exactness and failure evidence

The focused tests cover:

- float64 bit-for-bit encode/decode for all four probability vectors;
- checkpoint-entry mismatch rejection;
- entry checksum tamper rejection;
- non-contiguous append rejection;
- settlement-prefix overflow rejection in the evaluator;
- a real 61-fold run interrupted after settled fold 5;
- resumed fitting of exactly the remaining `56 * 3` learned probes;
- zero learned-probe fits when all 61 folds are settled;
- exact equality of uninterrupted, interrupted-resumed, and fully restored
  result mappings;
- byte-for-byte equality of uninterrupted and resumed original strict-prior
  checkpoint journals.

Validation completed so far:

```text
2 passed, 22 deselected
23 passed, 1 deselected
5 passed
1 passed, 23 deselected in 355.39s
ruff: all checks passed
black: all files formatted
git diff --check: clean
```

No statistical result payload was read during implementation or validation.

## Performance and storage evidence

The same real FORWARD_61 replicate was measured under `nice 19` while the live
22-worker production Supervisor retained priority:

| Path | Folds | Learned-probe fits | Wall seconds | Throughput |
|---|---:|---:|---:|---:|
| fresh exact evaluation | 61 | 183 | 194.938 | 0.313 folds/s |
| complete exact restore | 61 | 0 | 2.593 | 23.523 folds/s |

The measured complete-resume speedup is `75.174x`. The full evaluator fit count
is 244 when the empirical baseline preparation is included; the learned-probe
counter is 183 because the empirical baseline does not call `prepare_probe`.

The compressed sidecar measured 107,206 bytes for 61 folds, or 1,757.48 bytes
per fold. Applying that observed density to the Round 13 count of 61,638,178
missing folds gives about 100.89 GiB of additional storage. This is a restart
recovery cost, not a steady-state compute bottleneck; sequential append I/O is
small relative to model fitting.

## Gauss-style exact pass

This is a Gauss-inspired invariant and residual check, not an appeal to
historical authority.

- Object: one immutable replicate with a contiguous settled prefix and missing
  suffix.
- Invariant: same fold identities, pre-target checkpoint bytes, float64
  predictions, state digests, target vectors, settlement digests, and final
  result.
- Boundary: a pre-target digest alone cannot recover its hidden probability or
  state inputs; a legacy prefix pays one replay.
- Residual: uninterrupted result minus resumed result is exactly zero, and
  uninterrupted checkpoint bytes minus resumed checkpoint bytes is exactly
  zero.
- Failure condition: any chain, fold, checkpoint, probability, state, target,
  gap, or length mismatch aborts before suffix execution.
- Smallest defensible conclusion: the new sidecar makes future process restarts
  skip already-settled model fits exactly; it cannot retroactively eliminate
  the first replay of legacy checkpoint-only folds.

## Integration matrix

| Mainline link | Round 16 evidence | Status |
|---|---|---|
| Goal | approved Engineering request #274 | complete |
| Resolver | canonical production Resolver unchanged | pending Operator |
| Ready Queue | canonical P2.6.1 task unchanged | pending Operator |
| Supervisor | isolated evaluator only | pending Operator |
| Capability | exact settled-prefix hydration implemented | code complete |
| Artifacts | sidecar, tests, benchmark, and this report | complete |
| Status | Engineering execution #195 | executing |
| Next task | merge, then separately authorized runtime migration | pending |
| Replay | isolated crash/recovery exact replay | passed |

Mainline integration answer:

**NO — INTEGRATION_PENDING until the merged runtime is exercised by the
unified mainline Supervisor and deterministically replayed.**
