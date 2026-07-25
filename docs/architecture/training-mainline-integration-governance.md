# Training Mainline Integration Governance

This is a permanent DEHPS Definition of Done. It applies to training, research,
features, models, evaluation, metrics, synthetic validation, walk-forward,
negative controls, bootstrap, permutation, power, forward evidence, Promotion
Gate, and automatic decisions.

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
