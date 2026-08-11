# M4-P3 Predictive Route Reconciliation and P2R-to-P6 Policy

Date: 2026-08-11
Round: 139
Finalization round: 140
Role: Engineering Agent
Engineering Request / Execution: 474 / 395
Final-report Engineering Request / Execution: 476 / 397
Final-report approval Decision: 1987
Status: `COMPLETE`

## Primary goal

Integrate the result-blind decisions `DAG_REPAIR_REQUIRED` and
`RESEARCH_ALLOWED_PROMOTION_BLOCKED` as a singular zero-compute Research OS
governance path. The round repairs only predictive-P3, P4, and P6 dependency
definitions and the unified status projection. It neither executes nor changes
the predictive scientific contract.

## Explicit non-goals

- No P2 reopen, rerun, threshold change, or `REPAIR` to `PASS` mapping.
- No P2R execution or validation-sample generation.
- No structural-P3 reopen, reinterpretation, gate change, or rerun.
- No predictive-P3 successor, global-routing execution, predictive execution,
  history load, fold, bootstrap, candidate, Evidence, Promotion, betting output,
  or production strategy action.
- No relabelling of `MARGINAL_STATIC` as `MARGINAL_HISTORICAL` and no synthesis
  of missing replay or adaptive-eligibility facts.

## Frozen starting identities

| Identity | Frozen value |
| --- | --- |
| Inspected `main` | `f58f46829f0dede149bc5f116e0fd660768d3a82` |
| Pre-round static manifest | `f3f263d3ef9c5028223070b7fc228c2ef95ffc315a86479d17ebccb0a87b890b` |
| Audited durable manifest | `0194d06a18cfbf51394af87aaf03149a440fc1f39f608e0acbe8fd0df75ca763` |
| Audited durable snapshot | `e7466e5b8752630c21c808b8dc2e7b27d197fd9a80d023ca001762b83b9be591` |
| Route source contract | `911fa45a1276ecc0502ad569760ceffbf2257dfaca42f8ec8bf1f4249af666ea` |
| Source-set digest | `d165970cfd364ccb5dc234e7644217be3efe0bdc9e2cfa14e91b39867465a771` |
| Repaired static manifest | `f8f6375b04359676d47a5c56c9f0b38874466ecf88d5a92f4c54115e39a2035a` |
| Additive migration dry run | `d285e0bf4206cfc9752121269568aab7e98e26f709ae08620c47ad645ba0cbf0` |
| Dry-run merged durable manifest | `f906975a91e22b01b5335e6d4f74f4cdf73fd48e8ace12d7044a3972c0e1dd54` |

At dry-run creation this identity was not yet an import record; Operator 475
later imported the exact same manifest identity. The dry-run artifact was
produced in memory from the audited live manifest and the additive builder;
`import_performed=false`.

## Superseded-goal audit

The prior “Repair-Outcome Successor Path” produced no attributable local or
durable work. Exact classification is `A=∅`, `B=∅`, `C=∅`, `D=∅`:

- no local changes, branches, commits, request/execution records, task rows,
  artifacts, runtime directories, or PRs;
- no predictive result read or computation;
- merged PRs 336 and 337 are pre-existing P2-closure context, not successor
  output.

`RESULT_BLINDNESS_POTENTIALLY_BREACHED=false`.

## Result-blind reconciliation

The static and durable definitions disagree for the same predictive task key:

| Surface | `m4-p3-strict-historical-walk-forward` dependencies |
| --- | --- |
| Audited durable DAG | completed P2 closure + absent legacy `m4-p2-measurement-decision:PASS_TO_P3` |
| Canonical source | completed `m4-v2-global-routing` + available `m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE` |

This is proven task-definition drift, not merely delayed resolution. The global
router is `draft / dependency_wait / INTEGRATION_PENDING`; its required
`MARGINAL_HISTORICAL`, `TEMPORAL_MARGINAL_INCREMENT`, and
`JOINT_RESIDUAL_INCREMENT` replay facts and producer tasks are absent. The only
distinct branch fact is `MARGINAL_STATIC:VERIFIED`. The adaptive eligibility
fact is absent, so the repaired predictive P3 remains `dependency_wait`.

