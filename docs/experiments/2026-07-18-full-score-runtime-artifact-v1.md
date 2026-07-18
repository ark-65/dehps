# FullScore Runtime Artifact v1 acceptance report

## Round contract

- Primary goal: eliminate the remaining research full-score ndarray bypass.
- Engineering authorization: Agent Request `124`
  (`engineering-full-score-runtime-artifact-460d9ff`), execution `47`.
- Base commit: `460d9ff`.
- Runtime operation impact: none; no database, supervisor, deployment, prediction, or research
  decision operation was performed.

## Root cause

The near-residual backtest used `score_config_grid(...)`, which directly built a Feature component
matrix and returned a bare `ndarray`. Scores were deterministic, but the output carried no verified
History/Window/Candidate/Feature identity, WeightMatrix digest, Runtime state path, code commit, or
payload seal.

## Implemented boundary

- Added FullScore header, Artifact, Compiler, Verifier, and structured violation type.
- Full scores can be compiled only from a `VerifiedRuntimePackage` and explicit WeightMatrix.
- Candidate-major `float64[N,C]` output preserves the existing research data contract.
- Runtime Envelope reaches `artifact_produced` and seals the FullScore payload digest.
- Artifact metadata propagates into every near-residual target row.
- The compatibility array API now projects from a verified Artifact instead of recomputing outside
  Runtime enforcement.
- Benchmark-only `_score_matrix(...)` remains the independent reference oracle.

## Acceptance checks

- exact score-grid equality against the frozen reference;
- deterministic artifact, payload, Runtime, weight, and score digests;
- warm Runtime/Feature cache reuse;
- read-only candidate-major output;
- score mutation rejection;
- weight mismatch rejection;
- writable/wrong-layout rejection;
- Runtime Envelope drift rejection;
- raw Runtime rejection.

## Validation

Focused regression:

```text
68 passed
```

Complete worker regression:

```text
1210 passed, 4 warnings in 48.97s
```

The warnings are the existing Python 3.14 `multiprocessing` warning about calling `fork()` from a
multi-threaded process; this round did not introduce a new failure or warning class.

Full legal-universe measurement used all 1,107,568 canonical red-ball combinations, 100 canonical
history rows, and two weight configurations. The Artifact output was compared with the independent
`_score_matrix(...)` reference using exact array equality.

| Measurement | Result |
| --- | ---: |
| Candidate count | 1,107,568 |
| Build time | 25.688 s |
| Cold Artifact compile/verify time | 34.410 s |
| Independent reference score time | 1.228 s |
| Exact equality | true |
| Score payload size | 16.9 MiB |
| Peak RSS | 1,253.1 MiB |
| Runtime state | `artifact_produced` |

Artifact digest:
`55f0877a5b999db83550d1a16398aa5c7bcc73fc740586406e2cae66837cb756`.
Payload digest:
`64256252aee89c9f28d603db804957c7b2575a7b7e7e6ebe4aecd3d20123c3aa`.

The cold Artifact path is intentionally slower than the bare reference in this first migration: it
includes CandidateStore preparation, Runtime input compilation, contract verification, digesting,
and Artifact sealing. This round establishes identity and rejection semantics; it does not claim a
FullScore throughput improvement. A later optimization may fuse producer-side verification and
cache immutable seals without weakening the contract boundary.

## Remaining boundary

Normal production/research scoring, simultaneous shadow, and full-score research artifacts now use
Verified Runtime inputs. Historical/post-hoc compatibility code and benchmark-only reference oracles
remain explicitly isolated. Three real future issue attestations and an independent backend promotion
decision remain outstanding.
