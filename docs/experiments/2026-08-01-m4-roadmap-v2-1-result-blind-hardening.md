# M4 Roadmap v2.1 Result-Blind Governance Hardening

Date: 2026-08-01

Engineering Request: `engineering-m4-roadmap-v2-1-result-blind-hardening-20260801`

Engineering execution id: `151`

Baseline merge commit: `2161dc9b4c6700a9ad3c03eaab398e75456cb272`

## Primary goal

Make the merged M4 Measurement Contract v2 physically replayable and safe to
integrate after P2.6.1, while preventing the legacy `PASS_TO_P3` fact from
bypassing full hierarchical coverage.

## Explicit non-goals

- No read of P2.6.1 partial replicate, aggregate, power, bias, coverage, MDE, or
  gate results.
- No stop, restart, manifest import, slot-event publication, or other live
  Supervisor operation.
- No P2.7 execution or P2.6.1 result binding in this Engineering execution.
- No formal P2.9 benchmark while P2.6.1 is running.
- No Temporal or Joint estimator, Expert Router, production candidate,
  strategy mutation, or Promotion Gate action.

## Frozen contracts

| Contract | Digest | Boundary |
| --- | --- | --- |
| `P261MarginalBindingContract.v1` | `dc45c140226a30d30f371f34628c05fa158b7dca86579f33431d2280a2987487` | Allowlisted replay metadata only; synthetic health only; Historical Evidence always `NOT_RUN` |
| Gate replay fixture | `92dddbf3528e61eb5997131c161b1ccb8c4d8bd20974d961d6f19c22b396300e` | Frozen health-only input and exact Gate Compiler output digest |
| M4-P2.9 runtime audit plan | `c34836c3464bafd408c3eef1c87505040a69f79a5323bbb7d803bce9565be674` | Maintenance lane, Engineering authority, single worker, Evidence Progress zero |
| Updated source control-plane manifest | `830cb10a322d033d8091907215f2a2b7396233455353ed9d22bc81e53cb3b08a` | Source definition only; not imported into the live control plane |

## Implemented chain

```text
M4 v2 Design
  -> Design Physical Replay
  -> replay VERIFIED fact
  -> branch identifiability preflight design

P2.6.1 terminal raw execution
  -> Raw Execution Replay
  -> P2.7 Gate Replay
  -> pre-frozen Marginal Binding
  -> Marginal Decision Replay
  -> formal Marginal branch Research contract
```

The Design Replay capability reconstructs the estimand, mechanism-role, Gate
contract, and completion artifacts using the original design execution id and
git commit. It then compares every registered artifact by content and identity,
runs the frozen Gate fixture, and emits immutable
`MeasurementContractV2ReplayArtifact` and `GateCompilerReplayArtifact` objects.

The P2.6.1 binding maps only replayed P2.7 acceptance:

| P2.7 replayed decision | Measurement Health | Historical Evidence |
| --- | --- | --- |
| `PASS_TO_P3` | `PASS` | `NOT_RUN` |
| `REPAIR_MEASUREMENT_SYSTEM` | `REPAIR` | `NOT_RUN` |
| missing, partial, identity drift, wrong parent, replay failure, or unknown decision | `INCONCLUSIVE` | `NOT_RUN` |

## Routing repair

The legacy P3 task no longer depends on
`m4-p2-measurement-decision:PASS_TO_P3`. It requires both the completed M4 v2
Global Routing task and `m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE`.

The routing compiler enforces:

- FULL plus any healthy POSITIVE branch -> `ADAPTIVE_RESEARCH_ELIGIBLE`.
- FULL plus three NEGATIVE branches ->
  `NO_DETECTABLE_INFORMATION_UNDER_FROZEN_M4_V2_CONTRACT`.
- PARTIAL or any INCONCLUSIVE -> `DEEPER_VALIDATION_REQUIRED`.
- REPAIR without a healthy positive branch -> `MEASUREMENT_REPAIR_REQUIRED`.
- Every route keeps `promotion_gate_opened=false`.

Thus a PARTIAL-coverage Gate Compiler output may still describe candidate
information, but it cannot enable Expert Router research.

## Terminal guard and migration boundary

The completion guard uses a dedicated SQL metadata projection that never loads
the event payload containing statistical summaries. It observes only event
identity, task/capability identity, terminal status, manifest identity, and
registered artifact metadata. It does not open the P2.6.1 completion artifact.

Its state machine is:

```text
WAITING
  -> durable unique completed event + registered completion artifact
  -> STOP_REQUIRED
  -> Operator stops resident service
  -> inactive + empty cgroup + no P2.7/P3 started event
  -> SAFE_TO_RELEASE_SLOT
```

FAILED, identity drift, duplicate completion, missing artifact, or a P2.7/P3
dispatch race produces a governance incident and never authorizes the slot
event.

The additive manifest builder starts from the exported live manifest. It
preserves live goals, task lifecycle state, and every fact; adds only allowlisted
M4 v2 definitions/contracts and the verified slot event; and permits the single
allowlisted P3 dependency hardening. It emits a dry-run artifact and performs no
database import itself.

## M4-P2.9

M4-P2.9 has its own active maintenance Goal and an executable Supervisor
capability. The formal task is externally blocked on
`m4-runtime-slot:p2-6-1-released`. It runs the same single replicate through the
reference evaluator and the observed evaluator, requires exact replicate and
child-artifact identities, and separates deterministic plan/equivalence
artifacts from environment-dependent timing observations. Missing `/proc`
metrics are emitted as `UNAVAILABLE`; host iowait is explicitly marked as not
process-attributable.

The optional observer records dataset generation, fold construction,
feature/cache work, four estimator/calibrator fits per fold, prediction/metric,
bootstrap, permutation, and checkpoint persistence without inserting timing
data into the replicate payload.

## Validation

Focused M4 v2 acceptance:

```text
48 passed in 4.87s
```

Complete Worker suite, rerun in an environment permitting multiprocessing:

```text
1936 passed, 4 skipped, 4 warnings in 338.19s
```

The four warnings are pre-existing Python multiprocessing deprecation warnings.
The skips are environment/integration skips already present in the suite.

Acceptance coverage includes:

- content tampering of a registered design child and frozen Gate fixture;
- binding PASS, REPAIR, missing input, partial/prohibited input, old manifest,
  wrong parent, and replay failure;
- FULL-positive, PARTIAL-positive, all-negative, repair, and inconclusive
  routing;
- completed, failed, duplicate/identity, and downstream dispatch race guard
  behavior;
- additive migration with zero existing deletion/regression;
- observer disabled/enabled exact output and explicit `UNAVAILABLE` metrics.

## Integration matrix

| Link | Source status | Live status |
| --- | --- | --- |
| Goal and Task DAG | Implemented | Not imported |
| Resolver and Ready Queue | Source manifest validated | Awaiting terminal-boundary migration |
| Unified Supervisor capabilities | Implemented | Running resident process remains on the accepted pre-change execution |
| Immutable artifacts and registry | Implemented | Not produced for v2.1 tasks |
| Status projection | Implemented | Not projected from live v2.1 execution |
| Downstream consumers | Wired | Not consumed |
| Deterministic replay | Focused tests pass | No physical run-once/replay yet |

Final training-mainline answer:

`NO — INTEGRATION_PENDING`

The next legal action is a separately approved Operator execution that arms the
result-blind completion guard. Only after P2.6.1 reaches its unique durable
terminal boundary may that execution stop the resident service, verify the
empty slot, build/import the additive manifest, and run Design plus Design
Replay explicitly.
