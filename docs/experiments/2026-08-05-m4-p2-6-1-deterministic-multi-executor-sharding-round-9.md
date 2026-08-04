# M4-P2.6.1 Deterministic Multi-Executor Sharding — Round 9

Date: 2026-08-05

Role: Engineering Agent
Agent Request:
`engineering-m4-p2-6-1-deterministic-multi-executor-sharding-round-9-20260805`
(request 264, execution 185)

Outcome before publication and live migration: `INTEGRATION_PENDING`

Round 10 audit correction: the original exact-owner totals in this report were
computed with the unit-test parent execution id (`"a" * 64`) and were not the
live P2.6.1 totals. Recomputing the repaired manifest with the immutable live
execution id gives 15,525 and 15,475. The remaining-work table was already
computed from the live artifact paths and remains unchanged. The partition
algorithm, shard indexes, child seeds, and 31,000-identity coverage are
unchanged.

## Round contract

The primary goal is to split the unchanged P2.6.1 execution between the
current Core Ultra 7 155H host and the user's Core i9-13900KF host without a
shared PostgreSQL instance or overlapping replicate work. The user-set
capacity goal remains completion of the frozen 31,000-replicate execution
within fourteen days.

Non-goals are changes to the generator, estimand, features, targets, four probe
families, hyperparameters, seed derivation, fold order, replicate count,
metrics, result schema, Gate policy, or statistical evidence. No statistical
result was read. The accepted identities remain:

- task digest:
  `80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa`;
- execution id:
  `cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3`.

The accepted `ec8bfd6` Supervisor remained active throughout Engineering.

## Rejected Round 8 operator candidate

Before selecting the scheduling change, exact Bernoulli sufficient-count and
single-pass frozen-tree calibration operators were retested on top of Round 7.
Six interleaved terminal LONG observations per path were bit-identical, but the
five warm observations failed the preregistered `1.05x` boundary:

| Path | Warm median | Relative |
| --- | ---: | ---: |
| Accepted Round 7 | 5.177124 s | 1.0000x |
| Auxiliary-operator candidate | 5.345674 s | 0.9685x |

The candidate regressed by 3.15% and was fully reverted. It was not committed,
published, or deployed. This negative result prevented a known-small operator
from consuming another production migration.

## Implementation

The coordinator now separates two independent concepts:

1. `worker_count` controls only local process parallelism;
2. `executor_shard_count/index` controls immutable machine ownership.

When no executor-shard values are supplied, the existing single-host plan and
execution order are unchanged. When both are supplied, the frozen
`assign_shard` mapping filters only missing work; already completed artifacts
from either executor remain globally visible. Supplying only one value, a
non-positive count, a negative index, or an out-of-range index fails closed.

The canonical Supervisor exposes the pair as:

```text
DEHPS_P26_EXECUTOR_SHARD_COUNT=2
DEHPS_P26_EXECUTOR_SHARD_INDEX=0|1
```

Each machine may independently choose `DEHPS_P26_WORKERS`. The current host
can retain 20 workers while the 13900KF host uses a separately validated local
worker envelope.

Persisted results are no longer accepted by checking only one identity field.
Every reused or imported result is reconstructed through the full frozen
replicate validator, must reproduce its exact artifact digest, and must have a
complete checkpoint journal with the expected digest, fold count, contiguous
fold indexes, and target-access boundary. Immutable collisions fail closed.

## Exact partition evidence

For two executor shards the frozen hash assignment is:

| Executor shard | All replicate identities |
| ---: | ---: |
| 0 | 15,525 |
| 1 | 15,475 |
| Union | 31,000 |

Each replicate is assigned exactly once, so the intersection is empty and the
union is the complete schedule. The live plan digest is
`808b9a0b804b9c0919a4a299304d4449eb0ec9c370fbdfef2c0af2b043661d79`.
Replicate identity and both child seeds are constructed before assignment and
therefore do not change when the executor count changes.

Using only artifact-path existence, without reading statistical payloads, the
remaining work at the measurement snapshot was:

