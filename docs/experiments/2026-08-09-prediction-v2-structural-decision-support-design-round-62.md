# Prediction v2 Structural Decision-Support Design — Round 62

Date: 2026-08-09

Role sequence: Research Agent -> Engineering Agent

Primary goal: compile the replay-verified structural-pivot decision into one
transparent, result-blind portfolio-design contract and route all executable
choices to a separate preregistration.

## Non-goals

- No history, database data row, CSV, fold, bootstrap child, checkpoint,
  candidate score, ranking, prediction, or duplicate index is read.
- No candidate portfolio or optimizer is executed.
- No budget, seed, null replicate count, tolerance, threshold, or scalar weight
  is selected.
- No Evidence, predictive model, expert, promotion, P3 transition, betting
  output, or production action is created.

## Typed authorization

- Research Request 385 / Execution 306 froze the result-blind design.
- Engineering Request 386 / Execution 307 authorizes only the compiler,
  additive DAG migration, Supervisor execution/replay integration, status,
  tests, and this report.
- Durable mainline execution remains forbidden until merge and a separate
  Operator release.

## Duplicate-validation removal

The decision object is an unordered fixed-budget set of canonical, strictly
increasing six-number tuples. A repeated portfolio member is therefore not a
representable state.

The implementation performs no duplicate scan. Following the explicit user
direction, the redundant `duplicate_validation` audit field was also removed
from this capability's source contract, frozen contract, three child
artifacts, mainline execution, status projection, replay result, and downstream
preregistration task definition. Historical capabilities and their immutable
records were not rewritten.

Tests recursively verify that the removed key is absent from every new
capability payload. The only retained boundary statement is
`CANONICAL_SET_CONSTRUCTION_NO_VALIDATION_PASS`.

## Frozen mathematical contract

The legal space is computed from immutable constants without enumeration:

```text
C(33, 6) = 1,107,568 legal combinations
C(33, 2) = 528 number pairs
C(6, 2) = 15 pairs per combination
```

For one future preregistered budget `B`, the contract records:

- compression fraction `1 - B / 1,107,568`;
- compression ratio `1,107,568 / B`;
- singleton concentration excess `sum(p_i^2) - 1/33`;
- pair concentration excess `sum(q_ij^2) - 1/528`;
- minimum and mean replacement distance `6 - |A intersection B|`.

These remain separate Pareto coordinates with no scalar weights. The null is
uniform sampling without replacement from the same legal universe at the same
budget. Budget, optimizer, seeds, replicates, tolerances, compute limit, and
acceptance rule remain pending the next result-blind preregistration.

## Scientific cross-review

Einstein-style pass: the falsifiable claim is structural usefulness relative
to a same-budget null, never increased draw probability. Any use of history or
post-hoc executable choices invalidates the contract.

Gauss-style pass: legal cardinalities, share conservation, concentration lower
bounds, and replacement-distance bounds are exact. No global optimum or
operationally best budget is established.

Riemann-style pass: the correct object is a finite block portfolio modulo
number-label permutations. Concentration and separation are non-equivalent
coordinates, so collapsing them into an unfrozen weighted score is rejected.

Disagreement: no current evidence selects a budget, optimizer, seed schedule,
or acceptance threshold.

Smallest shared conclusion: freeze only the label-invariant geometry and
same-budget null, then preregister every executable choice before generation.

## Mainline outputs

The capability consumes the source contract, the registered forward-or-pivot
execution, its three registered children, and the immutable Prediction v2
shadow contract. It emits exactly:

1. structural decision-support design contract;
2. structural preregistration handoff;
3. structural design completion;
4. unified mainline execution.

It creates only
`prediction-v2-structural-decision-support-design:COMPLETE` and routes to
`prediction-v2-structural-decision-support-preregistration`.

Content identities at this engineering checkpoint:

- source contract: `c0c31dff6aced2fbe5335e2702788f2f55367fa98c0b3f958dcf18c2c83b1778`;
- source set: `01e69d699518eadcbfce95f6c654318716b83fb8a7d11ec2c1a6eafa143a6ddd`;
- frozen contract: `9fa80b03a081805f14f2b2be630b3bd01cf96cbc81c5f96d9650e5d6a73147b3`;
- source manifest: `cdc74008ea7928f2ae6a9efffa252c8c5e7a5c27fb5e10c95d76d523efc13609`.

## Live additive migration dry-run

The exact migration was verified read-only against durable manifest
`9e9ba145b577f482428f222366be5d8c3f3fac008cc227a1d89a6c9a759e448d`:

- 62 live tasks -> 63 output tasks;
- 48 completed before -> 48 completed after;
- only the structural-design task is revised;
- only the structural preregistration task is added;
- existing state regressions: 0;
- existing fact deletions: 0;
- unallowlisted definition rewrites: 0;
- dry-run digest:
  `c5c89df7fcc79d68244cba0573252fe59667cd71dfc85f13acbb4f30176ee466`;
- output manifest digest:
  `413213c4e83a2282ba3a2f1c97515e7cab27de3626762dd45959fe8169817e45`;
- import performed: false.

## Validation

- Source contract, bound source bytes, legal constants, exact formulas, and
  deferred executable choices: PASS.
- Upstream tamper failure and canonical-set no-validation boundary: PASS.
- Additive migration, status projection, artifact index, capability execution,
  and deterministic replay: PASS.
- Focused structural-design tests: 7 passed.
- Focused Planner/Gate/Research-OS/hardening suite: 134 passed, 4 skipped.
- Complete non-retired Worker suite: 2172 passed, 4 skipped in 240.92s.
- Ruff, source-byte verification, JSON identities, and diff check: PASS.
- Fresh merged Supervisor execution and durable replay: pending publication.

## Integration matrix

| Link | Engineering proof | Durable mainline proof |
|---|---|---|
| Goal -> Resolver | exact source task and additive migration validate | pending import |
| Resolver -> Ready Queue | five registered input identities declared | pending Ready observation |
| Ready Queue -> Supervisor | singular design capability registered | pending merged run |
| Supervisor -> Capability | synthetic execution completes | pending merged run |
| Capability -> Artifacts | three children plus execution are deterministic | pending registration |
| Artifacts -> Status | frozen design and pending choices project | pending durable projection |
| Status -> Next Task | exact preregistration consumer declared | pending Ready observation |
| Deterministic replay | four synthetic payloads replay byte-identically | pending durable replay |

Final integration answer for this engineering checkpoint:

**NO — INTEGRATION_PENDING.**

It becomes `YES — validated by unified mainline execution and replay` only
after merge, additive import, one fresh merged Supervisor execution, four
registrations, exact downstream Ready observation, and deterministic replay.
