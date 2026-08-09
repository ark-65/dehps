# Prediction v2 Balanced-Design Search Index Optimization — Round 95

## Round contract

- Primary goal: replace repeated dense compatibility scans in the frozen exact
  multicover search with lossless indexes while preserving every observable
  search, checkpoint, certificate, and replay identity.
- Non-goals: no new model, hypothesis, symmetry reduction, heuristic, branch
  order, pruning rule, seed, parallel search order, result interpretation,
  Evidence decision, promotion, P3 action, or production action.
- Authority: approved Engineering Request
  `engineering-prediction-v2-balanced-design-search-index-optimization-round-95-20260809`
  (request 422, execution 343), under Research Request 417 / execution 338.
- Role: Engineering Agent only.

## Failure being repaired

The Round 94 Operator execution was stopped before its first checkpoint because
the frozen implementation repeatedly scanned all 16,773 signature groups at
each local search state and had no defensible two-week upper bound.

- Failed task digest:
  `113a96ee0ceac7dd53cfd212e50e0ef7ecfe0de8c12eb0c59da08be0128cea22`
- Failed execution:
  `92f0062bbaff69f9a81d11b65c70cbf84efea97077f94ad043a6e8d8da4df41e`
- Preserved started event:
  `6ffe902ecdb01847bb12e1ca0b8bdda1eb64379d3c388668d84f7e4f1b43cf24`
- Preserved failed event:
  `59068e014557d0931f2081f998701440ba71f98938d89c99712fa787b989b082`
- Preexisting checkpoints: 0
- Preexisting registered artifacts: 0
- Historical outcomes read: no

The recovery compiler accepts only those exact identities, the exact failure
message, and a zero-artifact registry. It revises only this task from
`failed/INTEGRATED` to a new definition in
`draft/INTEGRATION_PENDING`, adds one source fact, and preserves both immutable
events. The production dry run produced recovered manifest digest
`4100df19e9601efd1bbf08e900e55ec4a7929ad16696238de551cb0d5215b396`.

## Implementation

The search now builds one immutable inverted index over the signature groups:

- a bit set for each exact coordinate value;
- a cumulative `signature[coordinate] <= residual` bit set;
- a positive-contribution bit set per coordinate;
- exact bit removal only when a signature group's frozen multiplicity is
  exhausted.

Each state obtains the same compatible group set by intersecting those bit
sets. Set bits are expanded in ascending group index, so the old enumeration
order is unchanged. The allocation generator applies the same residual-fit
predicate through the index and computes the exact maximum legal multiplicity
before constructing a vector. It does not introduce a new rejection rule.

The signature weight and index invariants are checked once when the immutable
index is built instead of being rescanned at every node. Database queries,
historical reads, and physical repetition scans remain zero. Repetition
validation remains `ABSENT_BY_CONSTRUCTION`.

## Gauss–Riemann cross-review

### Gauss pass

The proof obligation was exact identity, not approximate speed: residuals,
short subset order, coordinate choice, signature group order, representative
selection, allocation order, node count, transcript digest, checkpoint stack,
certificate, and replay must remain equal. Exhaustive reduced-universe checks
and a bounded formal-prefix comparison were required before accepting any
throughput measurement.

### Riemann pass

The bottleneck was representational. A sparse residual-compatibility relation
was repeatedly evaluated as a dense 16,773-row scan. An inverted bit-set view
expresses the same relation directly without changing the search space.

### Disagreement and smallest shared conclusion

Riemann's structural reframing could have invited new symmetry or search-space
quotients; Gauss rejected those because they would alter the frozen proof
obligation. The shared conclusion was limited to lossless inverted indexes and
exact arithmetic shortcuts for the already-existing predicates.

### Next verification

After merge, an Operator must import the exact recovered manifest, run a fresh
Supervisor execution from zero checkpoint state, register its result artifacts,
and replay the completed mainline execution before any result decision.

## Validation evidence

### Exactness

- Exhaustive toy compatibility lattice: 625 `(residual, selected-count)` states;
  indexed compatible groups and branch coordinates matched the dense reference.
- Exhaustive toy allocation frames: 98 valid frames; every allocation and its
  order matched the dense reference exactly.
- Toy search, checkpoint resume, certificate verification, Supervisor execution,
  and replay tests passed.
- Formal-universe first 100 nodes matched the prior implementation exactly:
  - node count: 100
  - branch index: 0
  - root next-allocation index: 100
  - transcript digest:
    `2f6f78bf6688568e02bb5a77bd2c9c3955bdf8851d2938161cd9175810a27b44`

### Throughput

All performance validation was a bounded, result-blind prefix. No formal result
artifact was created or interpreted.

| Prefix | Result | Throughput | Mechanical 100M projection |
|---:|---|---:|---:|
| 10,000 nodes × 3 | all bounded; identical transcript | median 28,716.79 nodes/s | 0.97 h |
| 1,000,000 nodes | bounded; checkpoint written | 35,615.55 nodes/s | 0.78 h |

The million-node run took 28.078 seconds after inventory compilation, used
53,404 KiB peak RSS for the process, remained on branch 0 with stack depth 1,
and produced transcript digest
`64e6e5fc955dc72ce2b71f47ac702dccd9d96767302db38d96be02d0b0aac64e`.

The acceptance floor is 200 exact nodes/s, which projects the frozen 100M-node
cap to 5.79 days. The observed million-node throughput is 178 times that floor
and 431 times the 82.67 nodes/s required by the user's two-week limit. These are
prefix-based projections, not a guarantee that all later states have identical
cost.

### Focused tests and recovery dry run

```text
19 passed in 1.55s
recovery status: SAFE_TO_RECOVER
changed tasks: 1
added source facts: 1
deleted or rewritten events: 0
preexisting execution artifacts: 0
```

### Full worker CI

```text
2348 passed, 4 skipped, 26 warnings in 253.82s
```

The host has an active ignored runtime retirement artifact that intentionally
blocks legacy three-line tests. For the clean-CI-equivalent run, that single
file was moved to a temporary directory under an EXIT trap and restored with
the same SHA-256 after pytest; no runtime activation content was changed.

## Source identities

- Optimized source contract:
  `c54ee87e5b9d6e513945204bea0413e8d34a51206e587f3662d8123eb03b9538`
- Optimized task definition:
  `9e26bb42afd132ea381804d972a59fbd8df71b1f837a464159cdd48a51e875f4`
- Source-template manifest:
  `4609d472c9f0ce1c3ba96762038d4df34936f166f9f4e1d21ea3c381c233641c`

## Mainline integration matrix

| Link | Round 95 state |
|---|---|
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` unchanged |
| Resolver | corrected task definition compiled |
| Ready Queue | pending exact recovery import after merge |
| Supervisor | optimized capability and toy execution validated |
| Capability | code complete |
| Artifacts | source contract registered in source template; formal result absent |
| Status | `INTEGRATION_PENDING` |
| Next task | `prediction-v2-balanced-design-feasibility-result-decision` remains blocked |
| Deterministic replay | toy and bounded-prefix identity proven; merged formal replay pending |

Final integration answer for this Engineering round:

`NO — INTEGRATION_PENDING`

The capability is not complete until the merged source passes the exact recovery,
fresh unified mainline execution, artifact registration, status projection, and
deterministic replay chain.
