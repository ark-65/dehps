# M4-v2 Three-Branch Global Routing and P3 Activation Barrier

Date: 2026-08-11
Status: **INTEGRATION_PENDING**
Engineering authority: Request 487 / Approval Decision 2042 / Execution 408

## Primary goal

Integrate the frozen M4-v2 Marginal, Temporal and Joint Decision/Replay lineage, the finite Global Router, and a fail-closed predictive-P3 preregistration barrier into the canonical Research OS implementation. This round must stop before any predictive-P3 fold executes.

## Non-goals

- No historical, synthetic, bootstrap, health, fold, branch, Global Router or P3 workload execution.
- No durable manifest import, Supervisor dispatch, Evidence creation, Promotion action or production action.
- No interpretation or replacement of the frozen estimands, estimators, thresholds, Holm rules, failure mapping or route table.
- No use of the predecessor Request 483 / Execution 404 as authority.
- No weakening of mainline completion classification, source-integrity or replay validation to make legacy tests pass.

## Frozen implementation identities

The static base manifest was `f8f6375b04359676d47a5c56c9f0b38874466ecf88d5a92f4c54115e39a2035a` with 83 tasks. The additive output is `93f6a659bbeaa908ce94be4da2bfb5151a75eda09c61051f0d0826447384149a` with 94 tasks.

The durable control plane was not mutated. Its audited preflight identities remain:

- durable manifest: `b3a2ece6f5cde342ba6bb0bfefd8bb64b2aa69b819000ea064066252bdfbdd17`
- durable snapshot: `fd0bb1330890c3cdbd339c821f5727b41a0b857e2857f0cfa018bd3a33ad26d4`
- durable Ready Queue: `[]`

The four exact successor source contracts are:

| Family | Source contract digest |
|---|---|
| Marginal identity adoption | `34a49fd24be7c696636bb584a379776155407b8af2b120adfbffc2edfcea3857` |
| Temporal successor | `eb306e418182c8d2fc39272aa653018a9f5ad6afcbcf0c4825d88f09a8980c37` |
| Joint successor | `f7345320fc87b601cbdae58e2064ff89dc2195c449efcd70d043441067af0a44` |
| Global routing | `6ca7ae72f61ac14be9e29d18c74e1fab8444426b14b37ec137dc1c116a94783c` |

Each contract freezes exactly seven source entries, the 32 completed Research governance digests for Requests 478–482/484–486, the five failed-Request-483 digests, `future_artifact_digests=null`, and `production_action=none`.

## Additive DAG and activation barrier

The migration adds 11 tasks, revises the existing Global Router and predictive-P3 definitions, deletes no task or fact, and regresses no state.

| Task | Runner state in this round | Required next proof |
|---|---|---|
| Marginal identity adoption | implementation present; not dispatched | registered terminal Decision |
| Marginal Decision replay | implementation present; not dispatched | registered replay and exact VERIFIED fact |
| Temporal design | implementation present; not dispatched | registered design and FROZEN fact |
| Temporal preregistration | implementation present; not dispatched | registered preregistration and FROZEN fact |
| Temporal producer | parent-stop path implemented; accepted-parent scientific work remains fail-closed | registered terminal Decision and Completion |
| Temporal replay | implementation present; not dispatched | registered replay and exact VERIFIED fact |
| Joint design | implementation present; not dispatched | registered design and FROZEN fact |
| Joint preregistration | implementation present; not dispatched | registered preregistration and FROZEN fact |
| Joint producer | parent-stop path implemented; accepted-parent scientific work remains fail-closed | registered terminal Decision and Completion |
| Joint replay | implementation present; not dispatched | registered replay and exact VERIFIED fact |
| Global routing | finite categorical compiler and zero-write replay implemented; not dispatched | three exact branch replay facts, route artifact and replay proof |
| P3 preregistration placeholder | `requested_capability=null`, `runner=null`, `execution_authorized=false` | separate approved Research preregistration contract |
| Predictive P3 | `dependency_wait`; folds executed by this round = 0 | Global task completed + ADAPTIVE fact + prereg task completed + prereg FROZEN fact |

The predictive-P3 dependency set is an exact four-way AND. Even an `ADAPTIVE_RESEARCH_ELIGIBLE` route cannot make P3 Ready while the null-capability preregistration placeholder and missing FROZEN fact remain.

This four-way AND is only the current inert placeholder barrier. It is **not** the final activation contract required by the parent goal. A later result-blind P3 preregistration round must additionally bind the exact historical dataset snapshot, source-integrity manifest, seed manifest and independent Operator execution approval before any implementation may project predictive P3 as Ready.

## Atomicity and replay boundaries

