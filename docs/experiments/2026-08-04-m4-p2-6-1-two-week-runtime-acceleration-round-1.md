# M4-P2.6.1 Two-Week Runtime Acceleration — Round 1

Date: 2026-08-04

Role: Engineering Agent
Agent Request: `engineering-m4-p2-6-1-two-week-runtime-acceleration-20260804`
(request 246, execution 168)

## Round contract

The primary goal is to complete the remaining frozen P2.6.1 execution within
fourteen days by changing computational implementation only. The user set the
deadline explicitly: `好，那么你现在开始优化，我的底线是 2 周内完成`.

Non-goals are unchanged scientific semantics, including the generator,
estimand, state-visible features, four probe families and their frozen
hyperparameters, metrics, thresholds, seeds, folds, replicate counts,
workload, result schema, Gate policy, and immutable task/execution identities.
No partial statistical outcome was read.

## Checkpoint boundary

Operator Request 247 paused only
`dehps-research-evidence-supervisor.service` and its cgroup. The immutable
execution remained:

- task digest: `80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa`
- execution id: `cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3`
- completed replicates preserved: 13,637 of 31,000
- checkpoint journals preserved: 13,645
- failed replicates: 0
- coordinator-state SHA-256:
  `177aa945d35fc448831d5ad4417debe8070e19b0f2f9442c43c549283f72403a`

No artifact was deleted or rewritten. The same execution remains resumable.

## Einstein pass

The falsifiable question was not whether a local microbenchmark could become
faster. It was whether the remaining 62,218,903 outer folds could finish inside
the user's 14-day wall-clock budget.

- Required sustained aggregate throughput: 51.44 folds/second.
- Failure condition: an exact implementation whose measured conservative
  capacity remains below that value is not deployable as the claimed two-week
  solution.
- Smallest useful experiment: profile one cold terminal HISTORICAL fold, then
  measure one wave at 1, 8, 16, and 20 processes with all numerical thread
  pools fixed at one.
- Strongest counterfactual lower-bound probe: execute only the frozen logistic
  fit plus its required outer view. If even that partial path is below the
  target, local removal of the other probes cannot close the capacity gap.

## Profile and implementation

The accepted runtime changes are confined to the existing Phase 0 acceleration
boundary:

1. `StrictPriorFeatureCache` fills one immutable float64 feature buffer and one
   int8 target buffer as targets legally enter the training history.
2. Every expanding outer fold consumes zero-copy contiguous prefixes of those
   already revealed buffers instead of rebuilding NumPy arrays from Python
   tuples for every probe.
3. Tree model/calibration subviews are compact internal views over the current
   outer prefix; their public model, preprocessing, prediction, state, and
   result identities are unchanged.
4. The empirical baseline uses the same exact integer counts from the revealed
   target prefix without repeating 33 Python generator scans.
5. The evaluator retains the canonical train-feature digest computed from the
   original immutable tuple tree, but stores the ephemeral runtime view in
   compact arrays instead of retaining 32 expanding tuple copies per worker.

No shared frozen probe source was changed. The changed runtime source files are
the already approved acceleration surfaces: `feature_cache.py`, `reference.py`,
and `runtime_cache_backend.py`.

## Measurements

All measurements used the canonical environment:
`OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=1`
and `PYTHONHASHSEED=0`.

Cold terminal HISTORICAL fold:

| Path | Wall seconds | Relative |
| --- | ---: | ---: |
| Accepted runtime before this round | 1.032 | 1.00x |
| Round 1 exact runtime | 0.624 | 1.65x |

Concurrent cold-terminal throughput:

| Workers | Before, folds/s | Round 1, folds/s |
| ---: | ---: | ---: |
| 1 | 1.061 | 1.516 |
| 8 | 4.657 | 6.041 |
| 16 | 6.175 | 7.897 |
| 20 | 5.947 | 8.316 |

The 20-worker all-probe result is a 1.40x throughput improvement over the
pre-round implementation and 1.82x over the previous production configuration
of eight workers. The logistic-only 20-worker counterfactual reached only
11.25 folds/second. Consequently, even deleting every other cost would still
miss 51.44 folds/second by 4.57x; changing exact local orchestration alone
cannot satisfy the deadline.

At the measured full-path 8.316 folds/second, the optimistic remaining runtime
is 2,078 hours, or 86.6 days. This excludes some checkpoint, metric, resampling,
and coordinator overhead, so it is a lower bound, not a completion promise.
Meeting fourteen days requires at least 6.19 machines at the measured full-path
capacity. Seven equivalent machines is the arithmetic minimum; eight total are
recommended for orchestration and variance headroom.

## Exactness evidence

- Focused probe, measurement-validation, and golden-reference tests:
  `31 passed`.
- Ruff on all changed Python surfaces: PASS.
- Full Worker invocation: `1,968 passed, 4 skipped, 42 failed`. All 42 failures
  are pre-existing live-state conflicts caused by the active Prediction v2
  legacy-retirement artifact disabling legacy pipeline/mail/training tests;
  none is on a changed P2.6.1 surface. The clean-runtime GitHub suite remains
  required before acceptance.
- Independent literal full-replicate comparison: PASS for all 61 folds.
- Complete result object equality: PASS; artifact digest
  `246e989fdbc3f63635a1d7380605d40b6d4725774eb7fc689edaed214fbd8791`.
- Every captured fold/probe state, probability, IssueMetric, checkpoint, and
  settlement trace: exact equality.
- Checkpoint journal raw UTF-8/LF bytes: exact equality; journal digest
  `45f318ab19c46c94ea9771eb99119e50bd2f0d12c278f140dc15add8563b0ef0`.

## Decision and next bounded action

The implementation is locally exact and materially faster, but it does not
meet the two-week acceptance threshold on the current host. Therefore this
round does not authorize an in-flight runtime migration or claim the deadline.

The next bounded action is deterministic replicate sharding under the same
canonical Supervisor completion path across at least eight equivalent
executors. Deployment requires actual executor endpoints or an approved compute
environment; no paid infrastructure is inferred from this round.

## Mainline integration matrix

| Requirement | State |
| --- | --- |
| Goal and frozen scientific contract | PASS, unchanged |
| Resolver / Ready Queue / Supervisor | Existing canonical P2.6.1 path; paused at preserved checkpoint |
| Exact prediction, metric, artifact, and journal replay | PASS locally |
| Two-week measured capacity | FAIL on one host: 8.316 vs 51.44 folds/s |
| Accepted PR merged to `main` | PENDING |
| In-flight runtime migration | NOT DEPLOYED by acceptance rule |
| Fresh resumed mainline replicates | PENDING |
| Downstream completion guard and P2.9 consumer | PENDING |

Current completion answer:

```text
NO — INTEGRATION_PENDING
```
