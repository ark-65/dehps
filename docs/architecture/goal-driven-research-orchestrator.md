# Goal-Driven Research Orchestrator

- Status: accepted target architecture; implementation planned
- Architecture identity: `dehps.goal-driven-research-orchestrator.v1`
- Owner lanes: Research, Runtime, Knowledge, and Maintenance
- Approved design request: `engineering-goal-graph-research-os-architecture-v1`
- Production impact of this document: none

## Purpose

Contract Runtime answers **how DEHPS computes**. The Goal-Driven Research Orchestrator answers
**why a computation should run next**.

The governing question is:

> Do not ask whether the latest draw is available. Ask which nodes in the current dependency graph
> have all prerequisites satisfied.

An unavailable external observation may place one task in `external_wait`. It must not become a
global Research or Goal state unless every unfinished path genuinely depends on that same event.

This architecture is a control-plane design. It does not change a Feature, weight, Window formula,
ranking, prediction, Runtime contract, scientific conclusion, or production selection.

## Problem statement and current boundary

DEHPS already has two useful but incomplete scheduler generations:

1. `research_scheduler` provides audited request creation and a persistent queue, but its v1
   priority engine applies forward readiness and open-request checks globally before choosing most
   research work. One waiting forward obligation can therefore suppress unrelated work.
2. `research_runtime` deliberately ignores forward readiness and can cycle on immutable History
   Snapshots, but its scheduler is not goal-aware and its resident executor currently implements
   only a bounded pattern-discovery action family.

The target architecture preserves their good boundaries while replacing global wait propagation
with typed, task-local dependencies and durable Goal state.

## Research OS model

### Architecture freeze layers

PR #181 is the architecture freeze point between the established computation path and the new
control plane. DEHPS is divided into five cooperating subsystems:

| Subsystem | Owns | Governing question |
| --- | --- | --- |
| Research OS | Goal Graph, Task DAG, dependency resolution, Scheduler, Lease intent, Capability requirements | Why should a computation run next? |
| Contract Runtime | History, Window, Candidate, Feature, Scoring, Ranking, Evaluation contracts and compilers | Is the requested computation legal and reproducible? |
| Compute Runtime | Kernel Planner, NumPy, Numba, SIMD, OpenCL/GPU execution | How is the verified computation executed efficiently? |
| Evidence Runtime | Run Artifacts, digests, Evidence Compiler, Evidence Bundle assembly and verification | What claim do the outputs support under the declared contract? |
| Governance | Reviewer Decisions, Policy, Authority, Promotion authorization, ADRs, and Knowledge | Which reviewed claims and transitions are accepted? |

The Promotion mechanism consumes Evidence Runtime artifacts, but Promotion authority belongs to
Governance. Neither subsystem may bypass the other.

### Immutable layer-boundary rule

> Every transition between architecture layers must be represented by an immutable,
> digest-addressable artifact.

At minimum:

- Research OS emits a Task artifact; it never calls a Kernel directly.
- Contract Runtime emits a compiled and verified Runtime Package; raw requests do not enter Compute
  Runtime.
- Compute Runtime emits a Run Artifact; executor memory or logs are not Evidence.
- Evidence Runtime compiles one or more verified Artifacts into Evidence and an immutable Evidence
  Bundle.
- Governance emits a Reviewer Decision bound to the exact Evidence Bundle digest before Promotion
  can proceed.

An in-process function call may implement a transition, but it does not replace the required
artifact identity and provenance boundary.

```text
Goal Graph
  -> per-Goal Task DAG
  -> Scheduler decision
  -> Capability match
  -> Resource lease
  -> Contract Runtime / Kernel Runtime
  -> Run
  -> Artifact
  -> Evidence
  -> Review
  -> Goal transition
  -> optional Promotion review
```

There are two graph levels:

- **Goal Graph** records relationships between durable objectives.
- **Task DAG** records the executable work needed to gather evidence for one Goal.

Both graphs must be acyclic after resolving versioned supersession edges. A cycle is an integrity
failure, not a scheduling hint.

## Goal Graph

### Goal identity

A Goal is a versioned research or capability objective, not a task list. Its minimum contract is:

