# Training Mainline Integration Governance

This is a permanent DEHPS Definition of Done. It applies to training, research,
features, models, evaluation, metrics, synthetic validation, walk-forward,
negative controls, bootstrap, permutation, power, forward evidence, Promotion
Gate, and automatic decisions.

The report integrity and continuity acceptance contract below additionally
applies to every development task, including infrastructure and documentation.

## Canonical mainline

```text
Canonical Goal
-> Task Dependency Graph
-> Dependency Resolver
-> Ready Queue
-> Research Evidence Supervisor
-> Execution
-> Immutable Artifacts
-> Status Projection
-> Forward Wait / Settlement
-> Evidence Update
-> Decision Policy
-> Promotion Gate
-> Next Task
```

Code, a CLI, tests, configuration, a report, a manual run, or a merged PR proves
only engineering presence. None proves that the mainline gained a capability.
An unconsumed artifact or a capability reachable only through a manual command
is `INTEGRATION_PENDING`.

## Required design answers

Before implementation, every governed task must name:

1. the mainline problem it solves;
2. the node it replaces, extends, or supports;
3. its canonical Goal;
4. its formal Task;
5. the dependency condition that makes it Ready;
6. the registered Supervisor/Runner capability;
7. every upstream artifact identity;
8. every downstream artifact;
9. the unified status projection;
10. the next consumer;
11. its Engineering and Evidence progress rules;
12. the Decision Policy or Gate that ultimately consumes the result.

Missing answers keep the task `PLANNED / NOT_READY`.

## Lifecycle and proof

Governed capabilities use these completion classifications:

- `CODE_COMPLETE`: implementation and unit tests exist.
- `INTEGRATION_PENDING`: the mainline does not yet call it.
- `INTEGRATED`: Goal, Task, Ready Queue, Runner, and artifact path are connected.
- `VALIDATED_IN_MAINLINE`: the minimum end-to-end execution and replay passed.
- `COMPLETE`: projection, progress, downstream unlock, full validation, clean
  tree, merged PR, and accepted runtime deployment also passed.

`CODE_COMPLETE` may never jump directly to `COMPLETE`. The minimum end-to-end
proof is:

```text
Goal -> Resolver -> Ready Queue -> Runner -> Capability -> Artifact
     -> Status Projection -> Next Task
```

An executable task declared complete must carry exactly one canonical
`mainline-execution:<task-key>:<task-digest>:<execution-id>:completed` fact.
The durable repository must verify the corresponding immutable completed event
and at least one registered artifact. A string in a manifest without those
physical records fails closed.

## Single-source and replacement rules

Core behavior has one canonical implementation:

- Log Loss and Brier: Metric Kernel.
- Walk-forward folds: unified splitter.
- Feature availability: unified leakage guard.
- Decisions: frozen Decision Policy.
- Progress: unified status projection.
- Task dispatch: Research Evidence Supervisor.

Manual CLIs may validate or replay the canonical execution. They may not create
a second completion path. Replacements must state old/new implementations,
migration, cutover, rollback, compatibility window, deprecation, and a path
audit proving that the old implementation is no longer canonical.

## Required integration matrix

Every final training report contains:

| Integration item | Required evidence |
| --- | --- |
| Canonical Goal | Goal/task identity |
| Dependency Graph | dependency manifest |
| Ready Queue | pre-execution snapshot |
| Unified Runner | immutable execution id |
| Upstream artifacts | verified parent digests |
| Downstream artifacts | registered artifact digests |
| Status projection | post-execution snapshot |
| Engineering Progress | before/after |
| Evidence Progress | explicit policy and before/after |
| Downstream consumer | next Ready task |
| End-to-end replay | same execution/artifact identity |
| No old bypass | path audit |

Any critical failure classifies the task `INTEGRATION_PENDING`.

## Report integrity and continuity acceptance

User requirement, 2026-09-09: every completed development task must preserve
report completeness and must not disrupt reporting. Report acceptance is a
required completion gate, not an optional follow-up after code acceptance.

### Before implementation and release

1. Declare the expected issue, report kind, draw date, preparation/delivery
   deadline, and timezone from the canonical calendar and audited history.
   Record missing issues explicitly. Never infer the expected issue solely from
   the latest successfully completed replay or the latest sent ledger entry.
2. Capture the existing Goal/Task/Ready state, execution and artifact identities,
   source digests, report availability, delivery state, and timer schedule for
   the affected path. State existing failures separately from new regressions.
3. Trace direct and shared dependencies, including schema initialization and
   transaction locks, immutable source/import checks, supervisor dispatch,
   report selection/rendering, downstream consumers, mail configuration, and
   timers. A change outside the report module is not evidence of no impact.
4. Validate the affected canonical path in isolation before release. Reproduce
   the relevant failure and verify it cannot silently present an older issue as
   current success or block successor reports without a visible failure. Use
   the smallest sufficient checks; do not introduce a competing report runner.
5. Verify frozen source bindings against the proposed bytes, and document the
   authorized deployment/recovery and rollback approach when runtime changes
   are needed. Never change historical digests, definitions, or evidence to
   conceal incompatibility or obtain a passing result.

