# M4-v2 Bounded Deeper Validation and Superseding Global Route

Date: 2026-08-20

Role: Engineering Agent under approved Request 627 / Execution 511.

## Primary goal

Resolve the exact branch behind the frozen `DEEPER_VALIDATION_REQUIRED` route through one result-blind, bounded program, then register and replay a superseding Global Route without predictive P3, P4, Promotion, or mutation of historical artifacts.

## Non-goals

- No repair, extension, dependency, or rerun of `m4-v2-global-routing-recovery-v3-registered-replay-compatibility-v1`.
- No recovery-v4, generic schema, generic artifact registry, Temporal workload, or Joint workload.
- No new historical-outcome read, historical fold, predictive P3 fold, P4 task, or Promotion action.
- No repeated resampling interpreted as independent information.

## Registered intake and Reviewer decision

The immutable recovery-v3 route is `DEEPER_VALIDATION_REQUIRED`. Its registered branch projections are:

| Branch | Terminal decision | Exact unresolved reason |
| --- | --- | --- |
| `MARGINAL_STATIC` | `INCONCLUSIVE_DUE_TO_POWER` | Measurement health passed, but the frozen MDE is `0.013459908060402983` bits/issue, above the `0.01` practical threshold, and equivalence power is `0.5311893549808094`, below `0.8`. |
| `TEMPORAL_MARGINAL_INCREMENT` | `NOT_EVALUABLE_PARENT_NOT_ACCEPTED` | The Marginal parent was not accepted; no workload ran. |
| `JOINT_RESIDUAL_INCREMENT` | `NOT_EVALUABLE_PARENT_NOT_ACCEPTED` | Its parent chain was not accepted; no workload ran. |

Research Request 625 / Execution 509 registered the zero-compute Intake. Reviewer Decision 2627 under Request 626 / Execution 510 selected exactly `POWER_RESOLUTION_REQUIRED` for `MARGINAL_STATIC`; Engineering did not select the validation program.

## Power-feasibility result

The frozen inputs are 2,581 independent historical folds, MDE `0.013459908060402983`, practical threshold `0.01`, and target equivalence power `0.8`. The preregistered scaling calculation gives:

```text
ceil(2581 * (0.013459908060402983 / 0.01)^2) = 4676 folds
additional independent folds required = 4676 - 2581 = 2095
```

The accepted design permits post-cutoff use only with a real pre-draw checkpoint. No registered unused independent holdout checkpoint exists. Therefore the bounded program stops at `FORWARD_EVIDENCE_REQUIRED`, with zero new historical folds. Repeating the old resampling cannot supply the missing independent information.

## Canonical mainline chain

1. `m4-v2-deeper-validation-intake`
2. `m4-v2-deeper-validation-decision`
3. `m4-v2-deeper-validation-decision-replay`
4. `m4-v2-global-routing-after-deeper-validation`
5. `m4-v2-global-routing-after-deeper-validation-replay`

The manifest is additive to baseline manifest `175b4cf81a5ffd6398e00c97eb52a3efa06813f31f2d9bacfe6bfbb81243aceb`. Its dry-run output manifest was `41c13798ae053c58f9ac85f5b8bdf79419cc9f497e04c2e4aed0b0b2e7e23026`, resolving to snapshot `f70f499de2c9156183ef5492938b5f67f13022f8f5f927c5c292aa2d091a9732` with Intake as the unique Ready task. After all five unified-mainline executions, the persisted manifest is `31604e59c8355c97ee680fbd3bd6ba5a89b4e4d8ddbb961dc36880a4eba34ac8`, the snapshot is `7ae3457d07553ab90d3fd8813c551230bb4dcaef8de4df91e225a9c225790ef0`, and the Ready Queue is empty. The blocked compatibility successor is not a dependency and remains untouched.

## Validation before publication

- `test_m4_v2_deeper_validation.py`: 6 passed.
- Focused repository/recovery/compatibility regression plus new tests: 10 passed in 84.27 seconds on the publication commit.
- Ruff on all touched Python files: passed.
- Source contract and governance bindings: verified.
- Read-only repository import verifier against the live baseline: verified.
- Read-only Intake capability reconstruction: digest `869f4302cbfdfe2af8076e5bf2aea50779f1bb3f58548611bfbaa25af69a7685`, zero folds.
- GitHub PR #357 merged with the repository's normal squash method as `2bd333f1f0023333d21b162066b09cf6972e7e6a`. GitHub reported that the Actions runner did not start because the free quota, spending limit, or account billing prevented allocation; the repository's documented CI-unavailable exception therefore used the passing local validation instead of treating this as a code/test failure.

## Mainline execution evidence

Reviewer-approved Operator Release Request 628 / Execution 512 imported the exact additive manifest from merged main, dispatched each task exactly once, ran generic replay for all five tasks, read back the registrations and terminal state, and completed successfully under run `m4-v2-deeper-validation-mainline-release-v1`.

