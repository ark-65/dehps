# M4-P4 Formal P4 V3 armed implementation

Date: 2026-08-22
Role: Engineering Agent
Engineering Request: `648`
Engineering Execution: `527`
Reviewer Decision: `2724`

## Goal

Implement and deploy the frozen successor Formal P4 V3 capability without
modifying the active P3 lineage and without executing real Formal P4, P5, or
Promotion. In the absence of the durable successor `PASS_TO_P4`, the canonical
P4 execution task must remain `ARMED_DEPENDENCY_WAIT`.

## Frozen contract

- Research Request: `646`
- Reviewer Decision: `2718`
- Contract key: `M4_P4_FORWARD_PREQUENTIAL_FORMAL_NEGATIVE_CONTROLS_V3`
- Contract digest: `8bcc651713e7356c5488727b786f987d01f08ea486a1df75d20de27ef339b3ac`
- Freeze fact: `m4-p4-forward-prequential-formal-contract-v3:FROZEN`
- P3 source digest: `139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493`

The implementation preserves the six frozen controls, two disjoint Holm
families, deterministic NC3/NC4 behavior, whole-issue folds, leakage gates,
three-decision compiler, typed replay, and successor-only P5 route. The
historical diagnostic P4 has zero decision credit.

## Engineering scope

The change is additive and confined to the eight paths authorized by Request
648. It adds one content-addressed source contract, a Formal P4 V3 capability,
an additive manifest builder, an exact-key runner, focused tests, two systemd
units, and this report. No P3 source entry, base Supervisor, Repository,
estimator, feature, threshold, look, candidate, baseline, blue strategy, or
runtime profile changes.

The runner can call `run_once` only with one of these exact keys:

1. `m4-p4-forward-prequential-confirmatory-negative-controls`
2. `m4-p4-forward-prequential-formal-evidence-v3`
3. `m4-p4-forward-prequential-formal-decision-v3`
4. `m4-p4-forward-prequential-formal-decision-replay-v3`

It never performs unkeyed, P3, or P5 dispatch.

## DAG and routing

- Canonical P4 execution waits on exactly V3 freeze, P3 `COMPLETE`, and P3
  `PASS_TO_P4`.
- Evidence V3 waits on P4 execution completion.
- Decision V3 waits on Evidence V3.
- Typed replay V3 waits on Decision V3.
- `m4-p5-forward-evidence-successor-after-formal-p4-v1` waits on P4 completion,
  exact V3 `PASS_TO_P5`, and exact V3 typed replay.
- Legacy `m4-p5-forward-evidence` is unchanged.

The result-blind activation fixture is in-memory only. It proves a valid
synthetic P3 `COMPLETE + PASS_TO_P4` state makes exactly the canonical P4
execution task Ready and resolves its unique capability. It neither persists a
fact nor dispatches Formal P4. Removing the fixture restores
`ARMED_DEPENDENCY_WAIT`.

## Validation

Local validation before the merge handoff passed:

- focused Formal P4: `14 passed`;
- P3 plus control-plane compatibility: `16 passed`;
- mainline Supervisor, Repository, and immutability: `138 passed, 5 skipped`;
- measurement-system compatibility: `19 passed`;
- Ruff and Python compilation: passed;
- source artifact: `9ccb282c258ed35d8b0f5d246a20d3f63b8e616660d1c2bdae40f24d55a99f11`;
- source-set: `bf135aac0ce2b48981c06a863c5dfdee1982fd575cd42776defeb38f212cb907`;
- all five Formal P4 executable source entries and all seven protected P3
  source entries: exact SHA-256 and byte count matched;
- live additive manifest definition dry-run and result-blind activation fixture:
  verified with no import, no dispatch, and production restoration;
- exact eight-file scope: verified.

The replay task persists no outcome fact. The runner first verifies the generic
registered replay, then reloads the registered typed replay and complete parent
chain, and only then atomically publishes the replay/outcome facts. A focused
crash-resume fixture proves a timer restart completes this post-replay
activation without rerunning the workload; a generic-replay failure fixture
proves it publishes no PASS or replay fact.

## Integration matrix

| Stage | Binding | Validation state |
| --- | --- | --- |
| Goal | Existing successor P3/P4 activation Goal | Bound |
| Resolver | Additive V3 task revision and four new tasks | Verified result-blind |
| Ready Queue | No PASS: dependency wait; fixture PASS: one P4 Ready | Verified result-blind |
| Supervisor | P4-only subclass, four exact-key capabilities | Registered |
| Capability | Six controls, robustness, compilers, replay | Synthetic fixtures verified |
| Artifacts | V3 content-addressed prereg/input/execution/evidence/decision/replay | Deterministic fixtures verified |
| Status | `ARMED_DEPENDENCY_WAIT` without PASS | Verified |
| Next task | Successor-only P5 triple dependency | Wired, not executed |

Mainline integration answer before merge and Operator deployment:
`NO — INTEGRATION_PENDING`.

Scientific execution status: `NOT_EXECUTED`.
P5 status: `NOT_STARTED`.
Promotion status: `NOT_TRIGGERED`.
