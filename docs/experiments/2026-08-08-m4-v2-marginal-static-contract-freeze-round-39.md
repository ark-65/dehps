# M4 v2 Marginal-Static Contract Freeze — Round 39

Date: 2026-08-08

Role: Engineering Agent

Agent Request: `engineering-m4-v2-marginal-static-contract-freeze-round-39-20260808`

Request / execution: `313 / 234`

Research contract: `research-m4-v2-marginal-static-contract-freeze-round-39-20260808`
(`312 / 233`, frozen before implementation)

## Round contract

- Primary goal: freeze the first singular Measurement-v2 branch contract and
  integrate it through the canonical Goal, resolver, Ready Queue, Supervisor,
  immutable artifacts, status projection, next consumer, and replay path.
- Non-goals: no synthetic sampling, historical outcome read, fold execution,
  result inspection, Evidence, threshold selection, model acceptance,
  promotion, production action, temporal branch, or joint branch.
- Ready condition: the Measurement-v2 contract, marginal preflight design,
  completed branch-preflight execution, marginal branch-health PASS,
  preflight completion, approved Round-39 source contract, and the old P2.6.1
  marginal REPAIR decision plus its replay are all present under exact digests.
- Runner: unified Research Evidence Supervisor.
- Downstream artifacts: marginal-static measurement contract,
  contract-freeze completion, and one mainline execution artifact.
- Evidence rule: a mathematical estimator and score contract with zero sampled
  observations is not Evidence.
- Decision consumer: the V2 marginal-static synthetic measurement fixture
  freezer.
- Next consumer: `m4-v2-marginal-static-measurement-fixture-freeze`.

## Frozen estimator and score

For each red number `i`, using only the expanding outer-training window:

```text
q_i = (c_i + 2/11) / (n + 1)
minimum n = 900 issues
sum_i q_i = (6n + 6) / (n + 1) = 6 exactly
```

The prior strength is one legal uniform issue. There is no seed,
hyperparameter search, clipping, or renormalization. The target issue and all
future issues are forbidden inputs. The endpoint is the sum of 33 Bernoulli
log-score differences against `q0 = 2/11`, measured in bits per issue. It is
explicitly not a joint-information estimate.

The model artifact contract requires exactly 11 fields covering estimator
identity, fit boundary, counts, probabilities, their exact sum, dataset
identity, and source-contract identity. Acceptance defaults to false, artifacts
are immutable, and identical inputs must reproduce the same digest.

## Legacy REPAIR boundary

The existing P2.6.1 marginal decision remains authoritative:

```text
decision: 25bac6a352a132b95cbf96693c383eb4e203a1d0fa169ff96a7b93df9a62f513
replay:   792f2d635f342c86dedd791e9b8af5cedcb729b36a205cb2ea244c0db4495c45
health:   REPAIR
eligible for formal branch program: false
overridden by V2 preflight PASS: false
```

The V2 preflight PASS proves analytic identifiability only. Historical
execution remains `NOT_AUTHORIZED` until a separately frozen and executed V2
marginal-static synthetic measurement-health program passes.

## Duplicate-validation boundary

Both throughput removals remain permanent:

- No raw Measurement-v2 replay is reintroduced. The capability reads the
  registered canonical parent artifacts once.
- No routine physical scan of roughly 31,000 checkpoints / 40 GiB is
  reintroduced. Deep audit remains explicit opt-in.

This round executes zero folds and zero replicates. Deterministic replay only
reconstructs two small contract artifacts from their eight immutable parents
and compares registered identities and content.

## Additive migration proof

The exact in-memory dry-run against durable Round-38 truth reported:

```text
live manifest:                 2097823f8cb0478144cc2694d68a4bfc68a24f3df970751d19bc45045b6e4775
source manifest:               b815060056f3f2b0d26cc26660f86a3b641d864b8f6c9b37e0e14c4aa786234d
projected output manifest:     cf9116444515bc470a9f677e6bd0b5150c42299d032b43ab524f65b952707839
dry-run artifact:              59e18c52a23a6d6d97ea71a09fc1bf4b20d960916820d43b312604d00b36cea1
source contract:               db8109760e5aeaae30cc765bb60ccd704560a24674a934dff6304026d8b87de1
source set:                    86599ea83ffa3e88371bec7304560865720b5133db32868269da3dfe8ce164d8
tasks:                         43 -> 44
unchanged existing tasks:      42
existing Goal deletions:       0
existing Task deletions:       0
existing state regressions:    0
existing fact deletions:       0
unallowlisted rewrites:        0
```

Only the unstarted marginal-static contract task is revised, only its fixture
freezer is added, and only the approved source-contract fact is added.

## Validation

- New estimator, contract, fail-closed, source-integrity, capability,
  migration, status, and registration tests: `8 passed`.
- Focused new plus preflight and source-partition regressions:
  `84 passed in 12.80s`.
- Complete information-theory, M4, and unified Research OS surface:
  `521 passed, 4 skipped in 158.23s`.
- Clean detached full Worker suite:
  `2090 passed, 4 skipped, 4 existing warnings in 225.78s`. The warnings are
  the existing Python 3.14 multiprocessing `fork()` deprecations in training
  supervisor tests.
- Ruff and Python compilation: passed.
- Manifest digest validation, source-byte verification, JSON parsing,
  additive migration dry-run, and `git diff --check`: passed.
- Source partition coverage increments exactly once for the new worker module:
  audit orchestration `378 -> 379`, total classified `458 -> 459`.

## Integration matrix

| Link | Engineering handoff state | Proof |
| --- | --- | --- |
| Goal -> Resolver | Code complete | Exact task definition and approved source identity |
| Resolver -> Ready Queue | Dry-run verified | Only the marginal-static contract task becomes executable |
| Ready Queue -> Supervisor | Code complete | Capability registered under one exact request key |
| Supervisor -> Capability | Code complete | Eight ordered parent identities checked fail-closed |
| Capability -> Artifacts | Code complete | Two child artifacts plus one mainline execution |
| Artifacts -> Status | Code complete | Contract, legacy REPAIR boundary, and zero-work counters projected |
| Status -> Next Task | Code complete | Only the synthetic fixture freezer is named |
| Deterministic replay | Code complete | Small contract reconstruction and registered-byte comparison |

Final integration answer at engineering handoff:

`NO — INTEGRATION_PENDING`

The merged commit must be installed under a fresh unified Supervisor, the
exact additive manifest imported by an approved Operator, the task completed
once, and deterministic replay verified before this capability is `COMPLETE`.
