# M4-P2.6.1 Exact Sparse Tree Operator — Round 6

Date: 2026-08-04

Role: Engineering Agent  
Agent Request:
`engineering-m4-p2-6-1-sparse-tree-operator-round-6-20260804`
(request 259, execution 180)

Outcome before publication and live migration: `INTEGRATION_PENDING`

## Round contract

The primary goal is to reduce the late-prefix cost of the frozen P2.6.1
execution by replacing the dense shallow-tree fit operator with an exactly
compatible sparse operator. The user-set capacity goal remains completion of
the 31,000-replicate execution within fourteen days.

Non-goals are changes to the generator, estimand, state-visible features,
targets, probe families, hyperparameters, seed policy, fold order, replicate
count, metrics, thresholds, resampling, result schema, Gate policy, immutable
task/execution identities, or partial statistical evidence. No statistical
result was read and evidence progress remains zero.

The accepted task identity is unchanged:

- task key: `m4-p2-false-positive-and-power-runs`
- task digest:
  `80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa`
- execution id:
  `cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3`

The existing Supervisor continued on accepted commit
`5c3778a9004041aee2ca707e7b4cc24f338ab3ed`; this Engineering round did not
pause, restart, or migrate it.

## Rejected precursor operators

Round 4 proved exact NB sufficient-count and single-pass tree-calibration
operators, but rejected them on the preregistered performance boundary:

| Workload | Before median | Candidate median | Speedup | Required |
| --- | ---: | ---: | ---: | ---: |
| terminal HISTORICAL | 2.503087 s | 2.319173 s | 1.0793x | 1.08x |
| terminal LONG | 4.898727 s | 4.756060 s | 1.0300x | diagnostic |

Round 5 profiled a terminal LONG learned-probe fold before choosing another
operator:

| Component | Wall seconds | Share |
| --- | ---: | ---: |
| Logistic regression | 3.708 | 57.4% |
| Shallow calibrated tree | 2.327 | 36.0% |
| Naive Bayes | 0.388 | 6.0% |

The Round 5 direct StandardScaler-core candidate was bit-exact but rejected at
only `1.0191x` LONG speedup (`6.255654 s -> 6.138683 s`, required `1.10x`).
Both rejected candidates were fully reverted and were not published or used by
the live Supervisor.

## Gauss pass: exact operator obligation

The frozen terminal LONG model-training matrix has shape
`(229,713, 38)`, derived from `6,961` issues times 33 red-ball rows. Thirty-three
interaction columns have at most one nonzero interaction per row; the raw
matrix nonzero fraction is `0.1363`. StandardScaler centering makes those
columns dense even though the tree needs only their ordering.

The exact invariants were checked before accepting the implementation:

1. Every scaler scale is positive, so standardization preserves the order of
   finite values within a feature.
2. The candidate tree uses the same sklearn classifier, criterion, labels,
   maximum depth, minimum leaf size, and random seed.
3. The tree is fit over raw float32 values in CSC form, avoiding the centered
   dense scan.
4. For every chosen node, the accepted standardized float32 values are
   partitioned by the raw-tree split. The candidate fails closed unless
   `left_max < right_min`.
5. The public threshold is restored with sklearn's float32 midpoint rule,
   `left_max / 2 + right_min / 2`, before calibration, serialization, state
   hashing, or prediction.
6. The accepted StandardScaler state and dense transformed calibration and
   prediction paths remain unchanged.

The proof obligation was not approximate predictive agreement. It was exact
equality of tree arrays, probability bits, probe states, fold traces, result
objects, checkpoint identities, settlement identities, and journal bytes.

## Implementation

`ExactProbeRuntimeCache.fit_exact_sparse_tree` now:

- obtains the already revealed prior-only raw feature prefix;
- constructs a float32 CSC matrix for the tree fit;
- fits the frozen sklearn tree with unchanged parameters;
- recursively reconstructs every standardized public threshold from the exact
  node partition; and
- returns the restored tree to the unchanged Platt-calibration path.

The literal golden implementation does not import the acceleration backend and
continues to fit the accepted dense standardized matrix.

Because `shallow_calibrated_tree.py` is a shared frozen probe surface, this
round also adds a reviewed compatibility fixture and superseding source audit
plan rather than treating numerical equality as sufficient:

- reviewed fixture digest:
  `e8149632b3a2f507fdb7adbd2980d4217ce06fca45913273bedc4cbe61c431c9`
- runtime audit plan v1.1.2 digest:
  `ee8c6afd84299f8976ea3949959dba3180d487d4ed487e098ec7b778caa04e52`
