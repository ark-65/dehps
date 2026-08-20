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

The manifest is additive to baseline manifest `175b4cf81a5ffd6398e00c97eb52a3efa06813f31f2d9bacfe6bfbb81243aceb`. Dry-run output manifest `41c13798ae053c58f9ac85f5b8bdf79419cc9f497e04c2e4aed0b0b2e7e23026` resolves to snapshot `f70f499de2c9156183ef5492938b5f67f13022f8f5f927c5c292aa2d091a9732`, with Intake as the unique Ready task. The blocked compatibility successor is not a dependency.

## Validation before publication

- `test_m4_v2_deeper_validation.py`: 6 passed.
- Focused repository/recovery/compatibility regression plus new tests: 10 passed in 93.15 seconds.
- Source contract and governance bindings: verified.
- Read-only repository import verifier against the live baseline: verified.
- Read-only Intake capability reconstruction: digest `869f4302cbfdfe2af8076e5bf2aea50779f1bb3f58548611bfbaa25af69a7685`, zero folds.

## Mainline execution evidence

This section is completed only after the ready PR merges and the approved Operator execution imports and dispatches the five tasks.

| Link | Required proof | Current state |
| --- | --- | --- |
| Goal | Existing `M4_INFORMATION_THEORY_EVIDENCE` Goal | Bound |
| Resolver | Exact additive manifest and frozen dependencies | Verified in dry run |
| Ready Queue | Intake is the unique Ready task | Verified in dry run |
| Supervisor | Singular dispatcher for all five capabilities | Verified by test |
| Capability | Zero-compute Intake, power decision, decision replay, route, route replay | Verified before publication |
| Artifacts | Typed artifacts and immutable registrations | Pending mainline execution |
| Status | Each task reaches `COMPLETE` / `VALIDATED_IN_MAINLINE` | Pending mainline execution |
| Next task | Terminal `FORWARD_EVIDENCE_REQUIRED`; P3 closed | Pending mainline execution |

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

`NO — implementation remains INTEGRATION_PENDING` until the unified mainline execution and registered replay complete.