The predictive primary endpoint remains
`out_of_sample_log_loss_improvement`. A future equal-budget 100-ticket,
blue-ball, paired-random comparison is a separately preregistered secondary or
downstream decision-support contract; it is not the same primary endpoint.

## Frozen Research and Reviewer decisions

| Contract | Request / execution | Reviewer decision | Frozen selection |
| --- | --- | --- | --- |
| Predictive route reconciliation | 472 / 393 | 1969 | `DAG_REPAIR_REQUIRED` |
| P2R-to-P6 dependency policy | 473 / 394 | 1970 | `RESEARCH_ALLOWED_PROMOTION_BLOCKED` |
| Engineering integration | 474 / 395 | 1977 | exact additive implementation scope |

All three authorization lines are bound through immutable request metadata,
metadata-only execution identities, exact-one execution cardinality, strict
artifact-path list typing, and full append-only Reviewer Decision digests. The
runtime metadata query excludes `result_json` and `error_json`. Engineering
Execution 395 completed at `2026-08-11T11:38:06.854949+08:00`, bound to
implementation commit `31d7de2f0652578661f228c17fc3b11f44f9bcbb`; its
metadata-only authorization replay validated all 12 declared artifact paths.

## Additive implementation

The canonical source adds one task:

`m4-p3-predictive-route-reconciliation`

It emits exactly:

1. `M4P3PredictiveRouteReconciliationArtifact`;
2. `P2RToP6DependencyPolicyArtifact`;
3. `PredictiveP3RouteDecisionArtifact`;
4. the mandatory canonical mainline execution record.

Only these existing task definitions are revised:

- predictive P3: canonical global-router plus adaptive-fact dependencies;
- P4: predictive-P3 completion plus explicit
  `m4-p3-predictive-decision:PASS_TO_P4`;
- P6: immutable policy fact, research-summary allowance, and fail-closed
  production Promotion behavior.

P2R is not a P3/P4/P5 research dependency and is not a P6 research-summary
hard task dependency. Until independently accepted, it blocks production
Promotion; Prediction v2 remains `SHADOW_ONLY / BASELINE_ONLY`.

The additive dry run reports one new task, three allowlisted revisions, zero
goal/task/fact deletions, zero state regressions, and zero unallowlisted
definition rewrites. Its simulated Ready Queue is exactly the governance task.
The builder binds the audited durable manifest, resolved snapshot, legacy P3
dependency identity, and a seven-file source closure. No durable import was
performed in this Engineering round.

## Mainline publication and Operator execution

Implementation PR 338 passed PR-head CI run 31456048689 at
`19f80af5fb455696f3f90f9024471f3a829f4b4c`, was squash-merged to `main` as
`c5cd28529ca22bec40d75beb7b867359ffa44820`, and passed merged-main CI run
31456545451.

Operator Request 475 was approved by Reviewer Decision 1982 and has exactly one
Operator Execution, 396. The production operation imported the approved
additive manifest, dispatched only
`m4-p3-predictive-route-reconciliation` exactly once, observed the run-once
Supervisor exit, and performed one read-only deterministic replay. The durable
manifest progression is:

1. imported: `f906975a91e22b01b5335e6d4f74f4cdf73fd48e8ace12d7044a3972c0e1dd54`;
2. running: `330481307055ca9494f302b6e81c245f7146675f2a5ffca73a80fd0f9f8f273f`;
3. completed/current: `b3a2ece6f5cde342ba6bb0bfefd8bb64b2aa69b819000ea064066252bdfbdd17`.

The completed/current snapshot is
`fd0bb1330890c3cdbd339c821f5727b41a0b857e2857f0cfa018bd3a33ad26d4`.
Ready Queue transitioned from `[]`, to exactly
`[m4-p3-predictive-route-reconciliation]` after import, and back to `[]` after
the one governance execution.

