# M4-P3 result-blind structural-utility preregistration — round 118

Date: 2026-08-10

Role: Engineering Agent

Approved request: Engineering Request 450 / Execution 371

Research parent: Research Request 449 / Execution 370

Mainline parent: design execution
`887d67dd0475f5ea0580c8c10818354b7a1196434768371b4d0276119de64f83`

## Primary goal

Bind the completed Research preregistration to the canonical Goal, resolver,
Ready Queue, Research Evidence Supervisor, immutable artifact registry, unified
status, downstream blind-execution task, and deterministic replay without
running any generator, fold, metric, bootstrap, or model workload.

## Explicit non-goals

- No portfolio was generated and no walk-forward fold was executed.
- No target draw row, future draw, hit, payout, return, reward, rank, or
  structural result value was read by the capability.
- No bootstrap resample, historical feature snapshot, Evidence, prediction
  claim, model, expert, promotion, predictive P3, or production action was
  created.
- The old `static_100`, `dynamic_kdj`, and `dynamic_kdj_near` lines remain
  `FROZEN` and were not restarted.
- Prediction v2 remains `SHADOW_ONLY` / `BASELINE_ONLY`.
- The blind generator and 90-fold execution remain unimplemented and require a
  separate approved Research and Engineering contract.

## Frozen research identity

Research Request 449 / Execution 370 is the singular authoritative source for
the preregistration payload. The compiler verifies its completed typed-request
identity, parent request, result-blind metadata, context fingerprint, execution
status, zero-work counters, and canonical research-contract digest:

```text
research context fingerprint = 12ce0a5ba65d2d9ff1d3bebe43792bb6671aba9f2c24f2a572aa51e987fc9bb3
research preregistration digest = 407abd9dbedee32d5bca0456ae3018b5fae52720107ea895671e31ce360e6631
```

The source contract pins the compiler bytes and the same Research identity.
Its artifact digest is
`72f5032c40d339946f014f7f333dd400f9ccf3a8a48250943ee1143e347687b8`.
The compiler does not maintain an independently editable copy of the frozen
statistical choices.

The audit record truthfully preserves that older structural values were
incidentally observed during repository discovery. It separately verifies that
none was used to select a fold, source, configuration, seed, metric, tolerance,
threshold, or decision rule. It does not claim that no older value was ever
seen.

## Frozen choices

- 90 consecutive identifier-only folds, targets `2026002` through `2026091`,
  with expanding strictly prior-only history and a minimum of 900 prior rows;
- exactly 100 distinct canonical six-of-33 tickets per arm;
- 32 uniform-without-replacement null replicates per fold;
- one chronology-selected frozen legacy `score_topk` arm;
- one exact existing-fixture `greedy_score_diversity` candidate arm;
- six separately reported structural coordinates, with three primary-support
  and three protected-non-regression coordinates;
- invariant graph-family partition digest
  `448d0ab7bbf021ec3764982439f3d7fd51c8b66bfddb5e0fa0ea7aa586b1b86a`;
- circular moving-block bootstrap, block length 5, 20,000 future resamples;
- Holm familywise alpha 0.05 across 12 one-sided comparisons;
- no scalar utility score and no post-hoc coordinate promotion;
- fail closed on leakage, source/config/seed drift, missing or substituted
  folds, duplicates, nonfinite metrics, timeout, incomplete output, or replay
  mismatch.

## Deterministic zero-work artifacts

The capability compiles three children plus the standard mainline execution:

1. frozen preregistration;
2. blind-execution handoff;
3. preregistration completion;
4. Research OS mainline execution.

Every child records:

```text
portfolios_generated = 0
folds_executed = 0
random_replicates_executed = 0
metric_results_read = 0
target_draw_rows_read = 0
bootstrap_resamples_executed = 0
historical_feature_snapshots_materialized = 0
previous_structural_result_values_used_to_select_any_choice_count = 0
```

Replay reconstructs the registered contents from the pinned source, completed
Research request/execution projection, parent completed-event metadata, and
four parent registration identities. It declares `workload_rerun=false`.

## Additive migration rehearsal

The repository source manifest changes from 79 to 80 task definitions by
revising only the unstarted preregistration task and adding one unsupported
downstream task:

`m4-p3-result-blind-structural-utility-blind-generator-and-walk-forward`

The downstream task has no capability or inputs and waits on its own future
Research approval event. The final read-only rehearsal against the durable
79-task mainline reported:

