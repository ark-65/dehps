# M4 v2 Marginal-Static Repair Design — Round 44

## Primary goal

Integrate the approved result-aware repair design as a zero-sample canonical
mainline capability. The capability must preserve the Round-42 health result
and Round-43 `REPAIR_MEASUREMENT_SYSTEM` decision, emit an analytic feasibility
artifact, freeze independent seed domains, and route only to a separate repair
preregistration task.

## Non-goals

- No retroactive PASS or replacement of any Round-41 through Round-43 artifact.
- No power threshold selected from the observed Round-42 power values.
- No estimator, generator, fixture, scale, prediction model, or strategy change.
- No replicate, bootstrap, checkpoint/index read, historical outcome, Evidence,
  accepted model, Prediction v2 promotion, P3, or production action.

## Frozen evidence and diagnosis

The immutable health result is
`40b449a7abe4ac9fff6eb0e98212f5809e0f0ff76c93f1344b673b4716905e2d`.
The immutable decision is
`cb653dc02739958814b0e4b349e163bd10f9256a19c05f61dbc1808fe6948d50`.
It remains `REPAIR_MEASUREMENT_SYSTEM` with the same four failed cells.

The repair is required because the old health contract mixed distinct
quantities:

1. stationary oracle information;
2. finite-sample prequential utility of the expanding estimator;
3. detection power at a fixed horizon;
4. interval calibration under IID and dependent process geometry.

For the legal M1 family, exact convolution of the group-count distribution and
the randomized level-0.05 Neyman–Pearson test gives these upper envelopes:

| Horizon | Oracle target | Exact upper power | Old requirement | Classification |
| --- | ---: | ---: | ---: | --- |
| 61 | 0.010 bit/issue | 0.22958915217193457 | 0.80 | Analytically infeasible |
| 61 | 0.050 bit/issue | 0.6475131406108688 | 0.95 | Analytically infeasible |
| 2,581 | 0.010 bit/issue | 0.9999890785821147 | 0.80 | Oracle-feasible |

The 2,581-issue 0.010 cell is nevertheless not a positive online-estimator
control under the frozen 900-issue warm-up: its mean conditional truth is
`-0.0024829610710475126` bit/issue and only 15.625% of replicates have positive
conditional truth. That is a deployability limitation, not proof of a broken
score identity.

The three failed empirical bias point estimates also have 95% Monte Carlo
intervals containing zero. Round 44 therefore freezes the exact conditional
expectation identity as the primary bias proof obligation and leaves empirical
bias as an uncertainty-labelled diagnostic.

## Gauss / Riemann cross-review

### Gauss pass

- The legal sample space remains all `C(33,6)` subsets.
- The exact group-count mass, test size, horizon, and randomized boundary are
  explicit.
- A requested power gate is inadmissible when it exceeds the corresponding
  generator-specific Neyman–Pearson upper envelope.
- The old artifact identities and failed-cell topology are immutable.

### Riemann pass

- IID M1/uniform controls and the T1/J1 path-dependent controls occupy different
  sampling geometries.
- The next preregistration must freeze an IID inference route separately from
  the circular-block dependence route.
- Oracle information, online utility, sampling detection, and sensitivity
  limits remain separate typed outputs.

### Disagreement and smallest shared conclusion

An analytic feasibility bound alone cannot calibrate the deployed interval,
while an inference-routing change alone can preserve an impossible power gate.
The smallest shared repair is therefore: feasibility before gating, structural
inference routing before sampling, exact conditional truth, and wholly
independent future seeds.

## Implementation

- New source-bound capability:
  `m4_v2_marginal_static_measurement_repair_design`.
- New source contract:
  `m4-v2-marginal-static-repair-design-source-v1.json`.
- Three immutable child artifacts:
  analytic feasibility, repair design, and completion.
- New completion fact:
  `m4-v2-marginal-static-measurement-repair-design:FROZEN`.
- New sole downstream consumer:
  `m4-v2-marginal-static-measurement-repair-preregistration`.
- Replay reconstructs only the three design artifacts and execution identity.
- The execution and replay budgets are zero generated issues, zero synthetic
  replicates, zero checkpoint/index reads, and zero duplicate validation.

The independent future seed domains are:

- `M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_V1`
- `M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_BOOTSTRAP_V1`

## Validation

- Focused repair-design and health-decision tests: `12 passed`.
- Related M4 v2 and supervisor tests before the source-partition count update:
  `159 passed, 1 expected count failure`; the new module was then added to the
  audited orchestration partition and the focused regression passed.
- Full non-legacy-retirement Worker suite: `2,052 passed, 4 skipped`.
- The unfiltered local suite has `2,094 passed, 4 skipped, 43 failed`: 42 are
  the already active durable Prediction-v2 legacy-retirement guards, and the
  one Round-44 artifact-index mismatch was corrected before the clean
  non-legacy run.
- Additive migration dry-run:
  one revised repair-design task, one new repair-preregistration task, zero
  state regression, zero fact deletion, and zero unallowlisted rewrite.

## Mainline integration matrix

| Link | Engineering state |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` unchanged |
| Resolver | Repair design and preregistration dependencies declared |
| Ready Queue | Repair design becomes Ready only from exact Round-43 facts and the Round-44 source fact |
| Supervisor | Capability and registration path implemented |
| Capability | Three zero-work artifacts implemented |
| Artifacts | Source, feasibility, design, completion, and execution identities bound |
| Status | Repair-design and preregistration projections implemented |
| Next task | Independent repair preregistration only |
| Deterministic replay | Design-only reconstruction implemented and tested |
| Merged live execution | Pending PR merge and Operator release |

Capability complete:

`NO — INTEGRATION_PENDING` until the merged commit is executed by the unified
Research Evidence Supervisor and the exact registered artifacts replay.
