# M4 Measurement-v2 Repair-v2 Health Execution — Round 50

## Primary goal

Implement the frozen Repair-v2 formal health runner as the sole canonical
consumer of the Round 49 preregistration. The runner must execute 131,072
canonical children through 2,048 process-pool shard jobs, resume from one
compact append-only index, and skip already registered matching children
without regeneration or duplicate validation.

## Non-goals

- No change to fixtures, estimator, seeds, sample size, alpha, Wilson gates, or
  decision thresholds.
- No authoritative health decision in the execution capability.
- No historical outcome access, Evidence creation, accepted-model selection,
  Prediction-v2 promotion, P3 work, or production prediction.
- No formal child execution before a merged Operator release.

## Frozen execution geometry

The formal workload remains exactly:

- `3 * 2 * 1024 * 19 = 116736` matched reference children;
- `7 * 2 * 1024 = 14336` evaluation children;
- `116736 + 14336 = 131072` total children;
- `131072 / 64 = 2048` canonical process-pool shard jobs;
- `291110912` planned generated issues;
- `173146112` planned outer evaluation issues.

Reference blocks are matched on null family, scale, and evaluation index. An
IID block may be shared by same-scale, same-index IID evaluation cells, but no
cross-cell independence is claimed. The six-control false-REPAIR statement
remains the union bound `0.004767112426180425`.

## Implementation result

The new runner provides one canonical child set whose digests match the Round
49 preregistered reference/evaluation identity functions. Worker count and
shard layout do not enter child identity or seed derivation.

The formal scoring path replaces the slow per-coordinate scalar identity
oracle with an independent NumPy reduction. Preformal tests compare all four
base fixture families at both scales against the scalar oracle with absolute
error at most `1e-12`. This changes implementation cost, not the estimator or
statistical object.

The checkpoint path reads one compact JSONL completion index once. Matching
registered children are projected directly into the pending-set subtraction;
they are not generated, replayed, or revalidated. Missing work is dispatched
at most once per execution. A mismatched registered identity fails closed.
There is no recursive scan, raw replay, sentinel replay, or duplicate
validation. Completed-issue progress is maintained incrementally rather than
rescanning every prior row after each shard.

The capability registers exactly three child artifacts plus its immutable
mainline execution:

1. compact completion index;
2. aggregate Repair-v2 measurement-health result;
3. execution completion;
4. mainline execution identity.

Replay rebuilds the three registered aggregate artifacts from registered index
content and requires byte-identical identities. It generates no child and does
not read historical outcomes.

## Gauss–Riemann cross-review

### Gauss pass

The workload arithmetic, identity domains, index bounds, Wilson boundary, and
matched-reference coordinates are exact. A negative-control count of 74 has a
Wilson upper bound at or below `0.09`; 75 exceeds it. The registered source
contract freezes seed domains, strata, local admissibility power, estimator,
and all gates.

### Riemann pass

The compute topology was changed from 131,072 scheduling objects to 2,048
64-child shards without changing the statistical topology. Family, scale, and
evaluation-index strata remain explicit, while checkpoint state is a compact
projection of canonical child identities rather than a second execution path.

### Disagreement

Same-index IID reference sharing creates dependence among IID cell decisions.
It is valid for the frozen matched-block computation but cannot justify a
joint-binomial or independent-cell claim.

### Smallest shared conclusion

The runner is a compute and orchestration optimization only: exact canonical
identity plus load-once pending-set subtraction eliminates duplicate work while
preserving the frozen matched-null program and its union-bound discipline.

### Next verification

After merge, import the additive manifest through an approved Operator Request,
start a fresh merged supervisor, observe at least one durable completed shard,
restart once, and verify that those registered children are skipped with zero
regeneration before allowing the full run to continue.

## Validation

- Ruff and Python compilation: passed.
- New Repair-v2 health execution tests: 9 passed.
- Adjacent Repair-v2 execution/decision/design/preregistration tests: 39 passed.
- Full non-retired Worker mainline: 2,100 passed, 4 skipped.
- Unfiltered Worker run: 2,142 passed, 4 skipped; 42 expected failures remain
  confined to seven permanently retired legacy three-line entrypoint files.
  One additional current source-partition count exposed by the first run was
  fixed, then passed in the complete non-retired run.
- Additive migration dry run against the durable Round 49 manifest: one revised
  health-execution task, one new decision task, zero state regressions, zero
  fact deletions, and zero unallowlisted definition rewrites.
- Source contract digest:
  `e1a2b76b1df2bb93a696330256462569e8122608fc027b014051391b9d89abee`.
- Canonical source manifest digest:
  `1790affe3010f14921e6f823e8d8aa8b9843cddcbe6619c0cba2b257f7a9d135`.
- `git diff --check`: passed.

## Mainline integration matrix

| Binding | Round 50 status |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` bound |
| Resolver | additive migration dry-run verified |
| Ready Queue | health execution becomes Ready after Operator import |
| Supervisor | canonical capability registered |
| Capability | frozen sharded runner implemented |
| Artifacts | index, aggregate health result, completion implemented |
| Status | Repair-v2 execution and decision projection implemented |
| Next Task | separate Repair-v2 health decision declared |
| Replay | aggregate-only deterministic replay implemented |
| Merged mainline execution | pending Operator release |

Final training integration answer:

`NO — INTEGRATION_PENDING` until the merged supervisor executes the formal
Repair-v2 program, registers its completion fact, and replay-verifies the
registered aggregate content.
