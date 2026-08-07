# M4 v2 Marginal-Static Fixture Freeze — Round 40

Date: 2026-08-08

Role: Engineering Agent

Agent Request: `engineering-m4-v2-marginal-static-fixture-freeze-round-40-20260808`

Request / execution: `316 / 237`

Research contract: `research-m4-v2-marginal-static-fixture-freeze-round-40-20260808`
(`315 / 236`, frozen before implementation)

## Round contract

- Primary goal: freeze four exact legal fixtures and one compact future
  execution boundary for the marginal-static estimator, then integrate them
  through the canonical Goal, resolver, Ready Queue, Supervisor, immutable
  artifacts, status, next consumer, and deterministic replay.
- Non-goals: no sample-size or threshold selection, generated issues,
  replicates, folds, database training reads, CSV materialization, statistical
  result, Evidence, accepted model, history, temporal/joint implementation,
  promotion, prediction activation, or production action.
- Ready condition: the replay-verified Round-39 contract execution, contract
  and completion, frozen orthogonal fixture contract, fixture completion,
  marginal branch-health PASS, preflight completion, and approved Round-40
  source contract are available under eight exact digests.
- Runner: unified Research Evidence Supervisor.
- Downstream artifacts: four fixture contracts, one fixture bundle/runtime
  boundary, one completion, and one mainline execution.
- Evidence rule: fixture definitions and analytic anchors with zero samples are
  not Evidence.
- Decision consumer and next consumer:
  `m4-v2-marginal-static-measurement-health-design`.

## Frozen fixtures

The fixture order and branch roles are singular:

1. `V2_M1_GROUP_ODDS_2_STATIONARY` — positive control. Legal IID draws have
   probability proportional to the product of weights, with weight 2 on
   numbers 1–16 and weight 1 on 17–33. Elementary symmetric polynomials give
   partition `11248216`, exact group marginals `47343/200861` and
   `26334/200861`, exact total 6, and analytic marginal gain
   `0.4403398887146399` bits/issue.
2. `NULL_UNIFORM_LEGAL_SIX_OF_33` — negative control. Every marginal is
   exactly `2/11`.
3. `V2_T1_OVERLAP_ODDS_2_MARKOV` — negative control for the stationary
   marginal coordinate. Its transition weight is `2^intersection_size`; the
   symmetric kernel is doubly stochastic, so every stationary marginal remains
   `2/11` despite temporal dependence.
4. `V2_J1_HISTORY_IS4_LAMBDA_HALF` — negative control for the stationary
   marginal coordinate. Both history-selected joint states preserve every
   one-number marginal at `2/11` despite joint residual structure.

The analytic targets are recomputed from formulas and compared to the existing
frozen orthogonal fixture anchors. No preflight result payload is copied as a
new observation.

## Throughput boundary

The future hot path is explicitly independent of PostgreSQL and CSV:

```text
live state per replicate: issue_count + signed int64[33] counts
database reads during replicate:  0
database writes during replicate: 0
CSV materialization:              forbidden
checkpoint unit:                  completed replicate summary + seed identity
resume:                           load compact completion index, skip completed digests
raw draw replay:                  forbidden
routine physical checkpoint scan:forbidden
```

Each legal draw updates six counters in memory and is then discardable. This
avoids row-by-row database latency, large CSV copies, retained raw synthetic
draws, and the old duplicate checkpoint verification path. Sample sizes and
formal inference remain a separate preregistered design task.

## Additive migration proof

The exact in-memory dry-run against durable Round-39 truth reported:

