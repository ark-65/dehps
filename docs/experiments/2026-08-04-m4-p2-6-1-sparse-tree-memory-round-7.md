# M4-P2.6.1 Sparse Tree Memory — Round 7

Date: 2026-08-04

Role: Engineering Agent
Agent Request:
`engineering-m4-p2-6-1-sparse-tree-memory-round-7-20260804`
(request 261, execution 182)

Outcome before publication and live migration: `INTEGRATION_PENDING`

## Round contract

The primary goal is to remove the retained per-fit allocation introduced by
the exact sparse-tree operator, while preserving exact output identity and the
Round 6 late-prefix speed boundary. The user-set capacity goal remains
completion of the 31,000-replicate execution within fourteen days.

Non-goals are changes to the generator, estimand, state-visible features,
targets, probe families, hyperparameters, seed policy, fold order, replicate
count, metrics, thresholds, resampling, result schema, Gate policy, immutable
task/execution identities, or statistical evidence. No statistical result was
read and evidence progress remains zero.

The accepted task identity is unchanged:

- task key: `m4-p2-false-positive-and-power-runs`
- task digest:
  `80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa`
- execution id:
  `cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3`

The accepted rollback Supervisor continued on commit
`5c3778a9004041aee2ca707e7b4cc24f338ab3ed`; this Engineering round did not
pause, restart, or migrate it.

## Failed Round 6 live migration

The merged Round 6 runtime was started with the unchanged 20-worker envelope.
It completed no additional replicate before the kernel killed worker PID
`1930011` after 6 minutes 9 seconds. The user service recorded `oom-kill`,
26.1 GiB peak memory, and 7.2 GiB peak swap. Completion remained 13,742 and
failed replicates remained zero. The service was immediately rolled back to
the previously accepted commit and recovered with the same task and execution
identities.

This failure means Round 6 was code-complete and merged, but not accepted by a
live mainline execution.

## Gauss pass: exact memory diagnosis

`fit_exact_sparse_tree` used a nested recursive `restore` function. Python's
recursive closure cell referenced the function itself, and the function
captured the raw float32 and float64 matrices plus the tree arrays. Each
completed fit therefore left an unreachable cycle retaining its arrays until
cyclic GC happened to run. NumPy allocations do not themselves force that
collection cadence.

A repeated real fit over a `(23,760, 4)` model matrix was measured with cyclic
GC disabled:

| Fit count | RSS before fix |
| ---: | ---: |
| 0 | 235.3 MiB |
| 1 | 236.7 MiB |
| 5 | 238.2 MiB |
| 10 | 240.0 MiB |
| 20 | 243.6 MiB |
| 30 | 247.3 MiB |

The 30 fits retained 12.0 MiB. Re-enabling GC collected 360 cycle objects and
released all retained memory, leaving RSS 0.8 MiB below the starting point.
The approximately linear retained slope, its complete release by cyclic GC,
and the repeated object count establish the failure mechanism without relying
on the production OOM alone.

## Implementation

Threshold restoration now uses an explicit LIFO work stack. Right and left
children are pushed in the same effective traversal order as the former
recursion. The raw-tree split comparison, affine standardization, float32
boundary conversion, midpoint formula, fail-closed order check, and public
threshold assignment are unchanged. The implementation does not call
`gc.collect()`, reduce the worker count, or add a memory limit as a substitute
for fixing the retained allocation.

A crash regression test performs a real sparse-tree fit after clearing and
disabling cyclic GC, drops the returned tree, and requires an explicit
collection to find zero unreachable objects.

The identical repeated-fit measurement after the change was:

| Fit count | RSS after fix |
| ---: | ---: |
| 0 | 235.6 MiB |
| 1 | 237.1 MiB |
| 5 | 237.1 MiB |
| 10 | 237.1 MiB |
| 20 | 237.1 MiB |
| 30 | 237.1 MiB |

