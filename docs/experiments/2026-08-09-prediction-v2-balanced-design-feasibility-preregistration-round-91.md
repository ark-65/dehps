# Prediction v2 balanced-design feasibility preregistration — round 91

## Primary goal

Integrate approved Research Request 417 as the singular zero-work preregistration
capability for the complete `Z_33`-translation-invariant feasibility scope of a
simple `2-(33,6,5)` design.

## Non-goals

- No legal-block enumeration, orbit compilation, multicover search, checkpoint,
  certificate, or found/not-found result.
- No database, history, CSV, prior score, prediction, ranking, or prior search
  result read.
- No global existence or nonexistence conclusion.
- No Evidence, model, expert, promotion, P3, betting, or production action.

## Frozen mathematical boundary

The arithmetic identities are `v=33`, `k=6`, `b=176`, `r=32`, and
`lambda=5`. They are necessary but do not prove existence. The first executable
scope is all and only simple candidates invariant under translation by `Z_33`.

The legal universe has `C(33,6)=1,107,568` blocks. The frozen orbit inventory is
five short orbits of size 11 and 33,561 full orbits of size 33:

```text
55 + 33,561 * 33 = 1,107,568
```

Since `33f + 11s = 176` and `s <= 5`, the only cyclic orbit-count profiles are:

1. five full orbits plus one short orbit;
2. four full orbits plus four short orbits.

The 528 pair constraints are represented by the 16 undirected circular-distance
coordinates. For every distance `d=1..16`, the exact multicover residual is:

```text
sum(full_base_pair_count[d]) + sum(short_base_pair_count[d] / 3) = 5
```

The Gauss pass required exact integer identities and a 176-block certificate
before any positive conclusion. The Riemann pass required the cyclic subspace
and every symmetry restriction to remain explicit. Their shared conclusion is
asymmetric: a verified certificate proves existence, while a budget-bound miss
or exhaustion of the cyclic subspace never proves global nonexistence.

## Repetition removal

There is no independent duplicate, membership, uniqueness, or repetition scan.
The future search state selects canonical orbit representative IDs in strictly
increasing order, so one orbit cannot be selected twice. Canonical translation
orbits are disjoint. A positive block certificate is encoded as the first
combinadic block ID followed by 175 unsigned `gap_minus_one` values, making a
non-increasing block sequence unrepresentable. The only projected marker is:

```text
repetition_scan = ABSENT_BY_CONSTRUCTION
```

The exact verifier therefore performs one pass of integer point and pair
counting only; it does not add a second repetition pass.

## Frozen execution contract

- Constructor family: `Z33_TRANSLATION_ORBIT_EXACT_MULTICOVER_V1`
- Deterministic profile order: `5_FULL_1_SHORT`, then `4_FULL_4_SHORT`
- Seed: none
- Maximum legal IDs visited: 1,107,568
- Maximum full representatives: 33,561
- Maximum short representatives: 5
- Maximum multicover node expansions: 100,000,000
- Checkpoint interval: 1,000,000 node expansions
- Maximum resident bytes: 4 GiB
- Wall clock: not a decision boundary
- Positive: `FOUND_EXACT_2_33_6_5_DESIGN`
- Bounded negative: `NOT_FOUND_WITHIN_FROZEN_BUDGET`
- Invalid: `INVALID_EXECUTION_NO_DECISION`

## Implementation result

The capability emits exactly three immutable children:

1. cyclic feasibility preregistration;
2. feasibility execution handoff;
3. preregistration completion.

The additive migration revises only
`prediction-v2-balanced-design-feasibility-preregistration`, adds only
`prediction-v2-balanced-design-feasibility-execution`, and adds one source fact
plus the approved Research contract event. The new execution task has no
capability and remains outside this round's execution authority.

The live dry run verified a 71-to-72 task migration with 70 unchanged tasks,
one allowlisted revision, one allowlisted addition, zero state regressions, zero
fact deletion, and zero unallowlisted rewrites.

## Integration matrix

| Binding | Round-91 state |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | Preregistration dependency and approved event declared |
| Ready Queue | Source migration dry run proves the revised task is the sole intended runnable task |
| Supervisor | Capability, immutable registrations, and replay path implemented |
| Capability | Zero-work frozen cyclic preregistration implemented |
| Artifacts | Three children plus mainline execution contract implemented |
| Status | Frozen scope, zero-work counters, next task, and no-repeat representation projected |
| Next Task | Unsupported execution task declared as the stop boundary |
| Merged-main execution | Pending PR merge and CI |
| Deterministic durable replay | Pending merged-main Operator execution |

Integration answer at code-complete time:

```text
NO — INTEGRATION_PENDING
```

The answer may become `YES — validated by unified mainline execution and replay`
only after merged-main CI, an approved Operator import, one Supervisor
execution, four immutable registrations, status projection, and deterministic
replay all succeed.