```text
new goals = 0
new tasks = 1
revised tasks = 1
unchanged tasks = 78
state regressions = 0
fact deletions = 0
unallowlisted rewrites = 0
import_performed = false
production_action = none
dry-run digest = 0dbf93733f7a153d4bc168e5e21b7fcb122ec9f05cc960acc240dc1a0f4a275b
merged manifest digest = 79a406344952cf017d66c94869cf4f0c9f3e2b9b06c08b8c0964a1a51d33454d
```

The resolver produced exactly one Ready task: the preregistration. The new
blind-execution task resolved `external_wait`.

The canonical source manifest digest is
`6dff4a5326d7b7308cdca7be88c2307d7902c2366431d0a86a04c5ea3d6d1c95`.
Its artifact-index lineage directly supersedes the previously committed source
manifest `6bfb2795468b0a9fbe5ef86c005903ce243fee0900a7ab2f72410eccf0330d3e`;
no transient local candidate identity is retained.

## Validation

- New and updated M4-P3, historical recovery, and source-partition tests:
  21 passed.
- Focused M4-P3, M4 roadmap, Research OS resolver, repository, schema, CLI,
  shadow, and Supervisor suite: 113 passed, 4 skipped.
- Ruff import and unused-symbol checks on every touched Python surface: passed.
- Source contract byte verification: passed.
- Final additive live migration rehearsal: passed; exactly one Ready task.
- `git diff --check` and artifact-index JSON validation: passed.
- A local full Worker run before correcting four manifest-history expectations
  produced 2338 passed, 4 skipped, and 47 failed. The four failures caused by
  this new task/source identity were corrected and pass. The remaining 43 are
  existing tests of locally retired legacy prediction/training/mail paths; the
  checked-in main baseline had already passed GitHub CI before this round, and
  this round does not reactivate those paths.

## Integration matrix

| Link | Engineering code-review status |
| --- | --- |
| Goal -> Resolver | preregistration remains under the independent structural-utility Goal |
| Resolver -> Ready Queue | additive durable rehearsal resolves exactly preregistration as Ready |
| Ready Queue -> Supervisor | capability is registered in the singular Supervisor registry |
| Supervisor -> Capability | completed Research Request 449 and parent design identities are loaded and validated |
| Capability -> Artifacts | three deterministic zero-work children are compiled |
| Artifacts -> Status | preregistration completion and execution projection are implemented |
| Status -> Next Task | unsupported blind generator/walk-forward task is present and externally blocked |
| Deterministic replay | local registered-content reconstruction is implemented and tested |
| Merged-main durable execution and replay | pending separate Operator Request |

Integration answer at the Engineering code-review boundary:

```text
NO — INTEGRATION_PENDING
```

## Replay repository compatibility — round 123

PR 329 was auto-merged as commit
`56bad1208299b6843a97b484972ad21553c26b2c` before its Worker check
completed. PR run `31355753739` and main run `31355763328` then failed with 23
same-signature replay regressions:

```text
AttributeError: ReplayRepository has no attribute load_manifest
```

The Round-122 replay projection had added one unconditional durable-manifest
read solely to recover task identity. Existing isolated replay repositories
intentionally implement only immutable event and artifact reads, so the new
dependency broke their interface before any replay assertion ran. No scientific
or runtime result failed.

Engineering Request 455 / Execution 376 removes the manifest dependency. The
shared projection now accepts the task key and requested capability that each
caller already validated. Replay supplies its requested task key and the
digest-verified execution artifact capability. The exceptional zero projection
still requires the exact M4-P3 task, exact preregistration capability, and all
six explicit zero-work counters; every other missing or invalid fold count
remains fail-closed.

Ruff passed, and 209 tests passed across all 23 CI-failing replay files plus
the M4-P3 preregistration and shared Supervisor suites.

The durable running task, completed event, eight total registrations across the
failed and completed executions, and every artifact byte remain untouched.

The integration answer remains:

```text
NO — INTEGRATION_PENDING
```

## Completed-event finalization incident — rounds 121–122

PR 328 merged the first runtime recovery as commit
`d76a3f44186946367485814a50c74c59f42d3fb3`; main Worker CI run
`31354784595` passed. Operator Request 453 / Execution 374 imported the exact
recovery manifest and dispatched the only Ready task. The capability completed
without workload and immutably recorded:

