# Prediction v2 Structural Portfolio Execution — Round 66

Date: 2026-08-09

Role sequence: Research Agent -> Reviewer -> Engineering Agent

Primary goal: implement the frozen `B=176` structural portfolio experiment as
one bounded, checkpointable local-host capability and integrate it into the
canonical Research Evidence Supervisor without a duplicate-validation pass.

## Non-goals

- No historical draw, database row, CSV, fold, bootstrap child, Prediction v2
  score, expert output, promotion, P3 transition, betting output, or production
  action is read or created.
- No optimizer, weight, budget, seed, null count, threshold, timeout, or metric
  is selected after seeing an experiment result.
- No prediction p-value, probability edge, or global-optimality claim is made.
- The Engineering round does not run the complete scientific workload; durable
  execution requires merged code and a separate Operator authorization.

## Typed authorization

- Research Request 391 / Execution 312 froze the executable semantics.
- Reviewer approval accepted the exact arithmetic and leakage/null checks while
  explicitly allowing a failed structural gate as a valid result.
- Engineering Request 392 / Execution 313 authorizes the capability, additive
  DAG migration, Supervisor execution/replay, status projection, tests, and
  this report.
- Durable import and the full scientific workload remain pending merge and a
  separately typed Operator Request.

## Removing duplicate validation by construction

The optimizer maintains one permutation of all 1,107,568 legal ranks. Its
candidate portfolio is always the first 176 entries. A proposal swaps exactly
one prefix position with exactly one suffix position.

Therefore a repeated selected rank cannot be represented. There is no
membership rejection loop, uniqueness scan, post-generation duplicate pass,
or duplicate-validation artifact field. Checkpoint identity checks remain:
they detect wrong or corrupted state, not repeated portfolio members.

Completed island and null-shard results are content-addressed. A matching
completed child is loaded directly and skipped without regeneration or a
portfolio rescan. Partial islands resume only at the frozen 16,384-proposal
boundary.

## Exact computation

- legal universe: `C(33,6) = 1,107,568` lexicographic combinations;
- candidate budget: 176;
- optimizer: `DETERMINISTIC_PARETO_PREFIX_EXCHANGE_V1`;
- 22 islands x 262,144 proposals = 5,767,168 proposals;
- 4,096 same-budget uniform-without-replacement null portfolios in 64 shards;
- exact singleton and pair square sums plus a seven-bin replacement-distance
  histogram;
- proposal updates are `O(B)` exact-integer deltas rather than `O(B^2)` full
  portfolio recomputation;
- a pure-Python full recomputation checks the first 1,024 proposals before the
  official run restarts;
- all bounded draws use the frozen SHA-256 counter stream with rejection to
  remove modulo bias;
- comparison tolerance is zero.

The maintained distance sum must satisfy

```text
sum_distance = 6*C(B,2) - (sum_singleton_count_squared - 6B)/2
```

after every accepted proposal block and at child completion.

## Resource and failure semantics

- Linux `fork` workers share the immutable 48,732,992-byte universe tables;
- aggregate proportional-set-size memory is monitored against 2 GiB;
- optimizer and null phases each have a 7,200-second limit;
- timeout, memory breach, preflight disagreement, checkpoint identity drift,
  missing child, or arithmetic mismatch fails closed;
- no partial result is accepted and no same-execution retuning is allowed.

## Frozen gate

The mechanically selected island passes only if:

1. minimum replacement distance is at least two;
2. it strictly Pareto-dominates at least 3,893 of 4,096 nulls;
3. no null strictly Pareto-dominates it.

The exact joint failure fraction is retained as a cross-product identity check.
It describes structural performance of the frozen optimizer; it is not a
predictive p-value. Either pass or fail routes to the separate structural
evaluation task.

## Scientific cross-review

Einstein pass: the experiment tests only a result-blind structural claim.
Equal draw probability remains invariant, so no forecast advantage follows
from a structurally balanced portfolio alone.

Gauss pass: universe size, budget integrality, proposal count, null count,
distance identity, bounded RNG, and comparisons are exact. Neither exact block
design existence nor global optimizer success is asserted.

Riemann pass: the maintained permutation is a coordinate chart in which the
simple-set constraint is intrinsic. Singleton concentration and mean distance
are algebraically linked; pair concentration and minimum distance retain
separate global information.

