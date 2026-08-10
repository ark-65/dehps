# M4-P2 repair-outcome closure — Round 136

Date: 2026-08-10

Current role: Engineering Agent

Authorization chain:

- Research Request 468 / Execution 389:
  `research-m4-p2-closure-p2r-preregistration-round-136-20260810`
- Engineering Request 469 / Execution 390:
  `engineering-m4-p2-closure-p2r-integration-round-136-20260810`
- Operator Request 470 / Execution 391:
  `operator-m4-p2-repair-closure-mainline-round-137-20260810`
- Final report Engineering Request 471 / Execution 392:
  `engineering-m4-p2-closure-final-report-round-138-20260810`

## Primary goal

Close the completed legal M4-P2 measurement-validation flow under its immutable
automatic decision `REPAIR_MEASUREMENT_SYSTEM`, without rerunning measurement
work or changing the frozen outcome. The terminal P2 status is
`COMPLETE_WITH_REPAIR_OUTCOME`.

The unresolved measurement-repair question is moved to the independent task
`m4-p2r-measurement-repair-validation`, whose current status is
`PENDING_VALIDATION`. P2R is not a dependency of the already-active M4-P3
result-blind work.

## Non-goals and hard boundaries

- no P2 or P2R validation execution, sample generation, or long compute;
- no historical prediction, result, draw-fold, or statistical payload reads;
- no threshold, decision policy, fixture, seed, or frozen artifact change;
- no use of failed P2 samples for P2R tuning;
- no Evidence creation, evidence-progress increment, promotion, betting claim,
  or production action;
- no reinterpretation of `REPAIR_MEASUREMENT_SYSTEM` as predictive evidence.

## Immutable outcome compiled by the closure

The closure consumes only registered control-plane metadata, the completed
Research contract, and the exact registered P2.7 gate and replay identities:

| Item | Frozen identity or state |
|---|---|
| P2 decision policy | `824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d` |
| P2.6 validation manifest | `a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58` |
| P2.6.1 task / fixture | `80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa` / `f9716c799e1e55e58585c7e9acf0730f9d05111ab6e375cfb9bea85ecbdeacc5` |
| P2.6.1 preserved status | `FROZEN_INCOMPLETE` |
| P2.6.3 task / fixture | `85a08402a4a0c37f75ee1675f4970ef00a7a0b0992b4204251c0c2cc79324de4` / `53f9a4b7d92944dfd6a46d317b018bdc6b434fc69bb977d72ae6d1f177e0c73b` |
| P2.6.3 update policy | `ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99` |
| P2.6.3 preserved status | `SUPERSEDING_COMPLETE` |
| P2.7 execution / artifact | `d0e313e2672fae3ae2d8c096d2b24ba399687e01e7654f004767866e0dfa798d` / `be3507e895dcb7f3790db22553b0d6d262d5f8cd33cb769af8e167b34ed13576` |
| P2.7 automatic gate | `4b8a881c2d093d608d3e9c23e184034628f1440c9c0a08f868aea1028e78e3f8` |
| P2.7 registered replay | `69394a8405ad7b08b147eb20f9cf198581d9a186cb4b478d50805788af7dbbb0` |
| P2.7 replay execution | `a7a26dc61d7d2ead4cf38fc8d36142b95c3ec5a5125d18838777f7e2fb4bc2bf` |
| Closure source contract | `1f1b59c71345dc9d7de8bc7e0c4472c2759e99442f7c539373ec41ae78066929` |
| Static control-plane manifest | `f3f263d3ef9c5028223070b7fc228c2ef95ffc315a86479d17ebccb0a87b890b` |

The gate failed four frozen requirement families:

- all practical-strength cell power gates pass;
- all strong-signal cell power gates pass;
- all primary PE2 absolute-bias cell gates pass;
- all primary PE2 coverage cell gates pass.

This is why P2 can be operationally complete while its valid terminal outcome
is repair rather than pass. The closure does not erase these failures and does
not claim that the measurement system is repaired.