```yaml
goal_key: improve_recent100_v1
objective_class: prediction_quality
baseline:
  metric_manifest: recent_rank_metrics_v1
  value: [3, 3, 4]
target:
  value: [4, 4, 5]
success_evidence:
  required_bundle_types:
    - historical_stability
    - frozen_forward_generalization
  review_policy: independent_reviewer_required
guardrails:
  - unchanged_legal_and_ranked_universe
  - no_selection_window_relabelled_as_validation
  - no_automatic_promotion
```

Normative Goal fields are:

- `goal_key` and semantic version;
- `objective_class`;
- human-readable question;
- baseline and target metric contracts;
- `success_evidence` requirements;
- guardrails, failure conditions, budget, and stopping rule;
- owner lane and required authority;
- lifecycle status and supersession metadata;
- created, approved, last-reviewed, and retired identities.

### Objective namespaces

Goals must remain in separate KPI namespaces:

| Objective class | Examples | May count as success evidence |
| --- | --- | --- |
| `prediction_quality` | rank, calibration, stability, generalization | reviewed Research/Forward evidence under the declared metric contract |
| `runtime_capability` | determinism, throughput, latency, memory, backend equality | reviewed Runtime benchmark and verification evidence |
| `knowledge_quality` | contract coverage, definition consistency, decision traceability | reviewed Knowledge audit evidence |
| `maintenance_integrity` | cache health, artifact validity, digest coverage, freshness | reviewed integrity and operational evidence |

A Runtime Goal may enable a Prediction Quality task without becoming Prediction Quality evidence.
Goal edges therefore require a relation type:

- `requires_goal`: the upstream Goal must reach a declared lifecycle state;
- `requires_capability`: a verified capability or version is needed, but its KPI does not transfer;
- `requires_knowledge`: a definition or decision must be accepted;
- `supersedes_goal`: the new Goal replaces future work while preserving history;
- `informs_goal`: reviewed evidence may change priority but cannot satisfy success criteria.

This prevents `Runtime faster` from being interpreted as `model better`.

### Goal lifecycle

```text
draft -> approved -> active -> suspended -> active
                           -> completed -> retired
                           -> retired
```

- `draft`: editable proposal; no executable authority.
- `approved`: contract reviewed, but not yet consuming resources.
- `active`: may emit Task DAG work.
- `suspended`: preserved but temporarily not scheduling new tasks.
- `completed`: a Goal Review Decision confirms the required Evidence Bundle.
- `retired`: no new work; history, evidence, and supersession remain discoverable.

Completing all Tasks does not complete a Goal. Only a reviewed Goal decision bound to the required
Evidence Bundle may transition it to `completed`.

## Per-Goal Task DAG

A Task is the smallest schedulable unit. It must declare:

- `task_key`, `goal_key`, `task_type`, and version;
- input Artifact and data-snapshot identities;
- typed dependencies;
- requested capability, estimated cost, and resource class;
- required Agent role and approval state;
- execution, output Artifact, and Evidence contracts;
- idempotency key, retry policy, and failure conditions;
- whether its result is exploratory, selection, validation, forward, Runtime, or maintenance
  evidence.

### Definition and state separation

Goal and Task identity is immutable; lifecycle and dependency state are mutable projections:

```text
GoalDefinition(goal_digest)   + GoalState(status, retired_at, superseded_by)
TaskDefinition(task_digest)   + TaskState(declared_status, resolved_status, explanation)
```

`TaskDefinition` includes its exact Goal revision, typed dependency specification, lane, priority,
input Artifact identities, requested Capability name, and metric contract. It never includes
`ready`, `external_wait`, `approval_wait`, or another resolver result. Consequently, adding an
external-event fact changes the manifest and state projection but not the Task definition digest.

The P2 repository retains every Goal and Task definition revision. Re-importing the same digest is
idempotent. Reusing a key with a different definition creates a new digest revision and records a
supersession edge; no immutable definition is overwritten or deleted.

### Dependency types