| Link | Required proof | Final state |
| --- | --- | --- |
| Goal | Existing `M4_INFORMATION_THEORY_EVIDENCE` Goal | Bound |
| Resolver | Exact additive manifest and frozen dependencies | Persisted and replayed |
| Ready Queue | Intake initially unique; empty after terminal execution | Verified |
| Supervisor | Singular dispatcher for all five capabilities | Verified by five mainline executions |
| Capability | Zero-compute Intake, power decision, decision replay, route, route replay | Executed exactly once each |
| Artifacts | Typed artifacts and immutable registrations | Registered and read back |
| Status | Each task reaches `COMPLETE` / `VALIDATED_IN_MAINLINE` | Verified for all five tasks |
| Next task | Terminal `FORWARD_EVIDENCE_REQUIRED`; P3 closed | Persisted; no Ready task remains |

## Registered execution evidence

| Task | Execution ID | Typed artifact digest | Registration digest | Result |
| --- | --- | --- | --- | --- |
| Intake | `617841f02282e782b5f7fd9bf389e987b10b8134b34b54e5dab84c2b512ca5b1` | `869f4302cbfdfe2af8076e5bf2aea50779f1bb3f58548611bfbaa25af69a7685` | `a60e28736c2a150f0bad484ddd418a603ff7079aefd055540a4037c75a9450c5` | `MARGINAL_STATIC` / `POWER_RESOLUTION_REQUIRED` |
| Decision | `accb75a71fea961335a05b7d6ea0c1f0b606f622f5dc039c6593cf364eaa426a` | `dbac3aad6128787f737a1450461a9833c948068ba915f194df41a02f6fd9d9e3` | `d1a4e282db04dfa2d3b46049144e9732f5b06e06085587bc89d6e6cd1484ab12` | `FORWARD_EVIDENCE_REQUIRED` |
| Decision replay | `eef8e6f52a91109d07b0dc1ba8db1a6385f97fec7d55683aa672b7370c6e19a5` | `111852665f9493777becf0a46b77d75f4d487b9076b0d0a3b2dd41df2c92ab53` | `3d44346be05d9bbab0842dbdef6fee2458996f719c67700f19fdc69cf76ac382` | `REGISTERED_REPLAY_VERIFIED` |
| Superseding route | `805b9bd91b8d995cbd08726c3b8cfc42dfd97ec4649371e1ee9c765387334fa6` | `225286ea27d48cad2abefc4adf1677b1b04da160a25bec49da98bcc5952e133c` | `3e1450af1b455a043d7a43cf2ce8f189773ed2f6fabf01b8f46534412bed0058` | `FORWARD_EVIDENCE_REQUIRED` |
| Route replay | `51ea06920a74b7a2fac3f60561f40f0cf8f9dc6518054b6d1b6f75fbd789979d` | `f817eacc432466f53d81145dbe3996ddeed2e0b601f07f0e2ea805e15cbc2606` | `9f56e1d05a007bbffcd4106617297921c829dd3b3bc6b77d1e37c451596d4294` | `REGISTERED_REPLAY_VERIFIED` |

The route execution also registered P3 closure artifact `2dcd3630d4e0987022a22e27ae8818bed9edd39758138e90579b85fef5fe0bbc` under registration `0f545b0b0375e53a43424c9b8fdca414abbefa0cf4159290cd26decac64fd19e`. Generic Supervisor replay returned `REPLAY_VERIFIED`, identical execution identity, and identical artifact identity for each of the five tasks without rerunning a workload.

## Acceptance counters

| Counter | Value |
| --- | ---: |
| Unresolved branches executed | 1 (`MARGINAL_STATIC` feasibility only) |
| Formal validation executions | 0 |
| CI fixes | 0 |
| New holdout or forward programs declared | 1 |
| New historical folds | 0 |
| Predictive P3 folds | 0 |
| P4 started | 0 |
| Promotion triggered | 0 |
| Historical artifacts modified | 0 |
| Old compatibility successor dependency | 0 |

## Current integration conclusion

```text
old_global_route: DEEPER_VALIDATION_REQUIRED
old_infrastructure_incident: P3_INFRASTRUCTURE_BLOCKED_PERMANENT
unresolved_branch: MARGINAL_STATIC
unresolved_reason: INCONCLUSIVE_DUE_TO_POWER; frozen MDE exceeds the practical threshold and equivalence power is below target
validation_program: POWER_RESOLUTION_REQUIRED
independent_new_data_used: false
new_historical_folds: 0
deeper_validation_decision: FORWARD_EVIDENCE_REQUIRED
superseding_global_route: FORWARD_EVIDENCE_REQUIRED
predictive_p3_folds: 0
predictive_p3_status: CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION
p4_started: false
promotion_triggered: false
natural_expansion: STOPPED
next_legal_task: terminal state; a separately authorized forward-evidence program only
```

`YES — validated by unified mainline execution and replay`.
