# M4 v2 Marginal-Static Health Execution Integration — Round 42

Date: 2026-08-08

## Primary goal

Integrate the frozen 7,168-replicate marginal-static synthetic measurement-health
program into the singular Research Evidence Supervisor path, with direct compact
checkpoint recovery, no database or CSV I/O inside a replicate, and no duplicate
raw replay.

## Non-goals

- Do not read historical outcomes.
- Do not inspect legacy P2.6.1 partial statistical results.
- Do not change the Round-41 sample sizes, generators, estimand, bootstrap,
  acceptance gates, or seed domains.
- Do not decide PASS versus REPAIR in the Engineering role.
- Do not promote a model, alter prediction-v2, or change production behavior.
- Do not execute the formal 7,168-replicate program before merged-code Operator
  authorization.

## Authorized contract

Research Request:
`research-m4-v2-marginal-static-health-execution-integration-round-42-20260808`
(request 325, execution 246).

Engineering Request:
`engineering-m4-v2-marginal-static-health-execution-round-42-20260808`
(request 326, execution 247).

The source contract is
`M4_V2_MARGINAL_STATIC_HEALTH_EXECUTION_SOURCE`, digest
`5fbeb6ab0533478ac097747ab73fb0188561849505a76cf7a63a3a02061b2354`.
It binds the execution kernel byte-for-byte and records that the Engineering
round was result-blind and executed zero formal replicates.

## Implementation outcome

The new execution kernel performs the frozen program entirely in memory inside
each process:

1. derive a PCG64DXSM child seed from the source digest, cell, scale, and
   replicate index;
2. generate a legal six-of-33 synthetic sequence;
3. calculate the expanding legal marginal estimator and endpoint with vectorized
   NumPy arrays;
4. calculate the exact conditional truth target;
5. execute the four frozen centered circular moving-block bootstraps;
6. discard raw draws and retain one compact replicate summary;
7. append the summary identity to a compact completion index.

There are no per-replicate database reads, database writes, or CSV files. The
supervisor loads the completion index once, resolves completed replicate digests
directly, and submits only the missing specifications. It never performs a
routine recursive scan of physical checkpoint directories.

The prior duplicate-validation path is removed from the formal design:

- no second raw-data replay;
- no second generation of all completed replicates;
- deterministic replay rebuilds aggregate artifacts from the registered compact
  index and recomputes exactly one frozen sentinel;
- the original compact summaries and completion index remain immutable and
  auditable.

The resident supervisor now exposes live fields for completed replicate count,
total count, worker count, measured replicate rate, and ETA. On recovery, rate
uses only work completed in the current process, so restored checkpoints cannot
artificially inflate throughput.

## Exact generator and inference checks

### Gauss pass

- Legal sample space: `C(33, 6) = 1,107,568`.
- T1 normalizer: `2,875,258`, verified by exact combinatorial summation.
- J1 lower/upper transition rows each sum to one and each retain expected
  group-A count `32/11`; therefore the conditional one-number marginals remain
  uniform even though the joint transition changes with history.
- M1 and local M1 draw group counts use the exact finite legal-space mass
  `C(16,k) C(17,6-k) odds^k`, followed by uniform conditional subsets.
- All production identities are independent of worker and shard placement.

### Riemann pass

- T1 and J1 remain stateful sequence generators; neither was flattened into an
  independent marginal approximation.
- The estimator state is the ordered 33-number sufficient statistic plus issue
  count, preserving the intended expanding path.
- The compact index changes storage topology only. It does not change the
  stochastic path, score geometry, bootstrap blocks, or decision surface.

### Smallest shared conclusion

The safe acceleration boundary is execution topology and vectorized sufficient
statistics. The scientific generator, sequential state, exact truth, seed
identity, and frozen gates remain unchanged.

## Local single-host benchmark

No endpoint values, detection rates, or health decision were inspected during
the Engineering benchmark.

| Check | Result |
|---|---:|
| Sequential representative cells | 10 |
| Slowest observed long stateful replicate | 0.091786 s |
| Pure-compute upper projection using that maximum and 22 workers | 29.905 s |
| Parallel long-stateful sentinels | 44 |
| Parallel wall time including process startup | 0.758639 s |
| Observed parallel throughput | 57.999 replicates/s |
| Conservative linear projection for 7,168 replicates | 123.589 s |

