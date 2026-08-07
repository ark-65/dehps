# M4 Measurement v2 Branch Preflight Design — Round 36

Date: 2026-08-07

Role: Engineering Agent

Agent Request: `engineering-m4-v2-branch-preflight-design-round-36-20260807`

Request / execution: `304 / 225`

## Round contract

- Primary goal: integrate the existing Ready task
  `m4-v2-branch-identifiability-preflight-design` as a result-blind mechanical
  projection of frozen Measurement Contract v2.
- Non-goals: no preflight execution, historical outcome read, statistical
  result read, solver tolerance, workload, threshold, model, hypothesis,
  Evidence, Prediction v2 promotion, production action, or P3 execution.
- Ready condition: the Measurement Contract v2 design and its registered replay
  are complete, and the dedicated preflight computation source contract is
  available.
- Runner: unified Research Evidence Supervisor.
- Upstream artifacts: frozen Measurement Contract v2, its completed design and
  replay executions, Gate Compiler replay artifact, and the dedicated preflight
  source contract.
- Downstream artifacts: three branch-local design contracts, one cross-branch
  no-duplicate-credit contract, one zero-execution completion, and the mainline
  execution artifact.
- Status projection:
  `CODE_COMPLETE -> INTEGRATION_PENDING -> VALIDATED_IN_MAINLINE -> COMPLETE`.
- Evidence rule: design projection creates zero Evidence and cannot assign
  `PASS` or `FAIL` to any branch.
- Decision consumer: branch preflight fixture freezer.
- Next consumer: `m4-v2-branch-identifiability-fixture-freeze`.

## Change

The new capability projects the exact branch order
`MARGINAL_HISTORICAL -> TEMPORAL_MARGINAL_INCREMENT ->
JOINT_RESIDUAL_INCREMENT`. Each branch receives its frozen legal domain,
estimand, adjacent baseline, mechanism-role matrix, validity checks,
measurement-acceptance checks, and unresolved contract markers. The
cross-branch artifact carries the frozen no-duplicate-credit invariants and
statistical-input/provenance contracts.

The completion is deliberately zero-execution:

```text
branch designs:               3
formal branch runs:           0
preflight results:            0
actual folds:                 0
historical outcomes read:     false
statistical results read:     false
Evidence created:             false
Evidence progress increment:  0
```

The source contract freezes only the stable computation kernel
`contracts.py + preflight_design.py`. Mutable orchestration, status projection,
and migration files are validated by tests and the execution git commit but are
not placed inside the future replay byte boundary. This is intentional: the
already-completed P2.6.3 slot-governance contract demonstrates that hashing a
shared mutable `progress.py` makes historical capability re-execution correctly
fail after later mainline evolution. The preflight replay must remain possible
while later consumers extend Supervisor and status projection.

## Additive migration proof

The migration was dry-run directly against the current durable manifest:

```text
live manifest:                 a794f0e98d7ed2dee478585f49c4e20549d153be009f884d613b5eb40c77a87a
source manifest:               9d67c07990707e783384386b4c5c09e2a1f5b3c3521d93dcfd38817feddc69f5
projected output manifest:     3fc3ad5ef8e291d423c01c08653fcda03a36043d36c412297657f50c2062063d
dry-run artifact:              6b2cc4fd3bf84740f8add3c1d2b3b7c683b13cf75cbc25679b979368a214bbd4
source contract:               6fb3a1e366da129ac460599a391891a49206ccc715b6367cf344e2aa3e9f2a3d
source set:                    300168c4e9500441aec4694d5e08b0a6725c833c7edd53d0899729158e103f6a
tasks:                         40 -> 41
unchanged existing tasks:      39
existing Goal deletions:       0
existing Task deletions:       0
existing state regressions:    0
existing fact deletions:       0
unallowlisted rewrites:        0
```

Only the unstarted preflight task is revised, only the fixture-freeze consumer
is added, and only the source-contract fact is added. The durable states and
facts for design, replay, raw source binding, P2.7 replay, marginal binding, and
marginal decision replay remain complete and unchanged.

