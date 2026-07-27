# M4-P2.6 Measurement Validation Mainline Implementation

Date: 2026-07-27

## Round contract

- Primary goal: implement the frozen P2.6 workload as the singular
  `m4-p2-false-positive-and-power-runs` mainline capability, including strict
  prior-only four-probe execution, complete formal resampling, immutable
  artifacts, automatic aggregation, MDE, replay, status projection, and the
  P2.7 PASS/REPAIR consumer.
- Non-goals: change signal strengths, change Gate thresholds, reduce the
  preregistered workload, select favorable seeds, use real history, promote a
  strategy, or count smoke output as Evidence.
- Frozen workload: 31 cells, 31,000 dataset replicates, 64,656,000 outer
  issues, four probes per issue, 2,000 bootstrap replicates and 2,000
  permutation replicates per analysis replicate, and 1,000 NC6 synthetic-null
  replicates per scale.

## Mainline implementation

The implementation binds the accepted P2.1-P2.5 artifacts to:

```text
Goal
-> Resolver
-> Ready Queue
-> Research Evidence Supervisor
-> deterministic execution plan
-> resumable process coordinator
-> P2.1 evaluation dataset generator
-> P2.3 strict walk-forward boundary
-> four frozen probes
-> P2.2 Metric Kernel
-> P2.5 bootstrap/permutation
-> 31,000 replicate artifacts
-> 31 cell aggregates
-> MDE summary
-> P2.6 completion
-> status projection
-> P2.7 automatic Gate
-> exactly one PASS_TO_P3 or REPAIR_MEASUREMENT_SYSTEM fact
```

The coordinator materializes all 31,000 identities before execution. Power,
evaluation-dataset, bootstrap, permutation, and shard-assignment seed domains
remain separate. Shard-count changes do not change child identities. Retries
and resumes reuse the same child seed.

Execution order is shortest outer scale first, then cell and replicate
identity. This is an operational order only: it does not inspect results and
does not alter the frozen plan, aggregate scope, Gate, or artifact identity.
Partial cells remain ineligible for Evidence.

## Leakage and replay controls

- The incremental feature cache advances only through a
  `TrainingDatasetView`; it cannot read the current outer target.
- Cached train and blind views reproduce the accepted P2.3 objects and digests.
- All four prediction checkpoint digests are appended to a strict-prior
  checkpoint journal before the target is accessed.
- A retry must reproduce every existing journal entry.
- The final replicate artifact commits the journal digest and entry count.
- Completion and replay verify all replicate identities, result digests,
  checkpoint journals, seed counts, cell aggregates, MDE identity, and
  completion identity.
- P2.7 replay reconstructs the automatic Gate and MDE from the P2.6 graph and
  requires the same decision fact.

## Formal negative-control interpretation

The frozen `negative_control_replicates = 1000` count is the complete
`NULL_UNIFORM` NC6 dataset-replicate cell at each scheduled scale. Therefore:

- 1,000 NC6 replicates at `FORWARD_61`;
- 1,000 NC6 replicates at `HISTORICAL`;
- 1,000 NC6 replicates at `LONG`;
- 3,000 NC6 replicates total.

It is not an additional 1,000 nested model retrainings inside every one of the
31,000 analysis replicates. P2.5 already validates the NC1-NC6 kernel
semantics; P2.6 formally exercises NC6 through the same complete measurement
path used by injected scenarios.

## Equivalence and live smoke

Equivalence checks cover:

- cached versus literal P2.3 train and blind feature objects and digests;
- cached versus literal state digest and probability output for all four
  probes;
- the P2.2 nested-validation aggregate API versus literal per-issue Metric
  Kernel output;
- vectorized permutation PE1 versus literal P2.2 issue output;
- deterministic seed, shard, journal, bootstrap, permutation, aggregation,
  MDE, Gate, and replay contracts.

One non-Evidence runtime smoke completed:

```text
Cell: FORWARD_61 / NULL_UNIFORM / replicate 0
Outer folds: 61 / 61
Probes: 4 / 4
Bootstrap: 2,000 / 2,000
Permutation: 2,000 / 2,000
Checkpoint journal: 61 / 61
Elapsed: 47.17 seconds
Positive-signal decision: false
Evidence eligibility: false (runtime smoke only)
```

The benchmark reduced the first four-probe fold from approximately 4.69
seconds to approximately 0.73 seconds without changing frozen outputs.
Terminal-fold measurements on this host were:

| Scale | Training issues at terminal fold | Four-probe fold |
|---|---:|---:|
| FORWARD_61 | 960 | approximately 0.8 seconds |
| HISTORICAL | 3,480 | 3.41 seconds |
| LONG | 6,961 | 5.95 seconds |

On the current 22-thread host, a conservative idealized 20-worker estimate is
roughly 100 continuous days for the literal full workload. This estimate is
operational information, not a reason to reduce or reinterpret the frozen
workload. The coordinator is restart-safe and exposes heartbeat, completed
count, throughput, retries, and ETA while the canonical Supervisor remains
running.

## Current integration matrix

| Requirement | Implementation | Current evidence |
|---|---|---|
| Canonical Goal and Task DAG | existing M4 Goal and P2.6/P2.7 tasks | PASS |
| Resolver and Ready Queue | P2.5 completion makes only P2.6 Ready | PASS |
| Unified Supervisor dispatch | P2.6 and P2.7 capabilities registered | code/test PASS |
| Full frozen workload | resumable 31,000-replicate coordinator | NOT YET COMPLETE |
| Immutable artifacts | plan, journals, replicates, aggregates, MDE, completion | code/test PASS |
| Status projection | P2.6 Evidence 25%, P2.7 decision retained while waiting | code/test PASS |
| Downstream consumer | mutually exclusive PASS/REPAIR fact and queue branch | code/test PASS |
| Deterministic replay | P2.6 graph and P2.7 Gate reconstruction | code/test PASS |
| Mainline invocation after accepted merge | fresh Supervisor required | PENDING |

Current completion answer:

```text
NO — INTEGRATION_PENDING
```

This changes to:

```text
YES — validated by unified mainline execution and replay
```

only after the accepted commit has run all frozen work, P2.7 has emitted one
automatic decision fact, the downstream branch is the sole Ready consumer, and
the complete graph has replayed successfully.