- `task`: another task reached its required terminal state;
- `artifact`: an exact verified Artifact exists;
- `evidence`: a reviewed Evidence or Evidence Bundle exists;
- `external_event`: draw, approval, hardware availability, or another outside event exists;
- `capability`: a compatible executor capability is registered;
- `resource`: Resource Manager can issue the requested lease;
- `authority`: the required Agent Request and execution authorization exist.

There is no implicit dependency on `latest_issue`. A task that needs a new issue must declare the
exact event or snapshot rule. Replay on an older immutable snapshot remains schedulable while a
forward Evaluation waits.

### Task lifecycle

```text
draft -> ready -> lease_requested -> leased -> running
      -> dependency_wait
      -> external_wait
      -> approval_wait
      -> resource_wait

running -> artifact_ready -> evidence_pending_review -> completed
        -> failed
        -> superseded
```

`external_wait`, `approval_wait`, and `resource_wait` are local states. `blocked` is reserved for an
invariant failure or an impasse with no legal recovery path.

## Run, Artifact, Evidence, and Review

The required provenance chain is:

```text
Goal -> Task -> Run -> Artifact -> Evidence -> Review -> Goal
```

- **Run** records one authorized execution, executor capability identity, lease, inputs, times, and
  result status.
- **Artifact** is immutable output plus canonical identity and provenance. It may be intermediate,
  failed, incomplete, diagnostic, or otherwise unsuitable as evidence.
- **Evidence** interprets verified Artifacts against a preregistered metric, baseline, null,
  boundary, uncertainty statement, and failure condition.
- **Evidence Bundle** groups the exact Evidence required by a Goal or Promotion policy and carries
  a canonical bundle digest.
- **Review** accepts, rejects, or requests revision of an Evidence Bundle without rewriting its
  members.

Task completion never means scientific success. Artifact existence never means Evidence acceptance.

### Promotion invariant

> Promotion may consume only an immutable Evidence Bundle with an approving Reviewer Decision that
> names the exact bundle digest and applicable Promotion policy.

Promotion must reject Task results, Run results, individual Artifacts, unreviewed Evidence, mixed
bundle identities, and bundles whose review has expired or been superseded. Research, Runtime, and
Maintenance schedulers have no direct Promotion authority.

## Three schedulers

### Production Scheduler

Production is event-driven. It owns:

- formal Prediction scheduling and sealing;
- post-outcome Evaluation;
- forward Evidence Bundle assembly;
- submission to Promotion review.

Waiting for a draw is normal here. The waiting state remains attached to the corresponding
Prediction/Evaluation task.

### Goal-Driven Research Scheduler

Research is Goal-driven. It may schedule:

- historical Replay and walk-forward experiments;
- Feature research and ablation;
- configuration and Candidate Compression benchmarks;
- diagnostics, calibration, stability, and importance analysis;
- Runtime/Kernel experiments when attached to a `runtime_capability` Goal;
- isolated experiment, engineering-planning, and Evidence-assembly tasks.

Research may run indefinitely on immutable historical snapshots. Selection results remain research
evidence and cannot acquire forward or promotion authority by repetition.

### Maintenance Scheduler

Maintenance is invariant- and policy-driven. It owns:

- cache validation and eviction planning;
- Artifact, ABI, digest, and lineage integrity audits;
- telemetry freshness and log retention;
- Knowledge-link, ADR, and contract-index checks;
- orphan lease, stale PID, failed resident, and ownership reconciliation diagnostics.

Maintenance may raise incidents and Engineering/Operator requests. It may not silently repair
scientific evidence or production state.

## Resource Manager

Schedulers select work; they do not assign hardware directly.

```text
Task -> Lease Request -> Resource Manager -> Lease -> Run -> Lease Release
```

A Lease Request names CPU, GPU, memory, storage, expected duration, concurrency mode, preemption
class, and owner Task. The Resource Manager:

- verifies capacity and policy;
- prevents incompatible exclusive owners;
- issues a time-bounded lease with a canonical identity;
- renews, expires, or revokes the lease audibly;
- accounts actual versus estimated consumption;
- never changes task scientific priority.

A heavy legacy supervisor is therefore represented as an existing exclusive lease, not as a reason
to terminate the entire Research Scheduler. Other tasks may continue when their resource requests
fit the remaining budget.