The one-time 1.5 MiB allocator waterline did not grow after the first fit.
Cyclic GC collected zero objects and changed RSS by 0.0 MiB.

## Source governance

The acceleration backend is a pinned source surface, so this round adds a
superseding plan rather than silently changing it:

- runtime audit plan v1.1.3 digest:
  `bf5a8728d355e0b83ab1a173cd656b8a2f23abce1a1b9036664af617a1d1b47e`
- approved acceleration source-set digest:
  `41ce7c0e4586c23a7722dd9f5cb9d7cbd129564b57545d0d537005c8d6fc20e9`
- audit/orchestration source-set digest:
  `827151afca875b88c048e61450f9c038dba6d6b04bbdb85085711825579f4a84`
- superseding control-plane manifest digest:
  `d99f6a248bb83a74cb98d344607e4c7caa92b88f9ab6fb1fc402b375e2be3ea6`

The reviewed shared-model fixture remains
`e8149632b3a2f507fdb7adbd2980d4217ce06fca45913273bedc4cbe61c431c9`
because the shared scientific model source did not change. The P2.6.1 task
digest remains exactly unchanged after the manifest update.

## Performance evidence

Four warm end-to-end learned-probe observations were measured on the terminal
LONG NULL fold, with numerical thread pools fixed at one:

`3.894307, 4.059753, 4.028105, 4.457429` seconds.

The median was `4.043929` seconds. Relative to the frozen Round 6 dense median
of `6.194529` seconds, the observed speedup was `1.531809x`, passing the
`1.10x` non-regression boundary. Host load affects this diagnostic timing; the
acceptance claim is that the memory fix did not remove the sparse operator or
fall below its frozen speed boundary.

## Exactness evidence

An independent 61-fold FORWARD_61 replay ran the literal and observed paths in
separate processes. The literal process did not import the acceleration
backend; the observed process did.

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

Focused source-governance, runtime-audit, probe, and crash regression tests
pass (`68 passed`). Ruff passes on every changed Python surface.

The clean detached-worktree Worker run passed the first 1,827 collected cases
before reproducing the project's documented Python 3.14 multithreaded-fork
deadlock at
`test_prefilter_configs_target_parallel_matches_single_worker`. The sleeping
child and zombie sibling were observed directly; there was no assertion
failure or memory growth. That test and the adjacent parallel evaluation test
both pass alone, and the exact remaining collection positions 1,830 through
2,022 pass (`193 passed`). Complete case coverage is therefore `2,018 passed,
4 skipped`; a single-invocation result remains delegated to standard GitHub
CI rather than being falsely reported as a locally completed invocation.

## Mainline integration matrix

| Requirement | State |
| --- | --- |
| Goal and frozen scientific contract | PASS, unchanged |
| Resolver / Ready Queue / Supervisor binding | Existing canonical P2.6.1 path preserved |
| Retained-allocation reproducer | PASS, 12.0 MiB retained before fix |
| Iterative threshold restoration | CODE_COMPLETE |
| Post-fix repeated-fit memory | PASS, zero slope after first fit and zero cyclic garbage |
| Superseding source audit plan and preflight | PASS |
| Independent full-replicate replay | PASS, 61 of 61 folds |
| Result / state / trace / journal-byte equality | PASS |
| LONG performance non-regression | PASS, 1.531809x >= 1.10x |
| Focused tests and Ruff | PASS |
| Clean full Worker case coverage | PASS, 2,018 passed / 4 skipped; single Python 3.14 invocation hit documented fork deadlock |
| Accepted PR merged to `main` | PENDING |
| Fresh Supervisor on merged commit | PENDING |
| At least two completed live replicates | PENDING |
| Conservative 20-worker live RSS below 16 GiB | PENDING |
| Downstream completion guard and P2.9 consumer | Existing consumer preserved; new runtime not yet exercised |
| Two-week measured system capacity | NOT YET PROVEN; additional executor remains required |

Current completion answer:

```text
NO — INTEGRATION_PENDING
```