- Each approved producer path stages content-addressed files, fsyncs them, publishes with no-replace inode ownership, then commits registrations, completion event, facts, task state and manifest head in one database transaction.
- Commit-ack ambiguity is reconciled read-only. Unknown or cleanup-incomplete outcomes become a governance incident and never fall through to a compensating failed-event write.
- Registered-missing-file, partial registration, mismatched canonical file and digest drift remain fail-closed.
- Global replay reads registered bytes and lineage only, returns `REPLAY_VERIFIED` / `REGISTERED_REPLAY_VERIFIED`, sets `workload_rerun=false`, and performs no durable state write.

## Validation

| Validation | Result |
|---|---|
| Ruff on all touched Python implementation/builders | PASS |
| `py_compile` on implementation/builders/test | PASS |
| Four source-contract self-seals and governance metadata verification | PASS |
| Additive build 83 → 94; zero deletion/regression | PASS |
| Repeated four-builder build | PASS, byte-identical manifest |
| Focused 45-item acceptance module | **20 passed** |
| Existing six-module focused regression bundle | **54 passed, 2 failed** |
| Full Worker suite | **2399 passed, 4 skipped, 55 failed** |
| Detached base `15760f143…` Worker suite | **2426 passed, 4 skipped, 8 failed** after correcting the detached-worktree import path |

The two directly relevant legacy failures are deliberately unresolved in this authority boundary:

1. The immutable predictive-route source contract still hashes shared files (`models.py`, `migration.py`, `supervisor.py`, `progress.py`) that Request 487 explicitly changes. Updating or superseding that old contract is not among the 21 authorized paths.
2. A legacy test mutates the now-executable Global task to `completed` without setting the mandatory `completion_classification=COMPLETE`. Weakening the mainline validator would violate the permanent integration rule; updating that test is outside the authorized focused-test path.

The 55 failures are now classified result-blind against the detached base:

- 44 are environment/clock isolation failures: 36 tests observe the shared `runtime/prediction-v2/legacy-retirement-activation.json`, while eight also fail on the unchanged base during the live 21:15–21:45 Asia/Shanghai draw-defer window. All 44 pass when the activation path and clock are explicitly isolated; no corresponding production file differs from base.
- nine are historical fixture/count assertions that derive old recovery manifests from the mutable canonical manifest and do not subtract the 11 additive successor tasks/facts (plus one source-partition count update and one old two-edge P3 fixture).
- one is the immutable predictive-route v1 source-contract drift described above.
- one is the incomplete executable-Global completion fixture described above.

Thus no production scientific bug was demonstrated by this failure set, but 11 compatibility/governance tests remain genuine PR blockers after environment isolation. All affected legacy test/contract/consumer paths are outside Request 487 and require a separate typed authorization; this round does not claim full-suite acceptance.

## Accepted-parent workload blocker

The current Temporal and Joint implementations are identity/schema complete for the zero-compute `PARENT_NOT_ACCEPTED` path, but they do **not** implement the accepted-parent scientific workload. Both Supervisor producer paths call only the parent-stop builder; an accepted parent therefore fails closed instead of running the frozen health, historical and gate pipeline.

The missing execution surface includes the legal-carrier and parameter solvers, branch-specific 14×512 synthetic health workloads, deterministic bootstrap/resampling, the 3481-row dataset and 2581-fold historical engines, checkpoint/resume inputs and the qT→qbase→z→eta→QJ runner. The approved seven-entry source closures expose no existing numerical workload module to these capabilities, and the Supervisor API supplies no dataset, fixture, seed-grid, fold or checkpoint input. Implementing an unreviewed substitute in one monolithic file, importing a hidden existing runner, or accepting precomputed artifacts would each violate the frozen source/identity contract.

One Temporal nested field also remains insufficiently typed for byte-unique execution: `sensitivity_summary.effect_interval_bits_per_issue` is named but has no exact JSON/nested schema. Engineering must not choose that representation.

Consequently, the static DAG must not be imported or dispatched as though all 11 capabilities were operational. This checkpoint proves the parent-stop and activation-barrier behavior only; paths with accepted Marginal or Temporal parents remain a separate fail-closed integration blocker.

## Decision and next legal action

The implementation is result-blind and the P3 barrier is correctly closed, but publication and Operator execution must not proceed. Two independent, narrowly scoped governance repairs are required before a publishable Engineering round:

1. freeze the accepted-parent Temporal/Joint execution surface, source-closure expansion or approved in-closure runner, exact remaining nested types and Supervisor workload inputs; and
2. freeze additive historical source-contract compatibility plus the legacy completion-classification/test-fixture reconciliation, without overwriting the immutable v1 digest.

After both are implemented, the focused module, required regression bundle and complete Worker suite must be green before PR-head and merged-main CI. Only then may a separate Operator Request authorize exact additive import. That Operator must follow the resolver one unique Ready task at a time and stop at the approved branch/global/P3-preregistration boundary; it must not batch-dispatch all 11 tasks. P3 execution remains outside that boundary.

## Mainline integration answer

**NO — INTEGRATION_PENDING**

The code, static manifest and focused acceptance are present, but no durable import, unified Supervisor execution, immutable mainline registration, status completion or deterministic registered replay has occurred for these successor tasks.
