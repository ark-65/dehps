# Prediction v2 Structural Baseline Comparison Execution — Round 78

## Round contract

- Primary goal: implement approved Research Request 405 as the singular high-throughput executor for the frozen three-class structural baseline comparison.
- Non-goals: no algorithm, seed, workload, threshold, portfolio, model, prediction, usefulness, promotion, P3, betting, or production change.
- Task: `prediction-v2-structural-baseline-comparison-execution`.
- Completion fact: `prediction-v2-structural-baseline-comparison-execution:COMPLETE`.
- Downstream consumer: `prediction-v2-structural-baseline-comparison-route-decision`.
- Engineering Request: 406; execution: 327.

## Implementation

The executor consumes only the registered preregistration execution and its three children, the immutable canonical B176 portfolio, and the bounded registered portfolio evaluation execution/decision. It queries no database, history, CSV, outcome, fold, bootstrap, or model data.

The frozen workload remains:

- three label-symmetric greedy classes;
- 128 replicates per class;
- 176 portfolio steps per replicate;
- one disjoint 256-candidate stream chunk per step;
- 45,056 candidate considerations per replicate;
- 5,767,168 per class;
- 17,301,504 total.

The performance path is:

1. materialize the 1,107,568 legal-combination number, mask, and pair tables once;
2. fork 22 workers so the immutable tables remain copy-on-write shared;
3. generate each replicate through the frozen SHA256 counter/rejection sparse partial Fisher–Yates stream;
4. evaluate a full 256-candidate step in one compiled integer kernel;
5. checkpoint exact stream, sparse swap-map, selected ranks, counts, and metrics every 16 completed steps;
6. reuse committed replicate results directly on restart;
7. register only the deterministic result index, gate outcome, completion, and mainline execution.

There is no duplicate, membership, uniqueness, or post-hoc repetition scan. Distinct stream positions follow directly from partial Fisher–Yates, and the 256-position chunks are disjoint by construction. The artifact/status marker is `repetition_scan=ABSENT_BY_CONSTRUCTION`.

## Exact gate

The registered candidate has exact coordinates:

| Metric | Value | Direction |
| --- | ---: | --- |
| singleton square sum | 33,796 | minimize |
| pair square sum | 14,152 | minimize |
| minimum replacement distance | 2 | maximize |
| sum pairwise replacement distance | 76,030 | maximize |

The decision remains preregistered and integer exact: the candidate must strictly Pareto-dominate at least 122 of 128 replicates in every class, and no baseline replicate in any class may strictly Pareto-dominate the candidate. A valid failure archives the portfolio as engineering evidence only. Invalid or incomplete execution creates no completion fact.

## Validation

- Focused executor/source/stream/checkpoint/artifact/replay/migration/status tests: `9 passed`.
- Full structural chain plus mainline Supervisor regression: `71 passed` (`56` structural-chain tests and `15` Supervisor tests).
- Full worker regression: `2,264 passed`, `4 skipped`, and the unchanged `42 failed` set confined to deliberately retired legacy training, old three-line, old forward-evaluation/mail, and related legacy entrypoints; no new failure remains.
- Exact additive durable dry-run: 68 to 69 tasks, one revised task, one new route-decision task, no state regression, no fact deletion, and no unallowlisted definition rewrite.
- Small multiprocess live program: three classes, one replicate each, 8×16 candidates, completed and reproduced identical artifacts from committed replicate results.
- Full-shape microbenchmark: three classes, one 176×256 replicate each, 135,168 candidate considerations total, completed in 0.62 seconds including table/process startup; this is an engineering observation, not the registered full-run outcome.
- Source contract pins the executor and reused immutable universe implementation bytes.

## Claim boundary

Einstein pass: the null remains that a transparent same-opportunity construction can reach the optimizer portfolio's structural region. Passing supports only incremental structural construction value beyond these three frozen baselines.

Gauss pass: `C(33,6)=1,107,568`; `176×256=45,056`; `45,056×128=5,767,168`; three classes yield `17,301,504`. Metrics and dominance use exact integers, and scalar/compiled fixtures agree.

Prediction v2 remains `SHADOW_ONLY / BASELINE_ONLY` with historical Evidence `INCONCLUSIVE`. No portfolio activation, prediction probability claim, model, expert, promotion, P3, betting output, or production action is authorized.

## Mainline integration matrix

| Link | Round 78 state |
| --- | --- |
| Goal → Resolver | source DAG defines the exact execution capability |
| Resolver → Ready Queue | additive 68→69 migration dry-run verified |
| Ready Queue → Supervisor | capability is registered and selected by the latest-summary path |
| Supervisor → Capability | implementation and small live multiprocess execution verified |
| Capability → Artifacts | deterministic three-child builder verified |
| Artifacts → Status | execution decision/counts/construction marker projected |
| Status → Next Task | separate route-decision placeholder defined |
| Deterministic replay | registered-row aggregate/dominance replay verified with zero generator workload |
| Merged-main durable execution | pending PR merge and separate Operator Request |

Final integration answer for this implementation round: **NO — INTEGRATION_PENDING**. The capability becomes complete only after the ready PR merges and a fresh merged-main Supervisor executes and replays the full frozen workload on the durable control plane.
