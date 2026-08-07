# M4 Measurement v2 Branch Fixture Freeze — Round 37

Date: 2026-08-07

Role: Engineering Agent

Agent Request: `engineering-m4-v2-branch-fixture-freeze-round-37-20260807`

Request / execution: `307 / 228`

## Round contract

- Primary goal: integrate the existing Ready task
  `m4-v2-branch-identifiability-fixture-freeze` as a result-blind mechanical
  freeze of the approved numerical solver, orthogonal controls, and legacy
  role-resolution fixtures.
- Non-goals: no formal branch execution, historical outcome read, statistical
  result read, threshold selection, model or feature change, Evidence,
  Prediction v2 promotion, production action, or P3 execution.
- Ready condition: the branch preflight design is complete and replayed, and
  the approved fixture-freeze source contract is available.
- Runner: unified Research Evidence Supervisor.
- Upstream artifacts: preflight design execution, preflight completion,
  cross-branch design, and the dedicated fixture-freeze source contract.
- Downstream artifacts: joint maximum-entropy solver fixture contract,
  orthogonal branch-control fixture contract, legacy IS2/IS3 role-resolution
  fixture contract, zero-execution completion, and mainline execution.
- Status projection:
  `CODE_COMPLETE -> INTEGRATION_PENDING -> VALIDATED_IN_MAINLINE -> COMPLETE`.
- Evidence rule: fixture freezing creates zero Evidence and cannot assign an
  empirical branch `PASS` or `FAIL`.
- Decision consumer: result-blind branch identifiability preflight executor.
- Next consumer: `m4-v2-branch-identifiability-preflight-execution`.

## Change

The new capability freezes the fixed-cardinality maximum-entropy family on the
exact legal six-of-33 support. The numerical contract uses gauge
`lambda_33=0`, elementary-symmetric-polynomial dynamic programming, analytic
covariance Hessian, deterministic damped Newton iteration, a 100-iteration
limit, `1e-12` input-sum and marginal-residual tolerances, and a `1e-9`
interior floor. Invalid input or non-convergence fails closed; it is never
renormalized and never replaced by uniform or independent-Bernoulli output.

Exact combinatorics regenerate the uniform and two weighted-group partition
fixtures. The same immutable source computes four orthogonal branch controls
and the legacy IS2/IS3 residual truth anchors. Contract loading rejects source
byte drift, formula drift, role drift, or numerical-boundary drift.

The completion is deliberately zero-execution:

```text
fixture contracts:            3
formal branch runs:           0
preflight executions:         0
preflight results:            0
actual folds:                 0
historical outcomes read:     false
statistical results read:     false
Evidence created:             false
Evidence progress increment:  0
```

The source-byte boundary contains only
`measurement_system_v2/fixture_freeze.py`. Supervisor orchestration, status
projection, migration tooling, and tests remain outside that immutable replay
boundary so later mainline consumers can evolve without invalidating this
completed fixture identity.

## Duplicate-validation boundary

This round does not restore either removed hot-path duplicate replay:

- Measurement v2 raw replay remains a single canonical read of the registered
  execution rather than a second full computation.
- P2.7 routine checkpoint replay remains metadata/content-address validation;
  the roughly 31,000-checkpoint physical scan is still an explicit deep-audit
  operation only.

The new deterministic replay reconstructs four small fixture artifacts from
their frozen source and parent identities. It does not scan checkpoints or
rerun historical/formal workloads.

## Additive migration proof

The exact migration was dry-run against the current durable database manifest:

```text
live manifest:                 5f6d86701ebc4b03623672731c2ad4e531515e44390211e06e76e47356f91c6b
source manifest:               3f27f9af24b9265b99abfd436299b2bdab16119c7880e1790d66101d193b0ea6
projected output manifest:     e65543c0e3066ee839d5fd377512252e23c65eb50f1be902dd1649557c1c4193
dry-run artifact:              571bc812afcef2b860e4421f2ce9ce05f7538aafdbb8419d2d23eed84a86bc8b
source contract:               391acc6a04518389f841e94a640a14dcaf98bd2c36614d31a0e713446980b06d
source set:                    611678e0602f25cd3f0e567761562f30ebedd2372eadbe0cb4376d011713c678
tasks:                         41 -> 42
unchanged existing tasks:      40
existing Goal deletions:       0
existing Task deletions:       0
existing state regressions:    0
existing fact deletions:       0
unallowlisted rewrites:        0
```

