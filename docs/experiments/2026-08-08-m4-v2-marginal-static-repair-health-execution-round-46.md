# M4 v2 Marginal-Static Repair Health Execution — Round 46

## Primary goal

Integrate the frozen Round-45 repaired measurement-health program as the sole
mainline execution capability. The merged Operator run will execute exactly
4,608 independent replicate paths, persist compact scalar summaries, aggregate
the preregistered scale-local split-conformal and interval diagnostics, and
unlock exactly one separate health-decision task.

## Non-goals

- No formal replicate or generated issue during this Engineering round.
- No estimator, fixture, scale, seed, workload, inference gate, feasibility
  value, threshold, or prior decision change.
- No nested bootstrap, raw replay, sentinel replay, duplicate validation,
  recursive checkpoint scan, database I/O per replicate, or CSV materialization.
- No authoritative repaired-health decision, historical outcome read, Evidence,
  accepted model, P3, Prediction-v2 promotion, betting output, or production
  action.

## Frozen execution

| Lane | Replicates | Generated sequence issues |
| --- | ---: | ---: |
| Scale-local uniform calibration | 1,024 | 2,274,304 |
| Four base + three local cells per scale | 3,584 | 7,960,064 |
| Total | 4,608 | 10,234,368 |

The program has 72 logical shards of 64 replicates and 6,087,168 outer
evaluation issues. Every child seed is derived from the immutable
preregistration digest, lane, cell, scale, and replicate index. Calibration and
evaluation domains are disjoint and Round-42 child identities are not reused.

## Exact inference and feasibility

- Each evaluation score is compared only with the 512 uniform calibration
  scores at the same scale.
- Split-conformal p-value:
  `(1 + count(calibration_score >= evaluation_score)) / 513`.
- The alpha-0.05 rejection boundary is exactly `count <= 24`; ties are
  exceedances.
- Conditional truth, residual, and observed means use two-sided 95% Student-t
  intervals over 256 independent replicate summaries, `df=255`,
  `t=1.9693105698498752`.
- Detection rates use two-sided 95% Wilson intervals without continuity
  correction, `z=1.959963984540054`.
- The exact randomized level-0.05 Neyman-Pearson upper-power values are
  recomputed before evaluation dispatch and checked against all six frozen
  values. A local target is admissible only when exact upper power is at least
  0.80 and the new conditional-truth lower confidence bound is positive.
- Vectorized conditional truth is checked against a separate scalar `fsum`
  oracle with maximum absolute error `1e-12` while preserving T1/J1 temporal
  generation.

## Gauss / Riemann cross-review

### Gauss pass

- Legal sample-space arithmetic, counts, finite values, exact parent digests,
  seed uniqueness, conservative conformal ties, and interval constants are
  executable proof obligations.
- The pre-sample feasibility artifact is created before replicate dispatch and
  cannot read alternative results.
- A truncated, duplicated, tampered, or context-mismatched compact-index row
  fails closed.

### Riemann pass

- Exchangeability applies to independently seeded replicate paths at a fixed
  scale, never to dependent issues within a T1/J1 path and never across scales.
- The scalar replicate endpoint is sufficient for the frozen health question;
  legality, probability normalization, conditional identity, and residual
  diagnostics retain the structural information needed to reject a broken
  implementation.
- Moving from issue-block bootstrap children to independent path outcomes
  changes the inference geometry without changing the generator or estimator.

### Disagreement and smallest shared conclusion

Exact feasibility alone does not prove online detectability, while a positive
empirical truth interval alone does not prove that the frozen detector had
adequate power. Both gates are therefore required. One independent calibration
lane, one independent evaluation lane, compact scalar summaries, and aggregate
replay are sufficient; a second raw or sentinel validation pass has no distinct
consumer and remains forbidden.

## Implementation

- New capability:
  `m4_v2_marginal_static_measurement_repair_health_execution`.
- Four immutable child artifacts: compact completion index, pre-sample
  feasibility, repaired measurement-health result, and execution completion.
- Direct resume loads one append-only compact index, verifies each row, and
  skips exact completed replicate digests without walking checkpoint files.
- Replay reconstructs all four artifacts from the compact index with zero raw
  replicate regeneration and zero sentinel recomputation.
- The execution result is explicitly preliminary. The old authoritative
  `REPAIR_MEASUREMENT_SYSTEM` decision remains in force.
- Completion fact:
  `m4-v2-marginal-static-measurement-repair-health-execution:COMPLETE`.
- Sole next consumer:
  `m4-v2-marginal-static-measurement-repair-health-decision`.

## Validation

- New source, statistics, identity, compact-index, aggregate, supervisor,
  replay, migration, status, and registration tests: `12 passed`.
- Full affected Measurement-v2, source partition, and Research Evidence
  Supervisor regression: `84 passed`.
- Full non-retired Worker suite: `2,073 passed, 4 skipped`.
- The first unfiltered run had `2,115 passed, 4 skipped, 43 failed`: 42 are
  durable guards against retired legacy three-line interfaces; the sole current
  failure was the expected source-partition count increment for the new module,
  which was corrected and passed before the non-retired full run.
- Static validation: Ruff clean, Python compilation clean, `git diff --check`
  clean.
- The test aggregate uses fabricated summaries and does not constitute a
  formal outcome. Engineering executed zero formal replicates and generated
  zero formal issues.

## Mainline integration matrix

| Link | Engineering state |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` unchanged |
| Resolver | Exact preregistration/source parents and separate decision dependency declared |
| Ready Queue | Execution becomes ready only after Round-45 completion and source fact |
| Supervisor | Formal capability, progress path, immutable registration, and completion event implemented |
| Capability | 1,024 calibration + 3,584 evaluation paths implemented |
| Artifacts | Compact index, feasibility, health result, completion, and execution identities bound |
| Status | Counts, preliminary health, authoritative-decision boundary, and next task projected |
| Next task | One separate repaired-health decision only |
| Deterministic replay | Compact-index aggregate reconstruction implemented and tested |
| Merged live execution | Pending PR merge and approved Operator release |

Capability complete:

`NO — INTEGRATION_PENDING` until the merged commit is executed by the unified
Research Evidence Supervisor, all 4,608 formal children complete, the registered
content replays exactly from the compact index, and the separate decision task
consumes the result.
