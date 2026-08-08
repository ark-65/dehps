# Prediction v2 Structural Execution Preregistration — Round 64

Date: 2026-08-09

Role sequence: Research Agent -> Reviewer -> Engineering Agent

Primary goal: freeze every executable choice for one result-blind structural
portfolio experiment, then integrate only the constant-size preregistration
compiler into the canonical Research Evidence Supervisor.

## Non-goals

- No portfolio, optimizer proposal, null replicate, metric result, or pass/fail
  result is generated in this round.
- No history, database data row, CSV, fold, bootstrap child, checkpoint, score,
  ranking, prediction, or previous result is read.
- No scalar score, probability-edge claim, global-optimality claim, Prediction
  v2 promotion, P3 transition, betting output, or production action is allowed.
- No separate uniqueness-validation path, membership rejection loop, or audit
  field is restored.

## Typed authorization

- Research Request 388 / Execution 309 froze the experiment contract.
- Reviewer approval records the exact arithmetic, result-blind boundary,
  falsifiable failure outcome, and no-retuning rule.
- Engineering Request 389 / Execution 310 authorizes only the compiler,
  additive DAG migration, Supervisor execution/replay integration, status,
  tests, and this report.
- Durable import and execution remain forbidden until merge and a separate
  Operator Request.

## Frozen budget and arithmetic

The primary budget is `B=176`. This is not selected from a run result. It is
the smallest positive budget satisfying both balance-integrality conditions:

```text
33 divides 6B   -> singleton target r = 6*176/33 = 32
528 divides 15B -> pair target lambda = 15*176/528 = 5
```

Therefore the ideal balance parameters are those of a possible
`2-(33,6,5)` block design with `b=176` and `r=32`. Existence of an exact
simple design is not claimed, and the optimizer is not claimed globally
optimal.

For minimum replacement distance two, every legal block has 162 distance-one
neighbours. The elementary greedy lower bound is
`floor(1,107,568 / 163) = 6,794`, which is greater than 176. Thus the distance
constraint itself is feasible without using any observed outcome.

## Frozen optimizer

The only optimizer is
`DETERMINISTIC_PARETO_PREFIX_EXCHANGE_V1`:

- 22 deterministic islands, matching the current host's logical workers;
- 262,144 proposals per island;
- 5,767,168 proposals total;
- a partial Fisher-Yates legal-rank permutation per island;
- the selected portfolio is the first 176 permutation positions;
- each proposal swaps one selected-prefix and one complement-suffix position;
- a move is accepted only by weak Pareto dominance with one strict coordinate,
  or by a lexicographically smaller rank vector on an exactly equal metric
  plateau;
- no scalar weights and no same-execution retuning.

The selected-prefix representation makes repeated members unrepresentable by
construction. It performs no scan, membership rejection loop, or separate
validation pass.

The exact sufficient statistics are singleton count squares, pair count
squares, minimum replacement distance, and total replacement distance. At
fixed `B`, mean replacement distance is the exact transform

```text
sum_distance = 6*C(B,2) - (sum_singleton_count_squared - 6B)/2
```

so it remains an audit coordinate and is not counted as an independent gain.

## Seeds, null, exactness, and compute envelope

- optimizer root seed:
  `124aed827e6f68471da3733717919b9956be3c2e4ed256b11cf7ed2c8ed9b9d2`;
- null root seed:
  `ce969021ed72f5638d2b4534bd9c70af44854a6eb95973e5d7115a92f7a454ac`;
- domain-separated SHA-256 derivation by island or replicate index;
- unbiased bounded integers from counter-mode SHA-256 with top-interval
  rejection;
- 4,096 uniform-without-replacement null portfolios at the same `B=176`;
- exact integer/cross-product comparison tolerance: zero;
- Numba exact-integer kernel with a 1,024-proposal scalar reference preflight;
- optimizer limit: 7,200 seconds;
- null limit: 7,200 seconds;
- resident-memory limit: 2 GiB;
- timeout disposition: incomplete, fail closed, no partial acceptance.

## Frozen structural gate

The single selected island candidate passes only if all conditions hold:

1. minimum replacement distance is at least two;
2. it strictly Pareto-dominates at least 3,893 of 4,096 null portfolios;
3. no null portfolio strictly Pareto-dominates it;
4. all fixed proposals and nulls finish within the frozen envelope.