## Independent P2R preregistration

Research Request 468 freezes a separate validation identity before any future
P2R execution:

- seed domain:
  `DEHPS|M4-P2R|measurement-repair-validation|v1|2026-08-10`;
- seed root SHA-256:
  `f486ec216030aeb1de38b68ebeac9543ab061b934bbfbed34b6cdc0367157016`;
- unsigned 64-bit seed: `17620030220225523377`;
- failed P2 samples available for tuning: false;
- execution authorized: false;
- current status: `PENDING_VALIDATION`;
- M4-P3 dependency: false.

The Einstein-style review made the boundary explicit: the repair hypothesis
must be tested as a fresh falsifiable claim, against the same frozen null and
failure obligations, using independent seed material. A plausible diagnosis
is not accepted as a repair result.

## Implementation

- The existing umbrella task `m4-p2-synthetic-measurement-validation` becomes
  the canonical zero-work repair-outcome closure task.
- The dependency resolver requires completed P2.7 gate and replay tasks, their
  exact immutable facts, and the completed closure Research contract.
- The unified Research Evidence Supervisor verifies source bytes, Research
  authorization, registered artifact identities, decision mapping, and replay
  identity before producing one immutable closure artifact and one mainline
  execution record.
- The status projection exposes P2 closure, P2R, and M4-P3 independently. Before
  closure execution, P2 remains integration-pending; after replay-verified
  closure, the active phase can remain M4-P3 while P2R waits externally.
- Deterministic replay rebuilds the closure from the same immutable parents and
  requires byte-equivalent structured identity.

The capability reports zero formal replicates, generated samples, historical
database reads, statistical result reads, artifact mutations, Evidence, and
promotion actions.

## Validation before merge

```text
ruff check (all touched Python files)
All checks passed

focused closure/control-plane/Supervisor/historical-fixture suite
134 passed in 42.83s

complete Worker suite
2372 passed, 4 skipped, 42 failed in 299.39s

git diff --check
passed
```

The 42 complete-suite failures are confined to the project's intentionally
retired legacy prediction, training, draw-sync, and mail entrypoints, matching
the established post-retirement baseline. The retirement guard was not bypassed
and no legacy test was weakened for this round.

The focused suite covers pure deterministic closure and replay, immutable input
protection, gate/replay drift rejection, additive source and live migration,
P2/P2R/P3 status projection, Supervisor registration, forbidden read-method
absence, and an isolated canonical capability execution with zero measurement
work and zero Evidence.

A final read-only live migration dry run observed 81 existing tasks and
projected 82, with no goal, task, or fact deletion, no state regression, and no
unallowlisted rewrite. Its report digest is
`6af8ffaac76b019a41754597c199723f6364d15bf9e05bd9198f3ce348724829`
and projected live manifest digest is
`4b7e9d7a00a87ef2fd3cf334bc9482a25fcebb942e7b8ad66acb2fa63ed77ef0`.
At the pre-merge boundary, the resolver projected the closure as the singular
ready task, P2R as external-wait, current P2 closure status as
`INTEGRATION_PENDING`, and M4-P3 as `ACTIVE`. Existing M4-P3 task definitions
were preserved. This dry run itself performed no import or execution.

## Pre-merge integration matrix

| Link | Pre-merge state |
|---|---|
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | exact gate, replay, decision, source, and Research-contract dependencies implemented |
| Ready Queue | additive migration projects closure ready and P2R external-wait |
| Supervisor | zero-work capability registered and isolated execution tested |
| Capability | repair-outcome compiler implemented; no measurement compute path |
| Artifacts | immutable closure and mainline execution registrations implemented |
| Status | P2/P2R/P3 independent projection implemented |
| Next Task | P2R pending separate authorization; M4-P3 remains nonblocking |
| Replay | deterministic local replay tested; merged canonical replay pending |

Pre-merge integration answer: **NO — INTEGRATION_PENDING**.

