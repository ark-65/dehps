# M4 Measurement v2 Branch Preflight Execution — Round 38

Date: 2026-08-07

Role: Engineering Agent

Agent Request: `engineering-m4-v2-branch-preflight-execution-round-38-20260807`

Request / execution: `310 / 231`

Research contract: `research-m4-v2-branch-preflight-execution-round-38-20260807`
(`309 / 230`, frozen before implementation)

## Round contract

- Primary goal: execute the Round-37 result-blind analytic fixtures through the
  canonical Goal, resolver, Ready Queue, unified Supervisor, immutable artifact
  registry, status projection, and deterministic replay path.
- Non-goals: no historical outcome read, formal branch workload, Monte Carlo,
  statistical result read, Evidence, model promotion, production action, or P3.
- Ready condition: the exact fixture-freeze execution, three fixture contracts,
  fixture completion, three branch designs, cross-branch design, and approved
  execution source contract are available.
- Runner: unified Research Evidence Supervisor.
- Downstream artifacts: one solver result, one orthogonal endpoint matrix, one
  legacy-role result, three branch-health results, one completion, and one
  mainline execution artifact.
- Evidence rule: deterministic analytic fixture results diagnose measurement
  health but create zero historical Evidence.
- Decision consumer: the marginal-static measurement contract freezer, and only
  when the immutable `ALL_BRANCHES_PASS` fact exists.
- Next consumer: `m4-v2-marginal-static-measurement-contract-freeze`.

## Change

The preflight executor runs three valid fixed-cardinality maximum-entropy
fixtures, five invalid numerical-boundary inputs, and the label permutation
that swaps numbers 1 and 17 while keeping the gauge label 33 fixed. It then
recomputes all 12 orthogonal branch-control endpoints and four legacy IS2/IS3
state residuals from the frozen formulas. Observations are never copied from
truth anchors.

The output state is fail-closed:

- `PASS` requires every numerical, permutation, positive-control,
  negative-control, and truth-anchor check to pass.
- `FAIL` represents a conclusive violated boundary.
- `UNRESOLVED` represents solver or analytic failure and cannot release a
  downstream task.

Only the exact ordered vector `PASS, PASS, PASS` emits
`m4-v2-branch-identifiability-preflight-execution:ALL_BRANCHES_PASS`.
Completion without that fact deliberately leaves the next consumer blocked.

The isolated deterministic execution produced:

```text
valid solver fixtures:        3 / 3 PASS
invalid boundary cases:       5 / 5 PASS (typed rejection)
permutation equivariance:     PASS
orthogonal endpoints:         12 / 12 PASS
legacy state residuals:       4 / 4 PASS
branch health:                PASS / PASS / PASS
historical outcomes read:     false
statistical results read:     false
Monte Carlo replicates:       0
Evidence created:             false
```

The tightest observed solver values remained inside the frozen Research
contract:

```text
maximum marginal residual:              9.6186947295962e-13 <= 1e-12
maximum gauge parameter absolute error: 1.2882250821633079e-11 <= 1e-9
maximum partition relative error:       4.857091773586411e-11 <= 1e-10
permutation marginal residual:           9.618139618083887e-13 <= 1e-12
permutation gauge error:                 1.021405182655144e-14 <= 1e-9
permutation log-partition error:         5.684341886080802e-14 <= 1e-10
```

## Duplicate-validation boundary

This round preserves both earlier throughput fixes:

- Measurement v2 raw replay is not restored; registered canonical execution is
  read once.
- Routine P2.7 completion still does not physically scan roughly 31,000
  checkpoints / 40 GiB; deep physical audit remains explicit opt-in only.

Deterministic replay reconstructs only the seven small preflight child
artifacts from frozen identities and compares their registered bytes. It does
not rerun historical folds, scan checkpoints, or repeat a formal workload.

## Additive migration proof

The exact migration and completed durable execution reported:

```text
source manifest:               4c2b1f44f2c1e20be80e128ab26e47e337989f21d7698b39d48c30391834cbad
live manifest before migration:96a9337a0f802bfb8f22b442f7b37589e8585b8053e88250c1884235cb57e88e
imported manifest:             e548fe0cb42648fb72d401eb7d56ac31b254345b738fc351b8bccd9afe35be9b
dry-run artifact:              dde2772fa1b2b1d8d8e30fd24376ce61efa57a20bfa44f7c4d57fc81d25ebb6b
completed live manifest:       2097823f8cb0478144cc2694d68a4bfc68a24f3df970751d19bc45045b6e4775
source contract:               7da905d15249813e44bcf57b4e107fac15bb2d02587c4c68134ca5c834aac5c1
tasks:                         42 -> 43
unchanged existing tasks:      41
existing Goal deletions:       0
existing Task deletions:       0
existing state regressions:    0
existing fact deletions:       0
unallowlisted rewrites:        0
```