The joint failure fraction is
`(1 + nulls_not_strictly_dominated) / 4097 <= 0.05`. This is a descriptive
structural performance gate for the entire frozen 22-island optimizer, not a
predictive p-value. Failure rejects the structural hypothesis at this budget
and forbids retuning within the same execution.

## Scientific cross-review

Einstein pass: the only falsifiable claim is structural balance/separation
relative to a same-budget null. Equal draw probability is invariant.

Gauss pass: budget minimality, target counts, proposal total, tight null count,
distance identity, and all comparisons are exact integers. Optimizer success
and exact block-design existence remain unproved.

Riemann pass: the object is a finite block portfolio modulo label
permutations. Singleton concentration and mean distance are algebraically
linked, while pair concentration and minimum distance retain distinct global
structure.

Disagreement: neither lens can establish before execution that the bounded
local optimizer passes. A failed run is therefore a valid scientific outcome.

Smallest shared conclusion: freeze exactly one budget, one optimizer, two seed
schedules, one null count, zero tolerance, one compute envelope, and one joint
gate before producing any output.

## Mainline outputs

The compiler consumes one source contract plus the registered structural
design execution and its three registered children. It emits exactly:

1. result-blind structural execution preregistration;
2. structural portfolio execution handoff;
3. structural preregistration completion;
4. unified mainline execution.

It creates only
`prediction-v2-structural-decision-support-preregistration:COMPLETE` and
routes to `prediction-v2-structural-portfolio-execution`.

Content identities at this engineering checkpoint:

- source contract: `d0e997b1b7442ce5dfe01652eb23ff9b8e234ee79e0a783a7f27f3a1e1f9821e`;
- source set: `c3c2be9973b19c116f083975e42a10bee8fefbff73209d3df11ad05478e8e211`;
- frozen contract: `175f8134c70a6cdea99ccdccb07464f9d1a84bf356306a79d4b34d41b89d1c87`;
- source manifest: `bcc26f14c355db2fa49ccc880e4c5b839ebc1bff1b76d36c064d9af2afa3336a`.

## Live additive migration dry-run

The exact migration was verified read-only against durable manifest
`80ae2b62813822e341a016b247a513cb2d6805f34c47d2aed9cc2ea74554b353`:

- 63 live tasks -> 64 output tasks;
- only the preregistration task is revised;
- only the structural portfolio execution task is added;
- existing state regressions: 0;
- existing task/goal/fact deletions: 0;
- unallowlisted definition rewrites: 0;
- dry-run digest:
  `0787e3cfc34ecaa7e72b034113aa52d5429c23926bbb8f046e4327bfe52af381`;
- output manifest digest:
  `7f21dbb38477a2dcbabfdc5f074430793f78499a450e70f5add5e42d13b2a357`;
- import performed: false.

## Validation

- Source contract, bound source bytes, exact frozen choices, arithmetic proof,
  upstream tamper failure, and no-validation construction: PASS.
- Additive migration, status projection, artifact index, capability execution,
  and deterministic replay: PASS in focused tests.
- New plus preceding structural tests: 14 passed.
- Planner/Gate/Research-OS/hardening focused suite: 173 passed, 4 skipped.
- Complete non-retired Worker suite: 2,179 passed, 4 skipped in 237.07s.
- The first complete run exposed three current-manifest artifact-index failures;
  the old manifest identity was preserved as superseded, the current identity
  was added, four focused regressions passed, and the complete suite then
  passed.
- Fresh merged Supervisor execution and durable replay: pending publication.

## Integration matrix

| Link | Engineering proof | Durable mainline proof |
|---|---|---|
| Goal -> Resolver | exact source task and additive migration validate | pending import |
| Resolver -> Ready Queue | five registered input identities declared | pending Ready observation |
| Ready Queue -> Supervisor | singular preregistration capability registered | pending merged run |
| Supervisor -> Capability | synthetic execution completes | pending merged run |
| Capability -> Artifacts | three children plus execution are deterministic | pending registration |
| Artifacts -> Status | all eight choices project as frozen | pending durable projection |
| Status -> Next Task | exact structural execution consumer declared | pending Ready observation |
| Deterministic replay | four synthetic payloads replay byte-identically | pending durable replay |

Final integration answer for this engineering checkpoint:

**NO — INTEGRATION_PENDING.**

It becomes `YES — validated by unified mainline execution and replay` only
after merge, additive import, one fresh merged Supervisor execution, four
registrations, exact downstream Ready observation, and deterministic replay.