Disagreement: no reasoning lens proves the frozen bounded search will pass.
The smallest shared conclusion is to execute exactly once, accept failure, and
interpret the registered result in a later task without rerunning or retuning.

## Performance evidence

- full universe build, JIT compilation, and a short preflight: 2.02 seconds;
- complete 1,024-proposal scalar-versus-incremental preflight: 4.67 seconds,
  exact match;
- one full 262,144-proposal island plus one null: 0.865 seconds, about 227 MiB
  maximum resident memory in the engineering benchmark;
- tiny interrupted island resumed at proposal 16 and produced the same formal
  child identity as an uninterrupted run;
- a repeated tiny run directly skipped completed children and reproduced all
  four registered artifact digests.

These are implementation benchmarks, not the official scientific outcome.

## Mainline outputs

The capability consumes one source contract and the prior preregistration
execution plus its three registered children. It emits exactly:

1. canonical `B=176` structural portfolio;
2. 22-island optimizer result index;
3. 4,096-replicate same-budget null comparison;
4. structural execution completion;
5. unified mainline execution.

It creates only
`prediction-v2-structural-portfolio-execution:COMPLETE` and routes to
`prediction-v2-structural-portfolio-evaluation`.

Content identities at this engineering checkpoint:

- source module: `a96230e1ee31a52e309958f4fa1b3e16edf947471750c2148f6fcb13b19e91bc`;
- source set: `1455fd309b6e9b5ad5cfca759bdd8b78417c554eb36d46aa8d1d4b8fab4850ff`;
- frozen contract: `14c3a5a4b3d6b2f8b987c6b76197fe0d71fae5eb9eafa5a66605f1f3440ab400`;
- source contract: `0796da84d80649913795eb71f003ed38ecfb801098e15488e8fe66c403c4eb73`;
- static source manifest: `78e3b5dd1a7654fcffda419a18511d2e27d72a8ee4d5d9465fea99ce4ec31c44`.

## Live additive migration dry-run

The migration was verified read-only against durable manifest
`c7908309903f522b0c94b5163116bde365ebead8c21d9f38bd54a4481f90d902`:

- 64 live tasks -> 65 output tasks;
- only the structural execution task is revised;
- only the structural evaluation task is added;
- existing state regressions: 0;
- existing task/goal/fact deletions: 0;
- unallowlisted definition rewrites: 0;
- dry-run digest:
  `8ef9158f4d7d0b201369009127e6642c7284ed72aa38aa53108d752b277e6b19`;
- output manifest digest:
  `2a97ca2244b639daff0e76aa78ec19b54958aa2e1e6c49804ca931f23ada7c92`;
- import performed: false.

## Validation

- Exact universe enumeration, RNG golden vectors, exact statistic identity,
  scalar preflight, dominance, checkpoint resume, direct child skip, upstream
  drift failure, and output replay: PASS.
- Additive migration, completed-status routing, artifact index, Supervisor
  execution, Supervisor replay, and absence of all duplicate/uniqueness
  validation keys: PASS in focused tests.
- Structural/planner/Gate/Supervisor focused suite: 67 passed.
- Complete non-retired Worker suite: 2,193 passed, 4 skipped, 1 deselected in
  240.83 seconds.
- The unfiltered suite additionally reached 2,233 passes before the source
  partition count fix; its 42 unrelated legacy-line failures are caused by the
  durable retirement activation correctly forbidding old three-line compute.
- Merged durable execution: pending publication.

## Integration matrix

| Link | Engineering proof | Durable mainline proof |
|---|---|---|
| Goal -> Resolver | exact revised task and migration validate | pending import |
| Resolver -> Ready Queue | five registered input identities declared | pending Ready observation |
| Ready Queue -> Supervisor | singular execution capability registered | pending merged run |
| Supervisor -> Capability | synthetic execution completes | pending merged run |
| Capability -> Artifacts | four children plus execution are deterministic | pending registration |
| Artifacts -> Status | gate, counts, identities, and disposition project | pending durable projection |
| Status -> Next Task | exact evaluation consumer declared | pending Ready observation |
| Deterministic replay | registered synthetic outputs replay without work | pending durable replay |

Final integration answer for this engineering checkpoint:

**NO — INTEGRATION_PENDING.**

It becomes `YES — validated by unified mainline execution and replay` only
after merge, additive import, one fresh merged Supervisor execution, five
registrations, exact downstream Ready observation, and deterministic replay.
