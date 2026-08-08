# M4 v2 Marginal-Static Repair Preregistration — Round 45

## Primary goal

Integrate the approved repair-health preregistration as the single zero-sample
mainline capability between the Round-44 repair design and one future repaired
health execution. Freeze the workload, independent seed lanes, split-conformal
test, interval definitions, decision gates, compact resume boundary, and sole
downstream consumer before generating the first new issue.

## Non-goals

- No calibration or evaluation replicate and no generated issue.
- No nested bootstrap, issue-block bootstrap, duplicate validation, raw replay,
  physical checkpoint scan, database read, or CSV materialization.
- No change to the estimator, generator, fixture, scale, threshold, Round-42
  health result, Round-43 decision, or Round-44 repair artifacts.
- No repaired health decision, historical measurement, Evidence, accepted
  model, Prediction v2 promotion, P3, betting output, or production action.

## Frozen workload

| Lane | Unit | Replicates | Generated sequence issues if executed |
| --- | --- | ---: | ---: |
| Null calibration | 512 per scale × 2 scales | 1,024 | 2,274,304 |
| Evaluation | 256 per cell × 7 cells × 2 scales | 3,584 | 7,960,064 |
| Total | 64 per shard × 72 shards | 4,608 | 10,234,368 |

The total outer evaluation horizon is 6,087,168 issue predictions. Round 42
used 7,168 outer replicates, so the new protocol removes 2,560 replicates, or
35.714285714285715%. Nested bootstrap work falls from 511 children per formal
replicate to zero.

This round executes none of that workload. It emits only immutable contracts.

## Frozen inference and exactness addendum

- Analysis unit: one independently seeded replicate's scalar mean prequential
  candidate-minus-uniform log-score gain in bits per issue.
- Per scale, the null calibration set contains 512 independently seeded uniform
  scores and never reads alternative outcomes.
- The upper-tail split-conformal p-value is
  `(1 + count(calibration_score >= evaluation_score)) / 513`.
- At alpha 0.05, rejection is exactly `exceedance_count <= 24`; equal scores
  count as exceedances and no randomized tie break is allowed.
- Mean conditional online truth and mean residual use the same two-sided 95%
  one-sample Student-t interval over exactly 256 independent replicate
  summaries, with `df=255` and critical value `1.9693105698498752`.
- Detection-rate intervals use the two-sided 95% Wilson interval without
  continuity correction and `z=1.959963984540054`.
- Wrong counts and non-finite inputs are structural failures. A finite
  zero-variance Student-t sample returns the point mean as both endpoints.

The exact conditional score identity remains a gate at absolute numerical
error at most `1e-12`. Empirical residual bias is diagnostic only.

## Gauss / Riemann cross-review

### Gauss pass

- The conformal denominator makes the rejecting integer rank explicit: 24
  exceedances pass, 25 fail.
- Calibration and evaluation seed sets are disjoint, deterministic, independent
  of worker/shard identity, and do not reuse Round-42 children.
- Local target feasibility is computed before formal evaluation dispatch.
- Workload arithmetic, finite-value checks, and all prior artifact digests are
  proof obligations rather than operational assumptions.

### Riemann pass

- Exchangeability is asserted across independent replicate paths, not across
  dependent issues inside a path.
- T1 and J1 remain orthogonal path-generating controls, while the primary
  detector consumes only the scalar replicate endpoint.
- Removing the issue-block bootstrap changes the inference geometry, not the
  estimator or the already frozen health outcome.

### Smallest shared conclusion

One scale-specific null calibration, one independent evaluation lane, exact
conditional-score identity, pre-sample feasibility, and fixed replicate-level
gates are sufficient. A second validation pass over completed folds or
replicates would add cost without adding a new registered decision consumer and
is therefore forbidden.

## Implementation

- New capability:
  `m4_v2_marginal_static_measurement_repair_preregistration`.
- Four immutable child artifacts: workload/seeds, inference/gates,
  preregistration, and completion.
- Completion fact:
  `m4-v2-marginal-static-measurement-repair-preregistration:FROZEN`.
- Sole next consumer:
  `m4-v2-marginal-static-measurement-repair-health-execution`.
- Replay reconstructs the same four artifacts and execution identity with zero
  samples, zero generated issues, zero bootstrap, zero checkpoint/index reads,
  and zero duplicate validation.
- The future execution may load one compact completion index once and skip
  matching completed replicate digests. It may not scan physical checkpoints,
  replay raw draws, query a database per replicate, or materialize CSV input.

## Validation

- New preregistration tests: `9 passed`.
- New plus affected repair-design, supervisor, and status tests: `33 passed`.
- Additive migration dry-run: one revised preregistration task, one new repaired
  health-execution task, zero state regression, zero fact deletion, and zero
  unallowlisted definition rewrite.
- Full non-retired Worker suite: `2,055 passed, 4 skipped, 6 deselected`.
- The unfiltered local run has `2,098 passed, 4 skipped, 6 deselected, 42
  failed`: every failure is an expected durable guard against an already
  retired legacy three-line interface under the local Prediction-v2 activation.

## Mainline integration matrix

| Link | Engineering state |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` unchanged |
| Resolver | Preregistration and repaired-health dependencies declared |
| Ready Queue | Preregistration requires exact Round-44 completion and source facts |
| Supervisor | Zero-sample capability and registration path implemented |
| Capability | Four immutable preregistration artifacts implemented |
| Artifacts | Source, Round-44 parents, workload, inference, preregistration, completion, and execution identities bound |
| Status | Preregistration and sole repaired-health consumer projected |
| Next task | One independent repaired-health execution only |
| Deterministic replay | Preregistration-only reconstruction implemented and tested |
| Merged live execution | Pending PR merge and Operator release |

Capability complete:

`NO — INTEGRATION_PENDING` until the merged commit is executed by the unified
Research Evidence Supervisor and the registered content and execution identity
replay exactly.
