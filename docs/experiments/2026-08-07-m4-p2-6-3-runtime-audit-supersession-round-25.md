# M4-P2.6.3 Runtime Audit Supersession — Round 25

Date: 2026-08-07

Role: Engineering Agent

Agent Request: `engineering-m4-p263-runtime-audit-supersession-round-25-20260807`

Request / execution: `293 / 214`

## Primary goal

Replace the frozen P2.6.1 Runtime Audit execution path with a distinct,
result-blind P2.6.3 audit plan, while preserving deterministic replay of the
old plan and proving the fixed-64 periodic-refit implementation remains
strict-prior at every fold.

## Non-goals

- Do not edit or rebind the immutable P2.6.1 plan, source fixture, checkpoints,
  results, or historical executions.
- Do not change the measurement model, probes, features, seeds, resampling,
  thresholds, Gate decision, research conclusion, or Evidence credit.
- Do not read historical outcomes or P2.6.1/P2.6.3 statistical result payloads.
- Do not promote Prediction v2, cut over production, import a live manifest, or
  restart the live Supervisor in this Engineering round.

## Supersession and source boundary

| Contract | Frozen P2.6.1 | Current P2.6.3 |
| --- | --- | --- |
| Runtime Audit plan | `e2bfb82be29bedac51be6905e6049b4a10e5c0cde0198995e12279bf969714ca` | `ccbed31f36ad9486f5489d5827c6456d1853259eaeb1ab7a61077347c7e06056` |
| Source compatibility fixture | Round-6 sparse-tree fixture retained | `1e6a499c75b75ced2b674f1c680b3bd4c9055c3c97d52724da86fce2b5733d6f` |
| Measurement task identity | frozen P2.6.1 | `85a08402a4a0c37f75ee1675f4970ef00a7a0b0992b4204251c0c2cc79324de4` |
| Update policy | per-fold historical contract | fixed-64 policy `ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99` |
| Result/checkpoint reuse | independently replayable only | forbidden |

The P2.6.3 plan freezes 65 shared sources, 4 approved acceleration sources,
11 independent-oracle sources, and 373 audit/orchestration sources. The old
P2.6.1 source partition remains independently validated against its own
literal counts and digests; no mutable current-source list is used to reinterpret
that historical artifact.

## Strict-prior and result-blind proof

The independent literal golden evaluator now implements the fixed-64 learned
probe cadence without importing the production periodic-refit module. Learned
probe state is fit at fold 0 and every 64th boundary, then reused only for the
predeclared interval. The empirical baseline continues to update every fold.

An explicit hostile target-access test makes every current target unavailable
until the fold checkpoint is persisted. It covers both ordinary folds and the
fold-64 refit boundary, and fails immediately if training, fitting, prediction,
or checkpoint construction reads target `T` before the strict-prior prediction
checkpoint.

The runtime plan and both new canonical tasks bind these facts:

- historical outcomes read: `false`
- previous score, prediction, ranking, power, false-positive, bias, RMSE,
  coverage, MDE, or selected threshold read: `false`
- P2.6.1 or P2.6.3 statistical result payload read: `false`
- P2.6.1 result or checkpoint reuse: `false`
- evidence progress increment: `0`
- production action: `none`

## Duplicate checkpoint validation boundary

PR #262 already removed the second complete checkpoint-journal verification
from completion assembly. Each replicate journal is now fully verified exactly
once by `_validate_persisted_replicate`; completion aggregation consumes that
validated payload without replaying the same bytes again. Recovery continuity,
digest/tamper rejection, artifact-commit validation, and the independent P2.6.3
audit attestation remain fail-closed because they enforce different boundaries.

## Canonical mainline path

```text
M4 Goal
  -> Resolver
  -> P2.6.3 compatibility acceptance
  -> Ready Queue
  -> unified Research Evidence Supervisor
  -> P2.6.3 golden-reference freeze
  -> exact replay + immutable artifacts
  -> P2.6.3 runtime audit
  -> runtime observation + equivalence/source attestations
  -> unified M4 status
  -> runtime bottleneck review
```

The old `m4-p2-9-golden-reference-freeze` and
`m4-p2-9-measurement-runtime-audit` tasks resolve as `SUPERSEDED`. The new
`m4-p2-9-p263-golden-reference-freeze` and
`m4-p2-9-p263-measurement-runtime-audit` tasks retain distinct task and
completion identities and cannot become Ready before the P2.6.3 compatibility
fact exists.

## Validation

Passed before the clean-worktree full-CI run:

```text
133 passed in 108.52s
ruff: passed
git diff --check: passed
generator replay: stable fixture and plan digests
```

The focused set covers frozen/current plan loading, complete source partitions,
recomputed-digest tamper rejection, fresh-import closure, independent golden
evaluation, exact replay, strict-prior target ordering, fixed-64 boundaries,
resume behavior, runtime observation counts, execution-commit byte checks,
Supervisor artifact materialization, resolver state, and unified status.

Full clean-worktree Worker CI, using an absolute worktree-local `PYTHONPATH` so
fresh-import subprocesses cannot resolve the live checkout:

```text
2047 passed, 4 skipped, 4 warnings in 208.19s
```

The four warnings are Python 3.14 multiprocessing `fork()` deprecation
warnings in pre-existing training-supervisor parallelism tests; there are no
test failures.

## Mainline integration matrix

| Required link | Source implementation | Live mainline proof |
| --- | --- | --- |
| Goal | declared | existing live M4 Goal |
| Resolver | old tasks superseded; new dependencies unit-verified | import pending |
| Ready Queue | compatibility-gated readiness unit-verified | import pending |
| Supervisor | both P2.6.3 capabilities registered and exercised | execution pending |
| Capability | periodic golden and runtime audit pass focused tests | execution pending |
| Artifacts | immutable plan, fixture, golden, replay, observation, and attestation contracts | registration pending |
| Status | P2.6.1 supersession and P2.6.3 state projected | live projection pending |
| Next Task | runtime bottleneck review declared | live dependency pending |
| Deterministic replay | exact source/golden/execution paths verified | post-import replay pending |

Final integration answer:

**NO — INTEGRATION_PENDING**

The next round requires a separately approved Operator Request after merge:
import the manifest, restart the merged Supervisor, execute compatibility,
golden freeze, and runtime audit through the unified mainline, then replay the
committed artifacts. Prediction v2 promotion remains outside this round.