## Executor Capability ABI

Schedulers dispatch capabilities, not concrete executors. A registered executor advertises a
versioned Capability contract such as:

```yaml
capability: feature_ablation
semantic_version: 1.0.0
input_contracts:
  - history_snapshot.v1
  - feature_contract.v1
output_contracts:
  - ablation_artifact.v1
resource_profile:
  cpu: 4
  gpu: 0
  memory_gb: 8
estimated_cost:
  cpu_hours: 4
determinism: seeded_reproducible
authority: engineering_experiment_tool
```

Capability resolution must verify semantic compatibility, input contracts, resource feasibility,
authority, determinism requirements, and output contracts before leasing. Unknown or incompatible
capabilities fail closed. Executor process names, paths, and implementation details stay outside the
Scheduler policy.

## Scheduling algorithm

Each control-plane tick performs the smallest deterministic sequence:

1. ingest external events, reviews, Artifacts, Evidence, and lease changes;
2. validate Goal Graph and Task DAG acyclicity and identities;
3. recompute the dependency state of each unfinished Task independently;
4. partition `ready` Tasks by Production, Research, and Maintenance lane;
5. apply authority, duplicate, budget, diversity, and capability checks;
6. request leases for a bounded portfolio, not only one global action;
7. dispatch leased Tasks and record Runs;
8. surface local waiting reasons without changing unrelated Task readiness.

Priority is lexicographic before it is numerical:

1. safety and integrity obligations;
2. tasks that unblock the most dependent nodes;
3. preregistered tests with the highest expected information gain per cost;
4. diversity and stale-goal recovery;
5. stable-key tie breaking.

The Scheduler must not optimize a repeatedly observed Recent-N result directly. Search, selection,
stability, and genuinely forward evidence retain distinct boundaries to control multiple-comparison
and post-hoc selection risk.

## Dashboard contract

The orchestrator dashboard has four independent surfaces:

| Surface | Required views |
| --- | --- |
| Goals | Prediction Quality, Runtime Capability, Knowledge Quality, Maintenance Integrity; lifecycle, gap, required Evidence |
| Tasks | Ready, Running, Waiting by reason, Failed, Completed; dependencies and Goal binding |
| Resources | CPU, GPU, memory, storage, active/expired leases, owners, estimated versus actual cost |
| Evidence | Pending Review, Accepted, Rejected, Superseded, Promotion-eligible bundles and review identities |

An aggregate status may be `active`, `quiescent`, or `degraded`; it must not report global `blocked`
merely because one Task is in `external_wait`.

## Frozen-Future-30 example

While issue `2026083` is unavailable:

```text
Goal: m2-frozen-future-30
  Evaluation(2026083)             external_wait

Goal: improve_prediction_quality
  historical_replay               ready
  baseline_null_diagnostics       ready
  feature_ablation                approval_wait or ready
  config_benchmark                resource_wait or ready
  stability_recent300             ready

Goal: maintenance_integrity
  sealed_artifact_audit           ready
  cache_and_digest_audit          ready
  resident_ownership_diagnostic   ready
```

The Frozen-Future Goal, frozen model identity, null, threshold, cohort size, and stopping rule remain
unchanged. Other Goals may gather evidence, but they may not mutate or retrospectively replace that
cohort.

## Current implementation gaps

The accepted target architecture is not yet the deployed implementation:

- M3-P1 implements immutable Goal and Task models, task-local dependency resolution, deterministic
  Ready Queue construction, legacy `WAIT_FORWARD` compatibility projection, and the read-only
  `dehps research-os resolve` command;
- the P1 `research-os resolve` path consumes a digest-addressed Control-Plane Manifest and emits a
  digest-addressed Resolution Snapshot without persistence or dispatch;
- M3-P2 adds an additive PostgreSQL repository for immutable manifest/Goal/Task revisions, mutable
  Goal/Task state projections, dependency facts, and append-only external executor observations;
- P2 import, export, and reload verify definition, manifest, and resolver-state digests before
  returning a Ready Queue; corruption or an unknown schema fails closed;
