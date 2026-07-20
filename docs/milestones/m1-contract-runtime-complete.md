# Milestone M1: Contract Runtime Complete

Status: accepted as a capability milestone on 2026-07-20.

Authorization: Agent Request `engineering-m1-roadmap-governance-e5ebffd`, execution `64`.

## Decision

Contract Runtime v1 has completed its foundational engineering objective and enters a stable lifecycle.
Its purpose is to make one computation input-bound, deterministic, reproducible, backend-comparable,
and auditable. It does not make a model better and does not carry Prediction Quality KPI.

The accepted runtime path is:

```text
Contract
  -> Compiler
  -> ABI
  -> Unified Runtime Verifier
  -> VerifiedRuntimePackage
  -> Kernel Planner
  -> NumPy / Numba / OpenCL
  -> Artifact Runtime
```

## Acceptance evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Contract DAG and compiler boundary | [Contract Runtime Architecture](../architecture/contract-runtime-architecture.md) | Accepted |
| One sealed package at the kernel boundary | [Unified Runtime Verifier](../architecture/unified-runtime-verifier.md) and its [acceptance report](../experiments/2026-07-17-unified-runtime-verifier.md) | Accepted |
| ABI mismatch and payload drift fail closed | [Candidate ABI](../architecture/candidate-abi-v1.md), [Feature Contract](../architecture/feature-contract-v1.md), [Runtime Envelope](../architecture/runtime-envelope-v1.md), and [Evaluation Contract](../architecture/evaluation-contract-v1.md) verifiers | Accepted |
| Golden identities exist | [Scoring Input](../architecture/scoring-input-contract-v1.md), Candidate, Feature, ABI, Scoring, Ranking, and Evaluation Golden suites | Accepted |
| Feature semantics and machine layout are frozen | [Feature Contract v1](../architecture/feature-contract-v1.md) and [Feature ABI v1](../experiments/2026-07-17-feature-abi-v1.md) | Accepted |
| Backends consume one verified identity | [Verified Runtime Shadow v1](../architecture/verified-runtime-shadow-v1.md) and [OpenCL acceptance](../experiments/2026-07-20-opencl-feature-abi-backend-v1.md) | Accepted |
| Runtime Envelope reaches durable artifacts | [Runtime Envelope v1](../architecture/runtime-envelope-v1.md), [FullScore Artifact](../experiments/2026-07-18-full-score-runtime-artifact-v1.md), and [Forward Evaluation integration](../experiments/2026-07-18-forward-evaluation-artifact-integration.md) | Accepted |
| Shadow, Evaluation, and Telemetry are integrated | [Verified Runtime shadow migration](../experiments/2026-07-18-verified-runtime-shadow-migration-v1.md), [shadow attestation closure](../experiments/2026-07-18-shadow-attestation-closure-v1.md), [Forward Evaluation integration](../experiments/2026-07-18-forward-evaluation-artifact-integration.md), and backend telemetry evidence | Accepted as capabilities |
| Complete Worker regression at milestone commit | [Research Success Learning Loop v1](../experiments/2026-07-20-research-success-learning-loop-v1.md) records `1285 passed, 4 warnings` at commit `e5ebffd` | Accepted evidence |

The OpenCL full-universe check used the same `VerifiedRuntimePackage` as NumPy and produced the same
result and artifact payload digests. It was approximately 7.5% slower in that measurement, so backend
correctness passed while production promotion did not.

## What this milestone does not claim

- It does not claim improved Recent-30, Recent-100, Recent-300, walk-forward, or forward prediction
  metrics.
- It does not claim that every live service is healthy or that every evidence item is fresh.
- It does not claim that the required three consecutive future shadow cohorts have completed.
- It does not promote OpenCL or Numba to a new production default.
- It does not backfill legacy artifacts with provenance that did not exist when they were produced.
- It does not make historical lift proof of future predictive generalization.

Capability completion and operational health are deliberately separate. A Runtime Dashboard must
show missing, stale, or failed live evidence as such; it must never hardcode M1 acceptance into a
permanent green status.

## Stable-lifecycle policy

Contract Runtime v1 work after M1 must be one of:

- a defect, integrity, security, compatibility, or observability correction;
- measured performance or capacity work under unchanged semantics;
- a versioned compatibility extension such as v1.1;
- a breaking contract/ABI generation such as v2;
- a new backend proving the same package, Golden, equality, and artifact identity gates.

New features, weights, windows, candidate compression, model selection, and prediction evaluation are
Research Roadmap work unless they change a normative contract or machine boundary. Runtime work is
successful when it improves trust, stability, verifiability, or measured platform performance—not
when a prediction metric happens to move.

## Successor milestone

[Milestone M2: Prediction Quality Improvement](../roadmaps/research.md) is now the active research
milestone. M1 remains maintained, but it is no longer the project's primary construction program.