Only the unstarted preflight-execution task is revised, only the conditional
marginal-static contract-freeze consumer is added, and only the preflight
source-contract fact is added.

The fresh merged Supervisor completed execution
`668fceb8663e3687a9f748e152c4fa066bf0048cb1efa5b9ce9a3f63f6cfd741`.
Its mainline execution artifact is
`dc6e9da1a8dfd0539078bc8eb82ee09f5ba5db5cf86c838b04a90128a88a4b3b`;
the three branch-health results are:

```text
MARGINAL_STATIC:             3d9207bb3e552283ead5125e395894cbb21038fabff02dd88f0530487896306a PASS
TEMPORAL_MARGINAL_INCREMENT: 2f238a0a4aff1698f50f2c155412352e994e0804277770c6a27afeb3ff133605 PASS
JOINT_RESIDUAL_INCREMENT:    9939b6f91fa42910ccf6d6066eff3bff9939bb0352d0dce018e44f68bbea076a PASS
completion:                  8d890a76e8e5b5f10099cb185042af1da2ff76b5fa7494b6805dc3a965c7cace
replay:                      REPLAY_VERIFIED, same identities and content
```

## Einstein diagnostic

The smallest falsifiable question is whether the intended three-way
decomposition responds only to its own legal-support control while the other
two branches remain null. A positive score alone is insufficient: every
off-branch endpoint must remain inside the frozen null tolerance and the joint
solver must reject invalid marginals without substitution.

## Gauss–Riemann cross-review

Historical boundary: Gauss and Riemann are historically inspired verification
and structural lenses, not literal minds or authority for this modern system.

### Gauss pass

- Exact obligation: verify the legal fixed-six partition, marginal residual,
  gauge, partition, invalid-domain rejection, and label-permutation invariance.
- Weakest assumption: float64 Newton convergence remains stable close to the
  `1e-12` residual boundary.
- Rejection condition: any fallback distribution, untyped invalid-input
  acceptance, tolerance breach, or truth-anchor mismatch.

### Riemann pass

- Structural obligation: preserve the nested static-marginal, temporal
  increment, and joint-residual coordinate split under all four controls.
- Weakest assumption: the legacy IS2/IS3 coordinates remain interpretable as
  diagnostic residuals without receiving v2 decision credit.
- Rejection condition: endpoint credit leaks across branches or the intended
  positive direction becomes inseparable from an adjacent branch.

### Shared conclusion

The smallest shared conclusion is the strict three-branch gate implemented in
this round. It establishes measurement identifiability only; it does not yet
establish predictive lift.

## Validation

- New execution, source-integrity, fail-closed, migration, status, capability,
  and determinism tests: `8 passed`.
- Execution plus existing fixture/design/Measurement-v2/Supervisor regression:
  `56 passed`.
- Complete information-theory, M4, and unified Research OS surface:
  `511 passed, 4 skipped in 158.63s`.
- Clean detached full Worker suite:
  `2082 passed, 4 skipped, 4 existing warnings in 231.34s`.
  The warnings are the existing Python 3.14 multiprocessing `fork()`
  deprecations in parallel training-supervisor tests.
- Source partition coverage incremented once for the new worker module:
  `377 -> 378`; exact partition test passed.
- The pre-release durable-artifact audit caught three stale branch-design
  digests in an intermediate working summary. They were replaced by the exact
  registered Round-36 identities and the source/import/dry-run digests were
  recomputed before push or live import.
- Ruff, Python compile, JSON parsing, source-byte verification, manifest digest
  validation, additive migration dry-run, and `git diff --check`: passed.

## Integration matrix

| Link | Engineering handoff state | Proof |
| --- | --- | --- |
| Goal -> Resolver | Validated | Exact M4 task definition and frozen source identity imported into durable truth |
| Resolver -> Ready Queue | Validated | Only preflight execution became executable |
| Ready Queue -> Supervisor | Validated | Fresh merged Supervisor claimed the exact task once |
| Supervisor -> Capability | Validated | Ten ordered parent identities and zero-result lineage checked |
| Capability -> Artifacts | Validated | Seven child artifacts plus mainline execution registered immutably |
| Artifacts -> Status | Validated | PASS/FAIL/UNRESOLVED and branch counters projected from durable execution |
| Status -> Next Task | Validated | `ALL_BRANCHES_PASS` released only the marginal-static contract freezer |
| Deterministic replay | Validated | Small artifacts reconstructed with identical registered identities and content |

Final integration answer after the approved Operator execution:

`YES — validated by unified mainline execution and replay`