| Executor | Remaining HISTORICAL | Remaining LONG | Remaining folds |
| ---: | ---: | ---: | ---: |
| Current host, shard 0 | 6,139 | 2,480 | 30,878,519 |
| 13900KF, shard 1 | 6,099 | 2,520 | 31,017,759 |

The remaining fold imbalance is 0.45%. Shard 1 is intentionally assigned to
the faster 13900KF host.

## Offline data transfer contract

The two machines do not share a live database. A reviewed Operator migration
must stop the current Supervisor at an exact checkpoint boundary and build one
data-only ZIP containing:

- a PostgreSQL 17 custom-format `pg_dump` of database `dehps`;
- the immutable P2.6.1 task execution directory, including results, partial
  checkpoint journals, runtime migrations, and incident recoveries;
- the audited Agent Request/runtime status required by the same Supervisor;
- a checksum manifest and a remote environment template assigning shard 1.

Code is excluded; the remote host clones the merged commit from GitHub and
starts PostgreSQL/Redis through `docker-compose.yaml`. A logical dump is used
instead of copying `runtime/postgres`, avoiding platform-specific raw database
files.

Returned remote results and journals are extracted into a temporary directory.
They enter the canonical main execution only after owner, result digest,
journal digest, and fold-count validation. Existing unequal files are an
immutable collision and abort the import. The main Supervisor remains the only
completion/assembly path after both executor sets are present.

## Source governance

The scheduler, persisted-result validator, and Supervisor are audit/
orchestration surfaces; shared model and acceleration bytes are unchanged.
A superseding runtime audit plan records the new bytes:

- runtime audit plan v1.1.4 digest:
  `4d0669386fc32b27b5345995bdaf5e902aaa63109e73472804fd6b6ba06fcf15`;
- audit/orchestration source-set digest:
  `5f44e29a3e877f2e8136e1a0541ea18079cd51174280a9aaa750f3018f9196d8`;
- shared frozen source-set digest, unchanged:
  `75c124ba95c3ec0913f597b48a58a292a471fd1a00d8d9246e255ecd7f35715b`;
- approved acceleration source-set digest, unchanged:
  `41ce7c0e4586c23a7722dd9f5cb9d7cbd129564b57545d0d537005c8d6fc20e9`;
- independent oracle source-set digest, unchanged:
  `3df0dee1cbb4140cfe78ceda01a7de12aeb943a479b26681e572ab23fc7c1a5b`;
- superseding control-plane manifest digest:
  `27056596c7181f74131ca507b1b83076fc8e25f7c925fb671a73e7dd25c801da`.

The real source preflight passes, and the P2.6.1 task digest remains exact.

## Validation so far

- Coordinator/executor measurement-validation suite: `21 passed`.
- Complete runtime-plan/source-integrity hardening suite: `63 passed`.
- Ruff on all changed Python surfaces: PASS.
- Default unsharded execution plan equals the pre-change plan: PASS.
- Two-shard counts, local-worker independence, resume, result tamper rejection,
  and checkpoint-journal validation: PASS.

Publication still requires the broader Worker suite and GitHub CI. Production
acceptance additionally requires a separate Operator restart of shard 0,
creation of the data-only ZIP, and at least one exact remote shard-1 replay.

## Mainline integration matrix

| Requirement | State |
| --- | --- |
| Goal and frozen scientific contract | PASS, unchanged |
| Deterministic two-executor ownership | CODE_COMPLETE |
| Disjointness and 31,000-identity coverage | PASS |
| Worker count independent from executor shard | PASS |
| Full persisted-result and journal validation | PASS |
| Default single-host compatibility | PASS |
| Superseding source audit plan and preflight | PASS |
| P2.6.1 task/execution identity | PASS, unchanged |
| Accepted PR merged to `main` | PENDING |
| Fresh main Supervisor on shard 0 | PENDING |
| Data-only migration ZIP | PENDING OPERATOR ACTION |
| 13900KF Supervisor on shard 1 | PENDING EXTERNAL HOST |
| Returned shard merged by canonical mainline | PENDING |
| Two-week measured combined capacity | NOT YET PROVEN |

Current completion answer:

```text
NO — INTEGRATION_PENDING
```
