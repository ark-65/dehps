# Runtime Roadmap

## Mission

Keep DEHPS computation deterministic, compatible, replaceable, reproducible, and auditable across
backends. [Milestone M1](../milestones/m1-contract-runtime-complete.md) establishes the v1 capability
baseline; this roadmap governs stability and version evolution.

Prediction lift is not a Runtime objective. A three-day Runtime change with unchanged Recent-100 is
still successful when its declared Runtime metric and acceptance gate improve. Conversely, a Research
change that improves ranking does not improve Runtime maturity unless Runtime evidence also changes.

## KPI namespace

| KPI | Required evidence | Failure signal |
| --- | --- | --- |
| Determinism | Repeated input/package/output identity | Same input produces a different digest |
| ABI stability | Compatibility matrix and fail-closed negative tests | An unknown or mismatched ABI executes |
| Cross-backend equality | Same verified package, exact result and artifact digests | Any identity, score, rank, TopK, or Red5 difference |
| Throughput | Versioned full-workload benchmark | Regression beyond the preregistered budget |
| Latency | Cold/control-plane and hot/kernel timings reported separately | Hidden setup cost or unexplained regression |
| Memory | Peak RSS, device workspace, allocation bounds, and swap | Bound exceeded or unreported materialization |
| Scalability | Candidate/config/window scaling curve | Resource growth violates the declared model |
| Reproducibility | Commit, contract, package, config, and artifact identities | Detached result cannot be reconstructed or verified |
| Auditability | Runtime Envelope, telemetry, rejection reason, evidence freshness | Missing, stale, mutable, or unverifiable evidence |

Test count is supporting evidence, not a standalone maturity score. Dashboard status must bind the
count to a commit, command, timestamp, scope, and result.

## Stable-lifecycle work classes

1. `v1 maintenance`: defects, integrity, security, observability, and compatibility corrections.
2. `v1 performance`: semantic-preserving throughput, latency, memory, and capacity work.
3. `v1.1 extension`: backward-compatible contract or telemetry additions with explicit compatibility.
4. `v2 generation`: breaking semantic or ABI changes with migration and rollback plans.
5. `backend research`: SIMD, CUDA, OpenCL, Rust, or other kernels behind the same verified boundary.

Every Runtime round must state its class and the Runtime KPI it is allowed to change. It must not use
Recent-30/100/300, hit rate, rank, calibration, or generalization as its acceptance criterion.

## Current state and next gates

| Area | State | Next evidence |
| --- | --- | --- |
| Contract/Compiler/ABI/Verifier/Planner/Artifact chain | Stable v1 capability | Maintenance only unless a versioned proposal is approved |
| NumPy and Numba equality | Implemented | Fresh evidence surfaced in Runtime Dashboard |
| OpenCL correctness | Research backend, exact on measured full universe | A new performance hypothesis before reconsidering promotion |
| Shadow capture and attestation | Capability implemented | Three consecutive future issues, all required lines, independently approved |
| Runtime Envelope propagation | Current artifacts integrated; legacy evidence preserved | Freshness and unavailable states exposed without synthetic backfill |
| Runtime Dashboard | Information architecture frozen | Separate Engineering Request for API/Web implementation |

## Change gate

A Runtime proposal may proceed only when it names:

- the affected contract, ABI, backend, or artifact boundary;
- the Runtime KPI and baseline;
- Golden and cross-backend obligations;
- negative/fail-closed coverage;
- performance and memory measurement where relevant;
- compatibility, migration, and rollback behavior;
- an explicit statement that prediction-quality metrics are non-goals.