The generic additive migrator also now normalizes Goal representations before
definition comparison while preserving all live Goal state fields exactly.
This permits a database-exported manifest containing explicit null state fields
to migrate against the compact source JSON without weakening definition or
state checks.

## Einstein diagnostic

The smallest falsifiable question is: can each branch be tested against its
exact adjacent baseline without reading result geometry, conditioning choices,
or prior scores? Round 36 answers only the design half. It freezes the testable
objects and leaves every empirical answer empty. A later fixture round must
show that those objects can be instantiated without changing the frozen
contract.

## Gauss–Riemann cross-review

Historical boundary: Gauss and Riemann are used as historically inspired
verification and structural lenses, not literal minds or authority for this
modern measurement pipeline.

### Gauss pass

- Strongest claim: the artifacts are exact deterministic projections of the
  frozen legal sample space, estimands, baselines, and acceptance obligations.
- Weakest assumption: unresolved numerical solver requirements can be carried
  forward without inventing tolerances in this round.
- Decisive test: reconstruct the five artifacts from the same frozen contract
  and parent digests, then require exact registered content equality.
- Rejection condition: any nonzero fold/result/Evidence count, missing unresolved
  marker, changed adjacent baseline, or source-byte mismatch.

### Riemann pass

- Strongest claim: the nested geometry is preserved as marginal, then temporal
  increment over accepted marginal structure, then joint residual over accepted
  temporal structure.
- Weakest assumption: artifact edges alone are sufficient to preserve that
  geometry until executable fixtures exist.
- Decisive test: require the exact ordered branch graph and the cross-branch
  no-duplicate-credit invariants in one immutable artifact set.
- Rejection condition: a branch becomes independent of its adjacent accepted
  parent, or a marginal/temporal contribution can be credited again downstream.

### Disagreement and synthesis

Gauss would prefer solver tolerances and boundary cases to be fixed before any
claim of identifiability; Riemann would first preserve the nested structural
edges and defer numerical coordinates. The smallest shared conclusion is the
implemented projection-only design. Solver, workload, conditioning-boundary,
and fixture choices remain explicitly unresolved and belong to the next task.

## Validation

- New preflight tests: `6 passed`.
- Existing Measurement v2, replay-integrity, status, and M4 hardening tests:
  `91 passed`.
- Complete information-theory, M4, and unified Supervisor test surface:
  `478 passed in 141.84s`.
- Full live-root Worker run: `2023 passed, 44 failed, 4 skipped`; 42 failures are
  the known fail-closed legacy tests caused by the existing untracked Prediction
  v2 activation runtime. The two initially relevant failures were corrected:
  the artifact index now supersedes the previous manifest identity, and the
  historical P2.6.3 source-governance test now asserts the intended rejection
  after shared orchestration evolution.
- Clean detached full-suite result with the detached source root bound through
  an absolute `PYTHONPATH`: `2067 passed, 4 skipped, 4 warnings in 215.29s`.
  The warnings are the existing Python 3.14 multiprocessing `fork()`
  deprecations in parallel training-supervisor tests.
- Ruff, Python compile, source-byte verification, manifest digest validation,
  and `git diff --check`: passed.

## Integration matrix

| Link | Round-36 engineering state | Proof |
| --- | --- | --- |
| Goal -> Resolver | Code complete | Existing M4 Goal and revised exact task |
| Resolver -> Ready Queue | Dry-run verified | Durable `a794f0…` projects preflight Ready |
| Ready Queue -> Supervisor | Code complete | Capability registered under exact requested capability |
| Supervisor -> Capability | Code complete | Parent design/replay lineage and source bytes validated |
| Capability -> Artifacts | Code complete | 3 branch + cross-branch + completion + execution |
| Artifacts -> Status | Code complete | `branch_preflight_design` projection and zero counters |
| Status -> Next Task | Declared | Fixture-freeze dependency consumes exact completion fact |
| Deterministic replay | Code complete | Reconstruction and registered-content verification implemented |

Final integration answer at engineering handoff:

`NO — INTEGRATION_PENDING`

The merged commit must be installed under a fresh unified Supervisor, the exact
additive manifest imported by an approved Operator, the preflight task completed
once, and its deterministic replay verified before this capability is
`COMPLETE`.