- P2 legacy compatibility is one-way: legacy queue/process state is read into a durable shadow
  manifest and external executor observations, with no legacy write-back or dispatch;
- the v1 autonomous priority engine still has a global forward gate and global open-request gate;
- the continuous scheduler has no durable Goal Graph or Task DAG;
- the resident executor implements only the pattern-discovery capability family;
- no independent Resource Manager or executor Capability ABI exists;
- no Maintenance Scheduler owns integrity and lifecycle work;
- the resident research service treats any matching legacy supervisor as a process-wide fatal
  conflict rather than a resource/ownership lease;
- the dashboard does not expose the four required surfaces.

Documentation must continue to label these as gaps until code, migrations, tests, and live evidence
prove otherwise.

## Migration plan

### Phase 1: control-plane schema and compatibility

- **P1 completed in isolation:** add immutable Goal and Task models, typed dependency resolution,
  deterministic Ready Queue construction, a legacy wait projection, and a read-only resolution CLI;
- **P2 completed as a durable shadow:** persist immutable revisions separately from mutable state,
  add idempotent import/export and restart recovery, and project legacy waits and running supervisor
  observations without changing legacy ownership;
- remain in migration Phase A: legacy is execution primary and Research OS is the shadow control
  plane; Phase B selection ownership and Phase C legacy retirement require later approval;
- next, add durable Goal edges before Capability/Executor integration;
- defer Run, Evidence Bundle, Review, Lease, and Capability records to their owning phases;
- project existing hypotheses, experiments, Agent Requests, queue rows, and Frozen-Future work into
  compatibility views;
- replace global forward/open-request gates with task-local dependencies;
- introduce graph and lifecycle verifiers before enabling writes.

### Phase 2: capability and resource routing

- register Replay, benchmark, diagnostics, ablation, Evidence assembly, and maintenance
  capabilities;
- introduce Resource Manager lease accounting and exclusive-owner reconciliation;
- retain all existing Agent role and execution-time authorization boundaries.

### Phase 3: resident ownership and dashboard

- import an active legacy research process as a resource lease or retire it through an approved
  Operator transition;
- make resident failure local and recoverable where safety permits;
- expose Goals, Tasks, Resources, and Evidence without claiming unimplemented capability.

### Phase 4: acceptance and activation

- run a frozen-snapshot scenario with one missing external draw;
- prove Evaluation alone enters `external_wait` while Research and Maintenance complete work;
- prove no Research/Maintenance Run writes production selection or bypasses Review;
- activate the Goal-driven scheduler only after compatibility and rollback checks pass.

## Acceptance scenarios

1. With `2026083` absent, `Evaluation(2026083)` is `external_wait` and at least one independent
   Research Task and one Maintenance Task remain `ready`.
2. An open Agent Request blocks only Tasks that depend on that request or authority.
3. A saturated GPU places GPU Tasks in `resource_wait` while CPU Tasks continue.
4. A Runtime Capability Goal may unblock a Research Task but cannot satisfy Prediction Quality
   `success_evidence`.
5. Completing every Task without an accepted Evidence Bundle leaves the Goal `active`.
6. Promotion rejects a raw Task result, Run, Artifact, individual Evidence item, or unreviewed
   bundle.
7. Restart reconstructs Goal, Task, dependency, Run, and Lease state without duplicate execution.
8. Frozen-Future-30 identities and production selection remain unchanged throughout migration.

## Einstein pass

- Core question: can the control plane keep producing relevant, auditable evidence when one external
  observation is missing?
- Invariant: scientific and production authority flows only through verified Artifacts, Evidence,
  independent Review, and the existing Promotion policy.
- Hypothesis: task-local typed dependencies prevent unrelated research from inheriting a forward
  wait.
- Measurement: under a missing-draw fixture, only dependent Tasks wait while independent Research
  and Maintenance Runs complete within their leases.
- Failure mode: a global gate remains hidden in queue selection, resource ownership, open-request
  handling, or dashboard aggregation.
- Next experiment: implement Phase 1 only and prove the eight acceptance scenarios with no algorithm
  or production change.
