# M4 P2.6.1 Round 13 terminal-fold feasibility audit

Date: 2026-08-05

Role: Engineering Agent

Agent Request:
`engineering-m4-p2-6-1-terminal-fold-hotspot-round-13-20260805`
(#270)

Execution: #191

## Primary goal

Locate one remaining exact Python, preprocessing, or auxiliary-probe hotspot
that can materially accelerate the post-Round-11 terminal fold on the current
primary host. The retained-code threshold was frozen at `1.15x` warm full-fold
speedup plus exact coefficient, prediction, state, result, and journal
identity.

## Non-goals

- No production service, worker, shard, database, workload, fold, refit
  cadence, solver, tolerance, model, task, or execution mutation.
- No approximate arithmetic, result-dependent shortcut, target leakage,
  statistical result payload read, Evidence Progress, Gate, or Promotion.
- No source change whose measured full-fold upper bound was already below the
  acceptance threshold.

## Result-blind hotspot profile

The profile used the terminal LONG/NULL fold with 6,961 training issues,
229,713 rows, 38 features, and all numerical thread pools fixed at one. It ran
on CPU 21 at nice 19 while the live Supervisor retained production priority.

| Path | CPU seconds | Full-fold share |
|---|---:|---:|
| exact frozen logistic preparation | 5.580 | 61.2% |
| exact sparse shallow calibrated tree | 2.869 | 31.4% |
| exact Bernoulli naive Bayes | 0.634 | 6.9% |
| empirical baseline and prediction remainder | about 0.041 | 0.5% |
| measured full four-probe fold | 9.124 | 100% |

Within the tree path, exact sparse-tree fitting used 1.628 seconds, including
about 0.501 seconds for dense-to-CSC construction and 1.009 seconds for the
unchanged sklearn tree fit. Model-prefix preprocessing used 0.541 seconds,
calibration-prefix transformation 0.103 seconds, and the calibrated wrapper
about 0.559 seconds. In a canonical consecutive-fold run, Round 11 already
reuses exact earlier prefix preprocessors and one repeated tree in each
five-fold `floor(0.8N)` cycle, so the cold terminal profile overstates the
remaining reusable portion.

The terminal matrix has 226,631 unique feature rows out of 229,713 and 227,413
unique feature-plus-target rows. Duplicate-row aggregation therefore has an
optimistic compression ratio of only `1.0136x` and was rejected without a
scientific change.

## Exact authorized-prefix CSC experiment

The last exact structural candidate used a property of the tree split: the
tree model prefix is only the first 80% of the already authorized outer
training prefix. A CSC matrix built from the current authorized prefix can be
cached and sliced for later tree prefixes without accessing a future target.

For the terminal fold, a direct 183,744-row model-prefix CSC build took:

`0.387575, 0.343374, 0.389556` CPU seconds.

Slicing the same prefix from an already authorized 229,713-row CSC took:

`0.023618, 0.031547, 0.038900` CPU seconds.

The direct and sliced CSC `data`, `indices`, and `indptr` arrays were exactly
equal; their common byte identity was
`cfe41f6b2e8a1256d7e33726ee3d6a8810f42c5cb3dd83cc9c4078669cc6e6c2`.
The one-time authorized outer CSC build cost 0.462296 seconds and could be
amortized across later prefixes.

The median per-miss saving was only about 0.356 seconds. Even granting that
entire saving on every 9.124-second fold gives an optimistic `1.041x` upper
bound before cache-rebuild cost and the existing one-in-five exact tree hit.
It cannot pass the predeclared `1.15x` full-fold gate. No production source was
changed.

## Gauss-style exact capacity pass

This is a Gauss-inspired arithmetic and residual check, not a historical
authority claim.

### Object and invariant

The object is the still-missing subset of the immutable 31,000-replicate,
64,656,000-outer-fold execution. The invariant is exact coverage of the same
replicate and fold identities under task
`80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa`
and execution
`cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3`.

An artifact-path-only pass at 13,862 completed replicates produced:

| Owner | Missing HISTORICAL | Missing LONG | Missing replicates | Missing folds |
|---:|---:|---:|---:|---:|
| shard 0, current host | 6,039 | 2,480 | 8,519 | 30,620,419 |
| shard 1, not running | 6,099 | 2,520 | 8,619 | 31,017,759 |
| total | 12,138 | 5,000 | 17,138 | 61,638,178 |

The count residual is exact:
`13,862 + 8,519 + 8,619 - 31,000 = 0`.

Completing 61,638,178 folds in fourteen days requires a sustained aggregate
`50.9575 folds/s`. Over a 94.366-second live result-blind interval, all 20
active journals advanced and wrote 963 new contiguous fold entries, or
`10.2050 folds/s`. The immediate throughput residual is therefore
`-40.7525 folds/s`; even this current HISTORICAL-stage sample needs
`4.993x` acceleration. Half the remaining folds belong to the larger LONG
scale, so treating the current rate as constant would be optimistic.

The earlier exact 20-worker logistic-only counterfactual reached 11.25
folds/s. Thus deleting every non-logistic cost while leaving the frozen
per-fold sklearn liblinear fit intact would still miss the current fourteen-
day requirement by `4.53x`. Round 12 then showed that native plus LTO
compilation improves the decisive full fold by only `1.033x`.

### Smallest defensible conclusion

The following three conditions cannot all be claimed from measured evidence:

1. keep the current frozen every-fold refit and exact sklearn model bits;
2. use only the current Core Ultra 7 155H host;
3. finish the remaining immutable workload within fourteen days.

Removing executor sharding is still required before the current host can own
the 8,619 shard-1 misses, but it changes coverage, not compute capacity. Local
exact caching, native compilation, or removal of all auxiliary probes cannot
close the measured throughput residual.

The smallest algorithmic change likely to alter the conclusion is a new,
reviewed periodic-refit contract that predicts every outer fold but retrains
the learned probes only at fixed preregistered boundaries. That would create a
new scientific task/execution and cannot silently reuse the 13,862 completed
every-fold-refit results. It requires an explicit Research contract before
Engineering implementation.

## Production observation

The Round 11 Supervisor remained active/running during all Round 13 probes,
with invocation `2ba05ff3b4d043e5951921326def4dd7`, zero restarts in the
current invocation, zero failed or retried replicates, worker count 20, and
executor shard 0 of 2. Round 13 made no production mutation.

## Integration matrix

| Mainline link | Round 13 evidence | Status |
|---|---|---|
| Goal | approved Engineering request #270 | complete |
| Resolver | production Resolver unchanged | not integrated |
| Ready Queue | production queue unchanged | not integrated |
| Supervisor | isolated result-blind probes only | not integrated |
| Capability | CSC candidate below 1.15x; no code retained | rejected |
| Artifacts | hotspot, matrix-structure, CSC, workload, and live-rate evidence | engineering evidence only |
| Status | negative feasibility report | complete |
| Next task | explicit Research decision on a periodic-refit task | blocked on contract authority |
| Replay | not run after the speed upper bound failed | not applicable |

Mainline integration answer for the Round 13 candidate:

**NO — candidate rejected before integration; the validated Round 11 runtime
remains canonical.**