```text
execution = 4263c9e224bd09cc416afa4fa9b50c7ed758d96cb38e7405f4c2efc9735c3ce9
started event = 9b4a7fa7ef9d154b6496d47983153998f1d8922cca02beed5945b08f494b466c
completed event = e4b91dc84d69bfb098becd7c3696d4af41436bf432c8dcef22e9ea3702bb9117
new registrations = 4
completed-event actual_fold_count = 0
```

The immediate status finalizer then failed closed with
`completed execution identity changed`. The first fix projected the zero fold
count when writing the completed event, but the shared completed-execution
loader still compared that event value against the absent raw field in the
frozen execution artifact. The task remains `running / INTEGRATED`; the
completed event and all four registrations are preserved. The capability must
not be dispatched again.

Engineering Request 454 / Execution 375 owns the second bounded fix. It applies
the same exact task/capability plus six-zero-counter projection when validating
the completed event and when reporting deterministic replay. It does not add a
field to, rewrite, or reinterpret the immutable execution artifact. Merged-main
Operator recovery must resume the already completed execution, project status,
replay it, and register no new artifact.

Round-122 validation completed with 117 passed and 4 skipped across the M4-P3
and Research OS focused suites. A live read-only call to the corrected completed
loader verified event `e4b91d...`, execution `4263c9e...`, four registrations,
the absent raw field, projected fold count zero, and unchanged running task.
Ruff and `git diff --check` passed.

The integration answer remains:

```text
NO — INTEGRATION_PENDING
```

The answer can become `YES — validated by unified mainline execution and replay`
only after a ready PR is merged and a separately approved Operator request
imports the additive merged manifest, dispatches the preregistration through
the canonical Supervisor, registers all four outputs, verifies replay, and
projects the blind-execution task without starting it.

## Post-merge incident and exact recovery — rounds 119–120

PR 327 was squash-merged as commit
`613f585c2b7334a762735a838015e8e4b30eb9cf`; GitHub Worker CI run
`31353494050` passed. Operator Request 451 / Execution 372 imported the exact
80-task merged manifest and observed only the preregistration Ready. The first
canonical dispatch then failed while constructing the generic completed event:

```text
execution = f5491f273bb09dda3c093f0286ca574f1fa3233f4e67ea8e1c00e0d0acee06a4
started event = 996846eaaa8d983816d950e4ad1c80ea2294a8a51a8f3a071f32020db6222d00
failed event = 9bded78f38a6ea0a23cdf3665a07c0d962566528948b787c225567123221aade
error = KeyError: 'actual_fold_count'
```

The capability correctly produced zero-work preregistration artifacts, which
do not contain a historical fold-result field. The generic Supervisor assumed
that every execution artifact exposed `actual_fold_count` and raised after
registering the four immutable outputs. The durable task therefore became
`failed / INTEGRATED`; no completed event was recorded. Operator 451 / 372 was
closed `FAILED`. No generator, fold, metric, bootstrap, Evidence, prediction,
promotion, or production workload ran.

Engineering Request 452 / Execution 373 owns the bounded recovery. The runtime
fix accepts `actual_fold_count = 0` only for this exact preregistration
task/capability and only when all six workload counters are explicitly zero;
missing or invalid values remain fail-closed everywhere else. This projection
is validated before any new artifact registration.

The recovery builder binds the exact failed manifest, task, execution, two
events, error, and four registration identities. Its live read-only result is:

```text
input failed manifest = a96333328326e9876a9bca514447f09d8fc72d2804bb3805e39c5fb7b29e9d41
output recovery manifest = 79a406344952cf017d66c94869cf4f0c9f3e2b9b06c08b8c0964a1a51d33454d
changed tasks = 1
transition = failed / INTEGRATED -> draft / INTEGRATION_PENDING
deleted or rewritten events = 0
deleted or rewritten registrations = 0
preserved registrations = 4
workload rerun = false
Ready Queue = m4-p3-result-blind-structural-utility-preregistration
blind execution = external_wait
status = SAFE_TO_RECOVER
```

The recovery manifest has exactly the original merged-manifest digest because
it restores only the canonical preregistration task state. Import and dispatch
remain prohibited during the Engineering role. They require a fresh approved
Operator Request after this recovery change is merged and its CI passes.

Round-120 validation completed with 116 passed and 4 skipped across the M4-P3
design/preregistration suites, Research OS control plane, repository, schema,
CLI, shadow and Supervisor suites, and M4 source-partition hardening. Ruff,
`git diff --check`, the live read-only recovery builder, exact manifest digest,
Ready Queue, and external-wait assertions also passed.

The integration answer remains:

```text
NO — INTEGRATION_PENDING
```
