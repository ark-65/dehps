# M4 v2 marginal-static Repair-v2 health decision — Round 51

Date: 2026-08-08

Role boundary: Research Request 359 -> Engineering Request 360

Primary goal: implement the frozen zero-work decision projector for the exact
Round-50 Repair-v2 aggregate and route a PASS only to a separate result-blind
historical-measurement design.

## Scope and non-goals

This round changes no estimator, fixture, seed, scale, sample count, conformal
rule, threshold, or statistical gate. It does not read the completion index,
regenerate a child, recompute a sentinel, repeat validation, or read a historical
outcome. It creates no Evidence, accepted model, prediction candidate, Promotion
Gate change, P3 transition, betting output, or production action.

The only allowed computation is a deterministic projection of three registered
parents:

1. mainline execution `7701f3ffe48e7163a7e8d68cd4b54d98008810b7cf1975bb4a3d533052f8e62a`;
2. aggregate health result `b09069a0774201b3cc59572f309416885c674e6d58d5bae050f01201e25493d5`;
3. execution completion `f817867000d810f622037c09a4b93280e46aae9178b8af0cd122e36f21397e21`.

## Frozen rule and exact result

The rule was frozen in inference-and-gates artifact
`2a4d86430b85e7a262918275a08fbe8e1977311de08eb3ee4fe603208714adf5`:

- `PASS`: completeness, legality, finiteness, identity, all six negative
  controls, both positive controls, and both preregistered admissible local
  targets pass;
- `REPAIR`: any completed required gate fails;
- `INCONCLUSIVE`: execution/lineage/proof completeness is absent;
- manual override and post-result threshold changes are forbidden.

The exact registered result is complete and legal, with zero failed required
gates. The largest negative-control detection count is 67 against the frozen
passing boundary of 74; the largest negative-control Wilson upper bound is
0.08225829572726125 against 0.09. The smallest positive-control Wilson lower
bound is 0.9872757325386061 against 0.8. Both admissible historical-scale local
targets pass, with Wilson lower bounds 0.8233194830352732 and
0.9962625959599825.

The unique mechanical projection is therefore:

```text
measurement health: PASS
authoritative decision: PASS_TO_HISTORICAL_MEASUREMENT
completion fact: m4-v2-marginal-static-measurement-repair-v2-health-decision:PASS
historical execution authorized: NO
next consumer: m4-v2-marginal-static-historical-measurement-design
```

The prospective immutable decision artifact digest is
`8b1badb229e8517695bc41aed6d87e469a27fe010006e60e11244e3792573124`.

## Preserved sensitivity limits

Four non-admissible local cells remain explicit limitations rather than being
relabelled as failures or hidden by the scalar PASS:

| Cell | Detection rate | Wilson 95% interval |
| --- | ---: | ---: |
| `LOCAL_M1:0.001:FORWARD_61` | 0.0439453125 | [0.03300347187860741, 0.0582960743844556] |
| `LOCAL_M1:0.001:HISTORICAL_2581` | 0.1103515625 | [0.09259750057271413, 0.13101817171628405] |
| `LOCAL_M1:0.010:FORWARD_61` | 0.11328125 | [0.09529706066474786, 0.13415608777245333] |
| `LOCAL_M1:0.050:FORWARD_61` | 0.41796875 | [0.3881208062204002, 0.4484298616299153] |

Instrument-health PASS therefore means only that the preregistered measurement
system is fit to design its next historical test. It does not mean historical or
forward information gain exists.

## Gauss–Riemann cross-review

Historical boundary: Gauss and Riemann are used as historically inspired lenses,
not literal minds, complete reconstructions, or evidence.

### Gauss pass — verification

- Strongest claim: all ten required cell gates and all structural obligations
  pass under the frozen rule.
- Weakest assumption: registered parent identities and frozen source bytes are
  exact and immutable.
- Cross-test: reject any digest, required-cell, Wilson interval, decision-rule,
  or sensitivity-topology drift.

### Riemann pass — structure

- Strongest claim: the result has explicit scale-local geometry; four
  low-resolution cells bound the instrument without invalidating the two
  preregistered detectable historical-scale targets.
- Weakest assumption: synthetic instrument health says nothing by itself about
  stable real-history or forward predictive information.
- Cross-test: the next design must freeze legal sample space, chronology,
  baseline/null, leakage boundary, uncertainty, and failure cases before reading
  outcomes.

### Cross-review, disagreement, and synthesis

Gauss rejects any structural explanation used to alter the frozen PASS rule.
Riemann rejects expanding PASS into a global prediction claim. The unresolved
question is whether weak forward-scale local power will later constrain forward
usefulness. The smallest shared conclusion is to issue instrument-health PASS,
preserve the four limitations, and authorize only a separate result-blind
historical-measurement design.

## Implementation

- Pure decision module with exact parent and source-byte validation.
- Source contract digest:
  `65dbd24e6a63fadfa62d0fb5d0bf7744d166ed1bfb2412bb48e57b04c2d190c6`.
- Source-set digest:
  `75b4b45bed987629bf4313ce514623fe993c433491e3c50b6645fb1d6435416e`.
- Canonical source manifest digest:
  `7eeae8b00bc57af820f28527432663dcd930545160d9a77ea75660b4ec988a88`.
- Additive migration changes exactly one existing task and adds exactly one
  downstream design task; it reports zero state regression, fact deletion, or
  unallowlisted rewrite.
- Supervisor execution and replay register only the decision and mainline
  execution artifacts. Both paths perform zero child generation, zero compact
  index reads, zero raw/sentinel replay, and zero duplicate validation.

## Validation

- New decision capability: 7 passed.
- Adjacent M4/Supervisor surface: 112 passed.
- Full non-retired Worker mainline: 2,108 passed, 4 skipped.
- Initial unfiltered Worker run: 2,148 passed, 4 skipped, 45 failed. Forty-two
  failures are confined to the seven permanently retired legacy three-line
  entrypoint files. The other three exposed the new canonical manifest identity
  missing from the append-only artifact index; the index was fixed and those
  three focused tests pass.
- Ruff, compileall, source-byte verification, additive migration dry run, and
  `git diff --check`: passed.

## Mainline integration matrix

| Link | Engineering state |
| --- | --- |
| Goal | Bound to `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | Decision depends on exact completed Round-50 execution and source fact |
| Ready Queue | Canonical decision revision is executable after additive migration |
| Supervisor | Capability registered; live merged execution still pending |
| Capability | Pure PASS projector implemented |
| Artifacts | Decision + mainline execution only |
| Status | Authoritative PASS and sensitivity limits projected |
| Next Task | Separate historical-measurement design declared |
| Replay | Decision-only reconstruction implemented; live replay pending |

Integration answer at Engineering completion:

```text
NO — INTEGRATION_PENDING
```

The capability becomes complete only after a ready PR merges, a fresh merged
unified Research Evidence Supervisor executes it from the durable Ready Queue,
the decision fact transitions the historical-design task to Ready, and replay
verifies both registered identities.
