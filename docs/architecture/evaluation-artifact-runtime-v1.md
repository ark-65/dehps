# Evaluation Artifact Runtime v1

## Purpose

`evaluation_artifact.v1` turns a successful `evaluation.v1.0.0` result into detached, digest-bound
evidence. The compiler does not trust a metrics dictionary supplied by a caller. It verifies the
parent evidence and recomputes metrics through the Evaluation Contract reference implementation.

```text
Candidate ABI Package ───────────────┐
                                     │
artifact_produced Runtime Envelope ──┤
                                     ▼
Prediction Evidence ─────────► Evaluation Artifact Compiler
Actual Outcome ───────────────►          │
Ranking Audit ────────────────►          ▼
                               Evaluation Stage Envelope
                                          │
                                          ▼
                               Evaluation Artifact v1
```

## Why this is a stage envelope

`runtime_envelope.v1` currently records the compute lifecycle:

```text
compiled_abi -> verified_runtime -> kernel_ready -> kernel_executing -> artifact_produced
```

An evaluation occurs after that artifact exists. Reusing the scoring envelope by changing its
`artifact_type`, payload digest, or state path would rewrite source evidence and falsely claim that
evaluation was a kernel transition. Evaluation therefore has a separate
`evaluation_stage_envelope.v1` which references the immutable scoring Runtime Envelope digest and
payload digest. A future Runtime Envelope v2 may generalize multi-stage lifecycles explicitly; v1 is
not silently reinterpreted.

## Parent artifacts

### Prediction Evidence

`prediction_evidence.v1` binds:

- prediction run and line keys;
- target issue;
- Candidate ABI package digest;
- source Scoring and Ranking Contracts;
- ordered candidate count and canonical candidate payload digest.

Candidate rows remain the original immutable tuple held by the caller. The Evaluation compiler does
not copy, rerank, deduplicate, cast, or repair them. When the Candidate ABI Package is resolved, every
candidate is checked against its `lex_id` and numbers buffers.

### Actual Outcome

`actual_outcome.v1` binds target issue, draw date, canonical red numbers, blue number, and
`blue_scored=false`. Outcome and Prediction target issues must match, and that issue must be strictly
after the source Runtime Envelope History Snapshot latest issue.

### Ranking Audit

Ranking Audit is stored as canonical JSON and bound by a domain-separated digest. The compiler does
not reinterpret its stage ranks or substitute one rank namespace for another.

## Stage envelope

The Evaluation Stage Envelope binds:

- `evaluation.v1.0.0` and metric-manifest digest;
- target issue and `evaluated` evidence status;
- source Runtime Envelope and source scoring-payload digests;
- Prediction, Outcome, and Ranking Audit digests;
- recomputed evaluation-payload digest;
- Evaluation compiler version and full code commit.

Any parent mutation changes the Evaluation Artifact identity.

## Verification modes

Object verification recomputes metrics and checks all parent bindings. When a Candidate ABI Package
is supplied, it additionally verifies candidate membership in the resolved source package.

Detached verification parses the complete JSON representation, verifies the embedded source Runtime
Envelope, reconstructs every parent artifact, recomputes metrics, and requires canonical
serialization and the same final artifact digest. Unknown fields, stale digests, altered metrics,
changed Ranking Audit, or noncanonical payloads are rejected; there is no repair mode.

## Current boundary

Evaluation Artifact v1 represents completed `evaluated` evidence only. Missing draw, missing
prediction, leakage failure, and execution lifecycle states remain operational attempt evidence and
must not be disguised as successful Evaluation Artifacts.

This round does not connect the compiler to pending forward evaluation or persistence. That is the
next migration and requires explicit legacy handling because historical prediction runs do not all
carry a Runtime Envelope or Candidate ABI artifact reference.