The completed route task definition digest is
`2707c36fdc59a79b1306c42fbb3b379ddc22a36ae5df2335b1b94f317fd6e8b0`.
Its mainline execution identity is
`7fd32a2d3cf9224cdb42c772ea83073f14bdc98b4b0bd062cb1e819c0d639446`.
It registered exactly four canonical artifacts:

| Registration | Digest | Canonical path |
| --- | --- | --- |
| `M4P3PredictiveRouteReconciliationArtifact` | `9475ed5f778a7fef4b75a38399393e4b29d1e67b5cc9598f7890f4c0860ba61a` | `runtime/research-os/mainline/tasks/m4-p3-predictive-route-reconciliation/7fd32a2d3cf9224cdb42c772ea83073f14bdc98b4b0bd062cb1e819c0d639446/artifacts/route-reconciliation/9475ed5f778a7fef4b75a38399393e4b29d1e67b5cc9598f7890f4c0860ba61a/reconciliation.json` |
| `P2RToP6DependencyPolicyArtifact` | `e960de14aa46b4752353aae27c1a59426dbcc70bf61d03852715a843b79a23dd` | `runtime/research-os/mainline/tasks/m4-p3-predictive-route-reconciliation/7fd32a2d3cf9224cdb42c772ea83073f14bdc98b4b0bd062cb1e819c0d639446/artifacts/p2r-to-p6-policy/e960de14aa46b4752353aae27c1a59426dbcc70bf61d03852715a843b79a23dd/policy.json` |
| `PredictiveP3RouteDecisionArtifact` | `fae350dde93441f207ecd0652563c23f4827aeba0f4895af0629a7a3e8c03b0b` | `runtime/research-os/mainline/tasks/m4-p3-predictive-route-reconciliation/7fd32a2d3cf9224cdb42c772ea83073f14bdc98b4b0bd062cb1e819c0d639446/artifacts/predictive-route-decision/fae350dde93441f207ecd0652563c23f4827aeba0f4895af0629a7a3e8c03b0b/decision.json` |
| Canonical mainline execution record | `7808bb91f545d38d929399305bf6986f6c6bc9196b1f8e5e519c0540c8d1700e` | `runtime/research-os/mainline/tasks/m4-p3-predictive-route-reconciliation/7fd32a2d3cf9224cdb42c772ea83073f14bdc98b4b0bd062cb1e819c0d639446/execution.json` |

The replay result is `REPLAY_VERIFIED`; the capability replay result is
`REGISTERED_REPLAY_VERIFIED`. Execution identity, artifact identity, registered
content, and all four registration identities matched.
The independent result-blind durable audit is `PASS` and matched the route task,
execution, manifest, snapshot, and four artifact digests above. Result and predictive
payload reads, historical-database reads, computation, new folds, Evidence
creation, Promotion, and production action all remained zero or not triggered.

The persisted downstream waits are exact and remain fail-closed:

| Task | State | Missing dependencies |
| --- | --- | --- |
| `m4-v2-global-routing` | `dependency_wait` | `m4-v2-branch-decision-replay:MARGINAL_HISTORICAL:VERIFIED`; `m4-v2-branch-decision-replay:TEMPORAL_MARGINAL_INCREMENT:VERIFIED`; `m4-v2-branch-decision-replay:JOINT_RESIDUAL_INCREMENT:VERIFIED` |
| `m4-p3-strict-historical-walk-forward` | `dependency_wait` | completed `m4-v2-global-routing`; `m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE` |
| `m4-p4-negative-controls-and-robustness` | `dependency_wait` | completed `m4-p3-strict-historical-walk-forward`; `m4-p3-predictive-decision:PASS_TO_P4` |
| `m4-p5-forward-evidence` | `dependency_wait` | completed `m4-p4-negative-controls-and-robustness`; completed `m4-forward-evidence-intake-2026085` |
| `m4-p6-information-bound-and-decision` | `dependency_wait` | completed predictive P3, P4, and P5; the immutable P2R policy fact is satisfied and P2R is not a hard task dependency |
| `m4-p2r-measurement-repair-validation` | `external_wait` | `research-contract:m4-p2r-measurement-repair-validation-execution:approved` |

## Integration matrix