Checkpoint creation, index fsync, aggregation, and supervisor/database commit
add overhead. The operational estimate for the full local run is therefore
approximately 2–10 minutes under normal availability, not weeks. Even allowing
large thermal or filesystem variance, the projection is far below the two-week
limit. The live progress artifact will replace this estimate once formal work
starts.

## Validation

- New execution tests: 11 passed.
- Related health-design, recovery, roadmap, and supervisor tests: 89 passed.
- Artifact-index replay test: passed after registering the new manifest and
  source contract identities.
- Ruff and Python byte compilation: passed.
- Worker full suite at the activated production-v2 runtime boundary:
  2,077 passed, 4 skipped, 43 failed before the artifact-index correction.
  One failure was the newly superseded manifest identity and was corrected and
  revalidated. The remaining 42 failures are existing legacy-line tests whose
  code intentionally fails closed because the local durable prediction-v2
  retirement activation is ACTIVE; the same failure reproduces at the prior
  merged runtime commit and is outside this round.

## First-release incident and exact recovery

The first merged-code dispatch failed closed before the first replicate. The
Round-42 source manifest carried four placeholder-looking parent digests that
did not equal the immutable Round-41 registered execution, workload, inference,
and design-completion artifacts. The single provenance check rejected the task
with `M4 v2 marginal-static health execution source identities changed`.

Immutable failed identity:

- task digest:
  `3f5a3250aaec1a1e02516734ad8f7ce49c5e8e0c18fafd098cb08bb9f2b103f0`;
- execution:
  `d0e5f7ee972ab33d899ca46d8d59cb718c1748888374bccf521273466663bfdf`;
- started event:
  `01445142e807fd3d0e996f7bc8818123ded5aa9860b5a28d6f562329bad79919`;
- failed event:
  `83cf08c7ef24550d932ef15d4439cac26ca48ff546c445874ef4b19a0db16ddc`;
- generated replicates, history reads, execution artifacts, database/CSV work,
  and Evidence: all zero.

The corrected manifest binds the task to the registered Round-41 identities
listed in that round's integration matrix. The recovery builder is bound to
the exact failed task, execution, two event digests, error text, failed state,
and absence of execution artifacts. Its live preflight permits exactly one
state transition, `failed/INTEGRATED -> draft/INTEGRATION_PENDING`, with zero
task/event deletion, event rewrite, or completed-task regression.

This does not remove the unique source-provenance check. It removes no safety
boundary and adds no second result-validation pass: duplicate raw replay,
database/CSV scanning, and routine physical checkpoint scanning remain off.
The original failed execution stays immutable and a separately approved
Operator recovery is still required before formal work can resume.

## Mainline integration matrix

| Binding | Round-42 status |
|---|---|
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Ready condition | Round-41 replay-verified design plus approved execution source |
| Runner | `research_evidence_supervisor` |
| Upstream artifacts | source, design execution, workload, inference, design completion |
| Ready Queue | capability registered; source manifest migration prepared |
| Supervisor | execution, progress, artifact registration, completion event implemented |
| Capability | 14 cells, 7,168 replicates, 112 logical shards, 22-worker local default |
| Checkpoint recovery | one compact index load; completed digests skipped directly |
| Downstream artifacts | completion index, health result, execution completion, mainline execution |
| Status projection | design, execution, live count/rate/ETA, next consumer |
| Evidence rule | synthetic health evidence only after complete registered replay |
| Decision consumer | separate `m4-v2-marginal-static-measurement-health-decision` task |
| Next consumer | health decision; historical execution remains unauthorized |
| Deterministic replay | compact aggregate reconstruction plus one raw sentinel |
| Formal mainline execution | pending merged-code Operator Request |

## Completion answer

`NO — INTEGRATION_PENDING`.

The code path and source migration are complete, but capability completion
requires the merged supervisor to run all cells, register the immutable
artifacts, emit the completion fact, feed the separate decision consumer, and
pass deterministic replay. A PR or unit test alone is not that proof.