Only the unstarted fixture-freeze task is revised, only the preflight-execution
consumer is added, and only the fixture source-contract fact is added. Every
completed design/replay/raw-binding/P2.7/marginal task and fact is preserved.

## Einstein diagnostic

The smallest falsifiable question is whether the three intended branch roles
can be distinguished on legal-support controls before any historical result is
read. This round fixes the data-generating mechanisms and exact truth anchors;
it does not claim that the production estimators have passed them. The next
task must execute these frozen controls without changing their identities.

## Gauss–Riemann cross-review

Historical boundary: Gauss and Riemann are used as historically inspired
verification and structural lenses, not literal minds or authority for this
modern measurement pipeline.

### Gauss pass

- Strongest claim: legal sample-space cardinality, weighted partitions,
  rational marginals, solver boundaries, and truth anchors are regenerated from
  explicit exact combinatorics and rejected on drift.
- Weakest assumption: float64 damped Newton will satisfy the frozen residual
  boundary across every later formal fixture.
- Decisive test: execute all exact/positive/negative/boundary fixtures and
  verify convergence, residual, direction, and fail-closed behavior.
- Rejection condition: normalization substitution, boundary acceptance,
  residual above `1e-12`, or a positive/negative control on the wrong side of
  its frozen threshold.

### Riemann pass

- Strongest claim: the controls are structurally orthogonal—static marginal,
  temporal increment, and joint residual each receive one isolated positive
  direction while adjacent branches remain null.
- Weakest assumption: the chosen history-state coordinates expose the intended
  temporal and joint geometry without estimator-induced aliasing.
- Decisive test: run the same estimator graph on all controls and require the
  frozen role matrix, not merely aggregate positive information.
- Rejection condition: credit leaks from one branch into another, or legacy
  IS2/IS3 cannot be resolved under the v2 joint-residual definition.

### Disagreement and synthesis

Gauss prioritizes numerical convergence and exact boundary rejection; Riemann
prioritizes preservation of the nested branch geometry. The smallest shared
conclusion is to freeze both in one immutable contract and defer every empirical
claim to the next result-blind preflight-execution task.

## Validation

- Fixture-freeze and existing preflight-design tests: `13 passed`.
- Supervisor, control-plane, Measurement v2, and status tests: `44 passed`.
- Complete information-theory, M4, and unified Supervisor surface:
  `503 passed, 4 skipped in 148.50s`.
- The first broad run exposed one expected source-partition count increment
  (`376 -> 377`) for the new migration entrypoint; the exact coverage assertion
  was updated and the full surface then passed.
- Ruff, Python compile, JSON parsing, source-byte verification, manifest digest
  validation, live additive migration dry-run, and `git diff --check`: passed.
- Clean detached full Worker suite:
  `2074 passed, 4 skipped, 4 warnings in 218.35s`. The warnings are the
  existing Python 3.14 multiprocessing `fork()` deprecations in parallel
  training-supervisor tests.

## Integration matrix

| Link | Round-37 engineering state | Proof |
| --- | --- | --- |
| Goal -> Resolver | Code complete | Existing M4 Goal and revised exact task |
| Resolver -> Ready Queue | Dry-run verified | Durable manifest projects only fixture-freeze Ready |
| Ready Queue -> Supervisor | Code complete | Capability registered under exact requested capability |
| Supervisor -> Capability | Code complete | Parent design lineage and source bytes validated |
| Capability -> Artifacts | Code complete | Solver + controls + legacy roles + completion + execution |
| Artifacts -> Status | Code complete | Fixture-freeze projection and zero-result counters |
| Status -> Next Task | Declared | Preflight-execution consumes exact completion fact |
| Deterministic replay | Code complete | Reconstruction and registered-content verification implemented |

Final integration answer at engineering handoff:

`NO — INTEGRATION_PENDING`

The merged commit must be installed under a fresh unified Supervisor, the exact
additive manifest imported by an approved Operator, the fixture-freeze task
completed once, and its deterministic replay verified before this capability is
`COMPLETE`.