```text
live manifest:                 96d0b713fc7a535fa3f8872a446dd3c3fcdb59cf02f01a03f6eaa72bc0297620
source manifest:               120ebb7a322125380e89945e9bb39fcb0c2a7967c777aa43389dd177ed1a2e0a
projected output manifest:     b905e2cce7f043dae05cdaeeb11cd22788dcc92483f894e394bfedafae7bc542
dry-run artifact:              77ed0c1bf92eba900cc6be3566df29578e6934770aaed577b0a18659bec8b833
source contract:               65a3b02964d35c8250bde2e6c9858f94c40617b7a60923c77d96541b29982b53
source set:                    c9e425e67b85be568831d4098ee1382eaf3b21cdabe75d8cad1684a9476b60ce
tasks:                         44 -> 45
unchanged existing tasks:      43
existing Goal deletions:       0
existing Task deletions:       0
existing state regressions:    0
existing fact deletions:       0
unallowlisted rewrites:        0
```

Only the unstarted fixture-freeze task is revised, only the health-design task
is added, and only the approved source-contract fact is added.

## Einstein diagnostic

The smallest falsifiable fixture question is whether the stationary estimator
responds to one legal stationary marginal perturbation while remaining null on
uniform-marginal temporal and joint structure. Any database path, fitted
hyperparameter, or copied result would confound that question, so none is
present in this round.

## Gauss–Riemann cross-review

Historical boundary: Gauss and Riemann are historically inspired verification
and structural lenses, not literal minds or authorities for this modern
system.

- Gauss pass: exact six-of-33 support, partition, rational marginal sums,
  fixed number order, four distinct fixture identities, and zero-work counters
  are explicit proof obligations.
- Riemann pass: M1 changes only the stationary marginal coordinate; T1 changes
  transition geometry; J1 changes joint residual geometry; null changes none.
- Shared conclusion: freeze exact formulas and the 33-count sufficient state;
  defer all sample sizes and inference to the next design.

## Validation

- New sufficient-state, fixture, orthogonality, fail-closed, source-integrity,
  capability, migration, status, and registration tests: `8 passed`.
- Focused fixture/contract/preflight/source-partition regressions:
  `99 passed in 17.85s`.
- Full Information Theory, ResearchOS, and M4 affected surface under the exact
  CI numeric bootstrap: `529 passed, 4 skipped in 147.62s`.
- Full Worker suite from detached commit `6fb82ab`, with its own source root
  pinned for fresh-import subprocesses: `2098 passed, 4 skipped, 4 existing
  fork deprecation warnings in 210.30s`.
- The first PR-271 GitHub run failed six legacy frozen-digest checks because a
  hosted-runner OpenBLAS kernel perturbed solved float payloads in their final
  bits. An unchanged rerun passed, confirming a numeric-environment flaky.
  Worker CI now initializes NumPy/OpenBLAS once on the portable Haswell kernel,
  removes the selector before pytest, and keeps all numeric thread pools at
  one. Four direct regressions prove both the affected frozen digests and the
  canonical Golden Reference environment contract remain exact. No replay or
  checkpoint scan was restored.
- Ruff and Python compilation: passed.
- Manifest digest validation, source-byte verification, JSON parsing,
  additive migration dry-run, and `git diff --check`: passed.
- Source partition coverage increments exactly once for the new worker module:
  audit orchestration `379 -> 380`, total classified `459 -> 460`.

## Integration matrix

| Link | Engineering handoff state | Proof |
| --- | --- | --- |
| Goal -> Resolver | Code complete | Exact task and source identity declared |
| Resolver -> Ready Queue | Dry-run verified | Only fixture freeze becomes executable |
| Ready Queue -> Supervisor | Code complete | One exact capability registration |
| Supervisor -> Capability | Code complete | Eight parent identities checked fail-closed |
| Capability -> Artifacts | Code complete | Six small child artifacts plus execution |
| Artifacts -> Status | Code complete | Fixture counts and zero-I/O boundary projected |
| Status -> Next Task | Code complete | Only measurement-health design is named |
| Deterministic replay | Code complete | Seven small artifacts reconstructed and compared |

Final integration answer at engineering handoff:

`NO — INTEGRATION_PENDING`

The merged commit must be installed under a fresh unified Supervisor, the
exact additive manifest imported by an approved Operator, the task completed
once, and deterministic replay verified before this capability is `COMPLETE`.