The answer remains NO until the accepted commit is merged, a separately
approved Operator execution imports the exact additive manifest, a fresh
merged-commit unified Supervisor executes the zero-work closure, immutable
artifacts register, and canonical replay proves the same identity. P2R remains
unexecuted throughout this closure round.

## Merged canonical execution and replay

PR 336 merged as commit
`546aaea4b0b0fe2dd444c6c6d05e1cd8367fa7c1`. Pull-request CI run
`31374642146` and merged-main CI run `31374734851` both completed successfully.

After approval of Operator Request 470, Execution 391 imported only the exact
additive manifest
`4b7e9d7a00a87ef2fd3cf334bc9482a25fcebb942e7b8ad66acb2fa63ed77ef0`.
The import preserved all 81 prior tasks and their state, added only P2R, revised
only the unstarted P2 umbrella, and resolved exactly the closure task as Ready.

A fresh merged-commit Research Evidence Supervisor process then completed the
singular closure task:

| Durable record | Identity |
|---|---|
| Task digest | `e322b4f9ec64525251a3800e3a56406de71cb9991e5f10ef6e3c69fa7a56ecc2` |
| Execution ID | `d02197201f082d654bca9d1e50923472c3fa4104edea8b149771f6c953c2addb` |
| Closure artifact | `fabf299721c73bfdfe1a0d6411398b3980564764ba3b48066f0d74276a7e060c` |
| Closure registration | `0b9cd41bacb27214f4dd956b645d1066bd546adb60f444375136c9bcdf388ff3` |
| Mainline execution artifact | `c83cb29bd1fc8f6ef3c0833f37c053c259c6fac53d8d11200fe92d025adfa9d0` |
| Execution registration | `b6b6267728e2b1ac37eb4d678cf5b909b5abbdc2214f9adab7041672579366c0` |
| Completed durable manifest | `0194d06a18cfbf51394af87aaf03149a440fc1f39f608e0acbe8fd0df75ca763` |

The execution is `VALIDATED_IN_MAINLINE`; deterministic replay returned
`REPLAY_VERIFIED`, `same_execution_identity: true`,
`same_artifact_identity: true`, and `manual_input_assembly: false` for the same
execution and both registrations.

The registered closure and execution record all of the following as zero:
formal replicates, generated samples, actual folds, historical database reads,
historical prediction reads, historical result reads, historical fold reads,
statistical result-payload reads, artifact mutations, and Evidence increment.
Evidence remained 25 before and after; no promotion gate opened and production
action remained `none`.

The durable status projection now reports:

- P2: `COMPLETE_WITH_REPAIR_OUTCOME`;
- final decision: `REPAIR_MEASUREMENT_SYSTEM`;
- P2.6.1: `FROZEN_INCOMPLETE`;
- P2.6.3: `SUPERSEDING_COMPLETE`;
- P2R: `PENDING_VALIDATION`, `external_wait`, execution not authorized;
- M4-P3: `ACTIVE`, not blocked by P2R;
- current phase: `M4-P3`;
- Ready Queue after closure: empty.

P2R was not dispatched, and no P2 measurement or historical-result workload
ran during import, execution, replay, or final status projection.

## Final mainline integration matrix

| Link | Durable proof |
|---|---|
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` retained in imported and completed manifests |
| Resolver | exact immutable gate, replay, decision, source and Research-contract dependencies resolved |
| Ready Queue | closure was the singular Ready task before dispatch; no Ready task remains afterward |
| Supervisor | fresh merged commit `546aaea` dispatched exactly one supported task |
| Capability | zero-work repair-outcome compiler completed with every workload/read counter zero |
| Artifacts | closure `fabf299…` and execution `c83cb2…` registered immutably |
| Status | P2 complete with repair; P2R pending; M4-P3 active and nonblocking |
| Next Task | P2R remains external-wait behind a separate unobserved approval event |
| Replay | `REPLAY_VERIFIED` with identical execution and artifact identities |

Final integration answer:
**YES — validated by unified mainline execution and replay**.
