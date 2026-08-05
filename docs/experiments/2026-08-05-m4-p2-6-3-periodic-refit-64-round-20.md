# M4 P2.6.3 fixed 64-fold periodic refit — round 20

Date: 2026-08-05

## Primary goal

Reduce the frozen 31,000-replicate P2.6 workload enough to finish on the current
single host within 12 forecast days, without reducing the formal workload or
changing the prediction, feature, seed, resampling, threshold, or gate
contracts.

## Non-goals

- No second host, remote shard, future deployment, CSV export, or database
  replacement.
- No statistical-result inspection and no research conclusion.
- No reuse or mixing of P2.6.1 result/checkpoint artifacts.
- No adaptive or result-dependent refit cadence.

## Frozen engineering contract

- Hypothesis: `m4-p2-6-3-fixed-strict-prior-learned-refit-64`
- Research preregistration request: `282`
- Engineering request/execution: `283` / `204`
- Policy digest:
  `ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99`
- Learned probes refit at folds `0, 64, 128, ...`; all four probes still predict
  every outer fold, and the empirical baseline still updates every fold.
- Capacity gate: weighted speedup at least `8x`, 22 local workers, forecast no
  more than 12 days.

Fixed 16-fold refit was rejected after a corrected 22.1-day estimate. Fixed
32-fold refit was rejected after a 12.6-day estimate because it had no safe
margin. Neither candidate generated or inspected formal result payloads.

## Implementation

1. The evaluator now carries the frozen update-policy digest through planning,
   execution, completion, replay, and downstream P2.7 identity.
2. Learned logistic, naive-Bayes, and shallow-tree states are reconstructed only
   at fixed boundaries. A resumed replicate reconstructs the latest boundary
   and skips settled folds.
3. The expanding empirical baseline uses cumulative 33-number counts instead of
   rebuilding the full target matrix. Runtime prefix validation no longer
   allocates an O(N) range tuple on every fold.
4. Moving-block bootstrap and block permutation avoid unused plan artifacts and
   use exact vectorized index generation. The permutation statistic precomputes
   invariant log terms while retaining the frozen per-row reduction order.
5. P2.6.1 recovery remains isolated under its frozen legacy capability and task
   digest. P2.6.3 receives a new task digest and must start with a fresh execution
   root.

## Exactness and recovery evidence

- Exact-runtime resampling was compared with the frozen implementation for issue
  counts 16, 61, and 257 across 31 replicates per length. Bootstrap values,
  permutation values, and seed digests were exactly equal.
- Eleven independently permuted prepared-statistic checks per length were exactly
  equal to the frozen statistic.
- A 61-fold periodic run made all `61 * 33 * 4` probability predictions while
  fitting the three learned probes once and updating the empirical baseline 61
  times.
- An injected crash after fold 20 resumed from the settled-fold journal,
  reconstructed boundary zero once, skipped completed folds, and produced the
  same final artifact as an uninterrupted run.
- Default execution without a periodic policy retains the P2.6.1 path.

No formal P2.6 statistical result payload was read for these checks.

## Single-host capacity evidence

The result-blind benchmark ran while the existing 22-worker P2.6.1 supervisor
continued saturating this same machine. It reused frozen every-fold timings and
measured fresh P2.6.3 forward, historical midpoint/terminal, and long
midpoint/terminal executions.

| Quantity | Measured/forecast value |
|---|---:|
| Forward-61 CPU per replicate | 14.546 s |
| Historical CPU per replicate | 405.118 s |
| Long CPU per replicate | 1,340.564 s |
| Old total CPU estimate | 582,680,848 s |
| P2.6.3 total CPU estimate | 12,158,450 s |
| Weighted compute speedup | 47.924x |
| Workers | 22 local |
| Utilization allowance | 85% |
| Single-host completion forecast | 7.525 days |

The forecast separates one-time dataset/fold/cache construction, boundary-only
learned fitting, every-fold prediction/checkpoint work, and full-length exact
resampling. It does not repeat one-time block costs for every fold. The 15%
utilization allowance covers scheduler and persistence overhead; the resulting
7.525-day estimate leaves 4.475 days of margin against the engineering gate and
6.475 days against the user's two-week limit.

The benchmark artifact is intentionally kept under ignored runtime state at
`runtime/benchmarks/m4-p2-6-3-periodic-refit.json`.

## Result-empty startup incident

The first post-merge Operator attempt used a clean detached worktree whose
empty, worktree-local `runtime` directory could not see the canonical P2.4 truth
artifacts already present on this host. Execution
`fca8f9cc0656f25b04743ffb12424993e5e6bf9f582ceeb46159a022d22f2075`
failed before dispatch with event
`09b57d599fdaf2d552f24d4dcda2dcb5e99165ecbf994f3d57c40368aee3dc9f`.
It created zero replicate results and no statistical result was read.

That failed identity is immutable and superseded rather than retried or
deleted. The next Operator request must bind its clean code worktree to the
canonical local runtime artifact root before starting a newly digest-addressed
P2.6.3 task and execution. This is a same-host path correction only; policy,
algorithms, workload, and the 7.525-day forecast are unchanged.

## Workload accounting

The formal workload remains 31,000 replicates and 64,656,000 outer-fold
predictions. Fixed-64 produces 1,021,000 refit boundaries and 3,063,000 learned
probe fits, down from 193,968,000 learned fits in the every-fold implementation.
It still performs 64,656,000 empirical-baseline updates and 258,624,000
probe/fold prediction vectors, containing 8,534,592,000 scalar number
probabilities.

## Integration matrix

| Link | Status | Evidence |
|---|---|---|
| Goal -> Resolver | complete in source | P2.6.3 capability and policy dependency in canonical manifest |
| Resolver -> Ready Queue | complete in source | repaired contract plus frozen policy readiness |
| Ready Queue -> Supervisor | complete in source | singular P2.6 capability runner |
| Supervisor -> Capability | complete in source | policy-bound coordinator/evaluator |
| Capability -> Artifacts | validated in isolated live runs | new policy identity, exact results, checkpoints, completion contract |
| Artifacts -> Status | validated in tests | P2.6.3 progress projection and counters |
| Status -> Next Task | validated in tests | P2.7 consumes the P2.6.3 policy identity |
| Deterministic replay | validated in tests | policy digest required by replay |
| Fresh unified mainline execution | pending | requires merged commit and separate Operator cutover |

Final integration answer: **NO — INTEGRATION_PENDING**. The code and isolated
runtime capacity gate are complete, but the report must be amended only after a
fresh merged P2.6.3 supervisor execution has completed live rounds and replay on
the canonical mainline.
