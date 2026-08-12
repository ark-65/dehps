# M4-v2 accepted-parent runners and source-v3 integration

Date: 2026-08-12

Primary goal: make the approved Temporal Marginal Increment and Joint Residual
Increment accepted-parent paths code-complete, deterministic, resumable, and
explicitly bound to their live v3 source contracts without executing a workload.

## Round boundary

The implementation is owned by approved Engineering Request 513 and Execution
427. It preserves the frozen science, terminal discriminants, registration
orders, seeds, fold chronology, artifact counts, and parent decisions. This
round did not run the Research Evidence Supervisor, either registered workload,
replay, Global routing, P3/P4, or Promotion.

The active production selectors are `temporal_v3` and `joint_v3`. Their source
contracts retain the v3 schema and contract names while using the Request 509
v4 ordered path-array identity. Each array has twelve entries and contains the
shared probability capsule exactly once at zero-based index 5. Historical v1/v2
source contracts remain immutable and are verified only from ordinary raw Git
blobs at pinned commit `4e787ebc1b13e1a16fe42b80054cb2a01f4c0b6b`.

## Mainline integration matrix

| Link | Code path | Evidence in this round | Status |
| --- | --- | --- | --- |
| Goal | M4 information-theory evidence | Existing canonical Goal retained | CODE_COMPLETE |
| Resolver | Exact parent/support/source digest lookup | Artificial focused tests only | CODE_COMPLETE |
| Ready Queue | v3 source facts and accepted parent gates | Manifest/static validation only | CODE_COMPLETE |
| Supervisor | Event/resume/transcript publisher | Not executed | INTEGRATION_PENDING |
| Capability | Temporal and Joint accepted-parent iterators | Artificial fixtures only | CODE_COMPLETE |
| Artifacts | Versioned v3 terminal envelopes and owned nested files | Not published | INTEGRATION_PENDING |
| Status | Unified successor projection | Static validation only | INTEGRATION_PENDING |
| Next Task | Replay then Global routing | Not dispatched | INTEGRATION_PENDING |

Next consumers are an independent review, a ready-for-review PR and CI, then a
separately approved Operator execution for additive manifest adoption, unified
mainline workload execution, and deterministic replay.

MAINLINE INTEGRATION: **NO — INTEGRATION_PENDING**.