- candidate golden source contract digest:
  `78794b92a06a8d17a8fbcf3cbb699a6b2edba458815721bf76a32a10d5010d06`
- superseding source manifest digest:
  `078337d9fcc172777d37f06e570181cf803f080e0805832b5964cef31117fb40`

The P2.6.1 task digest remains exactly unchanged after the manifest update.

## Performance evidence

Four warm observations per path were measured on the same terminal LONG fold,
with numerical thread pools fixed at one:

| Path | Observations, seconds | Median |
| --- | --- | ---: |
| Accepted dense tree | 6.114523, 6.193421, 6.237209, 6.195637 | 6.194529 s |
| Exact sparse tree | 5.755627, 5.614312, 5.570985, 5.612012 | 5.613162 s |

Measured end-to-end learned-probe speedup is `1.103572x`, passing the
preregistered `1.10x` Round 6 threshold. An isolated tree fit changed from
approximately `1.232 s` to `0.584 s`; that operator-only ratio is diagnostic
and is not used as the acceptance number.

This is a real late-prefix reduction but not a standalone proof of the
fourteen-day capacity goal. The previously measured single-host aggregate
capacity remained far below the required `51.44 folds/s`; the 13900KF executor
and deterministic multi-executor sharding remain necessary capacity work.

## Exactness evidence

Seven prefix spot cases passed exact state and probability comparison:

- HISTORICAL NULL folds `0`, `1290`, and `2580`;
- LONG NULL folds `0`, `3030`, and `6061`; and
- LONG `MEDIUM_PRACTICAL_PAIR` fold `6061`.

An independent 61-fold FORWARD_61 replay ran the literal and observed paths in
separate processes. The literal process did not import the acceleration
backend; the observed process did. Both captures were `7,807,211` bytes.

- result object and all float64 bits: exact;
- tree arrays and Platt parameters: exact;
- probability bits and ProbeState trees: exact;
- all fold traces: exact;
- checkpoints and settlements: exact;
- raw checkpoint journal: exact, `40,250` bytes;
- result float64-tree digest:
  `e239c79849894d269dc8d33997c8a13ec1e6dc75f40c7f1bbd614105de9370b4`;
- trace-set digest:
  `47ba09c16ffa7d965edc5c2adaf15487066d60b9506d0aef6427edc4d94d539f`;
- journal SHA-256:
  `5ad68b8a9b6e97067d692fdf82f101520e261d2451262591e5ee178b4966db24`.

Source-contract validation, construction/golden identity validation, and a
real preflight against the repository and baseline commit all pass. Focused
probe and source-governance tests pass (`67 passed`), and Ruff passes on every
changed Python surface.

The local full Worker invocation completed with `1,973 passed, 44 failed,
4 skipped`. All 44 failures are the pre-existing runtime-state conflict caused
by the active Prediction v2 legacy-retirement artifact; none imports or reaches
the Round 6 operator. Python 3.14 also reproduced the documented multithreaded
`fork()` deadlock in a training-supervisor parallel test.

The final CI-equivalent invocation ran the exact candidate commit in a clean
detached worktree with its Python source root explicitly bound so fresh-import
subprocesses could not resolve modules from the live worktree. It completed
with `2,017 passed, 4 skipped, 0 failed` in `1,103.69 s`. The four warnings are
the existing Python 3.14 multithreaded-`fork()` deprecation warnings.

## Mainline integration matrix

| Requirement | State |
| --- | --- |
| Goal and frozen scientific contract | PASS, unchanged |
| Resolver / Ready Queue / Supervisor binding | Existing canonical P2.6.1 path preserved |
| Exact sparse-tree implementation | CODE_COMPLETE |
| Reviewed shared-source fixture | PASS |
| Superseding source audit plan and preflight | PASS |
| Spot prefix comparison | PASS, 7 cases |
| Independent full-replicate replay | PASS, 61 of 61 folds |
| Result / state / trace / journal-byte equality | PASS |
| LONG performance boundary | PASS, 1.103572x >= 1.10x |
| Clean full Worker suite | PASS, 2,017 passed / 4 skipped / 0 failed |
| Accepted PR merged to `main` | PENDING |
| Fresh Supervisor on merged commit | PENDING |
| At least two completed live replicates | PENDING |
| Downstream completion guard and P2.9 consumer | Existing consumer preserved; new runtime not yet exercised |
| Two-week measured system capacity | NOT YET PROVEN; additional executor remains required |

Current completion answer:

```text
NO — INTEGRATION_PENDING
```