| Mainline link | Current proof | Status |
| --- | --- | --- |
| Goal | Existing `M4_INFORMATION_THEORY_EVIDENCE` | PASS |
| Resolver | Imported manifest resolved exactly the governance task; completed manifest resolves the persisted downstream waits | PASS |
| Ready Queue | Exactly the governance task after import; exactly `[]` after completion | PASS |
| Supervisor | Exactly one explicit governance-task dispatch; run-once process stopped | PASS |
| Capability | Executed once and produced the three zero-compute domain artifacts | PASS |
| Artifacts | Exactly four canonical registrations with independent digest verification | PASS |
| Status | Unified projection reports `COMPLETE`, route, policy, replay, and exact waits | PASS |
| Next task | Global routing and predictive P3 remain fail-closed on their exact fact dependencies | PASS |
| Deterministic replay | `REPLAY_VERIFIED` and `REGISTERED_REPLAY_VERIFIED` with the same execution and registration identities | PASS |
| Durable import and execution | Operator Request 475 / Decision 1982 / exact-one Execution 396 | PASS |

## Validation

- Focused route/policy suite:
  `20 passed in 5.36s`.
- Focused plus historical-recovery compatibility surface:
  `106 passed in 8.84s`.
- Complete worker suite in an isolated source-only worktree:
  `2434 passed, 4 skipped, 26 warnings in 298.80s`.
- Canonical source loader, seven byte hashes, source-set digest, manifest model
  digest, artifact-index pointers, builder idempotence, and repeated real
  metadata-only dry runs: PASS. Repeated dry runs were byte-identical and kept
  `import_performed=false` with all deletion/regression/rewrite counters zero.
- An earlier run in the operational worktree reported
  `49 failed, 2379 passed, 4 skipped`: 42 nodes were reproduced on untouched
  `origin/main` under the already-active legacy-prediction retirement marker;
  the other seven were historical-fixture/count compatibility failures caused
  by the additive task and were fixed. The final isolated full suite above
  excludes that runtime marker and hides no source regression.
- PR 338 head CI run 31456048689, squash merge
  `c5cd28529ca22bec40d75beb7b867359ffa44820`, and merged-main CI run
  31456545451: PASS.
- Operator Request 475 / Decision 1982 / exact-one Execution 396, additive
  import, exactly one governance dispatch, stopped Supervisor, and one read-only
  replay: PASS.
- Independent result-blind durable audit of the completed manifest, current
  snapshot, route task/execution, and four canonical registrations: PASS.

## Required status block

```text
M4-P2:
COMPLETE_WITH_REPAIR_OUTCOME

P2 DECISION:
REPAIR_MEASUREMENT_SYSTEM

P2R:
PENDING_VALIDATION / NOT_EXECUTED

STRUCTURAL P3:
NO_STABLE_STRUCTURAL_UTILITY / TERMINAL

PREDICTIVE P3 ROUTE:
DAG_REPAIR_REQUIRED

P2R-TO-P6 POLICY:
RESEARCH_ALLOWED_PROMOTION_BLOCKED

PREDICTIVE RESULT READS:
0

HISTORICAL DATABASE READS:
0

COMPUTATION:
0

NEW HISTORICAL FOLDS:
0

EVIDENCE CREATED:
NO

PROMOTION:
NOT_TRIGGERED

PRODUCTION ACTION:
none

READY QUEUE:
[]

GLOBAL ROUTING WAIT:
m4-v2-branch-decision-replay:MARGINAL_HISTORICAL:VERIFIED
m4-v2-branch-decision-replay:TEMPORAL_MARGINAL_INCREMENT:VERIFIED
m4-v2-branch-decision-replay:JOINT_RESIDUAL_INCREMENT:VERIFIED

PREDICTIVE P3 SUBSEQUENT WAIT:
m4-v2-global-routing:COMPLETED
m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE

NEXT LEGAL TASK:
m4-v2-global-routing after its three VERIFIED replay facts;
predictive P3 then additionally awaits ADAPTIVE_RESEARCH_ELIGIBLE

MAINLINE INTEGRATION:
YES — validated by unified mainline execution and replay
```