### Required before/after acceptance evidence

Every development report includes this matrix for affected report paths. All
identities and timestamps must refer to the intended issue and accepted commit.
Record evidence paths or durable record identities, not just a boolean claim.

| Check | Required evidence |
| --- | --- |
| Impact and expected issue | Changed files, shared dependencies, issue/date/timezone, deadlines, baseline failures and new differences |
| Prediction availability | Registered pre-draw artifact, source/checkpoint and history cutoff, sealed timestamp before the applicable deadline |
| Report completeness | Required contract sections, legal/unique candidate counts where applicable, input provenance, evidence level and explicit gaps; for post-draw reports, audited draw/payout input and reconciliation to the sealed prediction |
| Mainline and replay | Goal/Task/Ready and fresh execution id for changed runtime, deployed commit, registered artifact digests, required typed and generic replay results |
| Consumer continuity | The normal report consumer can read the same registered output; the next issue becomes Ready or enters its defined wait rather than remaining stuck |
| Delivery | Exact issue and kind in the ledger, authorized destination binding, status and timestamp, message identity where available, and no duplicate; distinguish transport acceptance from recipient receipt |
| Scheduling | Expected timers enabled/active, configured deadlines and next trigger, last execution result/time, and no new failure hidden by a successful service exit |
| Preservation | Original failed events, artifacts and prior delivery records unchanged; recovery facts appended through the approved path |

Read-only checks must remain read-only. Running a consumer that dispatches work,
imports state or sends mail requires the corresponding execution authorization.
Do not send test mail, resend, change timers, or restart production solely to
populate this matrix without the required authorization.

### Completion decisions and timing

These are acceptance-report verdicts; they do not create new Research OS task
states or replace existing mainline or authorization gates.

- `PASS`: all applicable checks for the affected report cycle passed, including
  delivery when due. State exactly which issue and cycle were observed.
- `PENDING_DELIVERY`: an affected report is ready but its authorized send window
  has not arrived. Record artifact/replay readiness and the next trigger. Code
  and deployment can be reported separately, but end-to-end delivery acceptance
  and overall runtime task completion remain pending until the due cycle is
  observed. An active timer alone cannot establish successful future delivery.
- `BLOCKED`: an affected due report is absent, incomplete, bound to the wrong
  issue, blocked upstream, not replay-verifiable, unreadable, unsuccessfully
  delivered, or missing required evidence. Report the failure, expected/actual
  issue and next recovery step; do not declare the task complete. Surface it
  through the existing authorized status/notification path. `ALREADY_SENT` or a
  zero exit code for an older issue cannot clear this verdict.
- `NO_RUNTIME_IMPACT`: allowed only when the diff and dependency/source-binding
  audit prove the change cannot affect reporting runtime. Record the evidence
  and any known historical gaps. No production restart or future draw is needed
  to accept such a task; this verdict makes no new delivery or mainline claim.

A historically missed pre-draw window cannot be repaired by generating a
prediction after the result is known. Preserve and disclose the missed issue
and the resulting absence of a valid return report. A separately scoped
recovery may be accepted on its own evidence, but cannot relabel the missed
issue as completed or use it as forward predictive evidence. Historical gaps
remain visible in later acceptance reports until explicitly accounted for.

Every final development report states the verdict, expected and observed issue,
evidence references, unresolved gaps, and next due time when applicable. A
policy/documentation change must also say whether any automated enforcement was
implemented; writing this rule alone is not proof of a new runtime health check.

## M4 chain

```text
P2.1 Synthetic Dataset
-> P2.2 Metric Kernel
-> P2.3 Walk-forward Harness
-> P2.4 Injected Signal Calibration
-> P2.5 Resampling
-> P2.6 False-positive / Power
-> P2.7 P2 Gate
-> P3 Historical Walk-forward
-> P4 Negative Controls
-> P5 Forward Evidence
-> P6 Information Bound and Decision
```

Each stage consumes the prior formal artifact, executes from the current Goal's
Ready Task through the same Supervisor, writes immutable artifacts and state,
and automatically exposes the next legal task or a defined wait.

For P2.3 specifically, the Supervisor must locate the canonical P2.1 dataset,
verify the P2.2 Metric Kernel, call the existing strict harness, register fold,
prediction, settlement, aggregate, and execution artifacts, project actual
fold/artifact counts, complete P2.3, and make P2.4 the sole Ready task. Replay
must require no manual dataset or manifest argument assembly.

## Scheduling priority

Nightly/self-iteration priority is:

1. mainline correctness or leakage;
2. integration of existing capabilities;
3. work blocking the current Gate;
4. new core capability;
5. performance/reporting;
6. optional refactoring.

Do not add a same-level capability while a critical one remains
`INTEGRATION_PENDING`. “For later”, “reserved for future use”, and “can be
integrated later” are not completion arguments.

## Mandatory final answer

Every governed task ends with exactly one unambiguous conclusion:

- `YES — validated by unified mainline execution and replay`, or
- `NO — implementation remains INTEGRATION_PENDING`.
